# Message Injection Input Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add message-injection input mode that sends mouse/keyboard events directly to target windows via PostMessage, completely bypassing the real system cursor.

**Architecture:** New `MessageInjector` class in `drivers/message_injector.py` uses Win32 `PostMessage` to inject `WM_LBUTTONDOWN`, `WM_MOUSEWHEEL`, etc. directly into target windows. `InputControl` gets a three-way dispatch (message/virtual/normal). `ExecutionEngine` defaults to message mode, configurable via `INPUT_MODE`.

**Tech Stack:** Python 3.x, `win32gui`/`win32api` (pywin32), `ctypes`

---

### Task 1: Add INPUT_MODE config

**Files:**
- Modify: `config/settings.py`

- [ ] **Step 1: Add INPUT_MODE to settings.py**

Add after the ACP config block (line 52):

```python
# ============ 输入模式配置 ============
INPUT_MODE = os.getenv("INPUT_MODE", "message")  # "message" | "virtual" | "normal"
```

- [ ] **Step 2: Commit**

```bash
git add config/settings.py
git commit -m "config: add INPUT_MODE setting for message injection mode"
```

---

### Task 2: Create MessageInjector

**Files:**
- Create: `drivers/message_injector.py`

- [ ] **Step 1: Write the MessageInjector class**

