"""
元素定位器
通过 GLM-OCR 文字识别 + GLM-4V 视觉模型定位，将语义 target 转换为屏幕坐标
"""
import cv2
import numpy as np
from pathlib import Path
from typing import Literal
from loguru import logger

from config.settings import SAMPLE_IMAGES_DIR
from drivers.screen_capture import get_screen_capture
from llm.glm_vision_client import GLMVisionClient, UIAction


class ElementLocator:
    """
    元素定位器
    策略：
    1. 优先用 GLM-OCR 精确文字定位（智谱官方 OCR，精确像素坐标）
    2. 若 GLM-OCR 匹配失败，调用 GLM-4V 视觉模型定位
    3. 若 GLM-4V 失败，尝试 OpenCV 模板匹配
    """

    def __init__(self, vision_client: GLMVisionClient | None = None):
        self.vision_client = vision_client or GLMVisionClient()
        self.screenshot = get_screen_capture()
        self._ocr_client = None

    def _get_ocr_client(self):
        """延迟初始化 GLM-OCR 客户端"""
        if self._ocr_client is None:
            from llm.glm_ocr_client import GLMOCRClient
            self._ocr_client = GLMOCRClient()
            logger.debug("GLM-OCR Client initialized")
        return self._ocr_client

    def locate(
        self,
        target: str,
        screenshot: np.ndarray | None = None,
        method: Literal["ocr", "template", "ui_tars", "auto"] = "auto"
    ) -> tuple[int, int] | None:
        """
        定位元素，返回屏幕坐标

        Args:
            target: 语义目标描述，如 "发送按钮"、"搜索框"
            screenshot: 当前截图（BGRA numpy array），若为 None 则自动截取
            method: 'ocr' / 'template' / 'ui_tars' / 'auto'

        Returns:
            (x, y) 坐标，若定位失败返回 None
        """
        if screenshot is None:
            screenshot = self.screenshot.capture()

        # 方法 1：OCR 精确文字定位（优先）
        if method in ("ocr", "auto"):
            result = self._locate_by_ocr(target, screenshot)
            if result:
                logger.info(f"OCR 定位成功: {target} -> {result}")
                return result

        # 方法 2：GLM-4V 视觉定位
        if method in ("ui_tars", "auto"):
            result = self._locate_by_ui_tars(target, screenshot)
            if result:
                logger.info(f"GLM-4V 定位成功: {target} -> {result}")
                return result

        # 方法 3：模板匹配
        if method in ("template", "auto"):
            result = self._locate_by_template(target, screenshot)
            if result:
                logger.info(f"模板匹配成功: {target} -> {result}")
                return result

        logger.warning(f"元素定位失败: {target}")
        return None

    def _locate_by_template(self, target: str, screenshot: np.ndarray) -> tuple[int, int] | None:
        """
        在样本库中查找目标元素的模板图像，用 OpenCV 匹配
        样本库目录：.sample_images/，文件命名规则：{target_name}.png
        """
        target_normalized = self._normalize_target_name(target)
        sample_path = SAMPLE_IMAGES_DIR / f"{target_normalized}.png"

        if not sample_path.exists():
            matches = list(SAMPLE_IMAGES_DIR.glob(f"*{target_normalized}*.png"))
            if matches:
                sample_path = matches[0]
            else:
                return None

        try:
            template = cv2.imread(str(sample_path), cv2.IMREAD_COLOR)
            if template is None:
                return None

            screenshot_bgr = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            res = cv2.matchTemplate(screenshot_bgr, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val >= 0.7:
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return (center_x, center_y)
        except Exception as e:
            logger.debug(f"模板匹配异常: {e}")

        return None

    def _locate_by_ocr(self, target: str, screenshot: np.ndarray) -> tuple[int, int] | None:
        """
        用 GLM-OCR 在截图中精确查找文字目标，返回中心像素坐标
        """
        try:
            ocr_client = self._get_ocr_client()
            coords = ocr_client.locate(target, screenshot_array=screenshot)
            if coords:
                logger.debug(f"GLM-OCR matched '{target}' -> {coords}")
                return coords
        except Exception as e:
            logger.debug(f"GLM-OCR 定位异常: {e}")
        return None

    def _locate_by_ui_tars(
        self, target: str, screenshot: np.ndarray
    ) -> tuple[int, int] | None:
        """
        调用 GLM-4V 视觉模型在当前截图中定位元素（强制返回像素坐标）
        """
        try:
            from PIL import Image
            import io, re, json, base64

            screenshot_bgr = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            img_pil = Image.fromarray(screenshot_bgr)
            img_bytes = io.BytesIO()
            img_pil.save(img_bytes, format="PNG")
            img_bytes = img_bytes.getvalue()

            instruction = (
                f'Find the center pixel coordinates of "{target}" in this screenshot. '
                'Return ONLY valid JSON: {"x": number, "y": number, "found": true/false}. '
                'If not found, return: {"found": false}. '
                'x and y must be pixel numbers from the top-left corner (0,0).'
            )

            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            payload = {
                "model": "glm-4v",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}},
                        {"type": "text", "text": instruction}
                    ]
                }],
                "temperature": 0.1,
                "max_tokens": 200
            }

            from config.settings import ZHIPU_API_URL
            resp = self.vision_client._session.post(
                ZHIPU_API_URL, json=payload, timeout=30
            )
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]

            m = re.search(r'\{.*\}', content, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                if data.get("found") and "x" in data and "y" in data:
                    coords = (int(data["x"]), int(data["y"]))
                    logger.info(f"GLM-4V 定位成功: {target} -> {coords}")
                    return coords

            logger.debug(f"GLM-4V 定位失败，内容: {content[:200]}")
        except Exception as e:
            logger.debug(f"GLM-4V 定位异常: {e}")

        return None

    @staticmethod
    def _normalize_target_name(target: str) -> str:
        """标准化目标名称，用于匹配文件名"""
        import re
        target = target.lower().strip()
        target = re.sub(r"[^\w\u4e00-\u9fff]", "_", target)
        target = re.sub(r"_+", "_", target)
        return target

    def save_sample(self, target: str, screenshot: np.ndarray, bbox: tuple[int, int, int, int]):
        """
        保存成功定位的截图样本，供后续模板匹配使用
        """
        x1, y1, x2, y2 = bbox
        screenshot_bgr = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
        crop = screenshot_bgr[y1:y2, x1:x2]

        target_normalized = self._normalize_target_name(target)
        save_path = SAMPLE_IMAGES_DIR / f"{target_normalized}.png"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(save_path), crop)
        logger.info(f"样本已保存: {save_path}")
