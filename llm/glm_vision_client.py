"""
智谱 GLM-4V 视觉模型客户端
替代 UI-TARS 作为视觉理解层
"""
import base64
import json
import re
import requests
from pathlib import Path
from io import BytesIO
from dataclasses import dataclass
from loguru import logger

from config.settings import ZHIPU_API_KEY


GLM_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


class GLMVisionClient:
    """
    智谱 GLM-4V-Flash 视觉理解客户端

    调用策略：
    1. 发送截图 + 指令给 GLM-4V-Flash
    2. 模型返回文字描述（可能含坐标）
    3. 解析 action_type 和 target，x/y 坐标优先从文字中提取
    4. 若文字无坐标，将 target 传给 element_locator 用 OpenCV 匹配
    """

    def __init__(self, api_key: str = ZHIPU_API_KEY):
        self.api_key = api_key
        self.model = "glm-4v"  # 智谱视觉模型（注意：不是 glm-4v-flash）
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })


@dataclass
class UIAction:
    """视觉模型返回的语义动作"""
    action_type: str          # click / type / scroll / press / hover / wait
    target: str | None        # 语义目标，如 "发送按钮"
    x: int | None            # 像素坐标 x
    y: int | None            # 像素坐标 y
    text: str | None         # 输入文本
    confidence: float         # 置信度 0-1
    thought: str | None      # 模型思考过程
    raw_response: dict | None


class GLMVisionClient:
    """
    智谱 GLM-4V-Flash 视觉理解客户端

    调用策略：
    1. 发送截图 + 指令给 GLM-4V-Flash
    2. 模型返回文字描述（可能含坐标）
    3. 解析 action_type 和 target，x/y 坐标优先从文字中提取
    4. 若文字无坐标，将 target 传给 element_locator 用 OpenCV 匹配
    """

    def __init__(self, api_key: str = ZHIPU_API_KEY):
        self.api_key = api_key
        self.model = "glm-4v"  # 智谱视觉模型（注意：不是 glm-4v-flash）
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def infer(
        self,
        screenshot: Path | str | bytes,
        instruction: str,
        history: list[dict] | None = None
    ) -> UIAction:
        """
        调用 GLM-4V-Flash 进行视觉推理

        Args:
            screenshot: 截图路径或图像数据
            instruction: 自然语言指令，如 "点击发送按钮"

        Returns:
            UIAction 对象
        """
        # 编码图像
        if isinstance(screenshot, (Path, str)):
            img_bytes = Path(screenshot).read_bytes()
        elif isinstance(screenshot, bytes):
            img_bytes = screenshot
        else:
            raise TypeError("screenshot 必须是 Path/str/bytes 类型")

        img_base64 = base64.b64encode(img_bytes).decode("utf-8")

        # 构建消息
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_base64}"
                }
            },
            {
                "type": "text",
                "text": (
                    f"你是一个 GUI 自动化助手。用户要求：{instruction}\n"
                    f"请分析截图，用 JSON 格式返回你要执行的动作。\n"
                    f"格式：{{\"action\": \"click|type|press|scroll|wait\", "
                    f"\"target\": \"元素语义名称\", "
                    f"\"x\": 像素坐标x(仅click有), \"y\": 像素坐标y(仅click有), "
                    f"\"text\": \"输入文本(仅type有)\", "
                    f"\"thought\": \"你的推理过程\"}}\n"
                    f"重要：如果无法确定精确坐标，x和y填 null，"
                    f"target 填语义名称如'发送按钮'，后续会通过图像匹配定位。"
                )
            }
        ]

        messages = [{"role": "user", "content": user_content}]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2048
        }

        logger.info(f"GLM-4V 推理请求: {instruction[:30]}...")
        try:
            resp = self._session.post(GLM_API_URL, json=payload, timeout=30)
            resp.raise_for_status()
            result = resp.json()
        except requests.RequestException as e:
            logger.error(f"GLM-4V API 调用失败: {e}")
            raise

        return self._parse_response(result)

    def _parse_response(self, raw: dict) -> UIAction:
        """解析 GLM-4V 响应"""
        try:
            content = raw["choices"][0]["message"]["content"]

            # 尝试提取 JSON
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
            else:
                data = {"action": "click", "target": content, "x": None, "y": None}

            action_type = data.get("action", "click")
            target = data.get("target")
            x = data.get("x")
            y = data.get("y")
            text = data.get("text")
            thought = data.get("thought", "")

            # 尝试从文字中解析坐标（模型可能在描述中提到坐标）
            if x is None or y is None:
                coord = self._extract_coords_from_text(content)
                if coord:
                    x, y = coord

            # 标准化 action_type
            action_type = self._normalize_action(action_type)

            confidence = 0.8 if x and y else 0.6

            return UIAction(
                action_type=action_type,
                target=target,
                x=x, y=y, text=text,
                confidence=confidence,
                thought=thought,
                raw_response=raw
            )
        except Exception as e:
            logger.warning(f"GLM-4V 响应解析失败: {e}\n原始: {str(raw)[:200]}")
            return UIAction(
                action_type="click",
                target=None, x=None, y=None, text=None,
                confidence=0.0,
                thought=str(raw),
                raw_response=raw
            )

    @staticmethod
    def _extract_coords_from_text(text: str) -> tuple[int, int] | None:
        """从文字描述中解析坐标"""
        # 匹配常见坐标格式: (123, 456), x=123, y=456, 坐标(123,456)
        patterns = [
            r"\((\d+)\s*,\s*(\d+)\)",
            r"x\s*=\s*(\d+)\s*[,，]\s*y\s*=\s*(\d+)",
            r"坐标[：:]?\s*(\d+)\s*[,，]\s*(\d+)",
            r"位置[：:]?\s*(\d+)\s*[,，]\s*(\d+)",
            r"像素[：:]?\s*(\d+)\s*[,，]\s*(\d+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return int(m.group(1)), int(m.group(2))
        return None

    @staticmethod
    def _normalize_action(action: str) -> str:
        """标准化动作名称"""
        action = action.lower().strip()
        if action in ("click", "tap", "left_click", "鼠标点击"):
            return "click"
        if action in ("type", "input", "输入", "打字"):
            return "type"
        if action in ("press", "key", "按键", "键盘"):
            return "press"
        if action in ("scroll", "滚轮", "滑动"):
            return "scroll"
        if action in ("wait", "sleep", "等待"):
            return "wait"
        if action in ("hover", "move", "移动", "悬停"):
            return "hover"
        return "click"

    def close(self):
        self._session.close()
