# ACP 协议设计 — 2026-04-25

## Context

为项目设计自定义 Agent Communication Protocol (ACP)，实现：
- 单一 Client ↔ Server 双向通信
- WebSocket 传输 + Bearer Token 认证
- 支持 Server 主动向 Client 发起确认/询问/推送

同时兼容标准 ACP 协议（Zed Industries / Linux Foundation A2A），支持：
- `initialize` / `newSession` / `loadSession` / `prompt` / `sessionUpdate`
- 扩展方法：`agent.confirm` / `agent.push` / `agent.ask_help` 等

---

## Architecture

```
Client (控制端/飞书机器人) ←WebSocket + Token→ Server (本项目)
         ↑ 双向 WebSocket 连接
    - Client → Server: 指令、响应
    - Server → Client: 确认请求、参数补全、异常求助、主动推送
```

---

## Message Format

基于 JSON-RPC 2.0 标准。

### 请求 / 响应

```json
{
  "jsonrpc": "2.0",
  "id": "唯一标识符 (string)",
  "method": "方法名",
  "params": {}
}
```

### 错误响应

```json
{
  "jsonrpc": "2.0",
  "id": "原请求id",
  "error": {
    "code": -32000,
    "message": "错误描述"
  }
}
```

---

## Methods

### Server → Client (主动发起)

| 方法名 | 用途 | params |
|--------|------|--------|
| `agent.confirm` | 执行前确认（危险操作等） | `{type: string, message: string, context: object, timeout: int}` |
| `agent.request_param` | 参数补全请求 | `{missing_params: list, current_state: object}` |
| `agent.ask_help` | 异常求助 | `{error: object, context: object, suggestions: list}` |
| `agent.push` | 主动推送 | `{type: string, data: object}` |

#### agent.confirm params

```json
{
  "type": "confirm|warn|danger",
  "message": "确认执行删除操作？",
  "context": {"path": "/tmp/file.txt"},
  "timeout": 30
}
```

#### agent.push type 枚举

| type | 说明 | data 示例 |
|------|------|-----------|
| `screenshot` | 截图推送 | `{base64: "..."}` |
| `status` | 状态更新 | `{state: "running", step: 3}` |
| `progress` | 进度报告 | `{current: 50, total: 100}` |
| `log` | 日志输出 | `{level: "info", message: "..."}` |

### Client → Server (被动响应)

| 方法名 | 用途 | params |
|--------|------|--------|
| `agent.execute` | 执行指令 | `{action: string, params: object}` |
| `agent.response` | 确认/询问响应 | `{request_id: string, result: object}` |
| `agent.cancel` | 取消操作 | `{request_id: string}` |
| `agent.ping` | 心跳检测 | `{}` |

---

## Standard ACP 兼容方法

### 核心方法

| 方法名 | 方向 | 用途 |
|--------|------|------|
| `initialize` | Client → Server | 能力协商，客户端声明支持的功能 |
| `newSession` | Client → Server | 创建新会话 |
| `loadSession` | Client → Server | 加载已有会话 |
| `prompt` | Client → Server | 提交用户指令 |
| `sessionUpdate` | Server → Client | 流式通知（推送） |

### initialize

```json
// Client 请求
{
  "jsonrpc": "2.0",
  "id": "init_001",
  "method": "initialize",
  "params": {
    "protocolVersion": "1.0",
    "capabilities": {
      "fs": {"readTextFile": true, "writeTextFile": true},
      "terminal": true
    },
    "clientInfo": {"name": "acpx", "version": "1.0.0"}
  }
}

// Server 响应
{
  "jsonrpc": "2.0",
  "id": "init_001",
  "result": {
    "protocolVersion": "1.0",
    "capabilities": {
      "execute": true,
      "confirm": true,
      "push": true,
      "fs": {"readTextFile": true, "writeTextFile": false},
      "terminal": false
    },
    "serverInfo": {"name": "feishu-agent", "version": "1.0.0"}
  }
}
```