```python
"""
消息注入驱动
通过 PostMessage 直接将鼠标/键盘消息投递到目标窗口，完全绕过系统光标
"""
import ctypes
import time
from loguru import logger

import win32api
import win32con
import win32gui


# Win32 常量
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEMOVE = 0x0200
WM_MOUSEWHEEL = 0x020A
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SETFOCUS = 0x0007
WHEEL_DELTA = 120
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
MK_MBUTTON = 0x0010

user32 = ctypes.windll.user32


def _make_lparam(x: int, y: int) -> int:
    return (y << 16) | (x & 0xFFFF)


def _make_wparam(lo: int, hi: int) -> int:
    return (hi << 16) | (lo & 0xFFFF)


class MessageInjector:
    """通过 PostMessage 直接向目标窗口注入鼠标/键盘消息"""

    def _find_window_and_pos(self, x: int, y: int):
        """找到坐标下的最深层窗口，返回 (hwnd, client_x, client_y)"""
        hwnd = win32gui.WindowFromPoint((x, y))
        cx, cy = win32gui.ScreenToClient(hwnd, (x, y))
        return hwnd, cx, cy

    def click(self, x: int, y: int, button: str = "left"):
        hwnd, cx, cy = self._find_window_and_pos(x, y)
        lparam = _make_lparam(cx, cy)

        if button == "right":
            user32.PostMessageW(hwnd, WM_RBUTTONDOWN, MK_RBUTTON, lparam)
            time.sleep(0.02)
            user32.PostMessageW(hwnd, WM_RBUTTONUP, 0, lparam)
        elif button == "middle":
            user32.PostMessageW(hwnd, WM_MBUTTONDOWN, MK_MBUTTON, lparam)
            time.sleep(0.02)
            user32.PostMessageW(hwnd, WM_MBUTTONUP, 0, lparam)
        else:
            user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
            time.sleep(0.02)
            user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)

        logger.debug(f"注入点击: ({x},{y}) -> hwnd={hwnd}, client=({cx},{cy}), btn={button}")

    def double_click(self, x: int, y: int, button: str = "left"):
        self.click(x, y, button)
        time.sleep(0.1)
        self.click(x, y, button)
        logger.debug(f"注入双击: ({x},{y}), btn={button}")

    def scroll(self, x: int, y: int, amount: int = 3):
        hwnd, cx, cy = self._find_window_and_pos(x, y)
        lparam = _make_lparam(cx, cy)
        wparam = _make_wparam(0, amount * WHEEL_DELTA)
        user32.PostMessageW(hwnd, WM_MOUSEWHEEL, wparam, lparam)
        logger.debug(f"注入滚动: ({x},{y}), amount={amount}")

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        hwnd, cx1, cy1 = self._find_window_and_pos(x1, y1)
        _, cx2, cy2 = self._find_window_and_pos(x2, y2)

        # 按下
        lparam = _make_lparam(cx1, cy1)
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(0.02)

        # 移动（用 SendMessage 确保顺序，沿路径分多帧）
        steps = max(2, int(duration * 30))
        for i in range(1, steps + 1):
            t = i / steps
            mx = int(cx1 + (cx2 - cx1) * t)
            my = int(cy1 + (cy2 - cy1) * t)
            lparam = _make_lparam(mx, my)
            user32.SendMessageW(hwnd, WM_MOUSEMOVE, MK_LBUTTON, lparam)
            time.sleep(duration / steps)

        # 释放
        lparam = _make_lparam(cx2, cy2)
        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
        logger.debug(f"注入拖拽: ({x1},{y1}) -> ({x2},{y2})")

    def type_text(self, text: str):
        """通过按键消息注入文本（ASCII），中文走剪贴板粘贴"""
        if any(ord(c) > 127 for c in text):
            import pyperclip
            old_clipboard = pyperclip.paste()
            pyperclip.copy(text)
            time.sleep(0.1)
            self.hotkey("ctrl", "v")
            time.sleep(0.1)
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass
        else:
            for ch in text:
                vk = _char_to_vk(ch)
                if vk:
                    self._post_key(vk)
        logger.debug(f"注入文本: {text[:20]}{'...' if len(text) > 20 else ''}")

    def press_key(self, key: str):
        vk = _key_to_vk(key)
        if vk:
            self._post_key(vk)
        logger.debug(f"注入按键: {key}")

    def hotkey(self, *keys: str):
        """注入组合键：按下所有键 → 释放所有键（逆序）"""
        vks = [_key_to_vk(k) for k in keys]
        for vk in vks:
            if vk:
                self._post_keydown(vk)
                time.sleep(0.02)
        for vk in reversed(vks):
            if vk:
                self._post_keyup(vk)
                time.sleep(0.02)
        logger.debug(f"注入组合键: {'+'.join(keys)}")

    def key_down(self, key: str):
        vk = _key_to_vk(key)
        if vk:
            self._post_keydown(vk)

    def key_up(self, key: str):
        vk = _key_to_vk(key)
        if vk:
            self._post_keyup(vk)

    def _post_key(self, vk: int):
        """发送完整的按下+释放键消息"""
        self._post_keydown(vk)
        time.sleep(0.02)
        self._post_keyup(vk)

    def _post_keydown(self, vk: int):
        hwnd = win32gui.GetForegroundWindow()
        lparam = (1 << 0) | (0x0E << 16)  # repeat=1, scancode=0x0E
        user32.PostMessageW(hwnd, WM_KEYDOWN, vk, lparam)

    def _post_keyup(self, vk: int):
        hwnd = win32gui.GetForegroundWindow()
        lparam = (1 << 0) | (1 << 31) | (0x0E << 16)  # repeat=1, previous state=1, scancode=0x0E
        user32.PostMessageW(hwnd, WM_KEYUP, vk, lparam)


# ============ 键码映射 ============

_VK_MAP = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
    "space": 0x20, "backspace": 0x08, "delete": 0x2E,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
    "win": 0x5B, "lwin": 0x5B, "rwin": 0x5C,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78,
    "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}


def _key_to_vk(key: str) -> int:
    key = key.strip().lower()
    if key in _VK_MAP:
        return _VK_MAP[key]
    if len(key) == 1 and 'a' <= key <= 'z':
        return ord(key.upper())
    if len(key) == 1 and '0' <= key <= '9':
        return ord(key)
    logger.warning(f"不支持的按键: {key}")
    return 0


def _char_to_vk(ch: str) -> int:
    """字符转虚拟键码（ASCII）"""
    if 'a' <= ch <= 'z':
        return ord(ch.upper())
    if 'A' <= ch <= 'Z':
        return ord(ch)
    if '0' <= ch <= '9':
        return ord(ch)
    char_map = {
        ' ': 0x20, '\n': 0x0D, '.': 0xBE, ',': 0xBC, '/': 0xBF,
        ';': 0xBA, "'": 0xDE, '[': 0xDB, ']': 0xDD, '\\': 0xDC,
        '-': 0xBD, '=': 0xBB,
    }
    if ch in char_map:
        return char_map[ch]
    return 0
```

- [ ] **Step 2: Commit**

```bash
git add drivers/message_injector.py
git commit -m "feat: add MessageInjector for PostMessage-based input injection"
```

---

### Task 3: Add message_mode to InputControl

**Files:**
- Modify: `drivers/input_control.py`

- [ ] **Step 1: Modify __init__ to accept message_mode**

Replace lines 25-26:
```python
def __init__(self, virtual_mode: bool = False):
    self.virtual_mode = virtual_mode
```
With:
```python
def __init__(self, virtual_mode: bool = False, message_mode: bool = False):
    self.virtual_mode = virtual_mode
    self.message_mode = message_mode
    if message_mode:
        from drivers.message_injector import MessageInjector
        self._injector = MessageInjector()
```

