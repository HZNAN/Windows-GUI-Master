#!/usr/bin/env python3
"""
ACP Stdio 服务端 - 集成 ReactAgent
供 acpx CLI 通过 stdio 连接测试

使用方法:
  acpx feishu-test sessions new
  acpx feishu-test "你的任务"
"""
import asyncio
import concurrent.futures
import json
import sys
import io
from pathlib import Path

# 强制设置 UTF-8 编码（解决 Windows 中文编码问题）
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, ".")

# 加载 .env 文件（确保在导入 settings 前执行）
from dotenv import load_dotenv
_project_root = Path(__file__).parent.resolve()
load_dotenv(_project_root / ".env")

from core.acp.types import ACPMessage, ACPMethod, ACPErrorCode
from core.acp.protocol import ACPProtocol
from core.agent_service import ReactAgentService, SessionNotFoundError


class StdioHandler:
    """Stdio 传输适配器 — 薄层，将协议消息转交给 ReactAgentService

    支持双模式 prompt:
      - 新任务: 启动 Agent 线程，轮询直到完成或需要人类输入
      - 人类响应: 注入回答到等待中的会话，继续轮询
    """

    def __init__(self):
        self.service = ReactAgentService()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    async def handle_initialize(self, params: dict) -> dict:
        client_info = params.get("clientInfo", {})
        capabilities = params.get("capabilities", {})
        print(f"[STDIO] Client initializing: {client_info}", file=sys.stderr)
        print(f"[STDIO] Client capabilities: {capabilities}", file=sys.stderr)
        return {
            "protocolVersion": "1.0",
            "capabilities": {"execute": True, "confirm": True, "push": True},
            "serverInfo": {"name": "feishu-react-agent", "version": "1.0.0"},
        }

    async def handle_new_session(self, params: dict) -> dict:
        session_id = self.service.create_session(
            session_id=params.get("sessionId"),
            cwd=params.get("cwd", ""),
        )
        print(f"[STDIO] New session: {session_id}", file=sys.stderr)
        return {"sessionId": session_id}

    async def handle_load_session(self, params: dict) -> dict:
        session_id = params.get("sessionId")
        print(f"[STDIO] Load session: {session_id}", file=sys.stderr)
        try:
            self.service.load_session(session_id)
            return {"sessionId": session_id}
        except SessionNotFoundError as e:
            return {"error": str(e)}

    async def handle_prompt(self, params: dict) -> dict:
        prompt_text = ReactAgentService.extract_prompt_text(
            params.get("prompt", [])
        )
        session_id = self.service.get_current_session_id()
        print(f"[STDIO] Prompt: {prompt_text[:50]}...", file=sys.stderr)

        if self.service.is_waiting_for_human(session_id):
            print(f"[STDIO] Prompt is human response, injecting into session", file=sys.stderr)
            self.service.inject_answer(session_id, prompt_text)
        else:
            future = self._executor.submit(
                self.service.run_agent_with_human_loop, prompt_text, session_id
            )
            session = self.service.get_session(session_id)
            if session:
                session.agent_future = future

        return await self._poll_agent_until_done_or_needs_help(session_id)

    async def _poll_agent_until_done_or_needs_help(self, session_id: str) -> dict:
        """轮询：Agent 完成了 → 返回结果；需要人类 → 返回 needs_human

        轮询期间排空通知队列，直接输出 session/update 通知到 stdout。
        """
        session = self.service.get_session(session_id)
        if session is None:
            return {"sessionId": session_id, "stopReason": "failed",
                    "message": f"Session not found: {session_id}"}

        while True:
            # 排空通知队列 → 输出 session/update 到 stdout
            for event in self.service.drain_notifications(session_id):
                update = ACPProtocol.build_session_update(
                    session_id=session_id,
                    update_type=event["type"],
                    content=event.get("content", ""),
                    extra=event.get("extra"),
                )
                print(ACPProtocol.encode(update), flush=True)

            future = session.agent_future
            if future and future.done():
                try:
                    result = future.result()
                except Exception as e:
                    result = {"success": False, "message": str(e)}
                print(f"[STDIO] Agent done: {result}", file=sys.stderr)
                return {
                    "sessionId": session_id,
                    "stopReason": "completed" if result["success"] else "failed",
                    "message": result["message"],
                }
            if session.is_waiting():
                print(f"[STDIO] Agent needs human: {session.question}", file=sys.stderr)
                return {
                    "sessionId": session_id,
                    "stopReason": "needs_human",
                    "message": session.question or "[Human input needed]",
                }
            await asyncio.sleep(0.1)

    async def handle_execute(self, params: dict) -> dict:
        action = params.get("action", "")
        action_params = params.get("params", {})
        print(f"[STDIO] Execute: action={action}", file=sys.stderr)

        if action == "server.info":
            return {"name": "feishu-react-agent", "version": "1.0.0", "status": "running"}
        elif action == "echo":
            return {"echo": action_params}
        elif action == "add":
            return {"result": action_params.get("a", 0) + action_params.get("b", 0)}
        else:
            raise ValueError(f"Unknown action: {action}")


