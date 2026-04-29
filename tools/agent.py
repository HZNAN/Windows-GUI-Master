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


@tool
def ask_human(question: str) -> str:
    """
    向人类请求帮助或确认。调用后会阻塞等待人类回复，然后继续执行。

    使用场景：
    - 遇到无法自行解决的异常情况
    - 执行敏感操作前需要人类确认
    - 需要人类提供额外的信息才能继续

    参数:
        question: 向人类提出的问题，用自然语言描述

    返回:
        人类的回复文本。如果超时（5分钟无响应）则返回 "[Human did not respond]"。
    """
    from core.agent_service import get_current_agent_session
    session = get_current_agent_session()
    if session is None:
        return "[Error: no active agent session]"
    return session.wait_for_human(question)