- [ ] **Step 2: Modify click method to three-way dispatch**

Replace lines 30-44:
```python
def click(self, x: int, y: int, button: str = "left"):
    if self.virtual_mode:
        self._virtual_click(x, y, button)
    else:
        self.move_to(x, y, duration=0.3)
        self._sleep()
        pyautogui.click(x=x, y=y, button=button)
    logger.debug(f"鼠标点击: ({x}, {y}), 按钮={button}")
```
With:
```python
def click(self, x: int, y: int, button: str = "left"):
    if self.message_mode:
        self._injector.click(x, y, button)
    elif self.virtual_mode:
        self._virtual_click(x, y, button)
    else:
        self.move_to(x, y, duration=0.3)
        self._sleep()
        pyautogui.click(x=x, y=y, button=button)
    logger.debug(f"鼠标点击: ({x}, {y}), 按钮={button}")
```

- [ ] **Step 3: Modify double_click method**

Replace lines 77-85:
```python
def double_click(self, x: int, y: int, button: str = "left"):
    if self.virtual_mode:
        self._virtual_click(x, y, button)
        time.sleep(0.1)
        self._virtual_click(x, y, button)
    else:
        pyautogui.doubleClick(x=x, y=y, button=button)
    logger.debug(f"鼠标双击: ({x}, {y})")
```
With:
```python
def double_click(self, x: int, y: int, button: str = "left"):
    if self.message_mode:
        self._injector.double_click(x, y, button)
    elif self.virtual_mode:
        self._virtual_click(x, y, button)
        time.sleep(0.1)
        self._virtual_click(x, y, button)
    else:
        pyautogui.doubleClick(x=x, y=y, button=button)
    logger.debug(f"鼠标双击: ({x}, {y})")
```

- [ ] **Step 4: Modify scroll method**

Replace lines 98-111:
```python
def scroll(self, x: int, y: int, amount: int = 3):
    if self.virtual_mode:
        self._virtual_scroll(x, y, amount)
    else:
        pyautogui.moveTo(x, y)
        pyautogui.scroll(amount)
    logger.debug(f"鼠标滚动: ({x}, {y}), 量={amount}")
```
With:
```python
def scroll(self, x: int, y: int, amount: int = 3):
    if self.message_mode:
        self._injector.scroll(x, y, amount)
    elif self.virtual_mode:
        self._virtual_scroll(x, y, amount)
    else:
        pyautogui.moveTo(x, y)
        pyautogui.scroll(amount)
    logger.debug(f"鼠标滚动: ({x}, {y}), 量={amount}")
```

- [ ] **Step 5: Modify drag method**

Replace lines 122-134:
```python
def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
    pyautogui.moveTo(x1, y1)
    self._sleep()
    pyautogui.drag(x2 - x1, y2 - y1, duration=duration, button="left")
    logger.debug(f"鼠标拖拽: ({x1},{y1}) -> ({x2},{y2})")
```
With:
```python
def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
    if self.message_mode:
        self._injector.drag(x1, y1, x2, y2, duration)
    else:
        pyautogui.moveTo(x1, y1)
        self._sleep()
        pyautogui.drag(x2 - x1, y2 - y1, duration=duration, button="left")
    logger.debug(f"鼠标拖拽: ({x1},{y1}) -> ({x2},{y2})")
```

- [ ] **Step 6: Commit**

```bash
git add drivers/input_control.py
git commit -m "feat: add message_mode dispatch to InputControl mouse methods"
```

---

### Task 4: Update ExecutionEngine for message_mode

**Files:**
- Modify: `core/execution_engine.py`

- [ ] **Step 1: Read INPUT_MODE config and default to message_mode**

Replace lines 20-23:
```python
def __init__(self):
    self.screen = get_screen_capture()
    self.input = InputControl(virtual_mode=True)
    self._virtual_cursor = get_virtual_cursor()
```
With:
```python
def __init__(self):
    from config.settings import INPUT_MODE
    self.screen = get_screen_capture()
    if INPUT_MODE == "message":
        self.input = InputControl(message_mode=True)
    elif INPUT_MODE == "virtual":
        self.input = InputControl(virtual_mode=True)
    else:
        self.input = InputControl()
    self._virtual_cursor = get_virtual_cursor()
```

- [ ] **Step 2: Add virtual cursor animation for drag**

