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
