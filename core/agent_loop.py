"""
Agent Loop - 主循环
整合 PlannerAgent + ExecutionEngine + 截图 + Planner 自检
"""
import time
from dataclasses import dataclass
from pathlib import Path
from loguru import logger

from core.planner_agent import PlannerAgent, Decision
from core.execution_engine import ExecutionEngine
from drivers.screen_capture import get_screen_capture


def _overlay_coord_grid(img):
    """
    在截图上叠加坐标参考标记，并缩放到 1092x1092（API resize 后的尺寸）。
    坐标系刻度按 1092x1092 标注，这样模型输出的坐标就是 1092x1092 空间，
    执行时再换算回原坐标。
    """
    import cv2
    output = img.copy()
    orig_h, orig_w = output.shape[:2]

    TARGET_SIZE = 1092
    output = cv2.resize(output, (TARGET_SIZE, TARGET_SIZE), interpolation=cv2.INTER_LINEAR)
    h, w = TARGET_SIZE, TARGET_SIZE

    font = cv2.FONT_HERSHEY_SIMPLEX

    overlay = output.copy()
    cv2.rectangle(overlay, (0, 0), (w-1, 55), (0, 0, 0), -1)
    cv2.rectangle(overlay, (0, h-55), (w-1, h-1), (0, 0, 0), -1)
    cv2.rectangle(overlay, (0, 0), (55, h-1), (0, 0, 0), -1)
    cv2.rectangle(overlay, (w-55, 0), (w-1, h-1), (0, 0, 0), -1)
    cv2.addWeighted(output, 0.6, overlay, 0.4, 0, output)

    fontScale = 0.9
    thickness = 2
    tick_len = 18

    cv2.rectangle(output, (0, 0), (w-1, h-1), (0, 0, 0), 4)

    for x in range(0, w, 100):
        cv2.line(output, (x, 0), (x, tick_len), (255, 255, 255), 3)
        cv2.putText(output, str(x), (x-20, 40), font, fontScale, (255, 255, 255), thickness)
        cv2.line(output, (x, h-1), (x, h-1-tick_len), (255, 255, 255), 3)
        cv2.putText(output, str(x), (x-20, h-8), font, fontScale, (255, 255, 255), thickness)

    for y in range(0, h, 100):
        cv2.line(output, (0, y), (tick_len, y), (255, 255, 255), 3)
        cv2.putText(output, str(y), (18, y+8), font, fontScale, (255, 255, 255), thickness)
        cv2.line(output, (w-1, y), (w-1-tick_len, y), (255, 255, 255), 3)
        cv2.putText(output, str(y), (w-42, y+8), font, fontScale, (255, 255, 255), thickness)

    big_font = 1.2
    cv2.rectangle(output, (3, 3), (170, 52), (0, 0, 0), -1)
    cv2.putText(output, "(0,0)", (8, 40), font, big_font, (255, 255, 255), 3)
    cv2.rectangle(output, (w-172, 3), (w-3, 52), (0, 0, 0), -1)
    cv2.putText(output, f"({w},0)", (w-167, 40), font, big_font, (255, 255, 255), 3)
    cv2.rectangle(output, (3, h-52), (170, h-3), (0, 0, 0), -1)
    cv2.putText(output, f"(0,{h})", (8, h-12), font, big_font, (255, 255, 255), 3)
    cv2.rectangle(output, (w-172, h-52), (w-3, h-3), (0, 0, 0), -1)
    cv2.putText(output, f"({w},{h})", (w-167, h-12), font, big_font, (255, 255, 255), 3)

    cx, cy = w // 2, h // 2
    cv2.drawMarker(output, (cx, cy), (0, 0, 255), cv2.MARKER_CROSS, 60, 4)
    cv2.rectangle(output, (cx-85, cy-50), (cx+85, cy-10), (0, 0, 0), -1)
    cv2.putText(output, f"CENTER({cx},{cy})", (cx-80, cy-18), font, 0.8, (0, 0, 255), 2)

    return output, orig_w, orig_h


def coords_1092_to_screen(x: int, y: int, orig_w: int, orig_h: int, grid_w: int = 1092, grid_h: int = 1092) -> tuple[int, int]:
    """将 1092x1092 网格坐标换算回原屏幕坐标"""
    scale_x = orig_w / grid_w
    scale_y = orig_h / grid_h
    return int(x * scale_x), int(y * scale_y)


