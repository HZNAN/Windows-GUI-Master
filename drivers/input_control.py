"""
鼠标键盘输入驱动
优先使用 pyautogui（跨平台，支持 Windows 截图和输入模拟）
备选 pirectinput（Windows 专用，更精准）

虚拟光标模式：使用 win32api.mouse_event 模拟点击，不移动真实鼠标
"""
import time
import pyautogui
import win32api
import win32con
from loguru import logger

# pyautogui 安全设置：移动到角落不会触发紧急停止
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


class InputControl:
    """
    鼠标键盘输入控制器
    使用 pyautogui 实现鼠标键盘模拟
    """

    def __init__(self, virtual_mode: bool = False):
        self.virtual_mode = virtual_mode

    # ============ 鼠标操作 ============

    def click(self, x: int, y: int, button: str = "left"):
        """
        在指定坐标点击

        Args:
            x, y: 目标坐标
            button: 'left' / 'right' / 'middle'
        """
        if self.virtual_mode:
            self._virtual_click(x, y, button)
        else:
            self.move_to(x, y, duration=0.3)
            self._sleep()
            pyautogui.click(x=x, y=y, button=button)
        logger.debug(f"鼠标点击: ({x}, {y}), 按钮={button}")

    def _virtual_click(self, x: int, y: int, button: str = "left"):
        """虚拟点击：移动真实光标到目标 → 点击 → 恢复原位置"""
        btn_map = {"left": 1, "right": 2, "middle": 4}
        btn_flag = btn_map.get(button, 1)

        # 保存真实光标位置
        original_pos = win32api.GetCursorPos()

        # 移动真实光标到目标位置
        win32api.SetCursorPos((x, y))
        time.sleep(0.01)  # 短暂等待确保移动完成

        # 触发点击
        if btn_flag == 1:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.02)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        elif btn_flag == 2:
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.02)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        elif btn_flag == 4:
            win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
            time.sleep(0.02)
            win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)

        time.sleep(0.01)

        # 恢复真实光标位置
        win32api.SetCursorPos(original_pos)

    def double_click(self, x: int, y: int, button: str = "left"):
        """双击"""
        if self.virtual_mode:
            self._virtual_click(x, y, button)
            time.sleep(0.1)
            self._virtual_click(x, y, button)
        else:
            pyautogui.doubleClick(x=x, y=y, button=button)
        logger.debug(f"鼠标双击: ({x}, {y})")

    def move_to(self, x: int, y: int, duration: float = 0.3):
        """
        移动鼠标到指定坐标

        Args:
            x, y: 目标坐标
            duration: 移动持续时间（秒），模拟人类移动速度
        """
        pyautogui.moveTo(x, y, duration=duration)
        logger.debug(f"鼠标移动: ({x}, {y}), duration={duration}s")

    def scroll(self, x: int, y: int, amount: int = 3):
        """
        在指定位置滚动

        Args:
            x, y: 滚动位置
            amount: 滚动量，正数向上滚动，负数向下滚动
        """
        pyautogui.moveTo(x, y)
        pyautogui.scroll(amount)  # pyautogui: 正数向上，负数向下
        logger.debug(f"鼠标滚动: ({x}, {y}), 量={amount}")

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """
        拖拽从 (x1, y1) 到 (x2, y2)

        Args:
            x1, y1: 起点坐标
            x2, y2: 终点坐标
            duration: 拖拽持续时间（秒）
        """
        pyautogui.moveTo(x1, y1)
        self._sleep()
        pyautogui.drag(x2 - x1, y2 - y1, duration=duration, button="left")
        logger.debug(f"鼠标拖拽: ({x1},{y1}) -> ({x2},{y2})")

    # ============ 键盘操作 ============

    def type_text(self, text: str, interval: float = 0.05):
        """
        输入文本（逐字输入或粘贴）

        Args:
            text: 要输入的文本
            interval: 每个字符之间的间隔（秒）
        """
        # 检查是否包含非ASCII字符（如中文），需要用剪贴板粘贴
        if any(ord(c) > 127 for c in text):
            # 使用剪贴板粘贴方式输入中文
            import pyperclip
            old_clipboard = pyperclip.paste()
            pyperclip.copy(text)
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
            # 恢复剪贴板内容
            try:
                pyperclip.copy(old_clipboard)
            except:
                pass
            logger.debug(f"剪贴板粘贴文本: {text[:20]}{'...' if len(text) > 20 else ''}")
        else:
            pyautogui.write(text, interval=interval)
            logger.debug(f"键盘输入文本: {text[:20]}{'...' if len(text) > 20 else ''}")

    def press_key(self, key: str):
        """
        按下一个键

        Args:
            key: 按键名称，支持的键包括:
                 Enter, Tab, Escape, Space, Backspace
                 a-z, 0-9, F1-F12
                 shift, ctrl, alt, esc
                 up, down, left, right, home, end, pageup, pagedown
        """
        key_code = self._parse_key(key)
        pyautogui.press(key_code)
        logger.debug(f"按键: {key}")

    def key_down(self, key: str):
        """按下并保持（不释放）"""
        key_code = self._parse_key(key)
        pyautogui.keyDown(key_code)
        logger.debug(f"按键按下: {key}")

    def key_up(self, key: str):
        """释放按键"""
        key_code = self._parse_key(key)
        pyautogui.keyUp(key_code)
        logger.debug(f"按键释放: {key}")

    def hotkey(self, *keys: str):
        """
        发送组合键

        Args:
            *keys: 组合键列表，如 hotkey("ctrl", "a") 全选
        """
        parsed_keys = [self._parse_key(k) for k in keys]
        pyautogui.hotkey(*parsed_keys)
        logger.debug(f"组合键: {'+'.join(keys)}")

    # ============ 辅助方法 ============

    @staticmethod
    def _sleep(seconds: float = 0.1):
        """等待"""
        time.sleep(seconds)

    @staticmethod
    def _parse_key(key: str) -> str:
        """将字符串按键名转换为 pyautogui 格式"""
        key = key.strip().lower()

        # 标准化按键名
        key_map = {
            # 字母（pyautogui 直接支持）
            "a": "a", "b": "b", "c": "c", "d": "d", "e": "e",
            "f": "f", "g": "g", "h": "h", "i": "i", "j": "j",
            "k": "k", "l": "l", "m": "m", "n": "n", "o": "o",
            "p": "p", "q": "q", "r": "r", "s": "s", "t": "t",
            "u": "u", "v": "v", "w": "w", "x": "x", "y": "y", "z": "z",
            # 数字
            "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
            "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
            # 功能键
            "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4", "f5": "f5",
            "f6": "f6", "f7": "f7", "f8": "f8", "f9": "f9",
            "f10": "f10", "f11": "f11", "f12": "f12",
            # 特殊键
            "enter": "enter", "return": "enter",
            "tab": "tab", "escape": "esc", "esc": "esc",
            "space": "space", "backspace": "backspace",
            "delete": "delete",
            "up": "up", "down": "down", "left": "left", "right": "right",
            "home": "home", "end": "end",
            "pageup": "pageup", "pagedown": "pagedown",
            "shift": "shift", "leftshift": "shift", "rightshift": "shift",
            "ctrl": "ctrl", "leftctrl": "ctrl", "rightctrl": "ctrl",
            "alt": "alt", "leftalt": "alt", "rightalt": "alt",
            "win": "win", "lwin": "win", "rwin": "rwin",
        }

        result = key_map.get(key)
        if result is None:
            raise ValueError(f"不支持的按键: {key}")
        return result


# 全局单例
_default_input: InputControl | None = None


def get_input_control() -> InputControl:
    """获取全局 InputControl 实例"""
    global _default_input
    if _default_input is None:
        _default_input = InputControl()
    return _default_input
