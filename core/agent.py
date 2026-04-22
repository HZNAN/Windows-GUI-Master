"""
Agent 主循环控制器
协调 Planner（规划）+ Executor（执行）+ Verifier（验证），
构成完整的 感知-规划-执行-验证 循环
"""
import time
from pathlib import Path
from typing import Literal
from dataclasses import dataclass, field
from loguru import logger

from config.settings import MAX_RETRY, STEP_TIMEOUT, HUMAN_IN_LOOP_ON_ERROR, CONFIDENCE_THRESHOLD
from drivers.screen_capture import get_screen_capture
from llm.ui_tars_client import UITarsClient
from llm.planner_llm_client import PlannerLLMClient, ExecutionPlan, PlannedStep
from .executor import Executor, ExecutionResult
from .verifier import Verifier, VerificationResult


@dataclass
class AgentConfig:
    """Agent 运行配置"""
    max_retry: int = MAX_RETRY
    step_timeout: int = STEP_TIMEOUT
    human_in_loop: bool = HUMAN_IN_LOOP_ON_ERROR
    confidence_threshold: float = CONFIDENCE_THRESHOLD


@dataclass
class StepRecord:
    """步骤执行记录"""
    step_index: int
    action: str
    target: str | None
    execution_result: ExecutionResult | None = None
    verification_result: VerificationResult | None = None
    screenshot_path: Path | None = None
    error: str | None = None


@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    goal: str
    steps: list[StepRecord] = field(default_factory=list)
    total_time: float = 0.0
    message: str = ""


