"""
动作执行器
将语义动作（来自 UI-TARS 或 Planner）转换为实际的鼠标键盘操作
"""
import time
from typing import Literal
from dataclasses import dataclass
from loguru import logger

from drivers.input_control import get_input_control
from llm.ui_tars_client import UIAction
from .element_locator import ElementLocator


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    action: str
    target: str | None
    x: int | None = None
    y: int | None = None
    message: str = ""


class Executor:
    """
    动作执行器
    接收语义动作指令，调用 ElementLocator 定位后，通过 InputControl 执行
    """

    def __init__(self, element_locator: ElementLocator | None = None):
        self.input_control = get_input_control()
        self.element_locator = element_locator or ElementLocator()

    def execute(self, action: UIAction, current_screenshot) -> ExecutionResult:
        """
        执行一个 UI-TARS 返回的动作

        Args:
            action: UIAction 对象
            current_screenshot: 当前屏幕截图

        Returns:
            ExecutionResult
        """
        action_type = action.action_type
        logger.info(f"执行动作: {action_type} | target={action.target} | coord=({action.x},{action.y})")

        try:
            if action_type == "click":
                return self._execute_click(action, current_screenshot)
            elif action_type == "type":
                return self._execute_type(action)
            elif action_type == "press":
                return self._execute_press(action)
            elif action_type == "scroll":
                return self._execute_scroll(action)
            elif action_type == "wait":
                return self._execute_wait(action)
            elif action_type == "hover":
                return self._execute_hover(action, current_screenshot)
            else:
                return ExecutionResult(
                    success=False,
                    action=action_type,
                    target=action.target,
                    message=f"未知动作类型: {action_type}"
                )
        except Exception as e:
            logger.error(f"动作执行异常: {e}")
            return ExecutionResult(
                success=False,
                action=action_type,
                target=action.target,
                message=str(e)
            )

    def execute_step(self, step: "PlannedStep", current_screenshot) -> ExecutionResult:
        """
        执行一个 Planner 分解出的步骤

        Args:
            step: PlannedStep 对象
            current_screenshot: 当前屏幕截图

        Returns:
            ExecutionResult
        """
        from llm.planner_llm_client import PlannedStep as PS

        action_type = step.action
        logger.info(f"执行步骤: {action_type} | target={step.target} | coord=({step.x},{step.y})")

        try:
            if action_type == "click":
                return self._execute_click_by_step(step, current_screenshot)
            elif action_type == "type":
                return self._execute_type_by_step(step)
            elif action_type == "press":
                return self._execute_press_by_step(step)
            elif action_type == "scroll":
                return self._execute_scroll_by_step(step)
            elif action_type == "wait":
                seconds = float(step.description.split()[0]) if step.description else 2
                return self._execute_wait_seconds(seconds)
            else:
                return ExecutionResult(
                    success=False,
                    action=action_type,
                    target=step.target,
                    message=f"未知步骤类型: {action_type}"
                )
        except Exception as e:
            logger.error(f"步骤执行异常: {e}")
            return ExecutionResult(
                success=False,
                action=action_type,
                target=step.target,
                message=str(e)
            )

    # ============ 私有方法（UIAction 驱动）============

    def _execute_click(self, action: UIAction, screenshot) -> ExecutionResult:
        """执行点击动作"""
        x, y = self._resolve_coordinates(action.target, action.x, action.y, screenshot)
        if x is None or y is None:
            return ExecutionResult(False, "click", action.target, message="无法解析坐标")

        self.input_control.click(x, y)
        return ExecutionResult(True, "click", action.target, x, y, "点击成功")

    def _execute_type(self, action: UIAction) -> ExecutionResult:
        """执行输入文本动作"""
        text = action.text or ""
        if action.target:
            # 先定位目标元素
            screenshot = get_screen_capture().capture()
            coords = self.element_locator.locate(action.target, screenshot)
            if coords:
                self.input_control.click(coords[0], coords[1])
                self.input_control._sleep()
        self.input_control.type_text(text)
        return ExecutionResult(True, "type", action.target, text=text, message=f"输入文本: {text}")

    def _execute_press(self, action: UIAction) -> ExecutionResult:
        """执行按键动作"""
        key = action.target or "Enter"
        self.input_control.press_key(key)
        return ExecutionResult(True, "press", key, message=f"按键: {key}")

    def _execute_scroll(self, action: UIAction) -> ExecutionResult:
        """执行滚动动作"""
        direction = action.target or "down"
        amount = int(action.text or "3")
        # 滚动先移动到当前位置再滚
        self.input_control.scroll(0, 0, -amount if direction == "down" else amount)
        return ExecutionResult(True, "scroll", direction, message=f"滚动 {direction} {amount} 步")

    def _execute_wait(self, action: UIAction) -> ExecutionResult:
        """执行等待动作"""
        seconds = float(action.text or "2")
        time.sleep(seconds)
        return ExecutionResult(True, "wait", message=f"等待 {seconds} 秒")

    def _execute_hover(self, action: UIAction, screenshot) -> ExecutionResult:
        """执行悬停动作"""
        x, y = self._resolve_coordinates(action.target, action.x, action.y, screenshot)
        if x is None:
            return ExecutionResult(False, "hover", action.target, message="无法解析坐标")
        self.input_control.move_to(x, y)
        return ExecutionResult(True, "hover", action.target, x, y, "悬停成功")

    # ============ 私有方法（PlannedStep 驱动）============

    def _execute_click_by_step(self, step, screenshot) -> ExecutionResult:
        """执行步骤中的点击"""
        x, y = self._resolve_step_coordinates(step, screenshot)
        if x is None:
            return ExecutionResult(False, "click", step.target, message="无法解析坐标")
        self.input_control.click(x, y)
        return ExecutionResult(True, "click", step.target, x, y, "点击成功")

    def _execute_type_by_step(self, step) -> ExecutionResult:
        """执行步骤中的文本输入"""
        text = step.text or ""
        if step.target:
            screenshot = get_screen_capture().capture()
            coords = self.element_locator.locate(step.target, screenshot)
            if coords:
                self.input_control.click(coords[0], coords[1])
                self.input_control._sleep()
        self.input_control.type_text(text)
        return ExecutionResult(True, "type", step.target, text=text, message=f"输入: {text}")

    def _execute_press_by_step(self, step) -> ExecutionResult:
        """执行步骤中的按键"""
        key = step.key or step.target or "Enter"
        self.input_control.press_key(key)
        return ExecutionResult(True, "press", key, message=f"按键: {key}")

    def _execute_scroll_by_step(self, step) -> ExecutionResult:
        """执行步骤中的滚动"""
        direction = step.target or "down"
        amount = int(step.text or "3")
        self.input_control.scroll(0, 0, -amount if direction == "down" else amount)
        return ExecutionResult(True, "scroll", direction, message=f"滚动 {direction} {amount} 步")

    def _execute_wait_seconds(self, seconds: float) -> ExecutionResult:
        time.sleep(seconds)
        return ExecutionResult(True, "wait", message=f"等待 {seconds} 秒")

    # ============ 辅助方法 ============

    def _resolve_coordinates(
        self, target: str | None, x: int | None, y: int | None, screenshot
    ) -> tuple[int | None, int | None]:
        """解析动作坐标，优先级：显式坐标 > UI-TARS 坐标 > 元素定位"""
        if x is not None and y is not None:
            return (x, y)

        if target:
            coords = self.element_locator.locate(target, screenshot)
            if coords:
                return coords

        return (None, None)

    def _resolve_step_coordinates(self, step, screenshot) -> tuple[int | None, int | None]:
        """解析步骤坐标"""
        if step.x is not None and step.y is not None:
            return (step.x, step.y)

        if step.target:
            coords = self.element_locator.locate(step.target, screenshot)
            if coords:
                return coords

        return (None, None)
