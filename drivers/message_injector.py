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
WM_CHAR = 0x0102
WM_SETFOCUS = 0x0007
WM_PASTE = 0x0302
WM_COPY = 0x0301
WM_CUT = 0x0300
EM_SETSEL = 0x00B1
WHEEL_DELTA = 120
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
MK_MBUTTON = 0x0010

user32 = ctypes.windll.user32

# 64-bit Windows 上必须设置 argtypes，否则 WPARAM/LPARAM 会被截断为 32-bit
user32.PostMessageW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong,
]
user32.PostMessageW.restype = ctypes.c_int
user32.SendMessageTimeoutW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong,
    ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
]
user32.SendMessageTimeoutW.restype = ctypes.c_longlong
user32.MapVirtualKeyW.argtypes = [ctypes.c_uint, ctypes.c_uint]
user32.MapVirtualKeyW.restype = ctypes.c_uint

MAPVK_VK_TO_VSC = 0
SMTO_NORMAL = 0x0000
SENDMSG_TIMEOUT = 100  # ms


def _vk_to_scancode(vk: int) -> int:
    """虚拟键码 → 硬件扫描码"""
    return user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)


def _send_message(hwnd: int, msg: int, wparam: int, lparam: int) -> bool:
    """发送窗口消息：PostMessage 优先（非阻塞），失败则 SendMessageTimeoutW（同步回退）"""
    if user32.PostMessageW(hwnd, msg, wparam, lparam):
        return True
    result = user32.SendMessageTimeoutW(
        hwnd, msg, wparam, lparam, SMTO_NORMAL, SENDMSG_TIMEOUT, None
    )
    if result == 0:
        err = ctypes.get_last_error()
        logger.warning(f"消息注入失败: hwnd={hwnd}, msg=0x{msg:X}, err={err}")
    return result != 0


def _make_lparam(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def _make_wparam(lo: int, hi: int) -> int:
    return ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)