class FeishuAgent:
    """
    飞书 AI Agent 主控制器

    支持两种运行模式：
    1. 规划模式（Planning Mode）：输入高层目标，LLM 分解步骤后逐步执行
    2. 直接模式（Direct Mode）：每步由视觉模型直接输出动作并执行

    默认使用智谱 GLM-4V-Flash 作为视觉层（可通过 vision_client 参数替换）
    """

    def __init__(
        self,
        vision_client=None,  # 默认使用 GLMVisionClient
        planner_client: PlannerLLMClient | None = None,
        config: AgentConfig | None = None
    ):
        from llm.glm_vision_client import GLMVisionClient
        from llm.ui_tars_client import UITarsClient
        from config.settings import VISION_PROVIDER

        self.config = config or AgentConfig()
        # 根据配置选择视觉客户端
        if vision_client is not None:
            self.vision = vision_client
        elif VISION_PROVIDER == "zhipu":
            self.vision = GLMVisionClient()
        else:
            self.vision = UITarsClient()
        self.planner = planner_client or PlannerLLMClient()
        self.screen = get_screen_capture()
        self.executor = Executor()
        self.verifier = Verifier()

    def run(self, goal: str, plan: ExecutionPlan | None = None) -> AgentResult:
        """
        运行 Agent 执行任务

        Args:
            goal: 高层测试目标
            plan: 可选，预计算的执行计划

        Returns:
            AgentResult
        """
        logger.info(f"=== Agent 启动: {goal} ===")
        start_time = time.time()
        records: list[StepRecord] = []
        success = True

        # 若无预计算计划，先调用 Planner 分解
        if plan is None:
            try:
                plan = self.planner.plan(goal)
                logger.info(f"计划分解完成，共 {len(plan.steps)} 步")
            except Exception as e:
                logger.error(f"计划分解失败: {e}")
                return AgentResult(False, goal, [], time.time() - start_time, str(e))

        # 逐步骤执行
        for i, step in enumerate(plan.steps):
            record = self._execute_step(i, step)
            records.append(record)

            if not record.execution_result or not record.execution_result.success:
                if self.config.human_in_loop:
                    decision = self._ask_human_confirm(i, step, record)
                    if decision == "abort":
                        success = False
                        logger.info("人工中止任务")
                        break
                    elif decision == "skip":
                        logger.info(f"跳过步骤 {i}")
                        continue
                    # retry 会继续重试
                else:
                    if record.execution_result and record.execution_result.success:
                        continue
                    success = False
                    break

        total_time = time.time() - start_time
        logger.info(f"=== Agent 结束: success={success}, time={total_time:.1f}s ===")
        return AgentResult(success, goal, records, total_time)

    def _execute_step(self, index: int, step: PlannedStep) -> StepRecord:
        """执行单个步骤（执行 + 验证）"""
        record = StepRecord(
            step_index=index,
            action=step.action,
            target=step.target
        )

        try:
            # 截图
            img, screenshot_path = self.screen.auto_save(prefix=f"step_{index}")
            record.screenshot_path = screenshot_path

            # 执行
            exec_result = self.executor.execute_step(step, img)
            record.execution_result = exec_result

            if not exec_result.success:
                record.error = exec_result.message
                return record

            # 等待页面响应
            time.sleep(1)

            # 验证
            if step.action in ("click", "type"):
                verify_ctx = {
                    "step_description": step.description,
                    "step_target": step.target,
                    "step_action": step.action
                }
                verify_result = self.verifier.verify(
                    operation=step.action,
                    expected=step.description,
                    method="api",
                    context=verify_ctx
                )
                record.verification_result = verify_result

                if not verify_result.passed:
                    logger.warning(f"步骤 {index} 验证失败: {verify_result.message}")

        except Exception as e:
            logger.error(f"步骤 {index} 执行异常: {e}")
            record.error = str(e)

        return record

    def _ask_human_confirm(
        self, index: int, step: PlannedStep, record: StepRecord
    ) -> Literal["retry", "skip", "abort"]:
        """
        人工确认（异常时暂停等待）

        Returns:
            'retry' / 'skip' / 'abort'
        """
        print(f"\n{'='*50}")
        print(f"[人工确认] 步骤 {index} 执行异常")
        print(f"  动作: {step.action}")
        print(f"  目标: {step.target}")
        print(f"  描述: {step.description}")
        if record.error:
            print(f"  错误: {record.error}")
        if record.execution_result:
            print(f"  执行结果: {record.execution_result.message}")
        print(f"{'='*50}")
        print("请选择: [r] 重试  [s] 跳过  [a] 中止: ", end="")

        # 简单从标准输入读取（实际项目建议用 GUI 对话框）
        try:
            choice = input().strip().lower()
            if choice == "r":
                return "retry"
            elif choice == "s":
                return "skip"
            else:
                return "abort"
        except Exception:
            return "abort"

    # ============ 直接模式（UI-TARS 驱动）============

    def run_direct(self, instruction: str, max_iterations: int = 20) -> AgentResult:
        """
        直接模式：不依赖 Planner，每轮直接调用 UI-TARS 获取动作并执行

        Args:
            instruction: 自然语言指令
            max_iterations: 最大迭代次数（防止死循环）

        Returns:
            AgentResult
        """
        logger.info(f"=== Agent 直接模式启动: {instruction} ===")
        start_time = time.time()
        records: list[StepRecord] = []
        success = True

        for i in range(max_iterations):
            img, screenshot_path = self.screen.auto_save(prefix=f"direct_{i}")

            try:
                action = self.vision.infer(screenshot=img, instruction=instruction)
                record = StepRecord(
                    step_index=i,
                    action=action.action_type,
                    target=action.target,
                    screenshot_path=screenshot_path
                )

                # 检查置信度
                if action.confidence < self.config.confidence_threshold:
                    logger.warning(f"置信度过低: {action.confidence:.2f}，等待人工确认")
                    if self.config.human_in_loop:
                        decision = self._ask_human_confirm(i, None, record)
                        if decision == "abort":
                            break

                # 执行动作
                exec_result = self.executor.execute(action, img)
                record.execution_result = exec_result

                if not exec_result.success:
                    logger.warning(f"执行失败: {exec_result.message}")
                    if self.config.human_in_loop:
                        decision = self._ask_human_confirm(i, None, record)
                        if decision == "abort":
                            success = False
                            break

                records.append(record)

                # 检查是否完成（等待或结束类动作）
                if action.action_type in ("wait",) and action.text:
                    try:
                        wait_time = float(action.text)
                        logger.info(f"UI-TARS 指示等待 {wait_time}s")
                        time.sleep(wait_time)
                    except ValueError:
                        time.sleep(2)

            except Exception as e:
                logger.error(f"迭代 {i} 异常: {e}")
                success = False
                break

        total_time = time.time() - start_time
        return AgentResult(success, instruction, records, total_time)
