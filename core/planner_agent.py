"""
PlannerAgent - 唯一决策者
接收截图(带坐标网格)+历史记忆，输出推理过程+执行指令
"""
import base64
import json
import time
import re
from dataclasses import dataclass
from pathlib import Path
from loguru import logger

from drivers.screen_capture import get_screen_capture


class PlannerAgent:
    """
    视觉规划代理
    - 输入: 目标 + 带坐标网格的截图 + 历史执行记忆
    - 输出: THINK推理 + EXEC指令 + STATUS状态
    """

    SYSTEM_PROMPT = """You are a task planning assistant for desktop screenshot action execution.

You receive:
1. A task goal from the user
2. A screenshot with coordinate reference markers overlaid on it
3. Past execution history
4. (Optional) Previous step goal with expected result - you MUST verify if it actually happened

IMPORTANT - Coordinate System (图片尺寸为 1092x1092):
- This image has been pre-processed to 1092x1092 (the size the API resizes images to)
- The edges have black strips with white tick numbers: x=0,100,...,1092 and y=0,100,...,1092
- Top-left corner: (0,0), Top-right: (1092,0), Bottom-left: (0,1092), Bottom-right: (1092,1092)
- Center red crosshair at (546, 546)
- The content area is UNCLOUDED - you can see the full UI clearly
- IMPORTANT: Output coordinates in 1092x1092 space, not the original screen resolution
- To find a target: use the edge tick marks to estimate the pixel position within the 1092x1092 grid
- Example: if "Agent Hands" is visually around the middle-left area, estimate (300, 200)

Your job:
1. Analyze the screenshot - identify the target UI element
2. If "上一步检查" section is provided:
   CRITICAL: You MUST explicitly check if the "预期结果" (expected result) is visible in the current screenshot.
   - The expected result tells you what SHOULD have changed after the previous action
   - Look carefully at the screenshot to see if that change actually happened
   - If the expected result IS visible: the previous action succeeded, continue to next step
   - If the expected result is NOT visible: the previous action FAILED, output action=retry with corrected coordinates
   IMPORTANT: Do NOT assume the previous action succeeded. Verify by looking for the expected result in the screenshot.
3. Use the edge tick marks to estimate precise pixel coordinates in 1092x1092 space
4. Based on past execution history, determine the next action to accomplish the goal
5. Output only the action instruction

Output format (MUST follow exactly):
---
当前任务: [What to do in this step - be specific, e.g. "点击消息列表中的 Agent Hands"]
执行动作: {"action":"[click|type|press|done|retry]","x":[number],"y":[number],"text":"[text]","key":"[key]"}
状态: [continue|success|failed]
---

Rules:
1. 状态=success 表示任务已完成
2. 状态=failed 表示无法完成
3. click 需要 x 和 y 坐标 - 使用 1092x1092 坐标系，禁止猜测
4. type 需要先 click 定位光标，再输入文本
5. press 需要按键名（如 "Enter", "Escape"）
6. done 表示任务完成
7. retry 表示上一步的预期结果没有出现，需要调整坐标重新执行上一步
8. 坐标必须为整数，禁止使用数组格式
9. 参考历史记录避免重复错误
10. 必须先验证上一步的预期结果是否出现，再决定下一步"""


    def __init__(self, api_key: str | None = None):
        from config.settings import ZHIPU_API_KEY
        self.api_key = api_key or ZHIPU_API_KEY
        self._session = None
        self._screen = get_screen_capture()
        self.model = "glm-4.6V"
        self.max_tokens = 1500

    @property
    def session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            })
        return self._session

    def decide(self, goal: str, screenshot_path: str | Path | None = None,
               screenshot_array=None, history: str = "",
               prev_step_goal: str | None = None) -> "Decision":
        """决策一步操作"""
        import cv2

        # 1. 获取截图
        if screenshot_array is not None:
            bgr = cv2.cvtColor(screenshot_array, cv2.COLOR_BGRA2BGR)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                cv2.imwrite(tmp.name, bgr)
                img_path = tmp.name
        elif screenshot_path:
            img_path = str(screenshot_path)
        else:
            img, path = self._screen.auto_save(prefix="planner")
            bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                cv2.imwrite(tmp.name, bgr)
                img_path = tmp.name

        # 2. 构建消息
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        history_section = f"\n\n=== Past Execution History ===\n{history}\n===" if history else ""

        # 如果有上一步信息，添加自检部分
        check_section = ""
        if prev_step_goal:
            check_section = f"""=== 上一步检查 ===
上一步目标: {prev_step_goal}
请分析当前截图，判断上一步的预期结果是否已经发生：
- 如果预期结果已出现（例如：聊天窗口已打开、按钮已被点击、输入框已激活等），说明上一步成功，继续执行下一步
- 如果预期结果未出现（例如：界面没有变化、点击位置错误、打开了错误的内容等），说明上一步失败，输出 action=retry 调整坐标重新执行上一步
重要：必须明确检查"预期结果"是否在截图中可见，不要假设上一步成功了

"""

        user_content = [
            {"type": "text", "text": f"Task goal: {goal}"},
            {"type": "text", "text": f"{check_section}{history_section}"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
        ]

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        # 4. 调用 API，带 retry
        from config.settings import ZHIPU_API_URL
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": self.max_tokens,
            # 关闭扩展思考模式，加快响应速度
            "extra": {
                "thinking": {
                    "type": "off"
                }
            }
        }

        response = None
        last_error = None
        for attempt in range(3):
            try:
                resp = self.session.post(ZHIPU_API_URL, json=payload, timeout=60)
                if resp.status_code == 429:
                    wait = (attempt + 1) * 10
                    logger.warning(f"Rate limited (attempt {attempt+1}), waiting {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                resp_text = resp.text
                logger.debug(f"API response text preview: {resp_text[:300]}")
                resp_data = resp.json()
                logger.debug(f"API response keys: {resp_data.keys()}")
                response = resp_data["choices"][0]["message"]["content"]
                logger.debug(f"API raw response: {response[:500]}")
                break
            except Exception as e:
                last_error = e
                logger.warning(f"API attempt {attempt+1} failed: {e}")
                time.sleep(3)

        logger.debug(f"Response before parsing: {repr(response[:200]) if response else None}")
        if response is None:
            logger.error(f"Planner API 调用失败 after 3 attempts: {last_error}")
            logger.debug(f"Last response was: {response}")
            return Decision(
                think=f"API调用失败: {last_error}",
                action=None, x=None, y=None, text=None, key=None,
                status="failed",
                raw_response=str(last_error)
            )

        return self._parse_response(response)

    def _parse_response(self, response: str) -> "Decision":
        """解析 Planner 输出（新版中文格式）"""
        logger.debug(f"_parse_response received: {repr(response[:300]) if response else None}")
        think = ""
        action = None
        x = y = None
        text = key = None
        status = "continue"
        raw = response

        # 提取当前任务（可选，不影响核心逻辑）
        m_task = re.search(r"当前任务:\s*(.+?)(?=---|$)", response, re.DOTALL)
        if m_task:
            think = m_task.group(1).strip()

        # 提取执行动作 JSON（兼容新旧格式）
        for m in re.finditer(r"(?:执行动作|EXEC):\s*(\{[^}]+\})", response):
            try:
                data = json.loads(m.group(1))
                action = data.get("action")
                raw_x = data.get("x")
                raw_y = data.get("y")

                if isinstance(raw_x, (int, float)):
                    x = int(raw_x)
                if isinstance(raw_y, (int, float)):
                    y = int(raw_y)
                if isinstance(raw_x, list) and len(raw_x) >= 1:
                    x = int(raw_x[0])
                    if len(raw_x) >= 2:
                        y = int(raw_x[1])

                text = data.get("text")
                key = data.get("key")
                break
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

        # 提取状态（兼容新旧格式）
        for m in re.finditer(r"(?:状态|STATUS):\s*(\w+)", response):
            status = m.group(1).strip().lower()
            if status in ("continue", "success", "failed"):
                break

        if action is None and status in ("success", "done"):
            action = "done"

        logger.info(f"Planner decision: {action} ({x},{y}) | status={status}")
        if think:
            logger.debug(f"THINK: {think[:100]}")

        return Decision(
            think=think,
            action=action, x=x, y=y, text=text, key=key,
            status=status,
            raw_response=raw
        )


@dataclass
class Decision:
    """规划决策结果"""
    think: str
    action: str | None
    x: int | None
    y: int | None
    text: str | None
    key: str | None
    status: str  # continue / success / failed
    raw_response: str = ""

