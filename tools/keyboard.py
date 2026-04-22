"""
键盘操作工具
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
def type_text(text: str, grid_x: int | None = None, grid_y: int | None = None) -> str:
    """
    输入文本。如果提供了坐标，先点击定位再输入；如果没有坐标，假设光标已存在，直接输入。

    参数:
        text: 要输入的文本内容
        grid_x: 1000x1000 网格坐标系中的 X 坐标（可选。如果光标已在此位置可不填）
        grid_y: 1000x1000 网格坐标系中的 Y 坐标（可选。如果光标已在此位置可不填）

    返回:
        操作结果描述
    """
    executor = _get_executor()

    if grid_x is not None and grid_y is not None:
        # 提供了坐标，先点击定位
        screen_x, screen_y = _grid_to_screen(grid_x, grid_y)
        ok1 = executor.execute(action="click", x=screen_x, y=screen_y)
        time.sleep(0.3)
    else:
        # 没有提供坐标，直接输入（假设光标已存在）
        ok1 = True
        screen_x, screen_y = None, None

    # 输入文本
    ok2 = executor.execute(action="type", x=screen_x, y=screen_y, text=text)

    if ok1 and ok2:
        if screen_x is not None:
            return f"成功在坐标 ({screen_x}, {screen_y}) 输入文本: {text}"
        else:
            return f"成功输入文本: {text}"
    else:
        return f"输入文本失败"


@tool
def press_key(key: str) -> str:
    """
    按下指定键盘按键。

    参数:
        key: 按键名称，如 "Enter", "Escape", "Tab", "Backspace", "Ctrl+A", "Ctrl+V" 等

    返回:
        操作结果描述
    """
    executor = _get_executor()
    ok = executor.execute(action="press", key=key)

    if ok:
        return f"成功按下按键: {key}"
    else:
        return f"按键 {key} 失败"


@tool
def hotkey(keys: str) -> str:
    """
    按下组合键（如 Ctrl+C 全选复制）。

    参数:
        keys: 组合键字符串，用逗号分隔，如 "ctrl,c" 表示 Ctrl+C，"ctrl,v" 表示 Ctrl+V，
              "ctrl,shift,a" 表示 Ctrl+Shift+A，"ctrl,a" 表示全选

    返回:
        操作结果描述
    """
    executor = _get_executor()
    ok = executor.execute(action="hotkey", text=keys)

    if ok:
        key_list = keys.split(",")
        return f"成功按下组合键: {'+'.join(key_list)}"
    else:
        return f"组合键 {keys} 失败"


@tool
def key_down(key: str) -> str:
    """
    按住指定按键不释放（用于需要组合键的场景，如拖拽时按住 Ctrl）。

    参数:
        key: 按键名称，如 "ctrl", "shift", "alt", "win" 等

    返回:
        操作结果描述
    """
    executor = _get_executor()
    ok = executor.execute(action="key_down", key=key)

    if ok:
        return f"成功按住按键: {key}"
    else:
        return f"按键 {key} 失败"


@tool
def key_up(key: str) -> str:
    """
    释放之前按住的按键（与 key_down 配合使用）。

    参数:
        key: 按键名称，如 "ctrl", "shift", "alt", "win" 等

    返回:
        操作结果描述
    """
    executor = _get_executor()
    ok = executor.execute(action="key_up", key=key)

    if ok:
        return f"成功释放按键: {key}"
    else:
        return f"按键 {key} 失败"


@tool
def wait(seconds: float = 1.0) -> str:
    """
    等待指定时间（秒）。

    参数:
        seconds: 等待时间（秒），默认 1.0

    返回:
        等待完成描述
    """
    time.sleep(seconds)
    return f"等待 {seconds} 秒完成"
