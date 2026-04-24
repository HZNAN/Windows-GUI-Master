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

# ============ 日志配置 ============
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = PROJECT_ROOT / "logs" / "agent.log"

# ============ 虚拟光标配置 ============
# 相对路径: 相对于 PROJECT_ROOT/cursors/ 目录，如 "universe"
# 绝对路径: 以 / 或盘符开头，如 "C:/custom_cursors/my_cursor" 或 "/usr/share/cursors"
VIRTUAL_CURSOR_PATH = os.getenv("VIRTUAL_CURSOR_PATH", "universe")
