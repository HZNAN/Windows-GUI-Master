"""
真实执行 Agent 操作 - 向 Agent Hands 发送消息
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
os.environ['ZHIPU_API_KEY'] = 'e539790a8240487c90e89c889f814b4f.1H5t3p9QsiOJuWn5'

from drivers.screen_capture import ScreenCapture
from drivers.input_control import InputControl
from llm.glm_vision_client import GLMVisionClient
from llm.planner_llm_client import PlannerLLMClient
from core.element_locator import ElementLocator

sc = ScreenCapture()
inp = InputControl()
vision = GLMVisionClient()
planner = PlannerLLMClient(provider="zhipu")
locator = ElementLocator(vision_client=vision)

GOAL = "给 Agent Hands 发送消息：测试"
STEP_TIMEOUT = 15  # 每步超时秒

print("=" * 60)
print("Agent Hands - Message Sending Execution")
print("=" * 60)
print(f"\nGoal: {GOAL}\n")

# 规划
plan = planner.plan(GOAL)
print(f"Plan: {len(plan.steps)} steps")
for i, s in enumerate(plan.steps):
    print(f"  [{i+1}] {s.action} | {s.target} | {s.description}")

print()

# 等待用户准备
import time
time.sleep(2)

# 逐步执行
for i, step in enumerate(plan.steps):
    print(f"\n--- Step {i+1}/{len(plan.steps)}: {step.action} | {step.target} ---")

    # 截图
    img, path = sc.auto_save(prefix=f"exec_{i+1}")
    print(f"  Screenshot: {path.name}")

    # 定位元素
    coords = None
    if step.action == "type" and step.target:
        # type 动作需要先定位目标
        coords = locator.locate(step.target, img, method="ui_tars")

    if not coords:
        # click 动作直接定位
        coords = locator.locate(step.target, img, method="ui_tars")

    if not coords:
        print(f"  [WARN] Cannot locate '{step.target}', trying direct mode...")
        # fallback: 让视觉模型直接给坐标
        action = vision.infer(screenshot=str(path),
            instruction=f"在截图上找到'{step.target}'的中心像素坐标，只返回JSON: {{\"x\":数字,\"y\":数字}}")
        raw = str(action.raw_response)
        import re
        m = re.search(r'"x"\s*:\s*(\d+).*?"y"\s*:\s*(\d+)', raw, re.DOTALL)
        if m:
            coords = (int(m.group(1)), int(m.group(2)))
            print(f"  [OK] Direct vision coords: {coords}")

    if not coords:
        print(f"  [SKIP] Cannot locate '{step.target}', skipping step")
        continue

    print(f"  Clicking at: {coords}")

    # 执行
    if step.action == "click":
        inp.click(coords[0], coords[1])
    elif step.action == "type":
        inp.click(coords[0], coords[1])
        time.sleep(0.5)
        inp.type_text(step.text or "")
        print(f"  Typed: {step.text}")
    elif step.action == "press":
        inp.press_key(step.key or "Enter")

    # 等待页面响应
    time.sleep(2)

print("\n" + "=" * 60)
print("Execution complete. Check Feishu desktop!")
print("=" * 60)
