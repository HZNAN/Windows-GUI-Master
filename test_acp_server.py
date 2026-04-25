"""
ACP 协议测试服务端
启动一个简单的 ACP Server 用于测试
"""
import asyncio
import sys

sys.path.insert(0, ".")

from core.acp.server import ACPServer, ACPHandler
from core.acp.types import ACPMethod, ACPErrorCode
from loguru import logger


class TestHandler(ACPHandler):
    """测试用 ACP 处理器"""

    async def on_initialize(self, client_info: dict, capabilities: dict) -> dict:
        """处理 initialize"""
        logger.info(f"Client initializing: {client_info}, capabilities: {capabilities}")
        return {
            "name": "feishu-agent-test",
            "version": "1.0.0",
        }

    async def on_new_session(self, session_id: str | None, cwd: str) -> dict:
        """处理 newSession"""
        import uuid
        session_id = session_id or str(uuid.uuid4())
        logger.info(f"New session: {session_id}, cwd: {cwd}")
        return {"sessionId": session_id}

    async def on_load_session(self, session_id: str) -> dict:
        """处理 loadSession"""
        logger.info(f"Load session: {session_id}")
        return {"sessionId": session_id}

    async def on_prompt(self, session_id: str, prompt: str, system_prompt: str | None) -> dict:
        """处理 prompt"""
        logger.info(f"Prompt received: {prompt[:50]}...")
        return {
            "sessionId": session_id,
            "stopReason": "completed",
            "message": f"Echo: {prompt}",
        }

    async def on_execute(self, action: str, params: dict) -> dict:
        """处理 agent.execute"""
        logger.info(f"收到执行指令: action={action}, params={params}")

        if action == "server.info":
            return {
                "name": "ACP Test Server",
                "version": "1.0.0",
                "status": "running",
            }
        elif action == "echo":
            return {"echo": params}
        elif action == "add":
            a = params.get("a", 0)
            b = params.get("b", 0)
            return {"result": a + b}
        else:
            raise ValueError(f"Unknown action: {action}")


async def main():
    """启动测试服务器"""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    host = os.getenv("ACP_HOST", "localhost")
    port = int(os.getenv("ACP_PORT", "8765"))
    token = os.getenv("ACP_TOKEN", "")

    logger.info(f"启动 ACP 测试服务器: {host}:{port}")
    logger.info(f"Token: {'已配置' if token else '未配置'}")

    handler = TestHandler()
    server = ACPServer(host=host, port=port, token=token or None, handler=handler)

    try:
        await server.start()
        logger.info("服务器已启动，按 Ctrl+C 停止")

        # 保持运行
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到停止信号")
    finally:
        await server.stop()
        logger.info("服务器已停止")


if __name__ == "__main__":
    asyncio.run(main())
