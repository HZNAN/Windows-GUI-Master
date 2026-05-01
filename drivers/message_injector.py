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

WHEEL_DELTA = 120

user32 = ctypes.windll.user32



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
        """鼠标点击：mouse_event + 透明光标，适用于所有窗口类型。

        PostMessage 点击对 UWP/系统 UI/非客户区/部分应用无效，
        统一使用 mouse_event 物理点击避免兼容性问题。
        """
        hwnd, _, _ = self._find_window_and_pos(x, y)
        self._last_click_hwnd = hwnd
        self._mouse_click(x, y, button)
        logger.debug(f"注入点击: ({x},{y}), btn={button}")

    def _mouse_click(self, x: int, y: int, button: str = "left"):
        """mouse_event + 透明光标物理点击（隐藏→移动→点击→恢复）"""
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
        finally:
            win32api.SetCursorPos(saved)
            self._show_real_cursor()

    def double_click(self, x: int, y: int, button: str = "left"):
        """双击：连续两次 mouse_event 物理点击"""
        hwnd, _, _ = self._find_window_and_pos(x, y)
        self._last_click_hwnd = hwnd
        self._mouse_click(x, y, button)
        time.sleep(0.05)
        self._mouse_click(x, y, button)
        logger.debug(f"注入双击: ({x},{y}), btn={button}")

    def scroll(self, x: int, y: int, amount: int = 3):
        """滚动：MOUSEEVENTF_ABSOLUTE 定位 + MOUSEEVENTF_WHEEL + 透明光标。

        MOUSEEVENTF_WHEEL 使用逻辑光标位置（MOUSEEVENTF_ABSOLUTE 坐标系），
        不能依赖 SetCursorPos 设置的物理位置。
        """
        hwnd, _, _ = self._find_window_and_pos(x, y)
        if hwnd is None:
            logger.warning(f"消息注入: 坐标 ({x},{y}) 下未找到窗口")
            return

        saved = win32api.GetCursorPos()
        self._hide_real_cursor()
        try:
            screen_w = win32api.GetSystemMetrics(0)
            screen_h = win32api.GetSystemMetrics(1)
            abs_x = int(x * 65535 / screen_w)
            abs_y = int(y * 65535 / screen_h)
            win32api.mouse_event(
                win32con.MOUSEEVENTF_ABSOLUTE | win32con.MOUSEEVENTF_MOVE,
                abs_x, abs_y, 0, 0)
            time.sleep(0.01)
            # 拆分成多个单步滚轮事件，避免 dwData 负值溢出
            # MOUSEEVENTF_WHEEL 的 dwData 是 DWORD (32-bit unsigned)
            steps = abs(amount)
            direction = 1 if amount > 0 else -1
            for _ in range(steps):
                win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0,
                                     direction * WHEEL_DELTA, 0)
                time.sleep(0.01)
            time.sleep(0.02)
            logger.debug(f"scroll: amount={amount}, class={win32gui.GetClassName(hwnd)}")
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

