# Window GUI Master

<p align="center">
  <img src="icon.svg" width="128" height="128" alt="Window GUI Master Icon">
</p>

Windows 桌面自动化代理，基于视觉模型的 ReAct 循环，通过截图分析控制鼠标键盘完成任务。

## 功能特性

- **视觉驱动**：截图 + 坐标网格，模型直接输出操作指令
- **ACP 协议**：支持 `acpx` CLI 通过 stdio/WebSocket 集成
- **虚拟光标**：贝塞尔曲线动画，不干扰真实鼠标
- **多输入模式**：message（隐藏光标）、virtual、normal
- **中文支持**：剪贴板粘贴，支持任意中文输入
- **人机协作**：`ask_human` 工具暂停等待人类输入

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY

# 配置 acpx（可选）
cp .acpxrc.json.example .acpxrc.json

# 运行（通过 acpx）
acpx gui-master "打开记事本并输入 Hello World"

# 或启动 WebSocket 服务器
python test_react_agent_acp.py
```

## 项目结构

```
agents/          - ReAct Agent 循环
config/          - 配置管理
core/            - ACP 协议、执行引擎、虚拟光标
drivers/         - 输入驱动、屏幕捕获、覆盖层
tools/           - LangChain 工具函数
prompts/         - 系统提示词
cursor/          - 虚拟光标资源
```

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | (必填) | OpenAI 兼容 API Key |
| `LLM_BASE_URL` | 火山引擎 | API 地址 |
| `LLM_MODEL` | doubao-seed-2.0 | 视觉模型名称 |
| `AGENT_MAX_STEPS` | 15 | 最大执行步数 |
| `LLM_TEMPERATURE` | 0.1 | 采样温度 |
| `LLM_MAX_TOKENS` | 1500 | 最大生成 token |
| `VIRTUAL_CURSOR_FPS` | 60 | 光标动画帧率 |
| `INPUT_MODE` | message | 输入模式 |

## 许可证

MIT License