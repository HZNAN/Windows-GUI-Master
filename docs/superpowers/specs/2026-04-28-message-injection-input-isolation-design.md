# Message Injection: Virtual Cursor & Real Cursor Isolation

Date: 2026-04-28

## Problem

The current "virtual" input mode in `InputControl._virtual_click` achieves apparent isolation by teleporting the real cursor: save position → `SetCursorPos` to target → `mouse_event` click → `SetCursorPos` restore. This is a "move-and-hide" hack, not true isolation. The real cursor still moves briefly, causing:

- Race conditions if the human user moves the mouse simultaneously
- Unwanted hover effects in applications
- Visual flickering of the real cursor

## Goal

Complete isolation: the agent operates in the background with zero impact on the real system cursor. The virtual cursor (rendered via `Win32Overlay`) is purely visual; all input is injected directly into target windows via window messages.

## Design

### Architecture

```
ExecutionEngine
    │
    ├── VirtualCursor (unchanged, purely visual overlay)
    │
    └── InputControl
            │
            ├── message_mode (NEW)      → MessageInjector → PostMessage/SendMessage → target window
            ├── virtual_mode (kept)      → SetCursorPos + mouse_event (fallback)
            └── normal  (kept)          → pyautogui
```

### Key Insight

`PostMessage` bypasses the entire input subsystem (HID driver → input subsystem → cursor position update → message generation). Instead, it posts window messages directly to the target window's message queue. The system cursor is never touched.

The kernel (`win32k.sys`) generates the same `WM_LBUTTONDOWN` / `WM_LBUTTONUP` messages for a real click as we do via `PostMessage`. At the message level, the target window cannot distinguish the source.

### New Module: `drivers/message_injector.py`

```
class MessageInjector:
    click(x, y, button)       → WindowFromPoint → ScreenToClient → PostMessage WM_LBUTTONDOWN/UP
    double_click(x, y, button) → click × 2
    scroll(x, y, amount)       → WindowFromPoint → PostMessage WM_MOUSEWHEEL
    drag(x1, y1, x2, y2, dur) → WM_LBUTTONDOWN → SendMessage WM_MOUSEMOVE(s) → WM_LBUTTONUP
    type_text(text)            → PostMessage WM_SETFOCUS + WM_KEYDOWN/UP (or clipboard paste for Chinese)
    press_key(key)             → PostMessage WM_KEYDOWN/UP
    hotkey(*keys)              → PostMessage WM_KEYDOWN/UP sequence
```

**Click flow:**
1. `WindowFromPoint(screen_x, screen_y)` — find window under coordinates
2. `ScreenToClient(hwnd, point)` — convert to client coordinates
3. `PostMessage(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, MAKELPARAM(cx, cy))`
4. `PostMessage(hwnd, WM_LBUTTONUP, 0, MAKELPARAM(cx, cy))`

**Scroll flow:**
1. Same coordinate translation as click
2. `PostMessage(hwnd, WM_MOUSEWHEEL, MAKEWPARAM(0, delta * WHEEL_DELTA), MAKELPARAM(cx, cy))`

**Drag flow:**
1. `PostMessage(WM_LBUTTONDOWN, ...)` at start
2. Multiple `SendMessage(WM_MOUSEMOVE, ...)` along path (SendMessage ensures ordering)
3. `PostMessage(WM_LBUTTONUP, ...)` at end

### Modified Module: `drivers/input_control.py`

Add `message_mode` parameter alongside existing `virtual_mode`:

```python
class InputControl:
    def __init__(self, virtual_mode=False, message_mode=False):
        self.message_mode = message_mode
        if message_mode:
            self._injector = MessageInjector()

    def click(self, x, y, button="left"):
        if self.message_mode:
            self._injector.click(x, y, button)
        elif self.virtual_mode:
            self._virtual_click(x, y, button)
        else:
            pyautogui.click(x, y, button=button)
```

Same three-way dispatch for: `click`, `double_click`, `scroll`, `drag`.

Keyboard methods (`type_text`, `press_key`, `hotkey`, `key_down`, `key_up`) gain `message_mode` support for focused-target input.

Old `_virtual_click` and `_virtual_scroll` are kept for backward compatibility via `virtual_mode`.

### Modified Module: `core/execution_engine.py`

```python
def __init__(self):
    self.input = InputControl(message_mode=True)  # default to message injection
    self._virtual_cursor = get_virtual_cursor()
```

- `click`: `_virtual_cursor.move_to` (visual only) → `input.click` (injection). Decoupled.
- `scroll`: same pattern as click.
- `drag`: `_virtual_cursor.move_to(x2, y2)` → `input.drag(x, y, x2, y2, duration)`.
- `type`: click target first via injection, then keyboard injection.
- `mouse_down`/`mouse_up`: `pyautogui.mouseDown()` replaced with injection.

### Configuration: `config/settings.py`

```python
INPUT_MODE = os.getenv("INPUT_MODE", "message")  # "message" | "virtual" | "normal"
```

`ExecutionEngine` reads `INPUT_MODE` to choose the mode, allowing runtime fallback.

## Change Summary

| File | Action | What |
|------|--------|------|
| `drivers/message_injector.py` | **Add** | MessageInjector class with click/scroll/drag/keyboard injection |
| `drivers/input_control.py` | **Modify** | Add `message_mode` parameter, three-way dispatch in mouse methods |
| `core/execution_engine.py` | **Modify** | Default to message_mode, add virtual cursor animation for drag |
| `config/settings.py` | **Modify** | Add `INPUT_MODE` config key |
| `drivers/__init__.py` | **Modify** | Export MessageInjector |

**Not changed:**
- `VirtualCursor` / `Win32Overlay` — purely visual, already decoupled
- `tools/` layer — only passes coordinates, unaware of injection method
- `agents/` — ReAct loop unchanged
- `drivers/screen_capture.py` — screenshots unchanged

## Known Limitations

- UWP apps and some Windows 11 components may not respond well to posted messages
- Apps that call `GetCursorPos()` internally instead of using message coordinates may misbehave
- Applications with anti-injection detection (games, security software) may ignore or flag injected messages
- `GetMessageExtraInfo()` can distinguish `SendInput`-generated messages, though `PostMessage` bypasses most checks

## Fallback

Set `INPUT_MODE=virtual` in `.env` to revert to the old teleport-based approach at runtime.