class StdioACPProcess:
    """Stdio 模式 ACP 服务进程 — 路由 ACP 方法到 StdioHandler"""

    VERSION = "1.0"

    def __init__(self):
        self.handler = StdioHandler()

    async def handle_message(self, raw: str) -> list:
        """处理接收到的消息，返回需要发送的消息列表"""
        try:
            msg = ACPProtocol.parse(raw)
        except Exception as e:
            print(f"[STDIO] Parse error: {e}", file=sys.stderr)
            error = ACPProtocol.build_error(None, ACPErrorCode.INVALID_PARAMS, str(e))
            return [ACPProtocol.encode(error)]

        msg_id = msg.id
        method = msg.method
        params = msg.params or {}

        print(f"[STDIO] Received: method={method}, id={msg_id}", file=sys.stderr)

        try:
            if method == ACPMethod.INITIALIZE.value:
                result = await self.handler.handle_initialize(params)
            elif method in (ACPMethod.NEW_SESSION.value, "session/new"):
                result = await self.handler.handle_new_session(params)
            elif method in (ACPMethod.LOAD_SESSION.value, "session/load"):
                result = await self.handler.handle_load_session(params)
            elif method in (ACPMethod.PROMPT.value, "session/prompt"):
                result = await self.handler.handle_prompt(params)
            elif method == ACPMethod.EXECUTE.value:
                result = await self.handler.handle_execute(params)
            elif method == ACPMethod.PING.value:
                result = {"pong": True}
            else:
                error = ACPProtocol.build_error(
                    msg_id, ACPErrorCode.INVALID_PARAMS, f"Unknown method: {method}"
                )
                return [ACPProtocol.encode(error)]

            response = ACPProtocol.build_response(msg_id, result=result)
            return [ACPProtocol.encode(response)]

        except SessionNotFoundError as e:
            error = ACPProtocol.build_error(msg_id, ACPErrorCode.INVALID_PARAMS, str(e))
            return [ACPProtocol.encode(error)]
        except Exception as e:
            print(f"[STDIO] Error handling {method}: {e}", file=sys.stderr)
            error = ACPProtocol.build_error(msg_id, ACPErrorCode.EXECUTION_FAILED, str(e))
            return [ACPProtocol.encode(error)]

    async def run(self):
        """运行 stdio 服务"""
        print("[STDIO] ReactAgent ACP Stdio Server started", file=sys.stderr, flush=True)
        print("[STDIO] Waiting for messages...", file=sys.stderr, flush=True)

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            print(f"[STDIO] Input: {line[:100]}", file=sys.stderr, flush=True)

            messages = await self.handle_message(line)
            for msg in messages:
                print(msg, flush=True)
                sys.stdout.flush()


def main():
    """主入口"""
    server = StdioACPProcess()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