Replace lines 105-111:
```python
elif action == "drag":
    if x is None or y is None or x2 is None or y2 is None:
        logger.error(f"drag 缺少坐标: ({x}, {y}) -> ({x2}, {y2})")
        return False
    self.input.drag(x, y, x2, y2, duration=duration)
    logger.info(f"执行 drag: ({x}, {y}) -> ({x2}, {y2})")
    return True
```
With:
```python
elif action == "drag":
    if x is None or y is None or x2 is None or y2 is None:
        logger.error(f"drag 缺少坐标: ({x}, {y}) -> ({x2}, {y2})")
        return False
    self._virtual_cursor.move_to(x2, y2)
    self.input.drag(x, y, x2, y2, duration=duration)
    logger.info(f"执行 drag: ({x}, {y}) -> ({x2}, {y2})")
    return True
```

- [ ] **Step 3: Commit**

```bash
git add core/execution_engine.py
git commit -m "feat: default ExecutionEngine to message_mode input, add virtual cursor for drag"
```

---

### Task 5: Update drivers __init__.py exports

**Files:**
- Modify: `drivers/__init__.py`

- [ ] **Step 1: Add MessageInjector export**

Replace the file:
```python
from .screen_capture import ScreenCapture, get_screen_capture
from .input_control import InputControl, get_input_control
from .message_injector import MessageInjector
```

- [ ] **Step 2: Commit**

```bash
git add drivers/__init__.py
git commit -m "feat: export MessageInjector from drivers"
```

---

### Task 6: Manual verification test

**Files:**
- Create: `test_message_injector.py`

- [ ] **Step 1: Write manual verification script**

```python
"""手动验证消息注入模式：打开记事本，点击并输入，确认真实光标未移动"""
import time
from drivers.message_injector import MessageInjector
from core.virtual_cursor import get_virtual_cursor
from drivers.screen_capture import get_screen_capture

injector = MessageInjector()
cursor = get_virtual_cursor()
screen = get_screen_capture()

print("=== 消息注入模式验证 ===")
print("1. 请确保记事本 (notepad) 已打开并可见")
print("2. 将真实光标移到屏幕角落（远离记事本窗口）")
print("3. 按 Enter 开始测试...")
input()

# 获取当前真实光标位置（应在角落）
import win32api
original = win32api.GetCursorPos()
print(f"真实光标位置: {original}")

# 截图查看当前画面
screen.auto_save(prefix="before_inject")

# 在记事本区域找一个可点击的位置 (假设记事本在屏幕左上区域)
# 这里使用固定坐标，测试前需根据实际情况调整
x, y = 500, 400
print(f"注入点击: ({x}, {y})")
injector.click(x, y)
time.sleep(0.5)

# 输入一些文字
print("注入文本: Hello from message injection!")
injector.type_text("Hello from message injection!")
time.sleep(0.5)

# 检查真实光标是否还在原位
after = win32api.GetCursorPos()
print(f"注入后真实光标位置: {after}")
print(f"真实光标是否未移动: {original == after}")

# 截图对比
screen.auto_save(prefix="after_inject")

print("\n=== 验证完成 ===")
print("检查 .screenshots/ 中的截图，确认:")
print("1. 记事本中出现了 'Hello from message injection!' 文本")
print("2. 真实光标仍在原始位置")
```

- [ ] **Step 2: Commit**

```bash
git add test_message_injector.py
git commit -m "test: add manual verification script for message injection"
```

---

### Task 7: Run and verify

- [ ] **Step 1: Verify imports work**

```bash
python -c "from drivers.message_injector import MessageInjector; print('MessageInjector OK')"
```

- [ ] **Step 2: Verify ExecutionEngine initializes correctly**

```bash
python -c "from core.execution_engine import ExecutionEngine; e = ExecutionEngine(); print('Mode:', 'message' if e.input.message_mode else ('virtual' if e.input.virtual_mode else 'normal'))"
```
Expected: Mode: message

- [ ] **Step 3: Run the manual test script**

```bash
python test_message_injector.py
```

- [ ] **Step 4: Verify fallback to virtual mode works**

```bash
INPUT_MODE=virtual python -c "from core.execution_engine import ExecutionEngine; e = ExecutionEngine(); print('Mode:', 'message' if e.input.message_mode else ('virtual' if e.input.virtual_mode else 'normal'))"
```
Expected: Mode: virtual<｜end▁of▁thinking｜>Plan written. Now let me do the self-review before presenting it.

<｜DSML｜tool_calls>
<｜DSML｜invoke name="Read">
<｜DSML｜parameter name="file_path" string="true">E:\programe\OpenClaw\feishu_hand\feishu_agent\docs\superpowers\plans\2026-04-28-message-injection-input-isolation.md