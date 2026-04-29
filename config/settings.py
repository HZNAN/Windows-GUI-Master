"""
全局配置文件
所有敏感信息（API Key 等）通过环境变量或 .env 文件管理
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============ 项目路径 ============
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SCREENSHOTS_DIR = PROJECT_ROOT / ".screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

# ============ 火山引擎 ARK 视觉模型配置 ============
ARK_API_KEY = os.getenv("ARK_API_KEY", "ark-692bf554-d0fc-4b45-bde6-ba0157d4de54-b4a75")
ARK_API_URL = os.getenv("ARK_API_URL", "https://ark.cn-beijing.volces.com/api/v3")
ARK_VISION_MODEL = os.getenv("ARK_VISION_MODEL", "doubao-seed-2-0-lite-260215")

# ============ Agent 执行配置 ============
MAX_RETRY = int(os.getenv("MAX_RETRY", "3"))
SCREENSHOT_INTERVAL = float(os.getenv("SCREENSHOT_INTERVAL", "0.5"))
STEP_TIMEOUT = int(os.getenv("STEP_TIMEOUT", "30"))

# ============ ReactAgent 配置 ============
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "15"))
AGENT_HISTORY_WINDOW = int(os.getenv("AGENT_HISTORY_WINDOW", "3"))
AGENT_TURN_DELAY = float(os.getenv("AGENT_TURN_DELAY", "0.3"))  # 每轮操作完成后到下一轮截图的等待（秒），给 UI 时间渲染

# ============ LLM 模型配置 ============
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1500"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "1.0"))

# ============ 日志配置 ============
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = PROJECT_ROOT / "logs" / "agent.log"

# ============ 虚拟光标配置 ============
# 相对路径: 相对于 PROJECT_ROOT/cursors/ 目录，如 "universe"
# 绝对路径: 以 / 或盘符开头，如 "C:/custom_cursors/my_cursor" 或 "/usr/share/cursors"
VIRTUAL_CURSOR_PATH = os.getenv("VIRTUAL_CURSOR_PATH", "universe")

# 虚拟光标动画参数
VIRTUAL_CURSOR_DURATION = float(os.getenv("VIRTUAL_CURSOR_DURATION", "0.5"))  # 移动时长（秒），越小越快
VIRTUAL_CURSOR_FPS = int(os.getenv("VIRTUAL_CURSOR_FPS", "60"))  # 帧率，越高越平滑
VIRTUAL_CURSOR_AMPLITUDE = int(os.getenv("VIRTUAL_CURSOR_AMPLITUDE", "15"))  # 曲线幅度扰动（像素）

# ============ ACP 协议配置 ============
ACP_HOST = os.getenv("ACP_HOST", "localhost")
ACP_PORT = int(os.getenv("ACP_PORT", "8765"))
ACP_TOKEN = os.getenv("ACP_TOKEN", "")  # Bearer token，为空则禁用认证

# ============ 输入模式配置 ============
INPUT_MODE = os.getenv("INPUT_MODE", "message")  # "message" | "virtual" | "normal"
