"""
ReactAgent 业务服务 — 与传输无关的共享逻辑

供 stdio 和 WebSocket 两种 ACP 传输层共享使用。
支持人机协同：Agent 可通过 ask_human 工具暂停并等待人类输入。
"""
import uuid
import time
import os
import queue
import threading
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger


class SessionNotFoundError(Exception):
    """会话不存在"""
    pass


# 线程局部存储：每个线程上正在运行的 AgentSession
_thread_local = threading.local()


def get_current_agent_session() -> Optional['AgentSession']:
    """返回当前线程所绑定的 AgentSession（由 ask_human 工具调用）"""
    return getattr(_thread_local, 'agent_session', None)


def push_notification(event_type: str, content, **extra):
    """Agent 线程调用：将通知事件推送到会话队列，供主线程发送 session/update

    event_type: "agent_message_chunk" | "tool_call" | "tool_result"
    """
    session = get_current_agent_session()
    if session is None:
        return
    event = {"type": event_type, "content": content}
    if extra:
        event["extra"] = extra
    session.notification_queue.put(event)


@dataclass
class AgentSession:
    """会话状态，包含人机协同的线程间通信桥接和通知队列"""

    session_id: str
    cwd: str = ""
    created_at: float = 0.0
    need_help: threading.Event = field(default_factory=threading.Event)
    answer_ready: threading.Event = field(default_factory=threading.Event)
    question: Optional[str] = None
    answer: Optional[str] = None
    agent_future: Optional['concurrent.futures.Future'] = None
    notification_queue: queue.Queue = field(default_factory=queue.Queue)

    def wait_for_human(self, question: str, timeout: float = 300) -> str:
        """在 Agent 线程中调用：阻塞直到人类响应（或超时）"""
        self.question = question
        self.need_help.set()
        ok = self.answer_ready.wait(timeout=timeout)
        if not ok:
            return "[Human did not respond]"
        return self.answer or ""

    def inject_answer(self, answer: str):
        """在主线程中调用：注入人类回答并唤醒 Agent 线程"""
        self.answer = answer
        self.need_help.clear()
        self.answer_ready.set()

    def is_waiting(self) -> bool:
        """是否正在等待人类输入（need_help 已设置但回答尚未到达）"""
        return self.need_help.is_set()

    def reset_help_state(self):
        """重置人机协同状态，准备下一次问答"""
        self.need_help.clear()
        self.answer_ready.clear()
        self.question = None
        self.answer = None


class ReactAgentService:
    """ReactAgent 会话管理与执行服务"""

    def __init__(self):
        self.sessions: dict[str, AgentSession] = {}
        self.current_session: Optional[str] = None

    # ===== 会话管理 =====

    def create_session(self, session_id: Optional[str] = None, cwd: str = "") -> str:
        """创建新会话，返回 session_id"""
        session_id = session_id or str(uuid.uuid4())
        self.sessions[session_id] = AgentSession(
            session_id=session_id,
            cwd=cwd,
            created_at=time.time(),
        )
        self.current_session = session_id
        logger.info(f"Session created: {session_id}, cwd={cwd}")
        return session_id

    def load_session(self, session_id: str) -> str:
        """加载已有会话，返回 session_id；不存在则抛 SessionNotFoundError"""
        if session_id not in self.sessions:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        self.current_session = session_id
        logger.info(f"Session loaded: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """获取会话对象"""
        return self.sessions.get(session_id)

    def get_current_session_id(self) -> str:
        """获取当前会话 ID"""
        return self.current_session or "default"

    def has_session(self) -> bool:
        """是否有活跃会话"""
        return self.current_session is not None

    # ===== Prompt 文本提取 =====

    @staticmethod
    def extract_prompt_text(prompt_content) -> str:
        """从 acpx 格式的 prompt 中提取纯文本"""
        if isinstance(prompt_content, list):
            text_parts = []
            for item in prompt_content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            return "".join(text_parts)
        return str(prompt_content)

    # ===== 人机协同：主线程侧 =====

    def is_waiting_for_human(self, session_id: str) -> bool:
        """主线程检查：会话是否正在等待人类输入"""
        session = self.sessions.get(session_id)
        return session is not None and session.is_waiting()

    def inject_answer(self, session_id: str, answer: str):
        """主线程注入人类回答，唤醒阻塞的 Agent 线程"""
        session = self.sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        session.inject_answer(answer)

    def drain_notifications(self, session_id: str) -> list[dict]:
        """主线程调用：排空会话通知队列，返回事件列表

        每个事件: {"type": str, "content": any, "extra": dict|None}
        """
        session = self.sessions.get(session_id)
        if session is None:
            return []
        events = []
        while not session.notification_queue.empty():
            try:
                events.append(session.notification_queue.get_nowait())
            except queue.Empty:
                break
        return events

    # ===== Agent 执行 =====

    def run_agent_with_human_loop(self, goal: str, session_id: str) -> dict:
        """在新线程中执行 Agent（由 run_in_executor 调用）。

        将 AgentSession 绑定到当前线程，使 ask_human 工具能找到它。
        每次新任务重置 help 状态，避免上一轮的 answer_ready 残留。
        """
        session = self.sessions.get(session_id)
        if session is None:
            return {"success": False, "message": f"Session not found: {session_id}"}

        session.reset_help_state()
        _thread_local.agent_session = session
        try:
            return self.run_agent(goal)
        finally:
            _thread_local.agent_session = None

    def run_agent(self, goal: str) -> dict:
        """同步执行 ReactAgent，返回 {"success": bool, "message": str}"""
        try:
            from agents.react_agent import ReactAgentLoop
            from config.settings import AGENT_MAX_STEPS, AGENT_HISTORY_WINDOW

            output_dir = "outputs/acp"
            os.makedirs(output_dir, exist_ok=True)

            agent = ReactAgentLoop(
                goal=goal,
                max_steps=AGENT_MAX_STEPS,
                history_window=AGENT_HISTORY_WINDOW,
                output_dir=output_dir,
            )
            logger.info(f"ReactAgent starting: goal={goal[:50]}...")
            result = agent.run()
            logger.info(f"ReactAgent completed: success={result.success}")

            return {
                "success": result.success,
                "message": result.final_message or "Task completed",
            }
        except Exception as e:
            import traceback
            logger.error(f"ReactAgent error: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "message": f"Error: {str(e)}",
            }
        finally:
            self.cleanup()

    # ===== 资源清理 =====

    def cleanup(self):
        """清理虚拟光标和 Executor 单例"""
        try:
            from core.virtual_cursor import get_virtual_cursor
            vc = get_virtual_cursor()
            vc.stop()
            vc.hide()
            logger.debug("Virtual cursor hidden")
        except Exception as e:
            logger.debug(f"Cleanup virtual cursor: {e}")

        try:
            from tools import _shared
            _shared._executor = None
            logger.debug("Executor singleton reset")
        except Exception as e:
            logger.debug(f"Cleanup executor: {e}")
