"""
飞书云盘（Drive）API 客户端
用于上传文件、管理文件夹等操作验证
"""
import requests
from typing import Literal
from pathlib import Path
from loguru import logger

from config.settings import FEISHU_BASE_URL
from .auth import get_feishu_auth


class DriveClient:
    """飞书云盘 API 客户端"""

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
            raise RuntimeError(f"飞书云盘 API 错误: {data}")
        return data.get("data", {})

    def upload_file(
        self, file_path: str | Path, parent_token: str = "", file_name: str | None = None
    ) -> dict:
        """
        上传文件到云盘

        Args:
            file_path: 本地文件路径
            parent_token: 目标文件夹 token，空则上传到根目录
            file_name: 可选，指定云盘中的文件名

        Returns:
            文件信息（包含 token / file_id）
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        name = file_name or path.name
        with open(path, "rb") as f:
            files = {"file": (name, f, "application/octet-stream")}
            data_form = {"file_name": name, "parent_tokens": [parent_token] if parent_token else []}
            result = self._request(
                "POST", "/drive/v1/files/upload_all",
                files=files, data=data_form
            )

        logger.info(f"文件上传成功: {result.get('file_token')}")
        return result

    def get_file_meta(self, file_token: str) -> dict:
        """
        获取文件元信息

        Args:
            file_token: 文件 token

        Returns:
            文件元信息
        """
        return self._request(
            "GET", "/drive/v1/metas/batch_query",
            params={"request_docs[0][token]": file_token}
        )

    def list_folder(self, folder_token: str = "", page_size: int = 50) -> list[dict]:
        """
        列出文件夹内容

        Args:
            folder_token: 文件夹 token，空则列出根目录
            page_size: 每页数量

        Returns:
            文件/文件夹列表
        """
        params = {"page_size": page_size}
        if folder_token:
            params["folder_token"] = folder_token

        result = self._request("GET", "/drive/v1/files", params=params)
        return result.get("files", [])

    def delete_file(self, file_token: str):
        """
        删除文件/文件夹

        Args:
            file_token: 文件 token
        """
        self._request("DELETE", f"/drive/v1/files/{file_token}")
        logger.info(f"文件已删除: {file_token}")

    def download_file(self, file_token: str, save_path: str | Path) -> Path:
        """
        下载文件

        Args:
            file_token: 文件 token
            save_path: 保存路径

        Returns:
            下载后的文件路径
        """
        token = self.auth.get_user_token()
        url = f"{self.base_url}/drive/v1/files/{file_token}/download"
        headers = {"Authorization": f"Bearer {token}"}

        resp = self._session.get(url, headers=headers, stream=True)
        resp.raise_for_status()

        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"文件下载成功: {save_path}")
        return save_path

    def create_folder(self, name: str, parent_token: str = "") -> dict:
        """
        创建文件夹

        Args:
            name: 文件夹名称
            parent_token: 父文件夹 token

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

    def close(self):
        self._session.close()
