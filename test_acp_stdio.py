#!/usr/bin/env python3
"""
ACP Stdio 服务端 - 集成 ReactAgent
供 acpx CLI 通过 stdio 连接测试

使用方法:
  acpx feishu-test sessions new
  acpx feishu-test "你的任务"
"""
import asyncio
import json
import sys
import io
import uuid
import time
from pathlib import Path
from typing import Optional

# 强制设置 UTF-8 编码（解决 Windows 中文编码问题）
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, ".")

# 加载 .env 文件（确保在导入 settings 前执行）
from dotenv import load_dotenv
# 查找项目根目录的 .env 文件
_project_root = Path(__file__).parent.resolve()
load_dotenv(_project_root / ".env")

from core.acp.types import ACPMessage, ACPMethod, ACPErrorCode
from core.acp.protocol import ACPProtocol


class ReactAgentHandler:
    """ReactAgent 处理器"""

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
            "serverInfo": {"name": "feishu-react-agent", "version": "1.0.0"},
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
        """处理 prompt - 调用 ReactAgent"""
        prompt_content = params.get("prompt", [])
        session_id = self.current_session or "default"

        # 提取文本内容
        if isinstance(prompt_content, list):
            text_parts = []
            for item in prompt_content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            prompt_text = "".join(text_parts)
        else:
            prompt_text = str(prompt_content)

        print(f"[STDIO] Prompt: {prompt_text[:50]}...", file=sys.stderr)

        # 在线程池中运行 ReactAgent
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._run_react_agent,
            prompt_text
        )

        print(f"[STDIO] ReactAgent result: {result}", file=sys.stderr)
        return {
            "sessionId": session_id,
            "stopReason": "completed" if result.get("success") else "failed",
            "message": result.get("message", ""),
        }

    def _run_react_agent(self, goal: str) -> dict:
        """在新线程中运行 ReactAgent"""
        try:
            from agents.react_agent import ReactAgentLoop
            import os
            from config.settings import AGENT_MAX_STEPS, AGENT_HISTORY_WINDOW

            print(f"[STDIO] _run_react_agent: starting, goal={goal[:30]}...", file=sys.stderr)

            # 确保输出目录存在
            output_dir = "outputs/stdio"
            os.makedirs(output_dir, exist_ok=True)

            agent = ReactAgentLoop(
                goal=goal,
                max_steps=AGENT_MAX_STEPS,
                history_window=AGENT_HISTORY_WINDOW,
                output_dir=output_dir
            )
            print(f"[STDIO] _run_react_agent: ReactAgentLoop created, calling run()...", file=sys.stderr)
            result = agent.run()
            print(f"[STDIO] _run_react_agent: run() completed, success={result.success}", file=sys.stderr)

            # 清理资源
            self._cleanup()

            return {
                "success": result.success,
                "message": result.final_message or "Task completed"
            }
        except Exception as e:
            import traceback
            print(f"[STDIO] ReactAgent error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            # 即使出错也要清理
            self._cleanup()
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    def _cleanup(self):
        """清理资源 - 隐藏虚拟光标并重置单例，复用窗口实例避免 WndProc 绑定问题"""
        try:
            from core.virtual_cursor import get_virtual_cursor
            vc = get_virtual_cursor()
            vc.stop()  # 停止可能正在进行的动画
            vc.hide()  # 隐藏虚拟光标（不销毁窗口，避免 WndProc 丢失）
            print(f"[STDIO] Virtual cursor hidden", file=sys.stderr)
        except Exception as e:
            print(f"[STDIO] Cleanup virtual cursor error: {e}", file=sys.stderr)

        # 重置 Executor 单例
        try:
            from tools import _shared
            _shared._executor = None
            print(f"[STDIO] Executor reset", file=sys.stderr)
        except Exception as e:
            print(f"[STDIO] Cleanup executor error: {e}", file=sys.stderr)

    async def handle_execute(self, msg_id: str, params: dict) -> dict:
        """处理 agent.execute"""
        action = params.get("action", "")
        action_params = params.get("params", {})
        print(f"[STDIO] Execute: action={action}", file=sys.stderr)

        if action == "server.info":
            return {
                "name": "feishu-react-agent",
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
        self.handler = ReactAgentHandler()
        self._running = True

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
                result = await self.handler.handle_initialize(msg_id, params)
                response = ACPProtocol.build_response(msg_id, result=result)
                return [ACPProtocol.encode(response)]

            elif method in (ACPMethod.NEW_SESSION.value, "session/new"):
                result = await self.handler.handle_new_session(msg_id, params)
                response = ACPProtocol.build_response(msg_id, result=result)
                return [ACPProtocol.encode(response)]

            elif method in (ACPMethod.LOAD_SESSION.value, "session/load"):
                result = await self.handler.handle_load_session(msg_id, params)
                response = ACPProtocol.build_response(msg_id, result=result)
                return [ACPProtocol.encode(response)]

            elif method in (ACPMethod.PROMPT.value, "session/prompt"):
                result = await self.handler.handle_prompt(msg_id, params)
                response = ACPProtocol.build_response(msg_id, result=result)
                return [ACPProtocol.encode(response)]

            elif method == ACPMethod.EXECUTE.value:
                action = params.get("action", "")
                action_params = params.get("params", {})
                result = await self.handler.handle_execute(msg_id, {"action": action, "params": action_params})
                response = ACPProtocol.build_response(msg_id, result=result)
                return [ACPProtocol.encode(response)]

            elif method == ACPMethod.PING.value:
                response = ACPProtocol.build_response(msg_id, result={"pong": True})
                return [ACPProtocol.encode(response)]

            else:
                error = ACPProtocol.build_error(
                    msg_id, ACPErrorCode.INVALID_PARAMS, f"Unknown method: {method}"
                )
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
