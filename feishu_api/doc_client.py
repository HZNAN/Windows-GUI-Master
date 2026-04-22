"""
飞书云文档 API 客户端
用于创建文档、编辑文档内容等操作验证
"""
import requests
from typing import Literal
from loguru import logger

from config.settings import FEISHU_BASE_URL
from .auth import get_feishu_auth


class DocClient:
    """飞书云文档 API 客户端"""

    def __init__(self):
        self.auth = get_feishu_auth()
        self.base_url = FEISHU_BASE_URL
        self._session = requests.Session()

    def _request(
        self, method: str, path: str,
        token_type: Literal["user", "app"] = "app",
        **kwargs
    ) -> dict:
        token = (
            self.auth.get_user_token()
            if token_type == "user"
            else self.auth.get_app_token()
        )
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {token}"}
        resp = self._session.request(method, url, headers=headers, **kwargs)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书文档 API 错误: {data}")
        return data.get("data", {})

    def create_doc(self, title: str, doc_type: str = "doc") -> dict:
        """
        创建空白文档

        Args:
            title: 文档标题
            doc_type: 文档类型，'doc'（传统文档）/ 'docx'（新版文档）

        Returns:
            创建的文档信息（包含 doc_id）
        """
        payload = {"title": title}
        if doc_type == "docx":
            result = self._request("POST", "/docx/v1/documents", json=payload)
        else:
            result = self._request("POST", "/doc/v1/docs", json=payload)
        logger.info(f"文档创建成功: {result.get('doc_id')}")
        return result

    def get_doc(self, doc_id: str, doc_type: str = "docx") -> dict:
        """
        获取文档详情

        Args:
            doc_id: 文档 ID
            doc_type: 'doc' / 'docx'

        Returns:
            文档详情
        """
        if doc_type == "docx":
            return self._request("GET", f"/docx/v1/documents/{doc_id}")
        else:
            return self._request("GET", f"/doc/v1/docs/{doc_id}")

    def list_docs(self, folder_token: str = "", page_size: int = 50) -> list[dict]:
        """
        列出文档列表

        Args:
            folder_token: 文件夹 token，空则列出根目录
            page_size: 每页数量

        Returns:
            文档列表
        """
        params = {"page_size": page_size}
        if folder_token:
            params["folder_token"] = folder_token
        result = self._request("GET", "/drive/v1/files", params=params)
        return result.get("files", [])

    def update_doc_title(self, doc_id: str, title: str, doc_type: str = "docx") -> dict:
        """更新文档标题"""
        payload = {"title": title}
        if doc_type == "docx":
            return self._request("PATCH", f"/docx/v1/documents/{doc_id}", json=payload)
        else:
            return self._request("PUT", f"/doc/v1/docs/{doc_id}/title", json=payload)

    def create_folder(self, name: str, parent_token: str = "") -> dict:
        """
        创建文件夹

        Args:
            name: 文件夹名称
            parent_token: 父文件夹 token，空则在根目录创建

        Returns:
            文件夹信息
        """
        payload = {
            "name": name,
            "folder_token": parent_token,
            "type": "folder"
        }
        result = self._request("POST", "/drive/v1/files/create_folder", json=payload)
        logger.info(f"文件夹创建成功: {result.get('token')}")
        return result

    def get_folder_meta(self, folder_token: str) -> dict:
        """获取文件夹元信息"""
        return self._request("GET", f"/drive/v1/metas/batch_query", params={"request_docs[0][token]": folder_token})

    def close(self):
        self._session.close()
