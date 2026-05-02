"""
鼠标操作工具
"""
from langchain_core.tools import tool

from config.settings import GRID_WIDTH, GRID_HEIGHT
from tools._shared import get_executor, grid_to_screen

_GRID = f"{GRID_WIDTH}×{GRID_HEIGHT}"


@tool(parse_docstring=True)
def click(grid_x: int, grid_y: int, reason: str, step_type: str) -> str:
    """
    在指定坐标处执行鼠标左键点击。

    Args:
        grid_x: 1000x1000 网格坐标系中的 X 坐标
        grid_y: 1000x1000 网格坐标系中的 Y 坐标
        reason: 简短描述本轮操作（过去式，不写未来计划），如"点击了搜索框"
        step_type: "continue"（操作成功，继续下一步）或 "retry"（操作失败，需要重试）

    Returns:
        操作结果描述
    """
    screen_x, screen_y = grid_to_screen(grid_x, grid_y)
    ok = get_executor().execute(action="click", x=screen_x, y=screen_y)
    if ok:
        return f"成功点击网格坐标 ({grid_x}, {grid_y})"
    return f"点击网格坐标 ({grid_x}, {grid_y}) 失败"


@tool(parse_docstring=True)
def move_mouse(grid_x: int, grid_y: int, reason: str, step_type: str) -> str:
    """
    将鼠标移动到指定坐标（不点击）。

    Args:
        grid_x: 1000x1000 网格坐标系中的 X 坐标
        grid_y: 1000x1000 网格坐标系中的 Y 坐标
        reason: 简短描述本轮操作（过去式）
        step_type: "continue" 或 "retry"

    Returns:
        操作结果描述
    """
    screen_x, screen_y = grid_to_screen(grid_x, grid_y)
    ok = get_executor().execute(action="move", x=screen_x, y=screen_y)
    if ok:
        return f"成功移动鼠标到网格坐标 ({grid_x}, {grid_y})"
    return f"移动鼠标到网格坐标 ({grid_x}, {grid_y}) 失败"


@tool(parse_docstring=True)
def double_click(grid_x: int, grid_y: int, reason: str, step_type: str) -> str:
    """
    在指定坐标处执行鼠标左键双击。

    Args:
        grid_x: 1000x1000 网格坐标系中的 X 坐标
        grid_y: 1000x1000 网格坐标系中的 Y 坐标
        reason: 简短描述本轮操作（过去式）
        step_type: "continue" 或 "retry"

    Returns:
        操作结果描述
    """
    screen_x, screen_y = grid_to_screen(grid_x, grid_y)
    ok = get_executor().execute(action="double_click", x=screen_x, y=screen_y)
    if ok:
        return f"成功双击网格坐标 ({grid_x}, {grid_y})"
    return f"双击网格坐标 ({grid_x}, {grid_y}) 失败"


@tool(parse_docstring=True)
def right_click(grid_x: int, grid_y: int, reason: str, step_type: str) -> str:
    """
    在指定坐标处执行鼠标右键点击（通常用于打开上下文菜单）。

    Args:
        grid_x: 1000x1000 网格坐标系中的 X 坐标
        grid_y: 1000x1000 网格坐标系中的 Y 坐标
        reason: 简短描述本轮操作（过去式）
        step_type: "continue" 或 "retry"

    Returns:
        操作结果描述
    """
    screen_x, screen_y = grid_to_screen(grid_x, grid_y)
    ok = get_executor().execute(action="right_click", x=screen_x, y=screen_y)
    if ok:
        return f"成功右键点击网格坐标 ({grid_x}, {grid_y})"
    return f"右键点击网格坐标 ({grid_x}, {grid_y}) 失败"


@tool(parse_docstring=True)
def scroll(grid_x: int, grid_y: int, reason: str, step_type: str, amount: int = 5) -> str:
    """
    在指定位置滚动鼠标滚轮。

    Args:
        grid_x: 1000x1000 网格坐标系中的 X 坐标（鼠标位置）
        grid_y: 1000x1000 网格坐标系中的 Y 坐标（鼠标位置）
        reason: 简短描述本轮操作（过去式）
        step_type: "continue" 或 "retry"
        amount: 滚动档位。正数向上滚动，负数向下滚动。
                1~3 ≈ 几行, 5 ≈ 半屏(默认), 10 ≈ 一整屏。

    Returns:
        操作结果描述
    """
    screen_x, screen_y = grid_to_screen(grid_x, grid_y)
    changed = get_executor().execute_scroll_with_detect(
        x=screen_x, y=screen_y, amount=amount
    )
    direction = "向上" if amount > 0 else "向下"
    if changed is None:
        return f"滚动失败（网格坐标 {grid_x},{grid_y}）"
    if not changed:
        return (f"在网格 ({grid_x},{grid_y}) 滚动 {direction} {abs(amount)} 档"
                f" —— 滚动无效，内容未变化（可能已到达边界，请停止向此方向滚动）")
    return f"成功在网格 ({grid_x},{grid_y}) 滚动 {direction} {abs(amount)} 档"


@tool(parse_docstring=True)
def drag(grid_x1: int, grid_y1: int, grid_x2: int, grid_y2: int,
         reason: str, step_type: str, duration: float = 0.5) -> str:
    """
    从起点坐标拖拽到终点坐标（按住左键拖动）。

    Args:
        grid_x1: 1000x1000 网格坐标系中的起点 X 坐标
        grid_y1: 1000x1000 网格坐标系中的起点 Y 坐标
        grid_x2: 1000x1000 网格坐标系中的终点 X 坐标
        grid_y2: 1000x1000 网格坐标系中的终点 Y 坐标
        reason: 简短描述本轮操作（过去式）
        step_type: "continue" 或 "retry"
        duration: 拖拽持续时间（秒），默认 0.5

    Returns:
        操作结果描述
    """
    screen_x1, screen_y1 = grid_to_screen(grid_x1, grid_y1)
    screen_x2, screen_y2 = grid_to_screen(grid_x2, grid_y2)
    ok = get_executor().execute(
        action="drag", x=screen_x1, y=screen_y1,
        x2=screen_x2, y2=screen_y2, duration=duration
    )
    if ok:
        return f"成功拖拽网格 ({grid_x1},{grid_y1}) → ({grid_x2},{grid_y2})"
    return f"拖拽网格 ({grid_x1},{grid_y1}) → ({grid_x2},{grid_y2}) 失败"


# 将工具描述中的硬编码 1000x1000 替换为实际配置值
for _t in [click, move_mouse, double_click, right_click, scroll, drag]:
    _t.description = _t.description.replace("1000×1000", _GRID).replace("1000x1000", _GRID)
