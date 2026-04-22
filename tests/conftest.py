"""
pytest 全局 fixture 和配置
"""
import pytest
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from config.settings import REPORTS_DIR


@pytest.fixture(scope="session")
def reports_dir():
    """确保报告目录存在"""
    REPORTS_DIR.mkdir(exist_ok=True)
    return REPORTS_DIR


@pytest.fixture(scope="function")
def agent():
    """每个测试函数获取一个新鲜的 Agent 实例"""
    from core.agent import FeishuAgent
    ag = FeishuAgent()
    yield ag
    # teardown
    logger.info("Agent 实例销毁")


@pytest.fixture(scope="function")
def screen():
    """截图工具"""
    from drivers.screen_capture import ScreenCapture
    sc = ScreenCapture()
    yield sc
    sc.close()


def pytest_configure(config):
    """pytest 启动时的配置"""
    # 添加自定义 marker
    config.addinivalue_line(
        "markers", "im: 飞书 IM 模块测试"
    )
    config.addinivalue_line(
        "markers", "calendar: 飞书日历模块测试"
    )
    config.addinivalue_line(
        "markers", "doc: 飞书文档模块测试"
    )
    config.addinivalue_line(
        "markers", "drive: 飞书云盘模块测试"
    )
    config.addinivalue_line(
        "markers", "planning: 需要规划分解的测试"
    )


def pytest_runtest_makereport(item, call):
    """测试结果钩子，为报告附加截图路径"""
    if call.when == "call" and call.excinfo is not None:
        # 测试失败时截图
        try:
            from drivers.screen_capture import get_screen_capture
            sc = get_screen_capture()
            _, path = sc.auto_save(prefix=f"failed_{item.name}")
            logger.info(f"失败截图: {path}")
        except Exception:
            pass
