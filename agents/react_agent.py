"""
LangChain ReAct 代理 - 使用标准 LangChain Agent 模式
"""
from dataclasses import dataclass
from pathlib import Path
from loguru import logger

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from tools.screen import screenshot
from tools.mouse import click, move_mouse, double_click, right_click, scroll, drag
from tools.keyboard import type_text, press_key, hotkey, key_down, key_up, wait
from tools.agent import finish, continue_steps, retry

# 状态工具名称
STATE_TOOLS = {"finish", "continue_steps", "retry"}


def _load_system_prompt() -> str:
    """从文件加载系统提示词"""
    prompt_path = Path(__file__).parent.parent / "prompts" / "system_prompt.txt"
    return prompt_path.read_text(encoding="utf-8")


SYSTEM_PROMPT = _load_system_prompt()


@dataclass
class ReactResult:
    goal: str
    success: bool
    total_steps: int
    final_message: str
    error_reason: str | None = None


class ReactAgentLoop:

    def __init__(self, goal: str, output_dir: str | Path | None = None):
        self.goal = goal
        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_steps = 15
        self._init_llm()

    def _init_llm(self):
        from config.settings import ARK_API_KEY, ARK_API_URL, ARK_VISION_MODEL

        # 绑定工具，LangChain 会自动处理 tool_call 格式
        self.llm = ChatOpenAI(
            model=ARK_VISION_MODEL,
            api_key=ARK_API_KEY,
            base_url=ARK_API_URL,
            temperature=0.1,
            max_tokens=1500,
        ).bind_tools(
            [
                click, move_mouse, double_click, right_click, scroll, drag,
                type_text, press_key, hotkey, key_down, key_up, wait,
                finish, continue_steps, retry
            ],
            tool_choice="auto"
        )

        # 预先缓存屏幕尺寸
        self._cache_screen_info()

    def _cache_screen_info(self):
        from tools.mouse import _screen_info_cache
        from tools.keyboard import _screen_info_cache as kb_screen_info_cache
        if _screen_info_cache[0] is None:
            from drivers.screen_capture import get_screen_capture
            screen = get_screen_capture()
            img, _ = screen.auto_save(prefix="temp")
            import cv2
            orig_h, orig_w = img.shape[:2]
            info = {"orig_w": orig_w, "orig_h": orig_h}
            _screen_info_cache[0] = info
            kb_screen_info_cache[0] = info
            logger.info(f"屏幕尺寸已缓存: {orig_w}x{orig_h}")

    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """执行单个工具"""
        try:
            args = dict(tool_args)

            if tool_name == "click":
                result = click.func(**args)
                grid_x = args.get('grid_x', args.get('x', 0))
                grid_y = args.get('grid_y', args.get('y', 0))
                return f"[click] grid_x={grid_x}, grid_y={grid_y} | Result: Clicked at ({grid_x}, {grid_y})"
            elif tool_name == "move_mouse":
                result = move_mouse.func(**args)
                grid_x = args.get('grid_x', args.get('x', 0))
                grid_y = args.get('grid_y', args.get('y', 0))
                return f"[move_mouse] grid_x={grid_x}, grid_y={grid_y} | Result: Moved to ({grid_x}, {grid_y})"
            elif tool_name == "double_click":
                result = double_click.func(**args)
                grid_x = args.get('grid_x', 0)
                grid_y = args.get('grid_y', 0)
                return f"[double_click] grid_x={grid_x}, grid_y={grid_y} | Result: Double clicked at ({grid_x}, {grid_y})"
            elif tool_name == "right_click":
                result = right_click.func(**args)
                grid_x = args.get('grid_x', 0)
                grid_y = args.get('grid_y', 0)
                return f"[right_click] grid_x={grid_x}, grid_y={grid_y} | Result: Right clicked at ({grid_x}, {grid_y})"
            elif tool_name == "type_text":
                result = type_text.func(**args)
                text = args.get('text', '')
                grid_x = args.get('grid_x')
                grid_y = args.get('grid_y')
                coord_str = f" at ({grid_x}, {grid_y})" if grid_x is not None else ""
                return f"[type_text] text='{text}'{coord_str} | Result: Typed '{text}'"
            elif tool_name == "press_key":
                result = press_key.func(**args)
                key = args.get('key', '')
                return f"[press_key] key='{key}' | Result: Pressed {key}"
            elif tool_name == "wait":
                result = wait.func(**args)
                return f"[wait] | Result: {result}"
            elif tool_name == "scroll":
                result = scroll.func(**args)
                grid_x = args.get('grid_x', 0)
                grid_y = args.get('grid_y', 0)
                amount = args.get('amount', 3)
                return f"[scroll] grid_x={grid_x}, grid_y={grid_y}, amount={amount} | Result: Scroll at ({grid_x}, {grid_y})"
            elif tool_name == "drag":
                result = drag.func(**args)
                grid_x1 = args.get('grid_x1', 0)
                grid_y1 = args.get('grid_y1', 0)
                grid_x2 = args.get('grid_x2', 0)
                grid_y2 = args.get('grid_y2', 0)
                return f"[drag] from ({grid_x1}, {grid_y1}) to ({grid_x2}, {grid_y2}) | Result: Dragged"
            elif tool_name == "hotkey":
                result = hotkey.func(**args)
                keys = args.get('keys', '')
                return f"[hotkey] keys='{keys}' | Result: Hotkey pressed"
            elif tool_name == "key_down":
                result = key_down.func(**args)
                key = args.get('key', '')
                return f"[key_down] key='{key}' | Result: Key down"
            elif tool_name == "key_up":
                result = key_up.func(**args)
                key = args.get('key', '')
                return f"[key_up] key='{key}' | Result: Key up"
            elif tool_name == "finish":
                result = finish.func()
                return f"[finish] | Result: TASK_COMPLETED"
            elif tool_name == "continue_steps":
                reason = args.get('reason', '')
                continue_steps.func(reason=reason)
                return f"[continue_steps] reason='{reason}' | Result: CONTINUE"
            elif tool_name == "retry":
                reason = args.get('reason', '')
                retry.func(reason=reason)
                return f"[retry] reason='{reason}' | Result: RETRY"
            else:
                return f"[unknown] | Result: Unknown tool: {tool_name}"
        except Exception as e:
            logger.error(f"工具执行失败: {tool_name}, {e}")
            return f"Tool error: {str(e)}"

    def run(self) -> ReactResult:
        """
        多工具调用模式：
        - 模型一次可调用多个工具
        - 每个工具执行后自动截图
        - 最后一个工具必须是 finish/continue_steps/retry

        Previous result 格式：
        reason | tool_output (status)
        - (check): 当前步需要被验证
        - (fail): 上一步验证失败
        """
        logger.info(f"ReActAgentLoop 开始 | Goal: {self.goal[:50]}")

        try:
            # history: list of (reason, tool_output, status)
            # status: "check" 或 "fail"
            history = []

            # 初始截图
            screenshot_data = screenshot.func()
            screenshot_url = screenshot_data["image"]

            step_count = 0

            while step_count < self.max_steps:
                step_count += 1
                logger.info(f"\n=== Turn {step_count} ===")

                # 构建 Previous result
                if history:
                    prev_result_lines = []
                    for reason, tool_output, status in history:
                        prev_result_lines.append(f"{reason} | {tool_output} ({status})")
                    prev_result_text = "\n".join(prev_result_lines)
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
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=user_content),
                ]

                # 调用 LLM
                try:
                    response = self.llm.invoke(messages, config={"timeout": 60})
                except Exception as e:
                    logger.error(f"LLM 调用失败: {e}")
                    screenshot_data = screenshot.func()
                    screenshot_url = screenshot_data["image"]
                    continue

                # 记录 LLM 响应
                content = response.content if hasattr(response, 'content') and response.content else ""
                logger.info(f"LLM 响应: {content[:200] if content else 'No content'}")

                # 检查是否有 tool_calls
                if not hasattr(response, 'tool_calls') or not response.tool_calls:
                    return ReactResult(
                        goal=self.goal,
                        success=False,
                        total_steps=step_count,
                        final_message=content or "No tool calls",
                        error_reason="模型未调用任何工具"
                    )

                # 收集当前轮次的操作（用于 continue/retry 时追加到 history）
                # 每个操作记录: (操作自身的reason, 工具输出)
                current_turn_operations = []

                # 执行所有工具
                for tc in response.tool_calls:
                    raw_name = tc.get("name", "")
                    # 清理工具名称（处理 LangChain 输出格式问题）
                    # 去掉末尾的 "string="true 等冗余内容
                    clean_name = raw_name.split('"')[0].strip() if '"' in raw_name else raw_name.strip()
                    tool_name = clean_name.lower()
                    raw_args = tc.get("args", {})
                    if hasattr(raw_args, 'model_dump'):
                        tool_args = {k: v for k, v in raw_args.model_dump().items() if v is not None}
                    elif isinstance(raw_args, dict):
                        tool_args = {k: v for k, v in raw_args.items() if v is not None}
                    else:
                        tool_args = {}

                    logger.info(f"执行工具: {tool_name}({tool_args})")
                    result = self._execute_tool(tool_name, tool_args)
                    logger.info(f"工具结果: {result}")

                    # 每个工具执行后自动截图
                    screenshot_data = screenshot.func()
                    screenshot_url = screenshot_data["image"]

                    # 处理 finish/continue/retry
                    if tool_name == "finish":
                        return ReactResult(
                            goal=self.goal,
                            success=True,
                            total_steps=step_count,
                            final_message="任务已完成"
                        )

                    elif tool_name == "continue_steps":
                        # 清空 history，然后追加当前操作 (check)
                        history = []
                        for op_reason, op_output in current_turn_operations:
                            history.append((op_reason, op_output, "check"))

                    elif tool_name == "retry":
                        # 不清空，把上一条操作改成 (fail)，然后追加当前操作 (check)
                        # 把 history 中最后一个变成 (fail)
                        if history:
                            last_idx = len(history) - 1
                            last_reason, last_output, _ = history[last_idx]
                            history[last_idx] = (last_reason, last_output, "fail")
                        # 追加当前操作 (check)
                        for op_reason, op_output in current_turn_operations:
                            history.append((op_reason, op_output, "check"))

                    else:
                        # 普通工具，记录到 current_turn_operations
                        # reason 从当前工具的参数中获取（表示这个操作本身的执行目标）
                        op_reason = tool_args.get('reason', '')
                        current_turn_operations.append((op_reason, result))

                # 最后一个工具不是 finish/continue/retry
                last_raw = response.tool_calls[-1].get("name", "")
                last_tool = last_raw.lower().replace('"string="true', '').replace('string="true', '').strip()
                logger.info(f"最后一个工具: {last_tool}, state_tools: {STATE_TOOLS}")
                if last_tool not in STATE_TOOLS:
                    # 模型忘记调用状态工具，自动插入 continue_steps
                    logger.warning(f"模型未调用状态工具，自动添加 continue_steps")
                    screenshot_data = screenshot.func()
                    screenshot_url = screenshot_data["image"]
                    continue  # 继续下一轮

            # 达到最大步数
            return ReactResult(
                goal=self.goal,
                success=False,
                total_steps=step_count,
                final_message="达到最大步数限制",
                error_reason="达到最大步数限制"
            )

        except Exception as e:
            logger.error(f"ReAct 代理执行失败: {e}")
            import traceback
            traceback.print_exc()
            return ReactResult(
                goal=self.goal,
                success=False,
                total_steps=0,
                final_message="",
                error_reason=str(e)
            )
