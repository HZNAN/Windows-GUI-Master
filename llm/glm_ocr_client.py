"""
GLM-OCR 客户端
使用智谱 GLM-OCR API 进行文字检测和定位
返回带 bounding box 坐标的结构化结果
"""
import base64
from pathlib import Path
from typing import Literal
from loguru import logger

from zai import ZaiClient
from config.settings import ZHIPU_API_KEY


class GLMOCRClient:
    """
    智谱 GLM-OCR 客户端
    支持布局解析和文字检测，返回像素级坐标
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or ZHIPU_API_KEY
        self._client = ZaiClient(api_key=self.api_key)

    def detect_text(self, image_path: str | Path) -> list[dict]:
        """
        检测图片中的所有文字元素，返回坐标和内容

        Args:
            image_path: 图片路径

        Returns:
            list of {text, x, y, x1, y1, x2, y2, label}
        """
        image_path = str(image_path)
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        resp = self._client.layout_parsing.create(
            model="glm-ocr",
            file=f"data:image/png;base64,{img_b64}",
        )

        results = []
        if not resp.layout_details:
            return results

        page = resp.layout_details[0]
        for el in page:
            if el.label == "text" and el.content and el.bbox_2d:
                x1, y1, x2, y2 = el.bbox_2d
                results.append({
                    "text": el.content,
                    "x1": int(x1),
                    "y1": int(y1),
                    "x2": int(x2),
                    "y2": int(y2),
                    "x": int((x1 + x2) / 2),
                    "y": int((y1 + y2) / 2),
                    "label": el.label,
                })

        return results

    def find_text(
        self,
        image_path: str | Path,
        target: str,
        match_mode: Literal["exact", "contains", "fuzzy"] = "contains"
    ) -> tuple[int, int] | None:
        """
        在图片中查找指定文字，返回中心坐标

        Args:
            image_path: 图片路径
            target: 要查找的文字（支持模糊匹配）
            match_mode: 'exact' / 'contains' / 'fuzzy'

        Returns:
            (x, y) 中心像素坐标，未找到返回 None
        """
        elements = self.detect_text(image_path)
        if not elements:
            return None

        target_lower = target.lower().strip()

        best_match = None
        best_score = 0

        for el in elements:
            text = el["text"].lower().strip()

            if match_mode == "exact":
                if text == target_lower:
                    return (el["x"], el["y"])
            elif match_mode == "contains":
                if target_lower in text or text in target_lower:
                    score = 100
                    # 短匹配优先（UI标签 vs 通知正文）
                    if len(text) <= len(target_lower) * 2:
                        score *= 1.3
                    if score > best_score:
                        best_score = score
                        best_match = (el["x"], el["y"])
            else:  # fuzzy
                from difflib import SequenceMatcher
                ratio = SequenceMatcher(None, text, target_lower).ratio()
                if ratio > 0.6 and ratio > best_score:
                    best_score = ratio
                    best_match = (el["x"], el["y"])

        return best_match

    def locate(
        self,
        target: str,
        screenshot_path: str | Path | None = None,
        screenshot_array=None,
    ) -> tuple[int, int] | None:
        """
        定位元素，返回中心坐标

        Args:
            target: 目标文字
            screenshot_path: 截图文件路径
            screenshot_array: 截图 numpy 数组（优先使用）

        Returns:
            (x, y) 坐标
        """
        # 如果有数组，先保存为临时文件
        import tempfile
        import cv2

        if screenshot_array is not None:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                # screenshot_array 是 BGRA 格式
                bgr = cv2.cvtColor(screenshot_array, cv2.COLOR_BGRA2BGR)
                cv2.imwrite(tmp.name, bgr)
                screenshot_path = tmp.name

        if screenshot_path is None:
            raise ValueError("需要提供 screenshot_path 或 screenshot_array")

        # 尝试多级匹配
        # 1. 精确包含匹配
        coords = self.find_text(screenshot_path, target, match_mode="contains")
        if coords:
            logger.debug(f"GLM-OCR matched '{target}' -> {coords}")
            return coords

        # 2. 模糊匹配
        coords = self.find_text(screenshot_path, target, match_mode="fuzzy")
        if coords:
            logger.debug(f"GLM-OCR fuzzy matched '{target}' -> {coords}")
            return coords

        logger.debug(f"GLM-OCR no match for '{target}'")
        return None
