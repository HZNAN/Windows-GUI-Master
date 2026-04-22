"""
Agent 控制工具
"""
from langchain_core.tools import tool


@tool
def finish() -> str:
    """
    标记任务已完成，代理将成功结束。

    只有当任务目标已经完全达成时才能调用此工具。
    调用此工具表示代理工作完成，不需要再执行任何操作。

    返回:
        TASK_COMPLETED
    """
    return "TASK_COMPLETED"


@tool
def continue_steps(reason: str) -> str:
    """
    继续执行下一步操作。

    当你完成了当前步骤，需要继续执行更多操作才能完成整体任务时调用此工具。

    参数:
        reason: 简短说明下一步要做什么

    返回:
        CONTINUE
    """
    return "CONTINUE"


@tool
def retry(reason: str) -> str:
    """
    重试当前操作。

    当上一步操作没有达到预期效果，需要重新尝试时调用此工具。

    参数:
        reason: 简短说明重试的原因和要调整的策略

    返回:
        RETRY
    """
    return "RETRY"