class AgentLoop:
    """
    Agent 主循环
    - PlannerAgent 决策（带历史记忆）+ 自检上一步是否达成目标
    - ExecutionEngine 执行
    - 截图 + Planner 自检
    """

    MAX_STEPS = 15
    MAX_RETRY_PER_STEP = 2  # 每步最多重试次数

    def __init__(self, goal: str, output_dir: str | Path | None = None):
        self.goal = goal
        self.planner = PlannerAgent()
        self.executor = ExecutionEngine()
        self.screen = get_screen_capture()

        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            from config.settings import SCREENSHOTS_DIR
            ts = time.strftime("%Y%m%d_%H%M%S")
            self.output_dir = SCREENSHOTS_DIR / f"agent_{ts}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.step_count = 0
        self.decisions = []
        self.step_completions = []
        # 保存上一步执行后的截图路径（用于自检），在每步执行完后更新
        self._prev_step_screenshot_path = None

    def run(self) -> "RunResult":
        """运行 Agent 主循环"""
        logger.info(f"AgentLoop 开始 | Goal: {self.goal[:50]}")
        logger.info(f"输出目录: {self.output_dir}")

        img, screenshot_path = self.screen.auto_save(
            prefix=f"step{self.step_count}",
            save_dir=self.output_dir
        )

        while self.step_count < self.MAX_STEPS:
            logger.info(f"\n=== Step {self.step_count + 1}/{self.MAX_STEPS} ===")

            import cv2

            orig_h, orig_w = img.shape[:2]

            # 当前截图（也是上一步执行结束后的状态）
            curr_grid_path = self.output_dir / f"step{self.step_count}_after_grid.png"
            img_grid, _, _ = _overlay_coord_grid(img)
            cv2.imwrite(str(curr_grid_path), img_grid)

            history = self._build_history_context()

            # Planner 决策（带历史 + 上一步目标供自检）
            decision = self.planner.decide(
                goal=self.goal,
                screenshot_path=str(curr_grid_path),
                history=history,
                prev_step_goal=self.step_completions[-1] if self.step_completions else None
            )
            self.decisions.append(decision)

            if decision.status in ("success", "failed"):
                self._save_decision_log(decision, self.step_count)
                if decision.status == "success":
                    logger.info("任务成功完成！")
                    return RunResult(
                        goal=self.goal,
                        success=True,
                        total_steps=self.step_count + 1,
                        decisions=self.decisions,
                        final_screenshot=str(screenshot_path)
                    )
                else:
                    logger.warning(f"任务失败: {decision.think[:100]}")
                    return RunResult(
                        goal=self.goal,
                        success=False,
                        total_steps=self.step_count + 1,
                        decisions=self.decisions,
                        final_screenshot=str(screenshot_path),
                        error_reason=decision.think
                    )

            step_goal = self._get_step_goal(decision)

            # 处理 retry 动作：重试时不推进步骤
            if decision.action == "retry":
                logger.info(f"Planner 判断上一步未达成，调整坐标重试: ({decision.x}, {decision.y})")
                # 执行重试
                if decision.x is not None and decision.y is not None:
                    screen_x, screen_y = coords_1092_to_screen(decision.x, decision.y, orig_w, orig_h)
                    self.executor.execute(
                        action="click",
                        x=screen_x,
                        y=screen_y,
                        text=decision.text,
                        key=decision.key
                    )
                time.sleep(1)
                img, screenshot_path = self.screen.auto_save(
                    prefix=f"step{self.step_count}_retry",
                    save_dir=self.output_dir
                )
                continue  # 不推进 step_count，重新让 Planner 判断

            # Planner 没有给出有效坐标，跳过此步
            if decision.x is None or decision.y is None:
                logger.warning("Planner 没有给出有效坐标，跳过执行")
                time.sleep(1)
                img, screenshot_path = self.screen.auto_save(
                    prefix=f"step{self.step_count + 1}",
                    save_dir=self.output_dir
                )
                self.step_count += 1
                continue

            # 坐标换算
            grid_x, grid_y = decision.x, decision.y
            screen_x, screen_y = coords_1092_to_screen(grid_x, grid_y, orig_w, orig_h)
            logger.info(f"坐标换算: ({grid_x},{grid_y}) in 1092x1092 -> ({screen_x},{screen_y}) in {orig_w}x{orig_h}")

            decision.x = screen_x
            decision.y = screen_y

            self._save_decision_log(decision, self.step_count)

            # ========== 执行 ==========
            if decision.action and decision.action != "done":
                ok = self.executor.execute(
                    action=decision.action,
                    x=screen_x,
                    y=screen_y,
                    text=decision.text,
                    key=decision.key
                )
                if not ok:
                    logger.warning(f"执行失败: {decision.action}")

            completion = f"已完成 step {self.step_count}: {step_goal}"
            self.step_completions.append(completion)
            logger.info(f"[Completion] {completion}")

            time.sleep(1)
            img, screenshot_path = self.screen.auto_save(
                prefix=f"step{self.step_count + 1}",
                save_dir=self.output_dir
            )
            # 保存这一步执行后的截图，供下一步自检用（before 状态）
            self._prev_step_screenshot_path = self.output_dir / f"step{self.step_count + 1}_after_grid.png"
            img_grid_prev, _, _ = _overlay_coord_grid(img)
            cv2.imwrite(str(self._prev_step_screenshot_path), img_grid_prev)

            self.step_count += 1

        logger.warning(f"达到最大步数 {self.MAX_STEPS}")
        return RunResult(
            goal=self.goal,
            success=False,
            total_steps=self.step_count,
            decisions=self.decisions,
            final_screenshot=str(screenshot_path),
            error_reason=f"达到最大步数限制 ({self.MAX_STEPS})"
        )

    def _get_step_goal(self, decision: Decision) -> str:
        """根据决策生成当前 step 的目标描述（描述预期结果，不只是动作）"""
        action = decision.action or "unknown"
        x = decision.x
        y = decision.y
        text = decision.text or ""
        key = decision.key or ""

        # 从 think 字段提取意图（当前任务描述）
        intent = decision.think if decision.think else ""

        if action == "click":
            if intent:
                return f"点击 {intent}（预期结果：界面应发生变化）"
            return f"点击坐标 ({x}, {y})（预期结果：点击的目标应被激活或打开）"
        elif action == "type":
            if intent:
                return f"{intent}（预期结果：文本应出现在输入框中）"
            return f"在坐标 ({x}, {y}) 输入文本: {text}"
        elif action == "press":
            return f"按键: {key}（预期结果：按键效果应生效）"
        elif action == "done":
            return "任务完成"
        else:
            return f"执行动作: {action}"

    def _build_history_context(self) -> str:
        """构建历史执行上下文"""
        if not self.decisions:
            return ""
        lines = []
        lines.append("\n\n=== Past Execution History ===")
        for i, d in enumerate(self.decisions):
            action_desc = f'action={d.action}'
            if d.x is not None and d.y is not None:
                action_desc += f' at ({d.x},{d.y})'
            if d.text:
                action_desc += f' text="{d.text}"'
            if d.key:
                action_desc += f' key="{d.key}"'
            lines.append(f"Step {i}: {action_desc} | THINK: {d.think[:80]}")
        lines.append("=============================")
        for comp in self.step_completions:
            lines.append(comp)
        lines.append("")
        return "\n".join(lines)

    def _save_decision_log(self, decision: Decision, step: int):
        log_file = self.output_dir / f"decision_{step:02d}.txt"
        content = (
            f"=== Step {step} ===\n"
            f"Status: {decision.status}\n"
            f"\n--- THINK ---\n"
            f"{decision.think}\n"
            f"\n--- EXEC ---\n"
            f"action={decision.action}, x={decision.x}, y={decision.y}, "
            f"text={decision.text}, key={decision.key}\n"
            f"\n--- RAW ---\n"
            f"{decision.raw_response}\n"
        )
        log_file.write_text(content, encoding="utf-8")


@dataclass
class RunResult:
    """运行结果"""
    goal: str
    success: bool
    total_steps: int
    decisions: list
    final_screenshot: str
    error_reason: str | None = None
