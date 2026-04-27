"""
ACP 消息编解码与验证
"""
import json
from typing import Any, Optional

from core.acp.types import (
    ACPMessage,
    ACPMethod,
    ACPErrorCode,
    ACPConfirmParams,
    ACPRequestParamParams,
    ACPAskHelpParams,
    ACPPushParams,
)


class ACPProtocolError(Exception):
    """协议错误"""

    def __init__(self, code: ACPErrorCode, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class ACPProtocol:
    """ACP 消息协议处理器"""

    VERSION = "2.0"

    @staticmethod
    def parse(raw: str | bytes) -> ACPMessage:
        """解析 JSON-RPC 2.0 消息"""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ACPProtocolError(
                ACPErrorCode.INVALID_PARAMS,
                f"Invalid JSON: {str(e)}",
            )

        if not isinstance(data, dict):
            raise ACPProtocolError(
                ACPErrorCode.INVALID_PARAMS,
                "Message must be a JSON object",
            )

        if data.get("jsonrpc") != ACPProtocol.VERSION:
            raise ACPProtocolError(
                ACPErrorCode.INVALID_PARAMS,
                f"Invalid JSON-RPC version: {data.get('jsonrpc')}",
            )

        msg = ACPMessage(
            jsonrpc=data.get("jsonrpc", ACPProtocol.VERSION),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error"),
        )

        return msg

    @staticmethod
    def build_request(
        method: str,
        params: Optional[dict] = None,
        msg_id: Optional[str] = None,
    ) -> ACPMessage:
        """构建请求消息"""
        return ACPMessage(
            jsonrpc=ACPProtocol.VERSION,
            id=msg_id,
            method=method,
            params=params or {},
        )

    @staticmethod
    def build_response(
        msg_id: Optional[str],
        result: Any = None,
        error: Optional[dict] = None,
    ) -> ACPMessage:
        """构建响应消息"""
        return ACPMessage(
            jsonrpc=ACPProtocol.VERSION,
            id=msg_id,
            result=result if error is None else None,
            error=error,
        )

    @staticmethod
    def build_error(
        msg_id: Optional[str],
        code: ACPErrorCode,
        message: str,
    ) -> ACPMessage:
        """构建错误消息"""
        return ACPMessage(
            jsonrpc=ACPProtocol.VERSION,
            id=msg_id,
            error={"code": int(code), "message": message},
        )

    @staticmethod
    def encode(msg: ACPMessage) -> str:
        """编码消息为 JSON 字符串"""
        return json.dumps(msg.to_dict(), ensure_ascii=False)

    @classmethod
    def build_confirm(
        cls,
        msg_id: str,
        confirm_type: str,
        message: str,
        context: Optional[dict] = None,
        timeout: int = 30,
    ) -> ACPMessage:
        """构建确认请求"""
        return cls.build_request(
            method=ACPMethod.CONFIRM.value,
            params={
                "type": confirm_type,
                "message": message,
                "context": context or {},
                "timeout": timeout,
            },
            msg_id=msg_id,
        )

    @classmethod
    def build_request_param(
        cls,
        msg_id: str,
        missing_params: list,
        current_state: Optional[dict] = None,
    ) -> ACPMessage:
        """构建参数补全请求"""
        return cls.build_request(
            method=ACPMethod.REQUEST_PARAM.value,
            params={
                "missing_params": missing_params,
                "current_state": current_state or {},
            },
            msg_id=msg_id,
        )

    @classmethod
    def build_ask_help(
        cls,
        msg_id: str,
        error: dict,
        context: Optional[dict] = None,
        suggestions: Optional[list] = None,
    ) -> ACPMessage:
        """构建异常求助请求"""
        return cls.build_request(
            method=ACPMethod.ASK_HELP.value,
            params={
                "error": error,
                "context": context or {},
                "suggestions": suggestions or [],
            },
            msg_id=msg_id,
        )

    @classmethod
    def build_push(
        cls,
        push_type: str,
        data: dict,
        msg_id: Optional[str] = None,
    ) -> ACPMessage:
        """构建主动推送"""
        return cls.build_request(
            method=ACPMethod.PUSH.value,
            params={"type": push_type, "data": data},
            msg_id=msg_id,
        )

    @classmethod
    def build_execute(
        cls,
        action: str,
        params: Optional[dict] = None,
        msg_id: Optional[str] = None,
    ) -> ACPMessage:
        """构建执行指令 (Client -> Server)"""
        return cls.build_request(
            method=ACPMethod.EXECUTE.value,
            params={"action": action, "params": params or {}},
            msg_id=msg_id,
        )

    @classmethod
    def build_agent_response(
        cls,
        request_id: str,
        result: dict,
    ) -> ACPMessage:
        """构建 agent.response 响应 (Client -> Server)"""
        return cls.build_request(
            method=ACPMethod.RESPONSE.value,
            params={"request_id": request_id, "result": result},
            msg_id=request_id,
        )

    # Alias for backwards compatibility
    build_response_for_agent = build_agent_response

    # ===== Standard ACP Method Builders =====

    @classmethod
    def build_initialize(
        cls,
        protocol_version: str,
        capabilities: dict,
        client_info: dict,
        msg_id: str,
    ) -> ACPMessage:
        """构建 initialize 请求 (Client -> Server)"""
        return cls.build_request(
            method=ACPMethod.INITIALIZE.value,
            params={
                "protocolVersion": protocol_version,
                "capabilities": capabilities,
                "clientInfo": client_info,
            },
            msg_id=msg_id,
        )

    @classmethod
    def build_initialize_response(
        cls,
        msg_id: str,
        protocol_version: str,
        capabilities: dict,
        server_info: dict,
    ) -> ACPMessage:
        """构建 initialize 响应 (Server -> Client)"""
        return cls.build_response(
            msg_id=msg_id,
            result={
                "protocolVersion": protocol_version,
                "capabilities": capabilities,
                "serverInfo": server_info,
            },
        )

    @classmethod
    def build_new_session(
        cls,
        session_id: Optional[str] = None,
        cwd: str = "",
        msg_id: Optional[str] = None,
    ) -> ACPMessage:
        """构建 newSession 请求 (Client -> Server)"""
        params = {}
        if session_id:
            params["sessionId"] = session_id
        if cwd:
            params["cwd"] = cwd
        return cls.build_request(
            method=ACPMethod.NEW_SESSION.value,
            params=params if params else None,
            msg_id=msg_id,
        )

    @classmethod
    def build_new_session_response(
        cls,
        msg_id: str,
        session_id: str,
    ) -> ACPMessage:
        """构建 newSession 响应 (Server -> Client)"""
        return cls.build_response(
            msg_id=msg_id,
            result={"sessionId": session_id},
        )

    @classmethod
    def build_load_session(
        cls,
        session_id: str,
        msg_id: Optional[str] = None,
    ) -> ACPMessage:
        """构建 loadSession 请求 (Client -> Server)"""
        return cls.build_request(
            method=ACPMethod.LOAD_SESSION.value,
            params={"sessionId": session_id},
            msg_id=msg_id,
        )

    @classmethod
    def build_prompt(
        cls,
        prompt: str,
        system_prompt: Optional[str] = None,
        msg_id: Optional[str] = None,
    ) -> ACPMessage:
        """构建 prompt 请求 (Client -> Server)"""
        params = {"prompt": prompt}
        if system_prompt:
            params["systemPrompt"] = system_prompt
        return cls.build_request(
            method=ACPMethod.PROMPT.value,
            params=params,
            msg_id=msg_id,
        )

    @classmethod
    def build_prompt_response(
        cls,
        msg_id: str,
        session_id: str,
        stop_reason: str,
        message: Any,
    ) -> ACPMessage:
        """构建 prompt 响应 (Server -> Client)"""
        return cls.build_response(
            msg_id=msg_id,
            result={
                "sessionId": session_id,
                "stopReason": stop_reason,
                "message": message,
            },
        )

    @classmethod
    def build_session_update(
        cls,
        session_id: str,
        update_type: str,
        content: Any,
    ) -> ACPMessage:
        """构建 sessionUpdate 通知 (Server -> Client, 无需响应)"""
        return ACPMessage(
            jsonrpc=ACPProtocol.VERSION,
            method=ACPMethod.SESSION_UPDATE.value,
            params={
                "sessionId": session_id,
                "update": {
                    "type": update_type,
                    "content": content,
                },
            },
        )
