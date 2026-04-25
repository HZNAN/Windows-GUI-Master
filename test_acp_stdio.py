#!/usr/bin/env python3
"""
ACP 协议测试服务端 (Stdio 版本)
供 acpx CLI 通过 stdio 连接测试

使用方法:
  python test_acp_stdio.py

acpx 会通过 stdin/stdout 与此进程通信
"""
import asyncio
import json
import sys
import uuid
import time
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, ".")

from core.acp.types import ACPMessage, ACPMethod, ACPErrorCode
from core.acp.protocol import ACPProtocol


class StdioACPHandler:
    """Stdio 模式下的 ACP 处理器"""

    def __init__(self):
        self.sessions = {}
        self.current_session = None

    async def handle_initialize(self, msg_id: str, params: dict) -> dict:
        """处理 initialize"""
        client_info = params.get("clientInfo", {})
        capabilities = params.get("capabilities", {})
        print(f"[STDIO] Client initializing: {client_info}", file=sys.stderr)
        print(f"[STDIO] Client capabilities: {capabilities}", file=sys.stderr)
        return {
            "protocolVersion": "1.0",
            "capabilities": {
                "execute": True,
                "confirm": True,
                "push": True,
            },
            "serverInfo": {"name": "feishu-agent-stdio", "version": "1.0.0"},
        }

    async def handle_new_session(self, msg_id: str, params: dict) -> dict:
        """处理 newSession"""
        session_id = params.get("sessionId") or str(uuid.uuid4())
        cwd = params.get("cwd", "")
        print(f"[STDIO] New session: {session_id}, cwd: {cwd}", file=sys.stderr)
        self.sessions[session_id] = {
            "session_id": session_id,
            "cwd": cwd,
            "created_at": time.time(),
        }
        self.current_session = session_id
        return {"sessionId": session_id}

    async def handle_load_session(self, msg_id: str, params: dict) -> dict:
        """处理 loadSession"""
        session_id = params.get("sessionId")
        print(f"[STDIO] Load session: {session_id}", file=sys.stderr)
        if session_id in self.sessions:
            self.current_session = session_id
            return {"sessionId": session_id}
        return {"error": f"Session not found: {session_id}"}

    async def handle_prompt(self, msg_id: str, params: dict) -> dict:
        """处理 prompt"""
        prompt_text = params.get("prompt", "")
        system_prompt = params.get("systemPrompt")
        session_id = self.current_session or "default"
        print(f"[STDIO] Prompt: {prompt_text[:50]}...", file=sys.stderr)

        # 模拟处理
        response = f"Echo: {prompt_text}"
        return {
            "sessionId": session_id,
            "stopReason": "completed",
            "message": response,
        }

    async def handle_execute(self, msg_id: str, params: dict) -> dict:
        """处理 agent.execute"""
        action = params.get("action", "")
        action_params = params.get("params", {})
        print(f"[STDIO] Execute: action={action}", file=sys.stderr)

        if action == "server.info":
            return {
                "name": "feishu-agent-stdio",
                "version": "1.0.0",
                "status": "running",
            }
        elif action == "echo":
            return {"echo": action_params}
        elif action == "add":
            a = action_params.get("a", 0)
            b = action_params.get("b", 0)
            return {"result": a + b}
        else:
            raise ValueError(f"Unknown action: {action}")


class StdioACPProcess:
    """Stdio 模式 ACP 服务进程"""

    VERSION = "1.0"

    def __init__(self):
        self.handler = StdioACPHandler()
        self._running = True

    async def handle_message(self, raw: str) -> Optional[str]:
        """处理接收到的消息"""
        try:
            msg = ACPProtocol.parse(raw)
        except Exception as e:
            print(f"[STDIO] Parse error: {e}", file=sys.stderr)
            error = ACPProtocol.build_error(None, ACPErrorCode.INVALID_PARAMS, str(e))
            return ACPProtocol.encode(error)

        msg_id = msg.id
        method = msg.method
        params = msg.params or {}

        print(f"[STDIO] Received: method={method}, id={msg_id}", file=sys.stderr)

        try:
            if method == ACPMethod.INITIALIZE.value:
                result = await self.handler.handle_initialize(msg_id, params)
                response = ACPProtocol.build_response(msg_id, result=result)

            elif method == ACPMethod.NEW_SESSION.value:
                result = await self.handler.handle_new_session(msg_id, params)
                response = ACPProtocol.build_response(msg_id, result=result)

            elif method == ACPMethod.LOAD_SESSION.value:
                result = await self.handler.handle_load_session(msg_id, params)
                response = ACPProtocol.build_response(msg_id, result=result)

            elif method == ACPMethod.PROMPT.value:
                result = await self.handler.handle_prompt(msg_id, params)
                response = ACPProtocol.build_response(msg_id, result=result)

            elif method == ACPMethod.EXECUTE.value:
                action = params.get("action", "")
                action_params = params.get("params", {})
                result = await self.handler.handle_execute(msg_id, {"action": action, "params": action_params})
                response = ACPProtocol.build_response(msg_id, result=result)

            elif method == ACPMethod.PING.value:
                response = ACPProtocol.build_response(msg_id, result={"pong": True})

            else:
                error = ACPProtocol.build_error(
                    msg_id, ACPErrorCode.INVALID_PARAMS, f"Unknown method: {method}"
                )
                return ACPProtocol.encode(error)

            return ACPProtocol.encode(response)

        except Exception as e:
            print(f"[STDIO] Error handling {method}: {e}", file=sys.stderr)
            error = ACPProtocol.build_error(msg_id, ACPErrorCode.EXECUTION_FAILED, str(e))
            return ACPProtocol.encode(error)

    async def run(self):
        """运行 stdio 服务"""
        print("[STDIO] ACP Stdio Server started", file=sys.stderr)
        print("[STDIO] Waiting for messages...", file=sys.stderr)

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            print(f"[STDIO] Input: {line[:100]}", file=sys.stderr)

            response = await self.handle_message(line)
            if response:
                print(response)
                sys.stdout.flush()


def main():
    """主入口"""
    server = StdioACPProcess()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
