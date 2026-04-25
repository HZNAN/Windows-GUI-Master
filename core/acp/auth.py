"""
ACP Bearer Token 认证
"""
import secrets
from typing import Optional

from loguru import logger


class ACPAuthError(Exception):
    """认证错误"""

    pass


class ACPAuth:
    """Bearer Token 认证处理器"""

    def __init__(self, token: Optional[str] = None):
        """
        初始化认证器

        Args:
            token: 预配置的 token，若为 None 则从环境变量读取
        """
        if token is None:
            from config.settings import os as _os
            token = _os.getenv("ACP_TOKEN", "")

        self._token = token
        self._enabled = bool(token)

        if self._enabled:
            logger.info(f"ACP authentication enabled")
        else:
            logger.warning("ACP authentication disabled (no token configured)")

    @property
    def is_enabled(self) -> bool:
        """是否启用了认证"""
        return self._enabled

    def validate(self, token: str) -> bool:
        """
        验证 token 是否合法

        Args:
            token: 待验证的 token

        Returns:
            是否验证通过
        """
        if not self._enabled:
            return True

        if not token:
            return False

        # 使用 constant-time 比较防止时序攻击
        return secrets.compare_digest(token, self._token)

    def extract_token(self, authorization: Optional[str]) -> Optional[str]:
        """
        从 Authorization header 中提取 token

        Args:
            authorization: Authorization header 值

        Returns:
            提取的 token，若失败返回 None
        """
        if not authorization:
            return None

        parts = authorization.split(" ", 1)
        if len(parts) != 2:
            return None

        scheme, credentials = parts
        if scheme.lower() != "bearer":
            return None

        return credentials

    def validate_request(self, authorization: Optional[str]) -> bool:
        """
        验证请求的认证信息

        Args:
            authorization: Authorization header 值

        Returns:
            是否验证通过
        """
        if not self._enabled:
            return True

        token = self.extract_token(authorization)
        if not token:
            logger.warning("Missing or invalid Authorization header")
            return False

        if not self.validate(token):
            logger.warning("Invalid ACP token")
            return False

        return True
