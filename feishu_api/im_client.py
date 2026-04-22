"""
飞书 IM（即时通讯）API 客户端
用于发送消息、查询消息列表等操作验证
"""
import requests
from typing import Literal
from loguru import logger

from config.settings import FEISHU_BASE_URL
from .auth import get_feishu_auth


class IMClient:
    """飞书 IM 模块 API 客户端"""

    def __init__(self):
        self.auth = get_feishu_auth()
        self.base_url = FEISHU_BASE_URL
        self._session = requests.Session()

    def _request(
        self, method: str, path: str,
        token_type: Literal["user", "app"] = "app",
        **kwargs
    ) -> dict:
        """统一请求方法，默认使用 app token"""
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
            raise RuntimeError(f"飞书 API 错误: {data}")
        return data.get("data", {})

    def send_text_message(
        self, receive_id_type: str, receive_id: str, msg_content: str
    ) -> dict:
        """
        发送文本消息

        Args:
            receive_id_type: 'open_id' / 'union_id' / 'user_id' / 'email'
            receive_id: 接收者 ID
            msg_content: 消息文本内容

        Returns:
            API 响应数据
        """
        payload = {
            "receive_id_type": receive_id_type,
            "receive_id": receive_id,
            "msg_type": "text",
            "content": '{"text":"' + msg_content + '"}'
        }
        return self._request("POST", "/im/v1/messages", json=payload, token_type="user")

    def send_image_message(self, receive_id_type: str, receive_id: str, image_key: str) -> dict:
        """发送图片消息"""
        payload = {
            "receive_id_type": receive_id_type,
            "receive_id": receive_id,
            "msg_type": "image",
            "content": '{"image_key":"' + image_key + '"}'
        }
        return self._request("POST", "/im/v1/messages", json=payload)

    def get_messages(
        self, container_id_type: str, container_id: str,
        start_time: int | None = None, end_time: int | None = None
    ) -> list[dict]:
        """
        获取消息列表（用于验证消息是否发送成功）

        Args:
            container_id_type: 'chat'（群）/ 'p2p'（单聊）
            container_id: 会话 ID
            start_time: 开始时间（毫秒时间戳）
            end_time: 结束时间（毫秒时间戳）

        Returns:
            消息列表
        """
        params = {"container_id_type": container_id_type, "container_id": container_id}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        result = self._request("GET", "/im/v1/messages", params=params)
        return result.get("items", [])

    def get_chat_info(self, chat_id: str) -> dict:
        """获取群聊信息"""
        return self._request("GET", f"/im/v1/chats/{chat_id}")

    def search_chats(self, query: str, page_size: int = 20) -> list[dict]:
        """
        搜索群聊

        Args:
            query: 搜索关键词
            page_size: 每页数量

        Returns:
            匹配的群聊列表
        """
        result = self._request(
            "GET", "/im/v1/chats",
            params={"query": query, "page_size": page_size}
        )
        return result.get("items", [])

    def search_users(self, query: str, page_size: int = 20) -> list[dict]:
        """
        搜索用户

        Args:
            query: 用户名或邮箱等搜索词

        Returns:
            匹配的用户列表
        """
        result = self._request(
            "GET", "/contact/v3/users/batch_get_id",
            params={"user_id_type": "open_id", "query": query}
        )
        return result.get("users", [])

    def upload_image(self, image_path: str) -> str:
        """
        上传图片到飞书，获取 image_key

        Returns:
            image_key 字符串
        """
        import pathlib
        files = {
            "image": (pathlib.Path(image_path).name, open(image_path, "rb"), "image/png")
        }
        token = self.auth.get_user_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = self._session.post(
            f"{self.base_url}/im/v1/images",
            headers=headers, files=files
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"图片上传失败: {data}")
        return data["data"]["image_key"]

    def close(self):
        self._session.close()
