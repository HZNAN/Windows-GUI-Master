"""
ACP WebSocket 服务端
"""
import asyncio
import uuid
from typing import Callable, Optional
from dataclasses import dataclass, field

import websockets
from websockets.server import WebSocketServerProtocol
from loguru import logger

from core.acp.types import ACPMessage, ACPMethod, ACPErrorCode
from core.acp.protocol import ACPProtocol, ACPProtocolError
from core.acp.auth import ACPAuth


@dataclass
class PendingRequest:
    """待处理的请求（等待 Client 响应）"""

    msg: ACPMessage
    event: asyncio.Event
    result: Optional[dict] = None
    timeout: float = 30.0


class ACPHandler:
    """ACP 消息处理器基类"""

    async def on_execute(self, action: str, params: dict) -> dict:
        """处理 agent.execute (Client -> Server)"""
        raise NotImplementedError

    async def on_push(self, push_type: str, data: dict):
        """处理主动推送"""
        pass


class ACPServer:
    """ACP WebSocket 服务端"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        token: Optional[str] = None,
        handler: Optional[ACPHandler] = None,
    ):
        self.host = host
        self.port = port
        self.auth = ACPAuth(token=token)
        self.handler = handler or ACPHandler()
        self._pending_requests: dict[str, PendingRequest] = {}
        self._server = None
        self._running = False

    async def start(self):
        """启动 WebSocket 服务"""
        self._running = True
        self._server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port,
            process_request=self._authenticate,
        )
        logger.info(f"ACP server started on {self.host}:{self.port}")

    async def stop(self):
        """停止 WebSocket 服务"""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("ACP server stopped")

    async def _authenticate(self, request_path, headers):
        """WebSocket 握手时的认证"""
        if not self.auth.is_enabled:
            return None

        auth_header = headers.get("Authorization") or headers.get("authorization")
        if not self.auth.validate_request(auth_header):
            return websockets.http.StatusLine(401, "Unauthorized", " ACP")

    async def _handle_client(self, ws: WebSocketServerProtocol, path: str):
        """处理客户端连接"""
        client_id = str(uuid.uuid4())[:8]
        logger.info(f"Client connected: {client_id}")

        try:
            async for raw_message in ws:
                await self._process_message(ws, raw_message, client_id)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Client error {client_id}: {e}")
        finally:
            self._cleanup_client(client_id)

    async def _process_message(
        self, ws: WebSocketServerProtocol, raw: str | bytes, client_id: str
    ):
        """处理接收到的消息"""
        try:
            msg = ACPProtocol.parse(raw)
        except ACPProtocolError as e:
            error = ACPProtocol.build_error(None, e.code, e.message)
            await ws.send(ACPProtocol.encode(error))
            return

        if msg.method == ACPMethod.EXECUTE.value:
            await self._handle_execute(ws, msg)
        elif msg.method == ACPMethod.RESPONSE.value:
            await self._handle_response(ws, msg)
        elif msg.method == ACPMethod.CANCEL.value:
            await self._handle_cancel(ws, msg)
        elif msg.method == ACPMethod.PING.value:
            await self._handle_ping(ws, msg)
        else:
            error = ACPProtocol.build_error(
                msg.id, ACPErrorCode.INVALID_PARAMS, f"Unknown method: {msg.method}"
            )
            await ws.send(ACPProtocol.encode(error))

    async def _handle_execute(self, ws: WebSocketServerProtocol, msg: ACPMessage):
        """处理 agent.execute"""
        try:
            action = msg.params.get("action") if msg.params else None
            params = msg.params.get("params", {}) if msg.params else {}

            if not action:
                error = ACPProtocol.build_error(
                    msg.id,
                    ACPErrorCode.INVALID_PARAMS,
                    "Missing 'action' in params",
                )
                await ws.send(ACPProtocol.encode(error))
                return

            result = await self.handler.on_execute(action, params)
            response = ACPProtocol.build_response(msg.id, result=result)
            await ws.send(ACPProtocol.encode(response))

        except Exception as e:
            error = ACPProtocol.build_error(
                msg.id, ACPErrorCode.EXECUTION_FAILED, str(e)
            )
            await ws.send(ACPProtocol.encode(error))

    async def _handle_response(self, ws: WebSocketServerProtocol, msg: ACPMessage):
        """处理 agent.response (Client 对 Server 请求的响应)"""
        request_id = msg.params.get("request_id") if msg.params else None
        result = msg.params.get("result", {}) if msg.params else {}

        if request_id and request_id in self._pending_requests:
            pending = self._pending_requests.pop(request_id)
            pending.result = result
            pending.event.set()
        else:
            logger.warning(f"Response for unknown or expired request: {request_id}")

    async def _handle_cancel(self, ws: WebSocketServerProtocol, msg: ACPMessage):
        """处理 agent.cancel"""
        request_id = msg.params.get("request_id") if msg.params else None

        if request_id and request_id in self._pending_requests:
            pending = self._pending_requests.pop(request_id)
            pending.result = {"cancelled": True}
            pending.event.set()
            logger.info(f"Request {request_id} cancelled")
        else:
            logger.warning(f"Cancel for unknown request: {request_id}")

    async def _handle_ping(self, ws: WebSocketServerProtocol, msg: ACPMessage):
        """处理 agent.ping"""
        response = ACPProtocol.build_response(msg.id, result={"pong": True})
        await ws.send(ACPProtocol.encode(response))

    def _cleanup_client(self, client_id: str):
        """清理客户端相关的待处理请求"""
        expired = [
            rid for rid, req in self._pending_requests.items()
            if req.msg.id == client_id
        ]
        for rid in expired:
            self._pending_requests.pop(rid, None)

    async def send_confirm(
        self,
        websocket,
        confirm_type: str,
        message: str,
        context: Optional[dict] = None,
        timeout: float = 30.0,
    ) -> dict:
        """发送确认请求并等待响应"""
        msg_id = str(uuid.uuid4())
        msg = ACPProtocol.build_confirm(
            msg_id=msg_id,
            confirm_type=confirm_type,
            message=message,
            context=context,
            timeout=int(timeout),
        )

        pending = PendingRequest(msg=msg, event=asyncio.Event(), timeout=timeout)
        self._pending_requests[msg_id] = pending

        await websocket.send(ACPProtocol.encode(msg))

        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(msg_id, None)
            return {"approved": False, "reason": "timeout"}

        return pending.result or {"approved": False}

    async def send_request_param(
        self,
        websocket,
        missing_params: list,
        current_state: Optional[dict] = None,
        timeout: float = 30.0,
    ) -> dict:
        """发送参数补全请求并等待响应"""
        msg_id = str(uuid.uuid4())
        msg = ACPProtocol.build_request_param(
            msg_id=msg_id,
            missing_params=missing_params,
            current_state=current_state,
        )

        pending = PendingRequest(msg=msg, event=asyncio.Event(), timeout=timeout)
        self._pending_requests[msg_id] = pending

        await websocket.send(ACPProtocol.encode(msg))

        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(msg_id, None)
            return {"params": None, "reason": "timeout"}

        return pending.result or {"params": None}

    async def send_ask_help(
        self,
        websocket,
        error: dict,
        context: Optional[dict] = None,
        suggestions: Optional[list] = None,
        timeout: float = 60.0,
    ) -> dict:
        """发送异常求助请求并等待响应"""
        msg_id = str(uuid.uuid4())
        msg = ACPProtocol.build_ask_help(
            msg_id=msg_id,
            error=error,
            context=context,
            suggestions=suggestions,
        )

        pending = PendingRequest(msg=msg, event=asyncio.Event(), timeout=timeout)
        self._pending_requests[msg_id] = pending

        await websocket.send(ACPProtocol.encode(msg))

        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(msg_id, None)
            return {"helped": False, "reason": "timeout"}

        return pending.result or {"helped": False}

    async def push(self, websocket, push_type: str, data: dict):
        """发送主动推送（无需响应）"""
        msg = ACPProtocol.build_push(push_type=push_type, data=data)
        await websocket.send(ACPProtocol.encode(msg))

