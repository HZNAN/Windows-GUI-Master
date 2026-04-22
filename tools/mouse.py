"""
鼠标操作工具
"""
import time
from langchain_core.tools import tool

from core.execution_engine import ExecutionEngine

_executor = None
# 使用可变容器存储缓存，避免线程问题
_screen_info_cache = [None]


def _get_executor():
    global _executor
    if _executor is None:
        _executor = ExecutionEngine()
    return _executor


def _grid_to_screen(grid_x: int, grid_y: int) -> tuple[int, int]:
    """将 1000x1000 网格坐标换算回原屏幕坐标"""
    info = _screen_info_cache[0]
    if info is None:
        info = {"orig_w": 1920, "orig_h": 1080}
    scale_x = info["orig_w"] / 1000
    scale_y = info["orig_h"] / 1000
    return int(grid_x * scale_x), int(grid_y * scale_y)


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
    screen_x, screen_y = _grid_to_screen(grid_x, grid_y)

    executor = _get_executor()
    ok = executor.execute(action="click", x=screen_x, y=screen_y)

    if ok:
        return f"成功点击坐标 ({screen_x}, {screen_y}) [网格坐标: ({grid_x}, {grid_y})]"
    else:
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
    screen_x, screen_y = _grid_to_screen(grid_x, grid_y)

    executor = _get_executor()
    ok = executor.execute(action="move", x=screen_x, y=screen_y)

    if ok:
        return f"成功移动鼠标到 ({screen_x}, {screen_y}) [网格坐标: ({grid_x}, {grid_y})]"
    else:
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
    screen_x, screen_y = _grid_to_screen(grid_x, grid_y)

    executor = _get_executor()
    ok = executor.execute(action="double_click", x=screen_x, y=screen_y)

    if ok:
        return f"成功双击坐标 ({screen_x}, {screen_y}) [网格坐标: ({grid_x}, {grid_y})]"
    else:
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
    screen_x, screen_y = _grid_to_screen(grid_x, grid_y)

    executor = _get_executor()
    ok = executor.execute(action="right_click", x=screen_x, y=screen_y)

    if ok:
        return f"成功右键点击坐标 ({screen_x}, {screen_y}) [网格坐标: ({grid_x}, {grid_y})]"
    else:
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
    screen_x, screen_y = _grid_to_screen(grid_x, grid_y)

    executor = _get_executor()
    ok = executor.execute(action="scroll", x=screen_x, y=screen_y, amount=amount)

    if ok:
        direction = "向上" if amount > 0 else "向下"
        return f"成功在 ({screen_x}, {screen_y}) 滚动 {direction} {abs(amount)} 格"
    else:
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
    screen_x1, screen_y1 = _grid_to_screen(grid_x1, grid_y1)
    screen_x2, screen_y2 = _grid_to_screen(grid_x2, grid_y2)

    executor = _get_executor()
    ok = executor.execute(action="drag", x=screen_x1, y=screen_y1, x2=screen_x2, y2=screen_y2, duration=duration)

    if ok:
        return f"成功拖拽 ({screen_x1}, {screen_y1}) -> ({screen_x2}, {screen_y2})"
    else:
        return f"拖拽失败"
