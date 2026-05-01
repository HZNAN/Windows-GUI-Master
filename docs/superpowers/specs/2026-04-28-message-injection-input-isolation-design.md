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

## Actual Implementation: Hybrid Approach

The initial design assumed all operations could be pure PostMessage/SendMessage. This proved incorrect for several fundamental reasons. The final implementation is a **hybrid**:

| Operation | Edit/RichEdit | Chrome/Browser | Explorer/Feishu/Other |
|-----------|--------------|----------------|----------------------|
| click | PostMessage WM_LBUTTONDOWN/UP | same | same |
| double_click | PostMessage WM_LBUTTONDBLCLK | same | same |
| scroll | PostMessage WM_MOUSEWHEEL | PostMessage WM_MOUSEWHEEL | mouse_event WHEEL (hidden cursor) |
| drag | mouse_event (hidden cursor) | same | same |
| mouse_down/up | mouse_event (hidden cursor) | same | same |
| type_text (ASCII) | keybd_event (VkKeyScanW) | same | same |
| type_text (Chinese) | Clipboard + WM_PASTE | keybd_event (VkKeyScanW) | keybd_event (VkKeyScanW) |
| hotkey (all combos) | keybd_event | same | same |
| hotkey ALT+F4 | WM_SYSCOMMAND SC_CLOSE | same | same |

## Pitfalls Discovered

### 1. 纯消息无法实现 drag / mouse_down / mouse_up

**根因：** Windows 拖拽状态机依赖三个系统级状态：
- `GetAsyncKeyState(VK_LBUTTON)` — 检测物理按键是否按下
- `GetCapture()` / `SetCapture()` — 鼠标捕获（有线程亲和性）
- `GetMessagePos()` — 系统维护的最近鼠标消息位置

PostMessage 发送的 `WM_LBUTTONDOWN` 到达时，`GetAsyncKeyState` 返回 0（按钮未按下），控件直接跳过拖拽状态机。

**解决：** 使用透明光标 + `mouse_event`。`_hide_real_cursor()` 用 `SetSystemCursor` 将系统箭头替换为透明 32×32 单色光标，操作完成后 `_show_real_cursor()` 恢复。

### 2. WM_MOUSEWHEEL 对部分窗口无效

**根因：** `WM_MOUSEWHEEL` 消息发送到 `WindowFromPoint` 返回的 hwnd。对于 Explorer（`DirectUIHWND`）和 Feishu（Electron），该 hwnd 是容器窗口，不处理滚轮消息。

**解决：** 非 Edit/Chrome 窗口使用 `mouse_event(MOVE|ABSOLUTE) → mouse_event(WHEEL)` 组合。关键：不能用 `SetCursorPos` 移动光标然后滚轮，必须用 `mouse_event(MOVE|ABSOLUTE)` 生成系统级移动事件，后续 `mouse_event(WHEEL)` 才能识别正确位置。

### 3. WM_PASTE 对非 Edit 控件无效

**根因：** `WM_PASTE` 只在标准 Windows Edit/RichEdit 控件中工作。浏览器（Chromium）和飞书（Electron）的输入框是自渲染的，不处理外部 PostMessage 发来的 `WM_PASTE`。

**尝试：** `keybd_event` 模拟 Ctrl+V — 需要键盘焦点，PostMessage 点击不会转移焦点。

**最终解决：** 非 Edit 控件用 `WM_CHAR` 逐字发送 Unicode 码点。`WM_CHAR` 的 wParam 可以承载 BMP 内所有字符（包括中文 0x4E00-0x9FFF），现代应用（Chromium/Electron）正确处理。

### 4. 双击需要 WM_LBUTTONDBLCLK

**根因：** Windows 双击检测在系统输入管道中完成——连续两次点击在时间窗口（500ms）和空间距离内，系统将第二次 `WM_LBUTTONDOWN` 替换为 `WM_LBUTTONDBLCLK`。两个 PostMessage `WM_LBUTTONDOWN` 只是两次独立点击。

**解决：** 第二击直接发送 `WM_LBUTTONDBLCLK`（0x0203）替代 `WM_LBUTTONDOWN`。

### 5. ShowCursor(False) 不可靠

