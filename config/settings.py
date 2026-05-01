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

# ============ LLM 模型配置（OpenAI 兼容 API，支持任意厂商） ============
# 优先级: LLM_* env > ARK_* env (向后兼容) > 默认值
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("ARK_API_KEY") or ""
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or os.getenv("ARK_API_URL") or "https://ark.cn-beijing.volces.com/api/v3"
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("ARK_VISION_MODEL") or "doubao-seed-2-0-lite-260215"
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1500"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "1.0"))

# ============ ReactAgent 配置 ============
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "15"))
AGENT_HISTORY_WINDOW = int(os.getenv("AGENT_HISTORY_WINDOW", "3"))
AGENT_TURN_DELAY = float(os.getenv("AGENT_TURN_DELAY", "0.3"))

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