### newSession / loadSession

```json
// newSession 请求
{
  "jsonrpc": "2.0",
  "id": "sess_001",
  "method": "newSession",
  "params": {
    "sessionId": "可选的会话ID",
    "cwd": "/path/to/workspace"
  }
}

// 响应
{
  "jsonrpc": "2.0",
  "id": "sess_001",
  "result": {
    "sessionId": "生成的会话ID"
  }
}
```

### prompt

```json
// Client 请求
{
  "jsonrpc": "2.0",
  "id": "prompt_001",
  "method": "prompt",
  "params": {
    "prompt": "用户输入的指令",
    "systemPrompt": "可选的系统提示"
  }
}

// Server 响应（完成时）
{
  "jsonrpc": "2.0",
  "id": "prompt_001",
  "result": {
    "sessionId": "会话ID",
    "stopReason": "completed",
    "message": "执行结果"
  }
}
```

### sessionUpdate (Server → Client 流式推送)

```json
{
  "jsonrpc": "2.0",
  "method": "sessionUpdate",
  "params": {
    "sessionId": "会话ID",
    "update": {
      "type": "thinking|tool_call|tool_result|message",
      "content": "内容"
    }
  }
}
```

---

## 扩展方法（我们自定义）

| 方法名 | 方向 | 用途 |
|--------|------|------|
| `agent.confirm` | Server → Client | 执行前确认 |
| `agent.request_param` | Server → Client | 参数补全请求 |
| `agent.ask_help` | Server → Client | 异常求助 |
| `agent.push` | Server → Client | 主动推送 |

#### agent.response result 示例

```json
// 确认
{"approved": true}
// 拒绝
{"approved": false, "reason": "取消操作"}
// 参数补全
{"params": {"x": 100, "y": 200}}
```

---

## Error Codes

| code | 说明 |
|------|------|
| `-32000` | 通用错误 |
| `-32001` | 认证失败 (Unauthorized) |
| `-32002` | 超时 (Timeout) |
| `-32003` | 参数无效 (Invalid Params) |
| `-32004` | 执行失败 (Execution Failed) |

---

## Authentication

- **Bearer Token**: `Authorization: Bearer <token>`
- WebSocket 握手时通过 HTTP Header 传递
- 认证失败返回 error code `-32001`

---

## Timeout Policy

- 默认超时可配置（建议 30s）
- 每个确认请求可单独设置 `timeout` 字段
- 超时处理策略：**默认取消**，可配置

---

## Implementation Status

### 协议层已实现 (2026-04-25)

- [x] `core/acp/types.py` — ACPMessage, ACPMethod, ACPErrorCode 等数据类型定义
- [x] `core/acp/protocol.py` — JSON-RPC 2.0 消息编解码、验证
- [x] `core/acp/auth.py` — Bearer Token 认证
- [x] `core/acp/server.py` — WebSocket 服务端，支持确认/参数补全/求助请求

### Standard ACP 兼容（待实现）

- [ ] `initialize` 方法 — 能力协商
- [ ] `newSession` / `loadSession` 方法 — 会话管理
- [ ] `prompt` 方法 — 指令提交
- [ ] `sessionUpdate` 推送 — 流式通知
- [ ] 协议版本协商

### 配置项 (.env)

```bash
ACP_HOST = "localhost"
ACP_PORT = 8765
ACP_TOKEN = ""  # Bearer token，为空则禁用认证
```

### 暂不实现

- 与现有 execution_engine 集成
- 完整 fs/* / terminal/* 工具支持
- 测试用例

---

## Files

```
core/acp/
  ├── __init__.py
  ├── types.py       # 数据类型定义 (Method, Message, Error)
  ├── protocol.py    # 消息编解码、验证
  ├── auth.py        # Bearer Token 认证
  └── server.py      # WebSocket 服务端
```

---

## Notes

- 不影响现有 execution_engine 和 agent 执行流程
- 协议层独立，可复用
- 单一客户端，不处理多连接路由