**根因：** `ShowCursor(False)` 递减显示计数，但某些系统配置下 `SetCursorPos` 或 `mouse_event` 会触发光标重新显示。具体原因可能是显示驱动、辅助功能设置或 DWM 的合成管道。

**解决：** 使用 `SetSystemCursor` 将 OCR_NORMAL 全局替换为透明光标。步骤：
1. `LoadCursorW(0, OCR_NORMAL)` 获取当前箭头
2. `CopyImage` 备份
3. `CreateCursor` 创建 32×32 单色透明光标（AND mask 全 1，XOR mask 全 0）
4. `SetSystemCursor` 替换
5. 操作完用备份恢复

所有使用透明光标的操作（drag/mouse_down/scroll）都用 try/finally 确保光标恢复。

### 6. PostMessage Ctrl/Ctrl+A 热键失败

**根因：** `PostMessage(WM_KEYDOWN, VK_CONTROL)` 不会更新系统修饰键状态。`GetAsyncKeyState(VK_CONTROL)` 仍返回 0。

**解决（2026-04-29 更新）：** 所有键盘操作统一使用 `keybd_event` 系统级注入，不再逐一映射为命令消息。`keybd_event` 注入系统输入队列，和物理键盘等效，自动处理所有修饰键状态。

### 7. keybd_event 需要键盘焦点

**根因：** `keybd_event` 注入进入系统输入队列，分发到当前有焦点的窗口。

**解决：** `GetGUIThreadInfo()` 跨线程获取真正焦点控件（`GetFocus()` 只返回本线程焦点），`AttachThreadInput` + `SetFocus` 仅在焦点不在目标时使用（已聚焦时跳过，避免干扰输入管道）。

### 8. 64-bit LPARAM/WPARAM 截断

**根因：** ctypes 默认将所有参数视为 32-bit。在 64-bit Windows 上，`PostMessageW` 和 `SendMessageW` 的 WPARAM 和 LPARAM 是 64-bit。不设 `argtypes` 会导致高位被截断，MAKELPARAM 坐标损坏。

**解决：** 必须在模块级别设置：
```python
user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong]
user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong]
user32.SendMessageTimeoutW.argtypes = [...]
user32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_uint, ctypes.c_ulonglong]
```

### 9. VkKeyScanW argtype 与 ord() 冲突 (2026-05-01)

**根因：** 设了 `user32.VkKeyScanW.argtypes = [ctypes.c_wchar]` 后，ctypes 校验参数类型。`VkKeyScanW(ord(ch))` 传 int，期望 wchar → TypeError。

**解决：** 传字符本身：`VkKeyScanW(ch)`（Python 单字符 str 自动转 c_wchar）。

### 10. GetFocus() 跨线程返回 NULL (2026-05-01)

**根因：** Win32 `GetFocus()` 只返回调用线程的焦点窗口。Python 进程和 UI 窗口在不同线程 → 始终返回 0。`_keyboard_hwnd` 永远退回到 `GetForegroundWindow()`，键盘注入发到错误的窗口。

**解决：** `GetGUIThreadInfo()` 获取前台窗口所在线程的 `hwndFocus`。`_GUITHREADINFO` 结构体 + `GetGUIThreadInfo(tid, &gti)` 跨线程安全。

### 11. 非客户区点击无效 (2026-05-01)

**根因：** `WindowFromPoint` → `ScreenToClient` 对标题栏按钮返回负坐标。`PostMessage(WM_LBUTTONDOWN)` 被解释为客户区点击（窗口收不到关闭/最小化/最大化指令）。

**解决：** `cx < 0 or cy < 0` 时判定为非客户区，回退到 `mouse_event` + 透明光标物理点击。

### 12. ALT+F4 PostMessage 无效 (2026-05-01)

**根因：** ALT+F4 是系统级热键，Windows 窗口管理器在 `DefWindowProc` 之前拦截。`PostMessage(WM_KEYDOWN, VK_F4)` 不触发 `SC_CLOSE`。

**解决：** `SendMessage(hwnd, WM_SYSCOMMAND, SC_CLOSE, 0)` 直接发送关闭命令。

## Fallback

Set `INPUT_MODE=virtual` in `.env` to revert to the teleport-based approach at runtime. Set `INPUT_MODE=normal` for pyautogui direct control.
