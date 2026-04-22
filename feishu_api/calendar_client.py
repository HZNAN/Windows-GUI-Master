"""
飞书日历 API 客户端
用于创建日程、查询日程等操作验证
"""
import requests
from datetime import datetime
from typing import Literal
from loguru import logger

from config.settings import FEISHU_BASE_URL
from .auth import get_feishu_auth


class CalendarClient:
    """飞书日历 API 客户端"""

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
            raise RuntimeError(f"飞书日历 API 错误: {data}")
        return data.get("data", {})

    def create_event(
        self,
        summary: str,
        start_time: datetime,
        end_time: datetime,
        description: str = "",
        attendee_ids: list[str] | None = None,
        location: str = ""
    ) -> dict:
        """
        创建日历日程

        Args:
            summary: 日程标题
            start_time: 开始时间（datetime 对象）
            end_time: 结束时间
            description: 日程描述
            attendee_ids: 参会人 open_id 列表
            location: 地点

        Returns:
            创建的日程信息（包含 calendar_id 和 event_id）
        """
        payload = {
            "summary": summary,
            "description": description,
            "location": location,
            "start_time": {
                "timestamp": int(start_time.timestamp()),
                "timezone": "Asia/Shanghai"
            },
            "end_time": {
                "timestamp": int(end_time.timestamp()),
                "timezone": "Asia/Shanghai"
            },
            "attendees": [
                {"type": "user", "user_id": uid}
                for uid in (attendee_ids or [])
            ] if attendee_ids else []
        }
        result = self._request("POST", "/calendar/v4/calendars/primary/events", json=payload)
        logger.info(f"日程创建成功: {result.get('event_id')}")
        return result

    def get_event(self, event_id: str) -> dict:
        """
        获取日程详情（用于验证）

        Args:
            event_id: 日程 ID

        Returns:
            日程详情
        """
        return self._request("GET", f"/calendar/v4/calendars/primary/events/{event_id}")

    def list_events(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page_size: int = 50
    ) -> list[dict]:
        """
        列出日历日程

        Args:
            start_time: 查询开始时间
            end_time: 查询结束时间
            page_size: 每页数量（仅作参考，默认50）

        Returns:
            日程列表
        """
        params = {}
        if start_time:
            params["start_time"] = int(start_time.timestamp())
            params["start_time_type"] = "UTC"
        if end_time:
            params["end_time"] = int(end_time.timestamp())
            params["end_time_type"] = "UTC"
        # 注意：飞书 calendar v4 API 不支持 page_size 作为 query 参数

        result = self._request("GET", "/calendar/v4/calendars/primary/events", params=params)
        return result.get("items", [])

    def delete_event(self, event_id: str):
        """删除日程"""
        self._request("DELETE", f"/calendar/v4/calendars/primary/events/{event_id}")
        logger.info(f"日程已删除: {event_id}")

    def search_events(self, query: str, page_size: int = 20) -> list[dict]:
        """搜索日程"""
        params = {"query": query, "page_size": page_size}
        result = self._request("GET", "/calendar/v4/calendars/primary/events/search", params=params)
        return result.get("items", [])

    def close(self):
        self._session.close()