class MessageInjector:
    """通过 PostMessage 直接向目标窗口注入鼠标/键盘消息"""

    def __init__(self):
        self._last_click_hwnd = None

    def _find_window_and_pos(self, x: int, y: int):
        """找到坐标下的窗口，返回 (hwnd, client_x, client_y)；未找到返回 (None, 0, 0)"""
        hwnd = win32gui.WindowFromPoint((x, y))
        if not hwnd:
            return None, 0, 0
        cx, cy = win32gui.ScreenToClient(hwnd, (x, y))
        return hwnd, cx, cy

    def _require_window(self, x: int, y: int):
        """获取窗口句柄和客户坐标，hwnd 为 None 时记录警告"""
        hwnd, cx, cy = self._find_window_and_pos(x, y)
        if hwnd is None:
            logger.warning(f"消息注入: 坐标 ({x},{y}) 下未找到窗口")
            return None, 0, 0
        return hwnd, cx, cy

    def click(self, x: int, y: int, button: str = "left"):
        hwnd, cx, cy = self._require_window(x, y)
        if hwnd is None:
            return
        self._last_click_hwnd = hwnd
        lparam = _make_lparam(cx, cy)

        if button == "right":
            self._post(hwnd, WM_RBUTTONDOWN, MK_RBUTTON, lparam)
            time.sleep(0.02)
            self._post(hwnd, WM_RBUTTONUP, 0, lparam)
        elif button == "middle":
            self._post(hwnd, WM_MBUTTONDOWN, MK_MBUTTON, lparam)
            time.sleep(0.02)
            self._post(hwnd, WM_MBUTTONUP, 0, lparam)
        else:
            self._post(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
            time.sleep(0.02)
            self._post(hwnd, WM_LBUTTONUP, 0, lparam)

        logger.debug(f"注入点击: ({x},{y}) -> hwnd={hwnd}, client=({cx},{cy}), btn={button}")

    @staticmethod
    def _post(hwnd, msg, wparam, lparam):
        _send_message(hwnd, msg, wparam, lparam)

    def double_click(self, x: int, y: int, button: str = "left"):
        self.click(x, y, button)
        time.sleep(0.1)
        self.click(x, y, button)
        logger.debug(f"注入双击: ({x},{y}), btn={button}")

    def scroll(self, x: int, y: int, amount: int = 3):
        hwnd, cx, cy = self._require_window(x, y)
        if hwnd is None:
            return
        lparam = _make_lparam(cx, cy)
        wparam = _make_wparam(0, amount * WHEEL_DELTA)
        self._post(hwnd, WM_MOUSEWHEEL, wparam, lparam)
        logger.debug(f"注入滚动: ({x},{y}), amount={amount}")

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """
        拖拽：光标瞬移至起点 → mouse_event 产生真实 WM_LBUTTONDOWN（<2ms 后恢复），
        中间帧 PostMessage WM_MOUSEMOVE，光标瞬移至终点释放 → 恢复。
        光标只在按下和释放瞬间各跳一次（<2ms），人眼不可见。
        """
        hwnd, cx1, cy1 = self._require_window(x1, y1)
        if hwnd is None:
            return
        _, cx2, cy2 = self._find_window_and_pos(x2, y2)

        import win32con as wc
        original = win32api.GetCursorPos()

        # 1. 光标瞬移至起点 → 真实 mouse_event 按下 → 立即恢复光标（<2ms 闪烁）
        win32api.SetCursorPos((x1, y1))
        win32api.mouse_event(wc.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.SetCursorPos(original)

        time.sleep(0.02)

        # 2. 中间帧：PostMessage WM_MOUSEMOVE（Edit 控件已进入拖拽模式，GetAsyncKeyState="按下"）
        steps = max(2, int(duration * 30))
        for i in range(1, steps + 1):
            t = i / steps
            mx = int(cx1 + (cx2 - cx1) * t)
            my = int(cy1 + (cy2 - cy1) * t)
            _send_message(hwnd, WM_MOUSEMOVE, MK_LBUTTON, _make_lparam(mx, my))
            time.sleep(duration / steps)

        # 3. 光标瞬移至终点 → PostMessage UP → 真实 mouse_event 释放 → 恢复光标
        win32api.SetCursorPos((x2, y2))
        _send_message(hwnd, WM_LBUTTONUP, 0, _make_lparam(cx2, cy2))
        win32api.mouse_event(wc.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        win32api.SetCursorPos(original)

        logger.debug(f"注入拖拽: ({x1},{y1}) -> ({x2},{y2})")

    def mouse_down(self, x: int, y: int, button: str = "left"):
        hwnd, cx, cy = self._require_window(x, y)
        if hwnd is None:
            return
        self._last_click_hwnd = hwnd
        self._mouse_up_button = button
        import win32con as wc

        down_flag = {"left": wc.MOUSEEVENTF_LEFTDOWN, "right": wc.MOUSEEVENTF_RIGHTDOWN,
                      "middle": wc.MOUSEEVENTF_MIDDLEDOWN}.get(button, wc.MOUSEEVENTF_LEFTDOWN)

        # 光标瞬移至目标 → 真实 mouse_event 按下 → 立即恢复（<2ms）
        original = win32api.GetCursorPos()
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(down_flag, 0, 0, 0, 0)
        win32api.SetCursorPos(original)
        logger.debug(f"注入按下: ({x},{y}), btn={button}")

    def mouse_up(self, button: str = "left"):
        hwnd = self._last_click_hwnd or win32gui.GetForegroundWindow()
        if hwnd is None:
            return
        import win32con as wc

        up_flag = {"left": wc.MOUSEEVENTF_LEFTUP, "right": wc.MOUSEEVENTF_RIGHTUP,
                    "middle": wc.MOUSEEVENTF_MIDDLEUP}.get(button, wc.MOUSEEVENTF_LEFTUP)
        win32api.mouse_event(up_flag, 0, 0, 0, 0)
        logger.debug(f"注入释放: btn={button}")

    def type_text(self, text: str):
        """注入文本：中文用剪贴板 + WM_PASTE，ASCII 用 WM_CHAR"""
        hwnd = self._keyboard_hwnd
        if not hwnd:
            logger.warning("type_text: 无目标窗口")
            return

        if any(ord(c) > 127 for c in text):
            import pyperclip
            old_clipboard = pyperclip.paste()
            pyperclip.copy(text)
            time.sleep(0.1)
            _send_message(hwnd, WM_PASTE, 0, 0)
            time.sleep(0.1)
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass
        else:
            for ch in text:
                _send_message(hwnd, WM_CHAR, ord(ch), 0)
                time.sleep(0.01)
        logger.debug(f"注入文本: {text[:20]}{'...' if len(text) > 20 else ''}")

    def press_key(self, key: str):
        vk = _key_to_vk(key)
        if vk:
            self._post_key(vk)
        logger.debug(f"注入按键: {key}")

    def hotkey(self, *keys: str):
        """注入组合键。常见快捷键用直接命令消息，通用情况用 keyboard 模拟"""
        combo = '+'.join(k.lower().strip() for k in keys)
        hwnd = self._keyboard_hwnd

        # 常见快捷键 → 直接命令消息（绕过系统按键状态依赖）
        if combo == "ctrl+a":
            _send_message(hwnd, EM_SETSEL, 0, -1)
            logger.debug(f"注入 EM_SETSEL (全选)")
            return
        if combo == "ctrl+c":
            _send_message(hwnd, WM_COPY, 0, 0)
            logger.debug(f"注入 WM_COPY (复制)")
            return
        if combo == "ctrl+v":
            _send_message(hwnd, WM_PASTE, 0, 0)
            logger.debug(f"注入 WM_PASTE (粘贴)")
            return
        if combo == "ctrl+x":
            _send_message(hwnd, WM_CUT, 0, 0)
            logger.debug(f"注入 WM_CUT (剪切)")
            return

        # 通用情况：PostMessage/SendMessage 键盘模拟
        vks = [_key_to_vk(k) for k in keys]
        for vk in vks:
            if vk:
                self._post_keydown(vk)
                time.sleep(0.02)
        for vk in reversed(vks):
            if vk:
                self._post_keyup(vk)
                time.sleep(0.02)
        logger.debug(f"注入组合键: {combo}")

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

    @property
    def _keyboard_hwnd(self):
        """键盘消息目标窗口：优先上次点击窗口，否则前台窗口"""
        return self._last_click_hwnd or win32gui.GetForegroundWindow()

    def _post_keydown(self, vk: int):
        hwnd = self._keyboard_hwnd
        scan = _vk_to_scancode(vk)
        lparam = (1 << 0) | (scan << 16)
        _send_message(hwnd, WM_KEYDOWN, vk, lparam)

    def _post_keyup(self, vk: int):
        hwnd = self._keyboard_hwnd
        scan = _vk_to_scancode(vk)
        lparam = (1 << 0) | (1 << 30) | (1 << 31) | (scan << 16)
        _send_message(hwnd, WM_KEYUP, vk, lparam)


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
