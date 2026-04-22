"""
飞书日历模块测试用例
"""
import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta

from core.agent import FeishuAgent
from llm.planner_llm_client import PlannerLLMClient


TEST_CASES_FILE = Path(__file__).parent.parent / "test_cases" / "calendar_test_cases.json"
if TEST_CASES_FILE.exists():
    TEST_CASES = json.loads(TEST_CASES_FILE.read_text(encoding="utf-8"))
else:
    TEST_CASES = {"cases": []}


@pytest.mark.calendar
class TestCalendar:
    """飞书日历模块测试套件"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.agent = FeishuAgent()
        self.planner = PlannerLLMClient()
        yield
        logger.info("日历测试结束")

    @pytest.mark.parametrize("case", TEST_CASES["cases"])
    def test_create_event(self, case):
        """测试创建日历日程"""
        goal = case["goal"]
        plan = self.planner.plan(goal)
        assert len(plan.steps) > 0
        result = self.agent.run(goal, plan)
        assert result.success or len(result.steps) > 0

    def test_create_tomorrow_meeting(self):
        """
        测试创建明天下午2点的会议日程
        """
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        goal = f"在飞书日历中创建日程：明天下午2点开会，标题：团队周会"
        plan = self.planner.plan(goal)
        result = self.agent.run(goal, plan)
        assert len(plan.steps) > 0

    def test_search_and_view_event(self):
        """测试搜索并查看日程"""
        goal = "在日历中搜索'周会'日程并查看详情"
        plan = self.planner.plan(goal)
        result = self.agent.run(goal, plan)
        assert len(plan.steps) > 0
