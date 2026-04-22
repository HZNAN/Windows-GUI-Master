"""
UI-TARS 模型客户端
通过 ModelScope 云端 API 调用 UI-TARS 视觉语言模型
"""
import base64
import json
import requests
from pathlib import Path
from io import BytesIO
from typing import Literal
from dataclasses import dataclass
from loguru import logger

from config.settings import (
    MODELSCOPE_API_URL, MODELSCOPE_API_KEY, MODELSCOPE_MODEL_ID
)


@dataclass
class UIAction:
    """UI-TARS 返回的语义动作"""
    action_type: str          # click / type / scroll / press / hover / wait
    target: str | None        # 语义目标，如 "发送按钮"、"输入框"
    x: int | None             # 像素坐标 x（如果模型输出）
    y: int | None             # 像素坐标 y
    text: str | None          # 输入文本（type 动作时）
    confidence: float         # 置信度 0-1
    thought: str | None       # 模型思考过程
    raw_response: dict | None # 原始响应


class UITarsClient:
    """
    UI-TARS ModelScope API 客户端

    核心功能：接收截图 + 自然语言指令，返回语义动作
    """

    def __init__(
        self,
        api_url: str = MODELSCOPE_API_URL,
        api_key: str = MODELSCOPE_API_KEY,
        model_id: str = MODELSCOPE_MODEL_ID
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.model_id = model_id
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
        调用 UI-TARS 模型进行推理

        Args:
            screenshot: 截图路径或图像数据（bytes）
            instruction: 自然语言指令，如 "点击发送按钮"
            history: 可选的对话历史

        Returns:
            UIAction 对象，包含解析后的语义动作
        """
        # 编码图像
        if isinstance(screenshot, (Path, str)):
            img_bytes = Path(screenshot).read_bytes()
        elif isinstance(screenshot, bytes):
            img_bytes = screenshot
        else:
            raise TypeError("screenshot 必须是 Path/str/bytes 类型")

        img_base64 = base64.b64encode(img_bytes).decode("utf-8")

        # 构建请求
        payload = {
            "model_id": self.model_id,
            "input": {
                "image": f"data:image/png;base64,{img_base64}",
                "instruction": instruction,
            }
        }
        if history:
            payload["input"]["history"] = history

        # 调用 API
        logger.info(f"UI-TARS 推理请求: {instruction[:30]}...")
        try:
            resp = self._session.post(self.api_url, json=payload, timeout=30)
            resp.raise_for_status()
            result = resp.json()
        except requests.RequestException as e:
            logger.error(f"UI-TARS API 调用失败: {e}")
            raise

        # 解析响应
        return self._parse_response(result)

    def _parse_response(self, raw: dict) -> UIAction:
        """解析 ModelScope API 响应，提取语义动作"""
        # ModelScope Agent API 返回格式
        try:
            outputs = raw.get("outputs", {})
            if isinstance(outputs, str):
                outputs = json.loads(outputs)

            # 通用解析逻辑：查找模型输出的动作信息
            action_text = outputs.get("action", "")
            thought = outputs.get("thought", "")
            confidence = outputs.get("confidence", 0.9)

            # 解析动作类型和目标
            action_type, target, x, y, text = self._extract_action(action_text)

            return UIAction(
                action_type=action_type,
                target=target,
                x=x, y=y, text=text,
                confidence=confidence,
                thought=thought,
                raw_response=raw
            )
        except Exception as e:
            logger.warning(f"UI-TARS 响应解析失败，使用默认值: {e}")
            return UIAction(
                action_type="wait",
                target=None, x=None, y=None, text=None,
                confidence=0.0,
                thought=str(raw),
                raw_response=raw
            )

    @staticmethod
    def _extract_action(action_text: str) -> tuple[str, str | None, int | None, int | None, str | None]:
        """
        从模型输出的文本中解析出结构化动作
        格式示例: "click(150, 320)" / "type('hello', target='input')" / "click('发送按钮')"
        """
        action_text = action_text.strip()

        # 尝试解析 click(x, y) 格式
        if action_text.startswith("click_at") or action_text.startswith("click("):
            import re
            # 格式: click_at(150, 320) 或 click_at("发送按钮")
            match = re.search(r"click[_\(]+(.+?)[,\)]", action_text)
            if match:
                inner = match.group(1).strip()
                # 检查是否是坐标
                coord_match = re.match(r"(\d+)\s*,\s*(\d+)", inner)
                if coord_match:
                    return "click", None, int(coord_match.group(1)), int(coord_match.group(2)), None
                # 否则是语义目标
                clean_target = inner.strip('"\'')
                return "click", clean_target, None, None, None

        # 尝试解析 type 格式
        if action_text.startswith("type("):
            import re
            text_match = re.search(r"type\s*\(\s*[\"'](.+?)[\"']", action_text)
            target_match = re.search(r"target\s*=\s*[\"'](.+?)[\"']", action_text)
            text = text_match.group(1) if text_match else None
            target = target_match.group(1) if target_match else None
            return "type", target, None, None, text

        # 尝试解析 scroll 格式
        if action_text.startswith("scroll"):
            import re
            dir_match = re.search(r"scroll\s*\(\s*[\"'](.+?)[\"']", action_text)
            amount_match = re.search(r"(\d+)", action_text)
            direction = dir_match.group(1) if dir_match else "down"
            amount = int(amount_match.group(1)) if amount_match else 3
            return "scroll", direction, None, None, str(amount)

        # 尝试解析 press 格式
        if action_text.startswith("press("):
            import re
            key_match = re.search(r"press\s*\(\s*[\"'](.+?)[\"']", action_text)
            key = key_match.group(1) if key_match else "Enter"
            return "press", key, None, None, None

        # 默认：认为是指令文本，需要进一步定位
        return "click", action_text, None, None, None

    def close(self):
        self._session.close()
