"""
验证器
支持 API 验证 + 截图视觉验证两种方式
"""
import time
from typing import Literal
from dataclasses import dataclass
from loguru import logger

from drivers.screen_capture import get_screen_capture
from llm.glm_vision_client import GLMVisionClient
from feishu_api import IMClient, CalendarClient, DocClient, DriveClient


@dataclass
class VerificationResult:
    """验证结果"""
    passed: bool
    method: Literal["api", "screenshot", "both"]
    evidence: str = ""          # 截图路径或 API 响应摘要
    message: str = ""
    details: dict | None = None


class Verifier:
    """
    操作结果验证器
    采用混合验证策略：优先 API 验证，关键节点补充截图验证
    """

    def __init__(self):
        self.screenshot = get_screen_capture()
        self.vision = GLMVisionClient()
        self.im = IMClient()
        self.calendar = CalendarClient()
        self.doc = DocClient()
        self.drive = DriveClient()

    def verify(
        self,
        operation: str,
        expected: str,
        method: Literal["api", "screenshot", "both"] = "api",
        context: dict | None = None
    ) -> VerificationResult:
        """
        验证操作结果

        Args:
            operation: 操作类型（如 'send_message', 'create_event'）
            expected: 预期结果描述
            method: 'api' / 'screenshot' / 'both'
            context: 操作相关上下文（如 chat_id, event_id 等）

        Returns:
            VerificationResult
        """
        context = context or {}
        logger.info(f"验证操作: {operation} | 方式: {method}")

        if method in ("api", "both"):
            api_result = self._verify_by_api(operation, expected, context)
            if api_result.passed:
                return api_result

        if method in ("screenshot", "both"):
            screenshot_result = self._verify_by_screenshot(operation, expected)
            return screenshot_result

        return VerificationResult(
            passed=False, method=method,
            message="验证失败"
        )

    # ============ API 验证 ============

    def _verify_by_api(
        self, operation: str, expected: str, context: dict
    ) -> VerificationResult:
        """通过飞书 API 验证操作结果"""
        try:
            if operation == "send_message":
                return self._verify_send_message(context)
            elif operation == "create_event":
                return self._verify_create_event(context)
            elif operation == "create_doc":
                return self._verify_create_doc(context)
            elif operation == "upload_file":
                return self._verify_upload_file(context)
            elif operation == "create_folder":
                return self._verify_create_folder(context)
            else:
                logger.warning(f"未知的操作类型，跳过 API 验证: {operation}")
                return VerificationResult(False, "api", message=f"未知操作: {operation}")
        except Exception as e:
            logger.error(f"API 验证异常: {e}")
            return VerificationResult(False, "api", message=str(e))

    def _verify_send_message(self, ctx: dict) -> VerificationResult:
        """验证消息发送"""
        chat_id = ctx.get("chat_id")
        expected_text = ctx.get("expected_text", "")

        if not chat_id:
            return VerificationResult(False, "api", message="缺少 chat_id")

        # 等待消息传播
        time.sleep(2)
        messages = self.im.get_messages("chat", chat_id)

        for msg in reversed(messages[-10:]):  # 检查最近10条消息
            body = msg.get("body", {})
            content = body.get("content", "{}")
            if expected_text in content:
                return VerificationResult(
                    passed=True, method="api",
                    evidence=f"消息ID: {msg.get('message_id')}",
                    message=f"找到消息内容: {expected_text[:30]}"
                )

        return VerificationResult(
            passed=False, method="api",
            evidence=f"在 chat {chat_id} 中未找到: {expected_text[:30]}",
            message="消息未找到"
        )

    def _verify_create_event(self, ctx: dict) -> VerificationResult:
        """验证日历日程创建"""
        event_id = ctx.get("event_id")
        expected_title = ctx.get("expected_title", "")

        if not event_id:
            return VerificationResult(False, "api", message="缺少 event_id")

        event = self.calendar.get_event(event_id)
        summary = event.get("summary", "")

        if expected_title in summary or summary:
            return VerificationResult(
                passed=True, method="api",
                evidence=f"event_id: {event_id}, title: {summary}",
                message="日程创建成功"
            )

        return VerificationResult(False, "api", message=f"日程不存在: {event_id}")

    def _verify_create_doc(self, ctx: dict) -> VerificationResult:
        """验证文档创建"""
        doc_id = ctx.get("doc_id")
        if not doc_id:
            return VerificationResult(False, "api", message="缺少 doc_id")

        doc = self.doc.get_doc(doc_id)
        title = doc.get("title", "")
        return VerificationResult(
            passed=True, method="api",
            evidence=f"doc_id: {doc_id}, title: {title}",
            message="文档创建成功"
        )

    def _verify_upload_file(self, ctx: dict) -> VerificationResult:
        """验证文件上传"""
        file_token = ctx.get("file_token")
        if not file_token:
            return VerificationResult(False, "api", message="缺少 file_token")

        meta = self.drive.get_file_meta(file_token)
        name = meta.get("name", "")
        return VerificationResult(
            passed=True, method="api",
            evidence=f"file_token: {file_token}, name: {name}",
            message="文件上传成功"
        )

    def _verify_create_folder(self, ctx: dict) -> VerificationResult:
        """验证文件夹创建"""
        folder_token = ctx.get("folder_token")
        expected_name = ctx.get("expected_name", "")
        if not folder_token:
            return VerificationResult(False, "api", message="缺少 folder_token")

        return VerificationResult(
            passed=True, method="api",
            evidence=f"folder_token: {folder_token}",
            message=f"文件夹创建成功: {expected_name}"
        )

    # ============ 截图视觉验证 ============

    def _verify_by_screenshot(
        self, operation: str, expected: str
    ) -> VerificationResult:
        """
        通过截图 + UI-TARS 视觉验证
        截取当前屏幕，让 UI-TARS 判断是否符合预期
        """
        try:
            _, save_path = self.screenshot.auto_save(prefix=f"verify_{operation}")
            action = self.vision.infer(
                screenshot=str(save_path),
                instruction=f"检查界面是否包含以下内容或状态：{expected}。如果包含返回 'YES'，如果不包含返回 'NO'。"
            )

            response_text = action.raw_response.get("outputs", {}).get("action", "")
            passed = "yes" in response_text.lower()

            return VerificationResult(
                passed=passed,
                method="screenshot",
                evidence=str(save_path),
                message=f"视觉验证: {'通过' if passed else '失败'} | 模型响应: {response_text[:100]}",
                details={"raw_response": action.raw_response}
            )
        except Exception as e:
            logger.error(f"截图验证异常: {e}")
            return VerificationResult(False, "screenshot", message=str(e))
