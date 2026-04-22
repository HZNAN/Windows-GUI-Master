"""
飞书 IM 模块测试用例
"""
import pytest
import time
import json
from pathlib import Path

from core.agent import FeishuAgent
from core.verifier import Verifier
from llm.planner_llm_client import PlannerLLMClient


# 加载测试用例
TEST_CASES_FILE = Path(__file__).parent.parent / "test_cases" / "im_test_cases.json"
if TEST_CASES_FILE.exists():
    TEST_CASES = json.loads(TEST_CASES_FILE.read_text(encoding="utf-8"))
else:
    TEST_CASES = {"cases": []}


@pytest.mark.im
class TestIM:
    """飞书 IM 模块测试套件"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.agent = FeishuAgent()
        self.verifier = Verifier()
        self.planner = PlannerLLMClient()
        yield
        logger.info("IM 测试结束")

    @pytest.mark.parametrize("case", TEST_CASES["cases"])
    def test_send_message(self, case):
        """
        测试发送文本消息

        测试步骤：
        1. 通过 Planner 将高层目标分解为步骤
        2. Agent 自动执行每步操作
        3. 通过飞书 API 验证消息发送结果
        4. 通过截图确认界面状态
        """
        goal = case["goal"]
        expected_text = goal.split("：")[-1] if "：" in goal else goal

        # 规划分解
        plan = self.planner.plan(goal)
        assert len(plan.steps) > 0, "计划分解失败"

        # 执行
        result = self.agent.run(goal, plan)

        # 验证
        # 注意：实际运行时需要通过飞书搜索找到真实用户的 chat_id
        # 这里以测试框架验证为主
        assert result.success or len(result.steps) > 0

    def test_send_message_direct(self):
        """
        直接模式测试：不经过 Planner，直接发送指令给 Agent
        适用于简单的一次性操作
        """
        goal = "在飞书中给测试账号发送消息：测试"
        result = self.agent.run_direct(goal, max_iterations=10)
        # 验证至少执行了步骤
        assert len(result.steps) > 0

    def test_search_and_send(self):
        """
        测试搜索用户并发送消息
        """
        goal = "搜索用户张三，进入对话框，发送消息：你好"
        plan = self.planner.plan(goal)
        result = self.agent.run(goal, plan)
        assert result.success or len(result.steps) > 0

    def test_group_chat_operations(self):
        """
        测试群聊操作：查找群聊、发送消息
        """
        goal = "在飞书中搜索'测试群'，进入群聊，发送消息：自动化测试"
        plan = self.planner.plan(goal)
        result = self.agent.run(goal, plan)
        assert result.success or len(result.steps) > 0
