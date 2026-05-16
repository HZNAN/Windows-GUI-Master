"""
ReactAgent ACP 集成测试
最小实现: acpx 发送任务 -> ReactAgent 处理 -> 返回结果

使用方式:
  1. python test_react_agent_acp.py  (启动 ACP 服务端)
  2. acpx gui-master "你的任务"
"""
import asyncio
import concurrent.futures
import sys
sys.path.insert(0, ".")

from loguru import logger

from core.acp.server import ACPServer, ACPHandler
from core.acp.types import ACPMessage, ACPErrorCode
from core.acp.protocol import ACPProtocol
from core.agent_service import ReactAgentService, SessionNotFoundError


class ReactAgentHandler(ACPHandler):
    """WebSocket ACP Handler — 薄层，将 ACPHandler 回调转交给 ReactAgentService

    支持双模式 prompt:
      - 新任务: 启动 Agent 线程，轮询直到完成或需要人类输入
      - 人类响应: 注入回答到等待中的会话，继续轮询
    """

    def __init__(self):
        self.service = ReactAgentService()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._ws = None  # 由 ACPServer._handle_prompt 临时设置，用于发送 session/update 通知

    async def on_initialize(self, client_info: dict, capabilities: dict) -> dict:
        logger.info(f"Client initializing: {client_info}, capabilities: {capabilities}")
        return {"name": "window-gui-master", "version": "1.0.0"}

    async def on_new_session(self, session_id: str | None, cwd: str) -> dict:
        session_id = self.service.create_session(session_id=session_id, cwd=cwd)
        return {"sessionId": session_id}

    async def on_load_session(self, session_id: str) -> dict:
        try:
            self.service.load_session(session_id)
            return {"sessionId": session_id}
        except SessionNotFoundError as e:
            return {"error": str(e)}

    async def on_prompt(self, session_id: str, prompt: str, system_prompt: str | None) -> dict:
        logger.info(f"Prompt received: {prompt[:50]}...")

        if self.service.is_waiting_for_human(session_id):
            logger.info("Prompt is human response, injecting into session")
            self.service.inject_answer(session_id, prompt)
        else:
            future = self._executor.submit(
                self.service.run_agent_with_human_loop, prompt, session_id
            )
            session = self.service.get_session(session_id)
            if session:
                session.agent_future = future

        return await self._poll_agent_until_done_or_needs_help(session_id)

    async def _poll_agent_until_done_or_needs_help(self, session_id: str) -> dict:
        """轮询：Agent 完成了 → 返回结果；需要人类 → 返回 needs_human

        轮询期间排空通知队列，通过 WebSocket 发送 session/update 通知。
        """
        session = self.service.get_session(session_id)
        if session is None:
            return {"sessionId": session_id, "stopReason": "failed",
                    "message": f"Session not found: {session_id}"}

        ws = getattr(self, '_ws', None)

        while True:
            # 排空通知队列 → 发送 session/update 到 WebSocket
            if ws:
                for event in self.service.drain_notifications(session_id):
                    update = ACPProtocol.build_session_update(
                        session_id=session_id,
                        update_type=event["type"],
                        content=event.get("content", ""),
                        extra=event.get("extra"),
                    )
                    await ws.send(ACPProtocol.encode(update))

            future = session.agent_future
            if future and future.done():
                try:
                    result = future.result()
                except Exception as e:
                    result = {"success": False, "message": str(e)}
                logger.info(f"Agent done: {result}")
                return {
                    "sessionId": session_id,
                    "stopReason": "completed" if result["success"] else "failed",
                    "message": result["message"],
                }
            if session.is_waiting():
                logger.info(f"Agent needs human: {session.question}")
                return {
                    "sessionId": session_id,
                    "stopReason": "needs_human",
                    "message": session.question or "[Human input needed]",
                }
            await asyncio.sleep(0.1)

    async def on_execute(self, action: str, params: dict) -> dict:
        logger.info(f"Execute: action={action}, params={params}")

        if action == "server.info":
            return {"name": "window-gui-master", "version": "1.0.0", "status": "running"}
        elif action == "echo":
            return {"echo": params}
        elif action == "add":
            return {"result": params.get("a", 0) + params.get("b", 0)}
        else:
            raise ValueError(f"Unknown action: {action}")


async def main():
    """启动 ACP 服务"""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    host = os.getenv("ACP_HOST", "localhost")
    port = int(os.getenv("ACP_PORT", "8765"))
    token = os.getenv("ACP_TOKEN", "")

    logger.info(f"Starting ReactAgent ACP server: {host}:{port}")
    logger.info(f"Token: {'configured' if token else 'not configured'}")

    handler = ReactAgentHandler()
    server = ACPServer(host=host, port=port, token=token or None, handler=handler)

    try:
        await server.start()
        logger.info("Server started. Press Ctrl+C to stop.")

        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await server.stop()
        logger.info("Server stopped.")


if __name__ == "__main__":
    asyncio.run(main())
