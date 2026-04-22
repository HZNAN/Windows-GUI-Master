# Feishu AI Agent 设计演化文档

## 1. 初始方案：手动 JSON 解析

### 方案描述
```
模型输出 JSON 字符串 → _parse_tool_call() 正则解析 → _execute_tool() 执行
```

模型被要求输出固定格式：
```json
{"name": "click", "arguments": {"x": 500, "y": 600}}
```

### 问题

#### 1.1 JSON 格式不稳定
模型输出各种错误格式：
```json
{"x": 488, 196}                    // 缺少 "y" key
{"x": 480, "200": y}              // key 是数字，value 是变量名
{"name": "click", "x": 500, "y": 600}  // 缺少 "arguments"
```

#### 1.2 解析逻辑越来越复杂
`_parse_tool_call` 需要处理多种错误格式：
```python
# 修复 {"x": 488, 196} → {"x": 488, "y": 196}
fixed = re.sub(r'"x":\s*(\d+),\s*(\d+)', r'"x": \1, "y": \2', content)

# 修复 {"x": 480, "200": y} → {"x": 480, "y": 200}
fixed = re.sub(r'"x":\s*(\d+),\s*"(\d+)":\s*(\w+)', r'"x": \1, "y": \2', content)
```

#### 1.3 System Prompt 与代码耦合
提示词写在代码里，难以维护和调整。

---

## 2. 第一次改进：解耦 + 增强 JSON 解析

### 改进措施
1. 将 System Prompt 提取到 `prompts/system_prompt.txt`
2. 添加更多正则修复规则
3. 添加 `<point>x y</point>` 格式支持

### 问题残留
- 模型仍然输出格式错误的 JSON
- 提示词越写越特定于"发消息"这个任务
- 解析逻辑仍是 workaround，不是根本解决方案

---

## 3. 第二次改进：标准 LangChain bind_tools

### 方案描述
```
使用 bind_tools([click, move_mouse, ...]) → 模型自动输出正确格式的 tool_calls
```

不再手动解析 JSON，而是依赖 LangChain 的工具绑定机制：
```python
self.llm = ChatOpenAI(...).bind_tools(
    [click, move_mouse, type_text, press_key, wait, screenshot, get_screen_info],
    tool_choice="auto"
)
```

### 优势
1. 模型输出自动是结构化的 `tool_calls`
2. 不需要手动解析
3. 参数名自动正确（`grid_x` 而非 `x`）

### 问题
1. **消息历史累积**：使用 `create_agent` 时，消息历史不断增长
2. **无法强制注入截图**：框架控制消息流程，我们不能每轮手动注入新截图

---

## 4. 第三次改进：回到轻量级手动循环

### 方案描述
保持 `bind_tools`，但放弃 `create_agent` 框架，回到手动循环：

```python
while step_count < max_steps:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=[
            {"type": "text", "text": "Task: xxx"},
            {"type": "image_url", "image_url": screenshot_url},
            {"type": "text", "text": f"Previous result: {tool_result}"},
        ])
    ]
    response = llm.invoke(messages)
    # 执行工具，获取新截图，继续下一轮
```

### 优势
1. 每轮只发 2 条消息（System + Human）
2. 完全控制消息注入时机
3. 每轮强制注入新截图

### 问题
- 停止规则依赖关键词检测（如"完成"、"成功"）
- 模型可能输出包含"完成"但并非想结束任务
- 模型可能不输出任何 tool_calls 也不说"完成"

---

## 5. 第四次改进：添加 finish 工具

### 方案描述
添加专用 `finish` 工具，让模型自行判断任务完成：

```python
@tool
def finish() -> str:
    """标记任务已完成，代理将成功结束。"""
    return "TASK_COMPLETED"
```

### 工作流程
```
模型: click(x, y) → 执行
模型: screenshot() → 观察
模型: finish() → 检测到 TASK_COMPLETED → return success=True
```

### 优势
1. 模型**明确知道**何时任务完成
2. 不再依赖模糊的关键词检测
3. 是结构化的"工具调用"，准确可控

### 结束条件对比

| | 关键词检测 | finish 工具 |
|---|---|---|
| 机制 | 文本匹配 | 结构化工具调用 |
| 准确性 | 低（可能误判） | 高（明确调用） |
| 模型认知 | 不知道何时"完成" | 被提示调用 finish() |

---

## 6. 第五次改进：type_text 坐标可选

### 问题
`type_text(grid_x, grid_y, text)` 总是先点击再输入，但有时 cursor 已经存在，不需要点击。

### 方案
```python
def type_text(text: str, grid_x: int | None = None, grid_y: int | None = None):
    if grid_x is not None and grid_y is not None:
        # 有坐标，先点击定位
        click(grid_x, grid_y)
    # 直接输入文本
    type_text(text)
```

### 使用方式
- **有 cursor** → `type_text(text="hello")`
- **无 cursor** → `type_text(grid_x=500, grid_y=600, text="hello")`

---

## 7. 第六次改进：鼠标平滑移动

### 问题
鼠标移动是瞬移的，不像人类操作。

### 方案
```python
def move_to(self, x: int, y: int, duration: float = 0.3):
    pyautogui.moveTo(x, y, duration=duration)  # 0.3秒平滑移动
```

### 效果
- `click()` 内部调用 `move_to(duration=0.3)`
- `move_mouse()` 同样使用 0.3 秒过渡
- 更像人类操作的自然移动

---

## 8. 当前架构总结

### 消息流程
```
┌─────────────────────────────────────────────────────────┐
│  HumanMessage (Task + 截图 + 上一轮结果)                │
│       ↓                                                  │
│  LLM (bind_tools) → AIMessage (tool_calls)              │
│       ↓                                                  │
│  _execute_tool() → ToolMessage 结果                      │
│       ↓                                                  │
│  新截图 → 回到第一步 (直到 finish() 或 max_steps)        │
└─────────────────────────────────────────────────────────┘
```

### 工具列表
| 工具 | 用途 | 坐标必填 |
|------|------|----------|
| click | 点击 | 是 |
| move_mouse | 移动 | 是 |
| type_text | 输入文本 | 否 |
| press_key | 按键 | - |
| wait | 等待 | - |
| screenshot | 截图 | - |
| get_screen_info | 屏幕信息 | - |
| finish | 完成任务 | - |
| need_more_steps | 请求更多步骤 | - |

### 关键设计决策

1. **轻量级消息**：每轮只发 SystemMessage + HumanMessage，不累积历史
2. **强制截图注入**：每轮工具执行后强制获取新截图
3. **finish 工具**：模型自行判断完成，不再依赖关键词
4. **可选坐标**：type_text 根据是否有 cursor 决定是否需要点击
5. **平滑鼠标**：0.3 秒过渡，更像人类操作

### 未来可能的改进方向

1. **多轮记忆**：考虑累积最近 N 轮的消息历史
2. **错误恢复**：模型连续失败后尝试不同策略
3. **主动询问**：无法完成时向用户确认
4. **create_agent 兼容**：解决 mss 多线程问题后，可尝试框架原生方案
