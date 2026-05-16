"""
Agent 状态控制工具 — finish 是唯一的独立状态工具，continue/retry 已整合到动作工具的 step_type 参数中
"""
from langchain_core.tools import tool


@tool(parse_docstring=True)
def finish() -> str:
    """
    任务已完成。当你确认屏幕上已达成任务目标时，调用此工具结束任务。

    Returns:
        TASK_COMPLETED
    """
    return "TASK_COMPLETED"


@tool(parse_docstring=True)
def ask_human(question: str, reason: str, step_type: str) -> str:
    """
    向人类请求帮助或确认。调用后会阻塞等待人类回复，然后继续执行。

    使用场景：
    - 遇到无法自行解决的异常情况
    - 执行敏感操作前需要人类确认
    - 需要人类提供额外的信息才能继续

    Args:
        question: 向人类提出的问题，用自然语言描述
        reason: 简短描述本轮操作（过去式），如"遇到无法识别的弹窗，请求人类帮助"
        step_type: "continue" 或 "retry"

    Returns:
        人类的回复文本。如果超时（5分钟无响应）则返回 "[Human did not respond]"。
    """
    from core.agent_service import get_current_agent_session
    session = get_current_agent_session()
    if session is None:
        return "[Error: no active agent session]"
    return session.wait_for_human(question)
