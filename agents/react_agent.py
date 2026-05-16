"""
LangChain ReAct 代理 - 使用标准 LangChain Agent 模式
"""
import time as _time
from dataclasses import dataclass
from pathlib import Path
from loguru import logger

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from tools.screen import screenshot
from tools.mouse import click, move_mouse, double_click, right_click, scroll, drag
from tools.keyboard import type_text, press_key, hotkey, key_down, key_up, wait
from tools.agent import finish, ask_human

# 独立状态工具（finish 终止任务，continue/retry 通过动作工具的 step_type 参数表达）
STATE_TOOLS = {"finish"}


_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")


def _build_system_prompt() -> str:
    """构建系统提示词，用当前 grid 配置填充占位符"""
    from config.settings import GRID_WIDTH, GRID_HEIGHT
    from tools.screen import _nice_step

    gw, gh = GRID_WIDTH, GRID_HEIGHT
    gsx = _nice_step(gw)
    gsy = _nice_step(gh)
    return _PROMPT_TEMPLATE.format(
        grid_width=gw,
        grid_height=gh,
        grid_step_x=gsx,
        grid_step_y=gsy,
        tick_step_x=max(gsx // 2, 10),
        tick_step_y=max(gsy // 2, 10),
        center_x=gw // 2,
        center_y=gh // 2,
    )


@dataclass
class ReactResult:
    goal: str
    success: bool
    total_steps: int
    final_message: str
    error_reason: str | None = None


class ReactAgentLoop:

    def __init__(self, goal: str, output_dir: str | Path | None = None,
                 max_steps: int = 15, history_window: int = 3):
        self.goal = goal
        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_steps = max_steps
        self.history_window = history_window
        self.task_log_path = None  # 任务日志文件路径
        self._init_llm()

    def _init_llm(self):
        from config.settings import (
            LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
            LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TOP_P,
            LLM_REASONING_EFFORT,
        )

        # 绑定工具，LangChain 会自动处理 tool_call 格式
        self.llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            top_p=LLM_TOP_P,
            model_kwargs={"reasoning_effort": LLM_REASONING_EFFORT},
        ).bind_tools(
            [
                click, move_mouse, double_click, right_click, scroll, drag,
                type_text, press_key, hotkey, key_down, key_up, wait,
                ask_human,
                finish,
            ],
            tool_choice="auto"
        )

        # 预先缓存屏幕尺寸
        self._cache_screen_info()

    def _cache_screen_info(self):
        from tools._shared import _screen_info_cache
        from drivers.screen_capture import get_screen_capture
        screen = get_screen_capture()
        img, _ = screen.auto_save(prefix="temp")
        orig_h, orig_w = img.shape[:2]
        _screen_info_cache[0] = {"orig_w": orig_w, "orig_h": orig_h}
        logger.info(f"屏幕尺寸已更新: {orig_w}x{orig_h}")

    @staticmethod
    def _clean_tool_name(raw_name: str) -> str:
        return raw_name.strip().strip('"').lower()

    @staticmethod
    def _clean_tool_args(raw_args) -> dict:
        if hasattr(raw_args, 'model_dump'):
            return {k: v for k, v in raw_args.model_dump().items() if v is not None}
        if isinstance(raw_args, dict):
            return {k: v for k, v in raw_args.items() if v is not None}
        return {}

    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """执行单个工具"""
        try:
            args = dict(tool_args)

            if tool_name == "click":
                result = click.func(**args)
                grid_x = args.get('grid_x', args.get('x', 0))
                grid_y = args.get('grid_y', args.get('y', 0))
                return f"[click] grid_x={grid_x}, grid_y={grid_y} | {result}"
            elif tool_name == "move_mouse":
                result = move_mouse.func(**args)
                grid_x = args.get('grid_x', args.get('x', 0))
                grid_y = args.get('grid_y', args.get('y', 0))
                return f"[move_mouse] grid_x={grid_x}, grid_y={grid_y} | {result}"
            elif tool_name == "double_click":
                result = double_click.func(**args)
                grid_x = args.get('grid_x', 0)
                grid_y = args.get('grid_y', 0)
                return f"[double_click] grid_x={grid_x}, grid_y={grid_y} | {result}"
            elif tool_name == "right_click":
                result = right_click.func(**args)
                grid_x = args.get('grid_x', 0)
                grid_y = args.get('grid_y', 0)
                return f"[right_click] grid_x={grid_x}, grid_y={grid_y} | {result}"
            elif tool_name == "type_text":
                result = type_text.func(**args)
                text = args.get('text', '')
                grid_x = args.get('grid_x')
                grid_y = args.get('grid_y')
                coord_str = f" at ({grid_x}, {grid_y})" if grid_x is not None else ""
                return f"[type_text] text='{text}'{coord_str} | {result}"
            elif tool_name == "press_key":
                result = press_key.func(**args)
                key = args.get('key', '')
                return f"[press_key] key='{key}' | {result}"
            elif tool_name == "wait":
                result = wait.func(**args)
                return f"[wait] | Result: {result}"
            elif tool_name == "scroll":
                result = scroll.func(**args)
                grid_x = args.get('grid_x', 0)
                grid_y = args.get('grid_y', 0)
                amount = args.get('amount', 5)
                return f"[scroll] grid_x={grid_x}, grid_y={grid_y}, amount={amount} | {result}"
            elif tool_name == "drag":
                result = drag.func(**args)
                grid_x1 = args.get('grid_x1', 0)
                grid_y1 = args.get('grid_y1', 0)
                grid_x2 = args.get('grid_x2', 0)
                grid_y2 = args.get('grid_y2', 0)
                return f"[drag] from ({grid_x1}, {grid_y1}) to ({grid_x2}, {grid_y2}) | {result}"
            elif tool_name == "hotkey":
                result = hotkey.func(**args)
                keys = args.get('keys', '')
                return f"[hotkey] keys='{keys}' | {result}"
            elif tool_name == "key_down":
                result = key_down.func(**args)
                key = args.get('key', '')
                return f"[key_down] key='{key}' | {result}"
            elif tool_name == "key_up":
                result = key_up.func(**args)
                key = args.get('key', '')
                return f"[key_up] key='{key}' | {result}"
            elif tool_name == "finish":
                finish.func()
                return f"[finish] | Result: TASK_COMPLETED"
            elif tool_name == "ask_human":
                result = ask_human.func(**args)
                question = args.get('question', '')
                return f"[ask_human] question='{question}' | 人类回答: {result}"
            else:
                return f"[unknown] | Result: Unknown tool: {tool_name}"
        except Exception as e:
            logger.error(f"工具执行失败: {tool_name}, {e}")
            return f"Tool error: {str(e)}"

    def _build_prev_result(self, history_turns: list) -> str | None:
        """将 history_turns 展平为 Previous result 文本"""
        if not history_turns:
            return None
        lines = []
        for reason, outputs, status in history_turns:
            for output in outputs:
                lines.append(f"{reason} | {output} ({status})")
        return "\n".join(lines)

    def _trim_history(self, history_turns: list) -> list:
        """按窗口大小裁剪，保留最近 N 轮"""
        if len(history_turns) > self.history_window:
            return history_turns[-self.history_window:]
        return history_turns

    def _update_history(self, history_turns: list, current_turn_operations: list,
                        reason: str, state: str) -> list:
        """
        统一的 history 更新逻辑。

        Args:
            state: "continue" 或 "retry"
        """
        target_status = "success" if state == "continue" else "fail"
        if history_turns and history_turns[-1][2] == "check":
            r, outs, _ = history_turns[-1]
            history_turns[-1] = (r, outs, target_status)

        current_outputs = [o for _, o in current_turn_operations]
        if current_outputs:
            history_turns.append((reason, current_outputs, "check"))
        return self._trim_history(history_turns)

    def _log_turn_input(self, step_count: int, prev_result_text: str | None):
        """输出每轮发给模型的完整输入信息"""
        logger.info(f"--- Turn {step_count} HumanMessage ---")
        logger.info(f"Task: {self.goal}")
        logger.info(f"Screenshot: [base64 image attached]")
        if prev_result_text:
            logger.info(f"Previous result:\n{prev_result_text}")
        else:
            logger.info(f"Previous result: (none)")
        logger.info(f"--- End HumanMessage ---")

    def _init_task_log(self):
        """初始化任务日志文件"""
        if not self.output_dir:
            return None
        import hashlib
        from datetime import datetime
        # 用 goal 的哈希和时间戳命名，避免重复
        goal_hash = hashlib.md5(self.goal.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.output_dir / f"task_{timestamp}_{goal_hash}.txt"
        # 写入任务头
        header = [
            f"=== Task Log ===",
            f"Goal: {self.goal}",
            f"Started: {datetime.now().isoformat()}",
            f"Max steps: {self.max_steps}",
            "=" * 50,
            "",
        ]
        log_file.write_text("\n".join(header), encoding="utf-8")
        return log_file

    def _append_turn_log(self, step_count: int, prev_result_text: str | None,
                         response_content: str, tool_calls_summary: str):
        """追加每轮日志到任务日志文件"""
        if not self.task_log_path:
            return
        lines = [
            f"\n=== Turn {step_count} ===",
            f"\n--- INPUT ---",
            f"Screenshot: [attached]",
        ]
        if prev_result_text:
            lines.append(f"Previous result:\n{prev_result_text}")
        else:
            lines.append(f"Previous result: (none)")
        lines.append(f"\n--- OUTPUT ---")
        lines.append(f"Content: {response_content}")
        lines.append(f"Tool calls:\n{tool_calls_summary}")
        # 追加模式
        with open(self.task_log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _finalize_task_log(self, result: ReactResult):
        """写入任务结果到日志文件"""
        if not self.task_log_path:
            return
        from datetime import datetime
        lines = [
            "\n" + "=" * 50,
            f"=== Task Complete ===",
            f"Success: {result.success}",
            f"Total steps: {result.total_steps}",
            f"Final message: {result.final_message}",
            f"Error reason: {result.error_reason or 'none'}",
            f"Finished: {datetime.now().isoformat()}",
        ]
        with open(self.task_log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def run(self) -> ReactResult:
        """
        多工具调用模式：
        - 每轮开始时截图一次（唯一一次），作为 LLM 视觉输入
        - 模型一次可调用多个工具，中间不再截图
        - 每个动作工具通过 step_type 参数表达本轮结果，任务完成时调用 finish

        Previous result 格式：
        reason | tool_output (status)
        - (success): 已验证成功的历史操作
        - (check):   刚执行的操作，需要模型从截图验证是否成功
        - (fail):    已确认失败的操作
        """
        logger.info(f"ReActAgentLoop 开始 | Goal: {self.goal[:50]}")

        try:
            # 初始化任务日志
            self.task_log_path = self._init_task_log()

            # history_turns: list of (reason, [tool_outputs], status)
            # 每个元素代表一轮操作，status 对该轮所有 outputs 统一生效
            history_turns = []

            step_count = 0

            while step_count < self.max_steps:
                step_count += 1

                from config.settings import AGENT_TURN_DELAY
                _time.sleep(AGENT_TURN_DELAY)

                screenshot_data = screenshot.func()
                screenshot_url = screenshot_data["image"]

                prev_result_text = self._build_prev_result(history_turns)

                logger.info(f"\n{'='*50}")
                logger.info(f"=== Turn {step_count}/{self.max_steps} ===")
                logger.info(f"{'='*50}")
                logger.info(f"[INPUT] Task: {self.goal}")
                logger.info(f"[INPUT] Screenshot: [base64 image attached]")
                if prev_result_text:
                    logger.info(f"[INPUT] Previous result:\n{prev_result_text}")
                else:
                    logger.info(f"[INPUT] Previous result: (首轮，无历史)")
                logger.info(f"{'='*50}")

                if prev_result_text:
                    user_content = [
                        {"type": "text", "text": f"Task: {self.goal}"},
                        {"type": "image_url", "image_url": {"url": screenshot_url}},
                        {"type": "text", "text": f"Previous result:\n{prev_result_text}"},
                    ]
                else:
                    user_content = [
                        {"type": "text", "text": f"Task: {self.goal}"},
                        {"type": "image_url", "image_url": {"url": screenshot_url}},
                    ]

                messages = [
                    SystemMessage(content=_build_system_prompt()),
                    HumanMessage(content=user_content),
                ]

                try:
                    response = self.llm.invoke(messages, config={"timeout": 60})
                except Exception as e:
                    logger.error(f"LLM 调用失败: {e}")
                    continue

                content = response.content if hasattr(response, 'content') and response.content else ""
                logger.info(f"[OUTPUT] LLM content: {content[:300] if content else '(empty)'}")

                # 通知主线程：LLM 文本输出
                if content:
                    from core.agent_service import push_notification
                    push_notification("agent_message_chunk", content)

                if not hasattr(response, 'tool_calls') or not response.tool_calls:
                    logger.info(f"[OUTPUT] Tool calls: (none)")
                    result = ReactResult(
                        goal=self.goal,
                        success=False,
                        total_steps=step_count,
                        final_message=content or "No tool calls",
                        error_reason="模型未调用任何工具"
                    )
                    self._finalize_task_log(result)
                    return result

                tc_names = [self._clean_tool_name(tc.get("name", "")) for tc in response.tool_calls]
                logger.info(f"[OUTPUT] Tool calls: {tc_names}")

                current_turn_operations = []
                _last_step_type = "continue"
                _last_reason = ""

                for tc in response.tool_calls:
                    tool_name = self._clean_tool_name(tc.get("name", ""))
                    tool_args = self._clean_tool_args(tc.get("args", {}))

                    # 通知主线程：工具调用 (非状态工具)
                    tc_id = ""
                    if tool_name not in STATE_TOOLS:
                        from core.agent_service import push_notification
                        import uuid as _uuid
                        tc_id = str(_uuid.uuid4())[:8]
                        push_notification("tool_call", str(tool_args),
                                          toolCallId=tc_id, title=tool_name,
                                          status="in_progress",
                                          rawInput={"text": str(tool_args)})

                    logger.info(f"  -> 执行: {tool_name}({tool_args})")
                    result = self._execute_tool(tool_name, tool_args)
                    logger.info(f"  <- 结果: {result}")

                    # 通知主线程：工具完成 (acpx 用 tool_call_update 表示工具结束)
                    if tool_name not in STATE_TOOLS:
                        push_notification("tool_call_update", result,
                                          toolCallId=tc_id, title=tool_name,
                                          status="completed",
                                          rawInput={"text": str(tool_args)},
                                          rawOutput={"text": result})

                    if tool_name == "finish":
                        # 在结束前先解析上一轮的 (check) 状态，避免历史丢失
                        st = _last_step_type if _last_step_type in ("continue", "retry") else "continue"
                        rsn = _last_reason if _last_reason else "任务已完成"
                        history_turns = self._update_history(
                            history_turns, current_turn_operations, rsn, st
                        )
                        finish_result = ReactResult(
                            goal=self.goal,
                            success=True,
                            total_steps=step_count,
                            final_message="任务已完成"
                        )
                        self._append_turn_log(step_count, prev_result_text, content, str(tc_names))
                        self._finalize_task_log(finish_result)
                        return finish_result

                    else:
                        current_turn_operations.append((tool_name, result))
                        # 从动作工具参数中提取 step_type 和 reason
                        _last_step_type = tool_args.get("step_type", "continue")
                        _last_reason = tool_args.get("reason", "")

                self._append_turn_log(step_count, prev_result_text, content, str(tc_names))

                # 根据动作工具的 step_type 确定本轮状态
                st = _last_step_type if _last_step_type in ("continue", "retry") else "continue"
                rsn = _last_reason if _last_reason else "操作已执行"
                logger.info(f"[STEP] step_type={st}, reason={rsn[:50]}")
                history_turns = self._update_history(
                    history_turns, current_turn_operations, rsn, st
                )

            result = ReactResult(
                goal=self.goal,
                success=False,
                total_steps=step_count,
                final_message="达到最大步数限制",
                error_reason="达到最大步数限制"
            )
            self._finalize_task_log(result)
            return result

        except Exception as e:
            logger.error(f"ReAct 代理执行失败: {e}")
            import traceback
            traceback.print_exc()
            result = ReactResult(
                goal=self.goal,
                success=False,
                total_steps=0,
                final_message="",
                error_reason=str(e)
            )
            self._finalize_task_log(result)
            return result
