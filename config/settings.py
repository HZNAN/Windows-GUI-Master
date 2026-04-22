"""
全局配置文件
所有敏感信息（API Key、App ID 等）建议通过环境变量或 .env 文件管理
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ============ 项目路径 ============
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
REPORTS_DIR = PROJECT_ROOT / "reports"
SCREENSHOTS_DIR = PROJECT_ROOT / ".screenshots"
SAMPLE_IMAGES_DIR = PROJECT_ROOT / ".sample_images"

REPORTS_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR.mkdir(exist_ok=True)
SAMPLE_IMAGES_DIR.mkdir(exist_ok=True)

# ============ 视觉模型配置（二选一）============
# 推荐使用智谱 GLM-4V-Flash（免费），也可选 ModelScope UI-TARS
VISION_PROVIDER = os.getenv("VISION_PROVIDER", "zhipu")  # zhipu / modelscope
VISION_API_KEY = os.getenv("VISION_API_KEY", "")

# ModelScope UI-TARS（备选）
MODELSCOPE_API_URL = os.getenv(
    "MODELSCOPE_API_URL",
    "https://api.modelscope.cn/v1/agent/inference"
)
MODELSCOPE_API_KEY = os.getenv("MODELSCOPE_API_KEY", "")
MODELSCOPE_MODEL_ID = os.getenv("MODELSCOPE_MODEL_ID", "AI-Research/UI-TARS-7B")

# ============ 火山引擎豆包配置（视觉层）============
# 火山引擎 ARK API (支持 doubao-vision 等多模态模型)
ARK_API_KEY = "ark-692bf554-d0fc-4b45-bde6-ba0157d4de54-b4a75"
ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3"
# 豆包视觉模型 endpoint ID
ARK_VISION_MODEL = "doubao-seed-2-0-lite-260215"

# ============ 智谱 GLM 配置（保留兼容性）============
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

# ============ 规划层 LLM 配置（用于 planner.py 任务分解）============
PLANNER_LLM_PROVIDER = os.getenv("PLANNER_LLM_PROVIDER", "zhipu")  # openai / zhipu / doubao
PLANNER_LLM_API_KEY = os.getenv("PLANNER_LLM_API_KEY", "")
PLANNER_LLM_BASE_URL = os.getenv("PLANNER_LLM_BASE_URL", "")
PLANNER_LLM_MODEL = os.getenv("PLANNER_LLM_MODEL", "glm-4-flash")

# ============ 飞书开放平台配置 ============
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_USER_TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token"
FEISHU_APP_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"

# 飞书 API 基础地址
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"

# ============ Agent 执行配置 ============
MAX_RETRY = int(os.getenv("MAX_RETRY", "3"))           # 单步最大重试次数
SCREENSHOT_INTERVAL = float(os.getenv("SCREENSHOT_INTERVAL", "0.5"))  # 截图间隔（秒）
STEP_TIMEOUT = int(os.getenv("STEP_TIMEOUT", "30"))    # 单步超时时间（秒）
HUMAN_IN_LOOP_ON_ERROR = os.getenv("HUMAN_IN_LOOP_ON_ERROR", "true").lower() == "true"
# UI-TARS 返回置信度低于此值时触发人工确认
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

# ============ 日志配置 ============
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = PROJECT_ROOT / "logs" / "feishu_agent.log"
