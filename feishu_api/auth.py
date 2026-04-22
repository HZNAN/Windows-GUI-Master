"""
飞书 API 鉴权管理
支持用户 Token（User Access Token）和应用 Token（App Access Token）
"""
import time
import requests
from dataclasses import dataclass
from loguru import logger

from config.settings import (
    FEISHU_APP_ID, FEISHU_APP_SECRET,
    FEISHU_USER_TOKEN_URL, FEISHU_APP_TOKEN_URL,
    FEISHU_BASE_URL
)


@dataclass
class TokenInfo:
    """Token 信息"""
    token: str
    expire_time: float  # 过期时间戳（秒）


class FeishuAuth:
    """
    飞书鉴权管理器
    自动管理 Token 刷新，对外暴露统一接口
    """

    def __init__(self, app_id: str = FEISHU_APP_ID, app_secret: str = FEISHU_APP_SECRET):
        self.app_id = app_id
        self.app_secret = app_secret
        self._user_token: TokenInfo | None = None
        self._app_token: TokenInfo | None = None
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def get_user_token(self, force_refresh: bool = False) -> str:
        """
        获取用户 Access Token（有效期 2 小时，自动续期）

        Args:
            force_refresh: 强制刷新

        Returns:
            用户 Token 字符串
        """
        if not force_refresh and self._is_token_valid(self._user_token):
            return self._user_token.token

        logger.info("刷新用户 Access Token...")
        payload = {
            "grant_type": "refresh_token",
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        resp = self._session.post(FEISHU_USER_TOKEN_URL, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"获取用户 Token 失败: {data}")

        # 飞书 v3 auth API 返回格式：token 在根层级
        token_data = data.get("data", data)  # 兼容有无 data 包装两种格式
        self._user_token = TokenInfo(
            token=token_data.get("access_token", token_data.get("app_access_token", "")),
            expire_time=time.time() + token_data.get("expire", 7200) - 60
        )
        logger.info("用户 Token 获取成功")
        return self._user_token.token

    def get_app_token(self, force_refresh: bool = False) -> str:
        """
        获取应用 Access Token

        Args:
            force_refresh: 强制刷新

        Returns:
            应用 Token 字符串
        """
        if not force_refresh and self._is_token_valid(self._app_token):
            return self._app_token.token

        logger.info("刷新应用 Access Token...")
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        resp = self._session.post(FEISHU_APP_TOKEN_URL, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"获取应用 Token 失败: {data}")

        # 飞书 v3 auth API 返回格式：token 在根层级
        token_data = data.get("data", data)  # 兼容有无 data 包装两种格式
        self._app_token = TokenInfo(
            token=token_data["app_access_token"],
            expire_time=time.time() + token_data.get("expire", 7200) - 60
        )
        logger.info("应用 Token 获取成功")
        return self._app_token.token

    def get_tenant_access_token(self) -> str:
        """获取 tenant_access_token（与 app_token 相同）"""
        return self.get_app_token()

    @staticmethod
    def _is_token_valid(token_info: TokenInfo | None) -> bool:
        """检查 Token 是否有效"""
        if token_info is None:
            return False
        return time.time() < token_info.expire_time

    def invalidate_user_token(self):
        """手动失效用户 Token（重新登录时调用）"""
        self._user_token = None
        logger.info("用户 Token 已失效")

    def close(self):
        self._session.close()


# 全局单例
_auth: FeishuAuth | None = None


def get_feishu_auth() -> FeishuAuth:
    global _auth
    if _auth is None:
        _auth = FeishuAuth()
    return _auth
