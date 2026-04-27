"""
Agent 状态控制工具 - 每轮必须调用其中之一
"""
from langchain_core.tools import tool


@tool
def finish() -> str:
    """
    任务已完成。当你确认屏幕上的状态已达成任务目标时，调用此工具结束任务。

    返回:
        TASK_COMPLETED
    """
    return "TASK_COMPLETED"


@tool
def continue_steps(reason: str) -> str:
    """
    当前步已执行，继续下一步。每轮操作后必须调用此工具或 retry 或 finish。

    参数:
        reason: 简短描述本轮做了什么（只说当前步，不要说未来计划）

    返回:
        CONTINUE
    """
    return "CONTINUE"


@tool
def retry(reason: str) -> str:
    """
    上一步未达到预期效果，用不同方式重试。

    参数:
        reason: 简短说明失败原因和调整策略

    返回:
        RETRY
    """
    return "RETRY"
