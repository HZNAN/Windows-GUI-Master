"""
飞书云盘模块测试用例
"""
import pytest
import json
from pathlib import Path

from core.agent import FeishuAgent
from llm.planner_llm_client import PlannerLLMClient


TEST_CASES_FILE = Path(__file__).parent.parent / "test_cases" / "drive_test_cases.json"
if TEST_CASES_FILE.exists():
    TEST_CASES = json.loads(TEST_CASES_FILE.read_text(encoding="utf-8"))
else:
    TEST_CASES = {"cases": []}


@pytest.mark.drive
class TestDrive:
    """飞书云盘模块测试套件"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.agent = FeishuAgent()
        self.planner = PlannerLLMClient()
        yield
        logger.info("云盘测试结束")

    @pytest.mark.parametrize("case", TEST_CASES["cases"])
    def test_drive_operations(self, case):
        """测试云盘操作"""
        goal = case["goal"]
        plan = self.planner.plan(goal)
        assert len(plan.steps) > 0
        result = self.agent.run(goal, plan)
        assert result.success or len(result.steps) > 0

    def test_create_folder(self):
        """测试创建文件夹"""
        goal = "在飞书云盘中创建一个新文件夹，名称为'自动化测试'"
        plan = self.planner.plan(goal)
        result = self.agent.run(goal, plan)
        assert len(plan.steps) > 0

    def test_upload_file(self):
        """测试上传文件到云盘"""
        goal = "将本地文件 test.txt 上传到飞书云盘根目录"
        plan = self.planner.plan(goal)
        result = self.agent.run(goal, plan)
        assert len(plan.steps) > 0

    def test_search_file(self):
        """测试搜索云盘文件"""
        goal = "在飞书云盘中搜索名称包含'测试'的文件"
        plan = self.planner.plan(goal)
        result = self.agent.run(goal, plan)
        assert len(plan.steps) > 0
