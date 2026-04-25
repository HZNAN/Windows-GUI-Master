"""
ACP 数据类型定义
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ACPMethod(str, Enum):
    """ACP 方法名枚举"""

    # ===== Standard ACP (Zed Industries) =====
    INITIALIZE = "initialize"
    NEW_SESSION = "newSession"
    LOAD_SESSION = "loadSession"
    PROMPT = "prompt"
    SESSION_UPDATE = "sessionUpdate"

    # ===== Extended Methods (我们的扩展) =====
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


# ===== Standard ACP Types =====


@dataclass
class ACPCapabilities:
    """客户端/服务端能力"""

    execute: bool = False
    confirm: bool = False
    push: bool = False
    fs_read_text_file: bool = False
    fs_write_text_file: bool = False
    terminal: bool = False

    def to_dict(self) -> dict:
        caps = {}
        if self.execute:
            caps["execute"] = True
        if self.confirm:
            caps["confirm"] = True
        if self.push:
            caps["push"] = True
        if self.fs_read_text_file or self.fs_write_text_file:
            caps["fs"] = {}
            if self.fs_read_text_file:
                caps["fs"]["readTextFile"] = True
            if self.fs_write_text_file:
                caps["fs"]["writeTextFile"] = True
        if self.terminal:
            caps["terminal"] = True
        return caps

    @classmethod
    def from_dict(cls, data: dict) -> "ACPCapabilities":
        caps = cls()
        caps.execute = data.get("execute", False)
        caps.confirm = data.get("confirm", False)
        caps.push = data.get("push", False)
        caps.terminal = data.get("terminal", False)
        fs = data.get("fs", {})
        caps.fs_read_text_file = fs.get("readTextFile", False)
        caps.fs_write_text_file = fs.get("writeTextFile", False)
        return caps


@dataclass
class ACPClientInfo:
    """客户端信息"""

    name: str
    version: str = "1.0.0"

    def to_dict(self) -> dict:
        return {"name": self.name, "version": self.version}

    @classmethod
    def from_dict(cls, data: dict) -> "ACPClientInfo":
        return cls(name=data.get("name", "unknown"), version=data.get("version", "1.0.0"))


@dataclass
class ACPServerInfo:
    """服务端信息"""

    name: str
    version: str = "1.0.0"

    def to_dict(self) -> dict:
        return {"name": self.name, "version": self.version}


@dataclass
class ACPSession:
    """ACP 会话"""

    session_id: str
    cwd: str = ""
    created_at: float = 0.0


class ACPSessionUpdateType(str, Enum):
    """sessionUpdate 类型"""

    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MESSAGE = "message"
    ERROR = "error"


@dataclass
class ACPSessionUpdate:
    """sessionUpdate 内容"""

    session_id: str
    update_type: str
    content: Any = None
