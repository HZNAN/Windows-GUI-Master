# Client ID vs Session ID 说明

## 两种 ID 的区别

| ID | 示例 | 用途 | 层级 |
|----|------|------|------|
| **Client ID** | `cf9e8c1f` | 追踪 WebSocket 连接 | 传输层 (WebSocket) |
| **Session ID** | `8bf1c0fc-414f-4d9a-8122-001fc517e9da` | 保持 ACP 会话上下文 | 应用层 (ACP) |

## Client ID (WebSocket 连接 ID)

```
客户端 ←→ WebSocket 连接 (TCP) ←→ 服务端
              ↓
         每次连接时生成
         用于追踪这个连接
```

- **生成时机**：每次 WebSocket 连接建立时
- **生命周期**：连接断开后消失
- **用途**：日志追踪、连接管理、异常排查
- **特点**：纯内部使用，不在协议中传递

## Session ID (ACP 会话 ID)

```
ACP Session (应用层)
  ├── Session ID: 8bf1c0fc-...  ← ACP 协议的会话标识
  ├── cwd: /project/path         ← 工作目录
  ├── history: [...]             ← 对话历史
  └── created_at: 1745582400    ← 创建时间
```

- **生成时机**：客户端调用 `newSession` 时（或服务端自动生成）
- **生命周期**：可以跨连接存在（如果支持 session 持久化）
- **用途**：保持对话上下文、历史记录、跨请求状态
- **特点**：通过 ACP 消息传递，是协议的一部分

## 测试日志解析

```
Client connected: a62f6103          ← WebSocket 连接 1
  → initialize (无 session)
New session: c20f456b-...          ← ACP newSession 创建
  cwd: /test/workspace
Client connected: 5ae466bf        ← WebSocket 连接 2
  → prompt (使用 session c20f456b)
Client connected: 9f34eab3        ← WebSocket 连接 3
  → prompt (继续同一个 session)
```

## 关系图

```
┌─────────────────────────────────────────────────────────┐
│  WebSocket Connection (Client ID: cf9e8c1f)            │
│  ┌─────────────────────────────────────────────────┐   │
│  │  ACP Session (Session ID: 8bf1c0fc-...)         │   │
│  │  ├── initialize                                  │   │
│  │  ├── newSession ────────────────────→ 创建会话    │   │
│  │  ├── prompt ──────────────────────────────────→ │   │
│  │  └── ...                                        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Stdio 模式（acpx）

Stdio 是单进程、单连接、同步请求-响应模型。不存在 `client_id`，`session_id` 即等价于连接标识。

```
acpx CLI ──(子进程 stdin/stdout)──► test_acp_stdio.py
   │                                      │
   │  initialize                          │
   │  session/new ──► session_id = abc    │
   │  prompt ──────────────────────────►  │
   │  session/update ← (通知)             │
   │  prompt response ← (stopReason)      │
   │  prompt (人类回答) ───────────────►  │
   │  ...                                 │
```

## 修复记录

- **2026-04-29**: `ACPServer._cleanup_client` 修复 — 原来用 `req.msg.id`（JSON-RPC 消息 ID）比较 `client_id`，两者永远不等导致清理空操作。修复：`PendingRequest` 新增 `client_id` 字段，`send_confirm`/`send_request_param`/`send_ask_help` 填入当前客户端 ID。

---

## 单一连接场景（WebSocket）

```
Client connected: abc123           ← 一个 WebSocket 连接
  → initialize
  → newSession: xyz789            ← 创建 ACP 会话
  → prompt (session: xyz789)
  → prompt (session: xyz789)
  → prompt (session: xyz789)
  → ...
Client disconnected                ← 连接关闭
```

这种情况下：
- Client ID `abc123` 标识这个 TCP 连接
- Session ID `xyz789` 标识这个 ACP 会话

## 代码中的对应

```python
# server.py
client_id = str(uuid.uuid4())[:8]  # WebSocket 连接 ID (日志用)
# 每个 WebSocket 连接都会分配一个 client_id

# ACP Session
session_id = str(uuid.uuid4())    # ACP 会话 ID (协议层)
self._sessions[session_id] = session_state
```

## 什么时候会创建新 Session

| 操作 | 说明 |
|------|------|
| `newSession` | 显式创建新会话 |
| `loadSession` | 加载已有会话（恢复上下文） |
| `prompt` (首次) | 如果没有当前会话，可能自动创建 |

## 总结

- **Client ID** = 传输层概念，追踪 TCP 连接
- **Session ID** = 应用层概念，保持对话上下文
- 一个 Client ID 可以创建多个 Session（通过多次 newSession）
- 一个 Session 可以跨多个 Client ID（通过 loadSession 恢复）
