"""
键盘操作工具
"""
import time
from langchain_core.tools import tool

from config.settings import GRID_WIDTH, GRID_HEIGHT
from tools._shared import get_executor, grid_to_screen

_GRID = f"{GRID_WIDTH}×{GRID_HEIGHT}"


@tool(parse_docstring=True)
def type_text(text: str, reason: str, step_type: str,
              grid_x: int | None = None, grid_y: int | None = None) -> str:
    """
    输入文本。如果提供了坐标，先点击定位再输入；如果没有坐标，假设光标已存在，直接输入。

    Args:
        text: 要输入的文本内容
        reason: 简短描述本轮操作（过去式），如"输入了搜索关键词"
        step_type: "continue"（操作成功，继续下一步）或 "retry"（操作失败，需要重试）
        grid_x: 1000x1000 网格坐标系中的 X 坐标（可选）
        grid_y: 1000x1000 网格坐标系中的 Y 坐标（可选）

    Returns:
        操作结果描述
    """
    executor = get_executor()

    if grid_x is not None and grid_y is not None:
        screen_x, screen_y = grid_to_screen(grid_x, grid_y)
    else:
        screen_x, screen_y = None, None

    ok = executor.execute(action="type", x=screen_x, y=screen_y, text=text)

    if ok:
        if grid_x is not None:
            return f"成功在网格坐标 ({grid_x}, {grid_y}) 输入文本: {text}"
        return f"成功输入文本: {text}"
    return f"输入文本失败"


@tool(parse_docstring=True)
def press_key(key: str, reason: str, step_type: str) -> str:
    """
    按下指定键盘按键。

    Args:
        key: 按键名称，如 "Enter", "Escape", "Tab", "Backspace" 等
        reason: 简短描述本轮操作（过去式），如"按下回车确认"
        step_type: "continue" 或 "retry"

    Returns:
        操作结果描述
    """
    ok = get_executor().execute(action="press", key=key)
    if ok:
        return f"成功按下按键: {key}"
    return f"按键 {key} 失败"


@tool(parse_docstring=True)
def hotkey(keys: str, reason: str, step_type: str) -> str:
    """
    按下组合键（如 Ctrl+V 粘贴）。

    Args:
        keys: 组合键字符串，用逗号分隔，如 "ctrl,c" 表示 Ctrl+C，"ctrl,v" 表示 Ctrl+V
        reason: 简短描述本轮操作（过去式），如"按下 Ctrl+V 粘贴内容"
        step_type: "continue" 或 "retry"

    Returns:
        操作结果描述
    """
    ok = get_executor().execute(action="hotkey", text=keys)
    if ok:
        key_list = keys.split(",")
        return f"成功按下组合键: {'+'.join(key_list)}"
    return f"组合键 {keys} 失败"


@tool(parse_docstring=True)
def key_down(key: str, reason: str, step_type: str) -> str:
    """
    按住指定按键不释放（用于需要组合键的场景，如拖拽时按住 Ctrl）。

    Args:
        key: 按键名称，如 "ctrl", "shift", "alt", "win" 等
        reason: 简短描述本轮操作（过去式）
        step_type: "continue" 或 "retry"

    Returns:
        操作结果描述
    """
    ok = get_executor().execute(action="key_down", key=key)
    if ok:
        return f"成功按住按键: {key}"
    return f"按键 {key} 失败"


@tool(parse_docstring=True)
def key_up(key: str, reason: str, step_type: str) -> str:
    """
    释放之前按住的按键（与 key_down 配合使用）。

    Args:
        key: 按键名称，如 "ctrl", "shift", "alt", "win" 等
        reason: 简短描述本轮操作（过去式）
        step_type: "continue" 或 "retry"

    Returns:
        操作结果描述
    """
    ok = get_executor().execute(action="key_up", key=key)
    if ok:
        return f"成功释放按键: {key}"
    return f"按键 {key} 失败"


@tool(parse_docstring=True)
def wait(seconds: float = 1.0, reason: str = "", step_type: str = "continue") -> str:
    """
    等待指定时间（秒）。

    Args:
        seconds: 等待时间（秒），默认 1.0
        reason: 简短描述等待原因（如"等待页面加载"）
        step_type: "continue" 或 "retry"

    Returns:
        等待完成描述
    """
    time.sleep(seconds)
    return f"等待 {seconds} 秒完成"


# 将工具描述中的硬编码 1000x1000 替换为实际配置值
for _t in [type_text, press_key, hotkey, key_down, key_up, wait]:
    _t.description = _t.description.replace("1000×1000", _GRID).replace("1000x1000", _GRID)
