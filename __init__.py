"""
飞书 AI Agent 自动化测试系统
基于视觉大模型（UI-TARS）的 Computer Use Agent
支持飞书 IM、日历、文档、云盘四大模块的自动化功能测试
"""

from .core import FeishuAgent, AgentConfig, AgentResult
from .drivers import ScreenCapture, InputControl
from .llm import UITarsClient, PlannerLLMClient
from .feishu_api import IMClient, CalendarClient, DocClient, DriveClient

__version__ = "0.1.0"
__all__ = [
    "FeishuAgent",
    "AgentConfig",
    "AgentResult",
    "ScreenCapture",
    "InputControl",
    "UITarsClient",
    "PlannerLLMClient",
    "IMClient",
    "CalendarClient",
    "DocClient",
    "DriveClient",
]
