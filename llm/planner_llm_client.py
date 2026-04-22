"""
规划层 LLM 客户端
用于将高层测试目标分解为可执行步骤序列
支持多种 LLM：OpenAI GPT-4o / 智谱 GLM / 豆包 等
"""
import json
import requests
from typing import Literal
from dataclasses import dataclass
from loguru import logger

from config.settings import (
    PLANNER_LLM_PROVIDER, PLANNER_LLM_API_KEY,
    PLANNER_LLM_BASE_URL, PLANNER_LLM_MODEL
)


@dataclass
class PlannedStep:
    """规划出的单个步骤"""
    action: str       # click / type / press / scroll / wait
    target: str | None
    description: str   # 步骤描述
    x: int | None = None
    y: int | None = None
    text: str | None = None
    key: str | None = None


@dataclass
class ExecutionPlan:
    """完整的执行计划"""
    goal: str
    steps: list[PlannedStep]
    raw_response: str


class PlannerLLMClient:
    """
    任务规划 LLM 客户端
    调用大语言模型将高层目标分解为步骤序列
    """

    SYSTEM_PROMPT = """You are a task planning assistant. Decompose high-level goals into ordered executable steps.

Output format: Strict JSON object with 'goal' field and 'steps' array.
Each step MUST contain these exact fields:
- action: action type (click / type / press / scroll / wait)
- target: semantic target name (e.g. "search box", "send button"), null if using coordinates
- x, y: pixel coordinates (only when action=click with known coordinates), null otherwise
- text: input text (only when action=type)
- key: key name (only when action=press)
- description: Chinese description of the step

Rules:
1. Steps must be minimal atomic operations
2. Do NOT assume element positions, only provide semantic targets
3. type actions must provide both target and text
4. Return empty steps array if task is impossible
5. Output ONLY the JSON, no markdown, no explanation"""

    FEW_SHOT_EXAMPLES = """
Example 1:
Input: Send a message to Zhang San saying 'Hello'
Output:
{"goal": "Send a message to Zhang San saying 'Hello'", "steps": [{"action": "click", "target": "Feishu icon", "x": null, "y": null, "text": null, "description": "Open Feishu app"}, {"action": "click", "target": "Search box", "x": null, "y": null, "text": null, "description": "Click search box"}, {"action": "type", "target": "Search box", "x": null, "y": null, "text": "Zhang San", "description": "Search for Zhang San"}, {"action": "click", "target": "Zhang San chat", "x": null, "y": null, "text": null, "description": "Open chat with Zhang San"}, {"action": "type", "target": "Input box", "x": null, "y": null, "text": "Hello", "description": "Type message content"}, {"action": "click", "target": "Send button", "x": null, "y": null, "text": null, "description": "Click send"}]}

Example 2:
Input: Create a calendar event for tomorrow 2pm meeting
Output:
{"goal": "Create calendar event for tomorrow 2pm meeting", "steps": [{"action": "click", "target": "Feishu icon", "x": null, "y": null, "text": null, "description": "Open Feishu"}, {"action": "click", "target": "Calendar icon", "x": null, "y": null, "text": null, "description": "Open calendar"}, {"action": "click", "target": "New event button", "x": null, "y": null, "text": null, "description": "Click new event"}, {"action": "type", "target": "Title input", "x": null, "y": null, "text": "Meeting", "description": "Enter event title"}, {"action": "click", "target": "Date picker", "x": null, "y": null, "text": null, "description": "Select tomorrow's date"}, {"action": "type", "target": "Time input", "x": null, "y": null, "text": "14:00", "description": "Enter time 2pm"}, {"action": "click", "target": "Save button", "x": null, "y": null, "text": null, "description": "Save event"}]}"""

    def __init__(
        self,
        provider: Literal["openai", "zhipu", "doubao"] = PLANNER_LLM_PROVIDER,
        api_key: str = PLANNER_LLM_API_KEY,
        base_url: str = PLANNER_LLM_BASE_URL,
        model: str = PLANNER_LLM_MODEL
    ):
        from config.settings import ZHIPU_API_KEY
        self.provider = provider
        # 当 provider 为 zhipu 时，使用 ZHIPU_API_KEY
        if provider == "zhipu" and not api_key:
            api_key = ZHIPU_API_KEY
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def plan(self, goal: str) -> ExecutionPlan:
        """
        将高层目标分解为执行计划

        Args:
            goal: 高层测试目标，如 "给张三发送消息：你好"

        Returns:
            ExecutionPlan 对象
        """
        logger.info(f"Planning request: {goal[:50]}...")
        user_content = f"{self.FEW_SHOT_EXAMPLES}\n\nInput: {goal}\nOutput:"

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        try:
            if self.provider == "openai":
                response = self._call_openai(messages)
            elif self.provider == "zhipu":
                response = self._call_zhipu(messages)
            elif self.provider == "doubao":
                response = self._call_doubao(messages)
            else:
                raise ValueError(f"不支持的 LLM Provider: {self.provider}")

            plan_data = self._parse_plan(response)
            return plan_data
        except Exception as e:
            logger.error(f"规划 LLM 调用失败: {e}")
            raise

    def _call_openai(self, messages: list[dict]) -> str:
        """调用 OpenAI 兼容 API"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2048
        }
        resp = self._session.post(
            f"{self.base_url}/chat/completions",
            json=payload, timeout=30
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_zhipu(self, messages: list[dict]) -> str:
        """调用智谱 GLM API"""
        from config.settings import ZHIPU_API_URL
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2048
        }
        resp = self._session.post(
            ZHIPU_API_URL,
            json=payload, timeout=30
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_doubao(self, messages: list[dict]) -> str:
        """调用豆包 API（与 OpenAI 兼容）"""
        return self._call_openai(messages)

    def _parse_plan(self, response: str) -> ExecutionPlan:
        """解析 LLM 返回的 JSON，构造 ExecutionPlan"""
        try:
            # 尝试从响应中提取 JSON
            text = response.strip()
            # 去掉可能的 markdown 代码块
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])

            data = json.loads(text)
            steps = []
            for item in data.get("steps", []):
                steps.append(PlannedStep(
                    action=item.get("action", "click"),
                    target=item.get("target"),
                    description=item.get("description", ""),
                    x=item.get("x"),
                    y=item.get("y"),
                    text=item.get("text"),
                    key=item.get("key")
                ))

            return ExecutionPlan(
                goal=data.get("goal", ""),
                steps=steps,
                raw_response=response
            )
        except json.JSONDecodeError as e:
            logger.error(f"规划响应 JSON 解析失败: {e}\n原始响应: {response[:500]}")
            raise
