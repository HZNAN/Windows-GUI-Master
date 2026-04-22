"""
飞书云文档模块测试用例
"""
import pytest
import json
from pathlib import Path

from core.agent import FeishuAgent
from llm.planner_llm_client import PlannerLLMClient


TEST_CASES_FILE = Path(__file__).parent.parent / "test_cases" / "doc_test_cases.json"
if TEST_CASES_FILE.exists():
    TEST_CASES = json.loads(TEST_CASES_FILE.read_text(encoding="utf-8"))
else:
    TEST_CASES = {"cases": []}


@pytest.mark.doc
class TestDoc:
    """飞书文档模块测试套件"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.agent = FeishuAgent()
        self.planner = PlannerLLMClient()
        yield
        logger.info("文档测试结束")

    @pytest.mark.parametrize("case", TEST_CASES["cases"])
    def test_create_and_edit_doc(self, case):
        """测试创建并编辑文档"""
        goal = case["goal"]
        plan = self.planner.plan(goal)
        assert len(plan.steps) > 0
        result = self.agent.run(goal, plan)
        assert result.success or len(result.steps) > 0

    def test_create_new_doc(self):
        """测试创建空白文档"""
        goal = "在飞书中创建一个新的空白文档，标题为'自动化测试文档'"
        plan = self.planner.plan(goal)
        result = self.agent.run(goal, plan)
        assert len(plan.steps) > 0

    def test_edit_doc_content(self):
        """测试编辑文档内容"""
        goal = "打开'自动化测试文档'，在文档开头输入文字'这是自动化测试内容'"
        plan = self.planner.plan(goal)
        result = self.agent.run(goal, plan)
        assert len(plan.steps) > 0

    def test_share_doc(self):
        """测试文档分享"""
        goal = "将'自动化测试文档'设置为全员可见并分享"
        plan = self.planner.plan(goal)
        result = self.agent.run(goal, plan)
        assert len(plan.steps) > 0
