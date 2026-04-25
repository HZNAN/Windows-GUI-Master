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
    def build_response(
        cls,
        request_id: str,
        result: dict,
    ) -> ACPMessage:
        """构建响应 (Client -> Server)"""
        return cls.build_request(
            method=ACPMethod.RESPONSE.value,
            params={"request_id": request_id, "result": result},
            msg_id=request_id,
        )
