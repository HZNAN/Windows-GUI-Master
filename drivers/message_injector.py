"""
消息注入驱动（混合模式）

瞬态操作（click/scroll/type/hotkey）：纯 PostMessage/SendMessage 注入，零光标操作。
长时操作（drag/mouse_down/mouse_up）：隐藏真实光标→操作→恢复原位→显示光标。
纯消息无法实现长时操作的原因：Windows 拖拽状态机依赖 GetAsyncKeyState + GetCapture + GetMessagePos，
这些系统级状态只能通过真实输入管道（mouse_event/SendInput）更新。
"""
import ctypes
import time
from loguru import logger

import win32api
import win32con
import win32gui


# Win32 常量
OCR_NORMAL = 32512  # 标准箭头光标 ID
IMAGE_CURSOR = 2

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEMOVE = 0x0200
WM_MOUSEWHEEL = 0x020A
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_CHAR = 0x0102
WM_SYSCOMMAND = 0x0112
WM_SETFOCUS = 0x0007
WM_PASTE = 0x0302
WM_COPY = 0x0301
WM_CUT = 0x0300
SC_CLOSE = 0xF060
EM_SETSEL = 0x00B1
EM_CHARFROMPOS = 0x00D7
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
user32.SendMessageW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong,
]
user32.SendMessageW.restype = ctypes.c_longlong
user32.MapVirtualKeyW.argtypes = [ctypes.c_uint, ctypes.c_uint]
user32.MapVirtualKeyW.restype = ctypes.c_uint
user32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_uint, ctypes.c_ulonglong]
user32.keybd_event.restype = None

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

    @staticmethod
    def _create_invisible_cursor():
        """创建完全透明的 32×32 单色光标。
        AND mask 全 1（屏幕像素原样通过），XOR mask 全 0（不反转）。
        结果：光标在任何背景下都不可见。"""
        and_mask = (ctypes.c_ubyte * 128)(*([0xFF] * 128))
        xor_mask = (ctypes.c_ubyte * 128)(*([0x00] * 128))
        return ctypes.windll.user32.CreateCursor(0, 0, 0, 32, 32, and_mask, xor_mask)

    def _hide_real_cursor(self):
        """替换系统箭头光标为透明光标，使真实光标彻底不可见"""
        h_arrow = ctypes.windll.user32.LoadCursorW(0, OCR_NORMAL)
        if h_arrow:
            self._backup_arrow = ctypes.windll.user32.CopyImage(
                h_arrow, IMAGE_CURSOR, 0, 0, 0x00004000  # LR_COPYFROMRESOURCE
            )
        if not getattr(self, '_backup_arrow', 0):
            logger.warning("无法备份系统箭头光标，光标隐藏可能失效")
            return

        h_invis = self._create_invisible_cursor()
        if h_invis:
            if not ctypes.windll.user32.SetSystemCursor(h_invis, OCR_NORMAL):
                logger.warning(f"SetSystemCursor 失败: {ctypes.get_last_error()}")
            else:
                logger.debug("系统光标已替换为透明光标")

    def _show_real_cursor(self):
        """恢复系统箭头光标（替换回备份的正常光标）"""
        if getattr(self, '_backup_arrow', 0):
            ctypes.windll.user32.SetSystemCursor(self._backup_arrow, OCR_NORMAL)
            self._backup_arrow = 0
            logger.debug("系统箭头光标已恢复")

    def click(self, x: int, y: int, button: str = "left"):
        hwnd, cx, cy = self._find_window_and_pos(x, y)
        if hwnd is None:
            logger.warning(f"消息注入: 坐标 ({x},{y}) 下未找到窗口")
            return

        # 非客户区（cx 或 cy 为负，如标题栏按钮）→ mouse_event 物理点击
        if cx < 0 or cy < 0:
            self._click_via_mouse_event(x, y, button)
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

    def _click_via_mouse_event(self, x: int, y: int, button: str = "left"):
        """非客户区点击：必须用真实鼠标事件（PostMessage 不处理标题栏/边框）"""
        saved = win32api.GetCursorPos()
        self._hide_real_cursor()
        try:
            win32api.SetCursorPos((x, y))
            time.sleep(0.01)
            btn_map = {
                "right": (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP),
                "middle": (win32con.MOUSEEVENTF_MIDDLEDOWN, win32con.MOUSEEVENTF_MIDDLEUP),
            }
            down, up = btn_map.get(button, (win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP))
            win32api.mouse_event(down, 0, 0, 0, 0)
            time.sleep(0.02)
            win32api.mouse_event(up, 0, 0, 0, 0)
            logger.debug(f"mouse_event 点击 (非客户区): ({x},{y}), btn={button}")
        finally:
            win32api.SetCursorPos(saved)
            self._show_real_cursor()

    @staticmethod
    def _post(hwnd, msg, wparam, lparam):
        _send_message(hwnd, msg, wparam, lparam)

    def double_click(self, x: int, y: int, button: str = "left"):
        """双击：第一次 click，第二次用 WM_LBUTTONDBLCLK 触发双击行为"""
        hwnd, cx, cy = self._find_window_and_pos(x, y)
        if hwnd is None:
            logger.warning(f"消息注入: 坐标 ({x},{y}) 下未找到窗口")
            return

        # 非客户区 → mouse_event 物理点击
        if cx < 0 or cy < 0:
            self._click_via_mouse_event(x, y, button)
            time.sleep(0.05)
            self._click_via_mouse_event(x, y, button)
            return

        self._last_click_hwnd = hwnd
        lparam = _make_lparam(cx, cy)

        # 第一击：正常 click
        self._post(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(0.02)
        self._post(hwnd, WM_LBUTTONUP, 0, lparam)
        time.sleep(0.05)

        # 第二击：WM_LBUTTONDBLCLK 替换 WM_LBUTTONDOWN
        self._post(hwnd, WM_LBUTTONDBLCLK, MK_LBUTTON, lparam)
        time.sleep(0.02)
        self._post(hwnd, WM_LBUTTONUP, 0, lparam)

        logger.debug(f"注入双击: ({x},{y}), btn={button}")

    def scroll(self, x: int, y: int, amount: int = 3):
        """滚动：Edit/浏览器用 WM_MOUSEWHEEL 纯消息，其他应用用 mouse_event 移动+滚轮。"""
        hwnd, cx, cy = self._require_window(x, y)
        if hwnd is None:
            return

        class_name = win32gui.GetClassName(hwnd)
        if class_name in ("Edit",) or class_name.startswith("RichEdit") or \
                "Chrome" in class_name or "RenderWidget" in class_name:
            lparam = _make_lparam(cx, cy)
            wparam = _make_wparam(0, amount * WHEEL_DELTA)
            self._post(hwnd, WM_MOUSEWHEEL, wparam, lparam)
            logger.debug(f"scroll WM_MOUSEWHEEL: amount={amount}, class={class_name}")
        else:
            saved = win32api.GetCursorPos()
            self._hide_real_cursor()
            try:
                # 用 mouse_event(MOVE|ABSOLUTE) 设定逻辑光标位置
                screen_w = win32api.GetSystemMetrics(0)
                screen_h = win32api.GetSystemMetrics(1)
                abs_x = int(x * 65535 / screen_w)
                abs_y = int(y * 65535 / screen_h)
                win32api.mouse_event(
                    win32con.MOUSEEVENTF_ABSOLUTE | win32con.MOUSEEVENTF_MOVE,
                    abs_x, abs_y, 0, 0)
                time.sleep(0.01)
                win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0,
                                     amount * WHEEL_DELTA, 0)
                time.sleep(0.02)
                logger.debug(f"scroll mouse_event: amount={amount}, class={class_name}")
            finally:
                win32api.SetCursorPos(saved)
                self._show_real_cursor()

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """
        拖拽：透明光标 → 移动到起点 → 按下 → 动画移到终点 → 释放 → 恢复原位 → 正常光标。
        纯消息无法实现拖拽（需要系统按钮状态 + capture），使用透明光标方式工作。
        """
        saved = win32api.GetCursorPos()
        self._hide_real_cursor()
        try:
            win32api.SetCursorPos((x1, y1))
            time.sleep(0.02)

            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.02)

            steps = max(int(duration / 0.016), 10)
            for i in range(1, steps + 1):
                t = i / steps
                cur_x = int(x1 + (x2 - x1) * t)
                cur_y = int(y1 + (y2 - y1) * t)
                win32api.SetCursorPos((cur_x, cur_y))
                time.sleep(duration / steps)

            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.02)

            logger.debug(f"drag: ({x1},{y1}) -> ({x2},{y2}), duration={duration}s")
        finally:
            win32api.SetCursorPos(saved)
            self._show_real_cursor()

    def mouse_down(self, x: int, y: int, button: str = "left"):
        """
        按住鼠标按键：透明光标 → 移动到目标 → mouse_event down。
        纯消息无法实现按住操作（需系统按钮状态），使用透明光标方式工作。
        """
        self._saved_cursor = win32api.GetCursorPos()
        self._hide_real_cursor()
        try:
            win32api.SetCursorPos((x, y))
            time.sleep(0.01)

            btn_flag = {
                "left": win32con.MOUSEEVENTF_LEFTDOWN,
                "right": win32con.MOUSEEVENTF_RIGHTDOWN,
                "middle": win32con.MOUSEEVENTF_MIDDLEDOWN,
            }.get(button, win32con.MOUSEEVENTF_LEFTDOWN)
            win32api.mouse_event(btn_flag, 0, 0, 0, 0)
            logger.debug(f"mouse_down: ({x},{y}), btn={button}")
        except Exception:
            self._show_real_cursor()
            raise

    def mouse_up(self, button: str = "left"):
        """
        释放鼠标按键：mouse_event up → 恢复光标位置 → 正常光标。
        """
        try:
            btn_flag = {
                "left": win32con.MOUSEEVENTF_LEFTUP,
                "right": win32con.MOUSEEVENTF_RIGHTUP,
                "middle": win32con.MOUSEEVENTF_MIDDLEUP,
            }.get(button, win32con.MOUSEEVENTF_LEFTUP)
            win32api.mouse_event(btn_flag, 0, 0, 0, 0)
            time.sleep(0.01)
            logger.debug(f"mouse_up: btn={button}")
        finally:
            if hasattr(self, '_saved_cursor'):
                win32api.SetCursorPos(self._saved_cursor)
            self._show_real_cursor()

    def _focus_window(self, hwnd: int):
        """将键盘焦点强制设到目标窗口。
        PostMessage 点击不会自动转移焦点，需要 AttachThreadInput + SetFocus。"""
        if not hwnd:
            return
        our_tid = ctypes.windll.kernel32.GetCurrentThreadId()
        target_tid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, 0)
        attached = False
        if our_tid != target_tid:
            attached = bool(ctypes.windll.user32.AttachThreadInput(our_tid, target_tid, True))
        ctypes.windll.user32.SetFocus(hwnd)
        time.sleep(0.05)
        if attached:
            ctypes.windll.user32.AttachThreadInput(our_tid, target_tid, False)
        logger.debug(f"SetFocus hwnd={hwnd}, attached={attached}")

    @staticmethod
    def _paste_via_keybd():
        """通过 keybd_event 模拟 Ctrl+V（系统级键盘注入，不涉及光标）。"""
        VK_CONTROL = 0x11
        VK_V = 0x56
        KEYEVENTF_KEYUP = 0x0002

        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)

    def type_text(self, text: str):
        """注入文本。
        Edit 控件中文用剪贴板粘贴（WM_CHAR 对非 ASCII 不可靠），
        其他应用（浏览器/飞书等）所有文字统一用 WM_CHAR 逐字发送。"""
        hwnd = self._keyboard_hwnd
        if not hwnd:
            logger.warning("type_text: 无目标窗口")
            return

        class_name = win32gui.GetClassName(hwnd)
        is_edit = class_name == "Edit" or class_name.startswith("RichEdit")

        if is_edit and any(ord(c) > 127 for c in text):
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
            logger.debug(f"中文 WM_PASTE -> class={class_name}")
        else:
            for ch in text:
                _send_message(hwnd, WM_CHAR, ord(ch), 0)
                time.sleep(0.01)
            logger.debug(f"WM_CHAR ({len(text)} chars) -> class={class_name}")
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

        # ALT+F4 → 直接发 WM_SYSCOMMAND(SC_CLOSE) 关闭窗口
        if combo == "alt+f4":
            hwnd = self._keyboard_hwnd
            if hwnd:
                _send_message(hwnd, WM_SYSCOMMAND, SC_CLOSE, 0)
                logger.debug(f"注入 WM_SYSCOMMAND SC_CLOSE -> hwnd={hwnd}")
            return

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
            class_name = win32gui.GetClassName(hwnd)
            if class_name == "Edit" or class_name.startswith("RichEdit"):
                _send_message(hwnd, WM_PASTE, 0, 0)
                logger.debug(f"注入 WM_PASTE (粘贴) -> class={class_name}")
            else:
                self._focus_window(hwnd)
                self._paste_via_keybd()
                logger.debug(f"注入 focus+keybd_event Ctrl+V -> class={class_name}")
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
