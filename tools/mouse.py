"""
鼠标操作工具
"""
from langchain_core.tools import tool

from tools._shared import get_executor, grid_to_screen


@tool
def click(grid_x: int, grid_y: int) -> str:
    """
    在指定坐标处执行鼠标左键点击。

    参数:
        grid_x: 1000x1000 网格坐标系中的 X 坐标
        grid_y: 1000x1000 网格坐标系中的 Y 坐标

    返回:
        操作结果描述
    """
    screen_x, screen_y = grid_to_screen(grid_x, grid_y)
    ok = get_executor().execute(action="click", x=screen_x, y=screen_y)
    if ok:
        return f"成功点击坐标 ({screen_x}, {screen_y}) [网格坐标: ({grid_x}, {grid_y})]"
    return f"点击坐标 ({screen_x}, {screen_y}) 失败"


@tool
def move_mouse(grid_x: int, grid_y: int) -> str:
    """
    将鼠标移动到指定坐标（不点击）。

    参数:
        grid_x: 1000x1000 网格坐标系中的 X 坐标
        grid_y: 1000x1000 网格坐标系中的 Y 坐标

    返回:
        操作结果描述
    """
    screen_x, screen_y = grid_to_screen(grid_x, grid_y)
    ok = get_executor().execute(action="move", x=screen_x, y=screen_y)
    if ok:
        return f"成功移动鼠标到 ({screen_x}, {screen_y}) [网格坐标: ({grid_x}, {grid_y})]"
    return f"移动鼠标到 ({screen_x}, {screen_y}) 失败"


@tool
def double_click(grid_x: int, grid_y: int) -> str:
    """
    在指定坐标处执行鼠标左键双击。

    参数:
        grid_x: 1000x1000 网格坐标系中的 X 坐标
        grid_y: 1000x1000 网格坐标系中的 Y 坐标

    返回:
        操作结果描述
    """
    screen_x, screen_y = grid_to_screen(grid_x, grid_y)
    ok = get_executor().execute(action="double_click", x=screen_x, y=screen_y)
    if ok:
        return f"成功双击坐标 ({screen_x}, {screen_y}) [网格坐标: ({grid_x}, {grid_y})]"
    return f"双击坐标 ({screen_x}, {screen_y}) 失败"


@tool
def right_click(grid_x: int, grid_y: int) -> str:
    """
    在指定坐标处执行鼠标右键点击（通常用于打开上下文菜单）。

    参数:
        grid_x: 1000x1000 网格坐标系中的 X 坐标
        grid_y: 1000x1000 网格坐标系中的 Y 坐标

    返回:
        操作结果描述
    """
    screen_x, screen_y = grid_to_screen(grid_x, grid_y)
    ok = get_executor().execute(action="right_click", x=screen_x, y=screen_y)
    if ok:
        return f"成功右键点击坐标 ({screen_x}, {screen_y}) [网格坐标: ({grid_x}, {grid_y})]"
    return f"右键点击坐标 ({screen_x}, {screen_y}) 失败"


@tool
def scroll(grid_x: int, grid_y: int, amount: int = 10) -> str:
    """
    在指定位置滚动鼠标滚轮。

    参数:
        grid_x: 1000x1000 网格坐标系中的 X 坐标（鼠标位置）
        grid_y: 1000x1000 网格坐标系中的 Y 坐标（鼠标位置）
        amount: 滚动量，正数向上滚动，负数向下滚动，默认 10

    返回:
        操作结果描述
    """
    screen_x, screen_y = grid_to_screen(grid_x, grid_y)
    ok = get_executor().execute(action="scroll", x=screen_x, y=screen_y, amount=amount)
    if ok:
        direction = "向上" if amount > 0 else "向下"
        return f"成功在 ({screen_x}, {screen_y}) 滚动 {direction} {abs(amount)} 格"
    return f"滚动失败"


@tool
def drag(grid_x1: int, grid_y1: int, grid_x2: int, grid_y2: int, duration: float = 0.5) -> str:
    """
    从起点坐标拖拽到终点坐标（按住左键拖动）。

    参数:
        grid_x1: 1000x1000 网格坐标系中的起点 X 坐标
        grid_y1: 1000x1000 网格坐标系中的起点 Y 坐标
        grid_x2: 1000x1000 网格坐标系中的终点 X 坐标
        grid_y2: 1000x1000 网格坐标系中的终点 Y 坐标
        duration: 拖拽持续时间（秒），默认 0.5

    返回:
        操作结果描述
    """
    screen_x1, screen_y1 = grid_to_screen(grid_x1, grid_y1)
    screen_x2, screen_y2 = grid_to_screen(grid_x2, grid_y2)
    ok = get_executor().execute(
        action="drag", x=screen_x1, y=screen_y1,
        x2=screen_x2, y2=screen_y2, duration=duration
    )
    if ok:
        return f"成功拖拽 ({screen_x1}, {screen_y1}) -> ({screen_x2}, {screen_y2})"
    return f"拖拽失败"
