"""
ACP 数据类型定义
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ACPMethod(str, Enum):
    """ACP 方法名枚举"""

    # Server -> Client
    CONFIRM = "agent.confirm"
    REQUEST_PARAM = "agent.request_param"
    ASK_HELP = "agent.ask_help"
    PUSH = "agent.push"

    # Client -> Server
    EXECUTE = "agent.execute"
    RESPONSE = "agent.response"
    CANCEL = "agent.cancel"
    PING = "agent.ping"


class ACPPushType(str, Enum):
    """Server -> Client 推送类型"""

    SCREENSHOT = "screenshot"
    STATUS = "status"
    PROGRESS = "progress"
    LOG = "log"


class ACPErrorCode(int, Enum):
    """ACP 错误码"""

    GENERAL = -32000
    UNAUTHORIZED = -32001
    TIMEOUT = -32002
    INVALID_PARAMS = -32003
    EXECUTION_FAILED = -32004


class ACPConfirmType(str, Enum):
    """确认类型"""

    CONFIRM = "confirm"
    WARN = "warn"
    DANGER = "danger"


@dataclass
class ACPMessage:
    """ACP 消息"""

    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: Optional[str] = None
    params: Optional[dict] = None
    result: Optional[Any] = None
    error: Optional[dict] = None

    def is_request(self) -> bool:
        return self.method is not None and self.error is None

    def is_response(self) -> bool:
        return self.result is not None or self.error is not None

    def is_notification(self) -> bool:
        return self.id is None and self.method is not None

    def to_dict(self) -> dict:
        msg = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            msg["id"] = self.id
        if self.method is not None:
            msg["method"] = self.method
        if self.params is not None:
            msg["params"] = self.params
        if self.result is not None:
            msg["result"] = self.result
        if self.error is not None:
            msg["error"] = self.error
        return msg


@dataclass
class ACPConfirmParams:
    """agent.confirm 参数"""

    type: str  # confirm | warn | danger
    message: str
    context: dict = field(default_factory=dict)
    timeout: int = 30


@dataclass
class ACPRequestParamParams:
    """agent.request_param 参数"""

    missing_params: list
    current_state: dict = field(default_factory=dict)


@dataclass
class ACPAskHelpParams:
    """agent.ask_help 参数"""

    error: dict
    context: dict = field(default_factory=dict)
    suggestions: list = field(default_factory=list)


@dataclass
class ACPPushParams:
    """agent.push 参数"""

    type: str  # screenshot | status | progress | log
    data: dict
