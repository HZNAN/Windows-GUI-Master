"""
tools 层共享工具：ExecutionEngine 单例、屏幕信息缓存、坐标转换
"""
from core.execution_engine import ExecutionEngine

_executor: ExecutionEngine | None = None
_screen_info_cache: list[dict | None] = [None]


def get_executor() -> ExecutionEngine:
    global _executor
    if _executor is None:
        _executor = ExecutionEngine()
    return _executor


def grid_to_screen(grid_x: int, grid_y: int) -> tuple[int, int]:
    """将网格坐标换算回原屏幕坐标（LLM 可能传字符串，做类型转换）"""
    from config.settings import GRID_WIDTH, GRID_HEIGHT
    info = _screen_info_cache[0]
    if info is None:
        info = {"orig_w": 1920, "orig_h": 1080}
    scale_x = info["orig_w"] / GRID_WIDTH
    scale_y = info["orig_h"] / GRID_HEIGHT
    return int(float(grid_x) * scale_x), int(float(grid_y) * scale_y)
