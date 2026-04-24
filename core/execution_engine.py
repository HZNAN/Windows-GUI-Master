"""
执行引擎
只负责按 Planner 指令执行操作，不做决策
"""
import time
import pyautogui
from loguru import logger

from drivers.screen_capture import get_screen_capture, ScreenCapture
from drivers.input_control import InputControl
from core.virtual_cursor import get_virtual_cursor


class ExecutionEngine:
    """
    执行器
    接收结构化指令，执行 click / type / press 操作
    """

    def __init__(self):
        self.screen = get_screen_capture()
        self.input = InputControl()
        self._virtual_cursor = get_virtual_cursor()

    def execute(self, action: str, x: int | None = None, y: int | None = None,
                text: str | None = None, key: str | None = None,
                x2: int | None = None, y2: int | None = None,
                amount: int | None = None, duration: float = 0.5,
                button: str = "left") -> bool:
        """
        执行 Planner 输出的指令

        Args:
            action: click / move / type / press / wait / done
                   / double_click / right_click / scroll / drag
                   / mouse_down / mouse_up / hotkey / key_down / key_up
            x, y: 坐标
            x2, y2: 拖拽终点坐标（drag 时使用）
            text: 输入文本（type 时使用）
            key: 按键名（press/hotkey 时使用）
            amount: 滚动量（scroll 时使用）
            duration: 拖拽持续时间
            button: 鼠标按钮（left/right/middle）
        """
        try:
            if action == "click":
                if x is None or y is None:
                    logger.error(f"click 缺少坐标: ({x}, {y})")
                    return False
                self._virtual_cursor.move_to(x, y)
                time.sleep(0.1)  # 等待动画完成
                self.input.click(x, y, button=button)
                logger.info(f"执行 click: ({x}, {y}), button={button}")
                return True

            elif action == "move":
                if x is None or y is None:
                    logger.error(f"move 缺少坐标: ({x}, {y})")
                    return False
                self._virtual_cursor.move_to(x, y)
                logger.info(f"执行 move: ({x}, {y})")
                return True

            elif action == "double_click":
                if x is None or y is None:
                    logger.error(f"double_click 缺少坐标: ({x}, {y})")
                    return False
                self.input.double_click(x, y, button=button)
                logger.info(f"执行 double_click: ({x}, {y})")
                return True

            elif action == "right_click":
                if x is None or y is None:
                    logger.error(f"right_click 缺少坐标: ({x}, {y})")
                    return False
                self.input.click(x, y, button="right")
                logger.info(f"执行 right_click: ({x}, {y})")
                return True

            elif action == "mouse_down":
                if x is None or y is None:
                    logger.error(f"mouse_down 缺少坐标: ({x}, {y})")
                    return False
                self.input.move_to(x, y, duration=0.1)
                pyautogui.mouseDown(button=button)
                logger.info(f"执行 mouse_down: ({x}, {y})")
                return True

            elif action == "mouse_up":
                pyautogui.mouseUp(button=button)
                logger.info(f"执行 mouse_up, button={button}")
                return True

            elif action == "scroll":
                if x is None or y is None:
                    logger.error(f"scroll 缺少坐标: ({x}, {y})")
                    return False
                scroll_amount = amount if amount is not None else 3
                self.input.scroll(x, y, scroll_amount)
                logger.info(f"执行 scroll: ({x}, {y}), amount={scroll_amount}")
                return True

            elif action == "drag":
                if x is None or y is None or x2 is None or y2 is None:
                    logger.error(f"drag 缺少坐标: ({x}, {y}) -> ({x2}, {y2})")
                    return False
                self.input.drag(x, y, x2, y2, duration=duration)
                logger.info(f"执行 drag: ({x}, {y}) -> ({x2}, {y2})")
                return True

            elif action == "type":
                if x is not None and y is not None:
                    # 有坐标，先点击定位
                    self.input.click(x, y)
                    time.sleep(0.3)
                # 直接输入文本（如果有坐标则假设已点击过，没有则假设cursor已存在）
                self.input.type_text(text or "")
                logger.info(f"执行 type: ({x}, {y}), text={text}")
                return True

            elif action == "press":
                self.input.press_key(key or "Enter")
                logger.info(f"执行 press: {key}")
                return True

            elif action == "key_down":
                self.input.key_down(key or "")
                logger.info(f"执行 key_down: {key}")
                return True

            elif action == "key_up":
                self.input.key_up(key or "")
                logger.info(f"执行 key_up: {key}")
                return True

            elif action == "hotkey":
                # text 格式: "ctrl,c,a" 或 ["ctrl", "a"]
                if text:
                    keys = [k.strip() for k in text.split(",")]
                else:
                    keys = [key] if key else []
                self.input.hotkey(*keys)
                logger.info(f"执行 hotkey: {keys}")
                return True

            elif action == "wait":
                delay = float(text or "1")
                time.sleep(delay)
                logger.info(f"执行 wait: {delay}s")
                return True

            elif action == "done":
                logger.info("执行 done，任务完成")
                return True

            else:
                logger.warning(f"未知 action 类型: {action}")
                return False

        except Exception as e:
            logger.error(f"执行异常: {e}")
            return False

    def capture(self) -> tuple:
        """执行后截图，返回 (numpy数组, 路径)"""
        return self.screen.auto_save(prefix="exec")
