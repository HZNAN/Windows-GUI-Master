# acpx 兼容性与技术方案分析

> 日期: 2026-04-25
> 讨论主题: ACP 协议与 acpx CLI 的兼容性分析

---

## 1. acpx 架构分析

### 1.1 通信模式

| 特性 | 说明 |
|------|------|
| 传输方式 | Stdio (stdin/stdout) |
| 通信模式 | 半双工 + 请求-响应 |
| 多路复用 | 不支持 |
| 主动推送 | 支持（session/update 通知，JSON-RPC notification） |

```
acpx 通信流程:
┌─────────────────────────────────────────────────────────┐
│  acpx (CLI Client)                                     │
│                                                          │
│   stdin ──────────►  agent (服务端)                     │
│                         │                               │
│                         │ 只能响应                       │
│                         ▼                               │
│   stdout ◄──────────  agent                             │
│                                                          │
│   循环: acpx发送请求 → agent响应 → acpx发送请求 → ...  │
└─────────────────────────────────────────────────────────┘
```

### 1.2 acpx 支持的方法

| 方法 | 方向 | 支持 |
|------|------|------|
| `initialize` | Client → Server | ✅ |
| `session/new` | Client → Server | ✅ |
| `session/load` | Client → Server | ✅ |
| `session/prompt` | Client → Server | ✅ |
| `session/update` | Server → Client | ✅ (2026-04-29 验证通过) |

**注意:** acpx 使用 `session/new` 而不是 `newSession`，需要服务端兼容两种格式。

### 1.3 acpx 命令

```bash
# Session 管理
acpx <agent> sessions new          # 创建 session
acpx <agent> sessions close       # 关闭 session
acpx <agent> sessions history     # 查看历史消息
acpx <agent> sessions read        # 读取完整历史

# 消息发送
acpx <agent> prompt "消息"        # 通过 persistent session 发送
acpx <agent> exec "消息"          # 一次性执行

# 其他
acpx <agent> cancel               # 取消当前请求
```

---

## 2. 五场景半双工可行性分析

### 2.1 五个扩展场景

| 场景 | 方法 | 方向 | 说明 |
|------|------|------|------|
| Confirm | `agent.confirm` | Server → Client | 执行前确认 |
| Request Param | `agent.request_param` | Server → Client | 参数补全请求 |
| Ask Help | `agent.ask_help` | Server → Client | 异常求助 |
| Push | `agent.push` | Server → Client | 主动推送 |
| Response | `agent.response` | Client → Server | 响应 |

### 2.2 半双工工作流

**关键洞察:** acpx session 维护完整消息历史，下一条用户消息自然成为上一条 agent 消息的响应。

```
对话流程:
┌─────────────────────────────────────────────────────────┐
│  acpx session 历史                                     │
│                                                          │
│  [User] 删除文件                                       │
│  [Agent] confirm "确认删除?"                           │
│  [User] 确认删除  ← 自然成为 confirm 的响应            │
│  [Agent] ask_help "出错了..."                          │
│  [User] 试试其他方法  ← 自然成为 ask_help 的响应       │
│  [Agent] result "完成"                                 │
└─────────────────────────────────────────────────────────┘
```

### 2.3 各场景工作流

| 场景 | acpx 处理 | ReactAgent 理解 |
|------|-----------|-----------------|
| confirm | 显示确认请求 | 看到用户下一条 = approve/reject |
| ask_help | 显示错误+建议 | 看到用户下一条 = 帮助响应 |
| push | 显示推送内容 | 看到用户下一条 = 确认继续 |
| request_param | 显示缺少参数 | 看到用户下一条 = 提供参数 |

### 2.4 架构分层

```
┌─────────────────────────────────────────────────────────┐
│  acpx session                                            │
│  - 消息传输                                              │
│  - 历史记录 (完整对话流)                                 │
│  - 消息展示给用户                                        │
└─────────────────────────────────────────────────────────┘
                           ↓ 读取历史
┌─────────────────────────────────────────────────────────┐
│  ReactAgent                                              │
│  - 读取 acpx session 历史                               │
│  - 理解对话上下文 (语义关联)                            │
│  - 决定下一步行动                                        │
│  - 维护挂起的请求状态 (confirm 等)                      │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 技术方案总结

### 3.1 传输层选择

| 方案 | 传输 | acpx CLI | WebSocket 客户端 | 服务端推送 |
|------|------|----------|------------------|------------|
| Stdio (acpx) | stdio | ✅ | ❌ | ❌ |
| WebSocket | WebSocket | ❌ | ✅ | ✅ |

**决策:** Stdio (acpx) 为主交互模式，WebSocket 为扩展模式

- 消息格式遵循 acpx 的 ACP 协议（含 session/update 通知）
- Stdio 模式支持人机协同（`stopReason: "needs_human"` + session 级 prompt 应答）
- WebSocket 模式支持异步人机协同（`agent.confirm` / `agent.ask_help` 扩展方法）
- `ReactAgentService` 共享业务逻辑层，两种传输层通过薄适配器对接

### 3.2 方法名兼容

服务端需要同时支持 Standard ACP 和 acpx 风格的方法名：

| Standard ACP | acpx 风格 |
|--------------|-----------|
| `initialize` | `initialize` |
| `newSession` | `session/new` |
| `loadSession` | `session/load` |
| `prompt` | `session/prompt` |

### 3.3 状态管理（待实现）

ReactAgent 需要维护以下状态：

```python
class ReactAgentState:
    pending_request: Optional[PendingRequest]  # 挂起的请求 (confirm 等)
    request_type: Optional[str]              # 挂起请求的类型
    request_context: Optional[dict]          # 请求上下文
```

---

## 4. 实现进度 (updated 2026-04-30)

- [x] ReactAgent 集成 ACP 协议 (`core/agent_service.py` 共享服务层)
- [x] 实现状态管理（`AgentSession` — 会话状态 + 线程间通信桥接）
- [x] 实现人机协同（`ask_human` 工具 + `stopReason: "needs_human"` + 下一条 prompt 注入答案）
- [x] session/update 通知（`agent_message_chunk` / `tool_call` / `tool_call_update`）
- [x] acpx 兼容格式验证（mock agent 测试通过）
- [x] 编写集成测试（`test_human_in_loop.py` — mock agent 协议模拟）
- [ ] WebSocket 侧异步人机协同（`agent.confirm` / `agent.ask_help` 扩展方法）

---

## 5. 相关文件

| 文件 | 说明 |
|------|------|
| `core/acp/protocol.py` | ACP 消息编解码 + session/update 构建（acpx 兼容） |
| `core/acp/types.py` | ACP 数据类型 |
| `core/acp/server.py` | WebSocket 服务端 |
| `core/agent_service.py` | 共享业务服务（会话、人机协同、通知系统） |
| `agents/react_agent.py` | ReAct Agent + ask_human 工具 + 通知推送 |
| `tools/agent.py` | finish/continue_steps/retry + ask_human 工具 |
| `test_acp_stdio.py` | acpx stdio 服务端（双模式 prompt 路由） |
| `test_react_agent_acp.py` | WebSocket 服务端（双模式 prompt 路由） |
| `test_acp_server.py` | WebSocket 测试服务端 |
| `test_human_in_loop.py` | Mock agent（协议模拟 + 通知测试，无 LLM 依赖） |
| `.acpxrc.json.example` | acpx 配置示例 |
