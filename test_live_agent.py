"""
真实飞书桌面流程测试
截取当前屏幕，观察飞书界面，让 Agent 理解并规划下一步操作
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
os.environ['ZHIPU_API_KEY'] = 'e539790a8240487c90e89c889f814b4f.1H5t3p9QsiOJuWn5'

print("=" * 60)
print("Real Feishu Desktop - Live Agent Test")
print("=" * 60)

# Step 1: 截取当前屏幕
print("\n1. Capturing current screen...")
from drivers.screen_capture import ScreenCapture
sc = ScreenCapture()

# 截取主屏
img, path = sc.auto_save(prefix="feishu_live")
print(f"   Screenshot saved: {path}")
print(f"   Image shape: {img.shape}")

# Step 2: 用 GLM-4V 理解当前界面
print("\n2. Understanding screen with GLM-4V...")
from llm.glm_vision_client import GLMVisionClient
vision = GLMVisionClient()

action = vision.infer(
    screenshot=str(path),
    instruction=(
        "这是飞书桌面客户端的截图。"
        "请描述：1) 当前界面是什么（IM/日历/文档等）"
        "2) 有哪些可交互元素（如搜索框、输入框、按钮等）"
        "3) 用 JSON 返回：{\"interface\": \"界面类型\", \"elements\": [\"元素1\", \"元素2\"], \"status\": \"状态描述\"}"
    )
)
print(f"   Interface: {action.raw_response['choices'][0]['message']['content'][:400]}")

# Step 3: 让 Agent 规划下一步操作
print("\n3. Planning next action...")
from llm.planner_llm_client import PlannerLLMClient
planner = PlannerLLMClient(provider="zhipu")

goal = "给 Agent Hands 发送消息：测试"
plan = planner.plan(goal)
print(f"   Goal: {goal}")
print(f"   Steps planned: {len(plan.steps)}")
for i, step in enumerate(plan.steps):
    print(f"   [{i+1}] {step.action} -> {step.target} | {step.description}")

# Step 4: 执行第一步操作（截图 + 视觉定位）
print("\n4. Executing first step...")
from core.element_locator import ElementLocator
locator = ElementLocator(vision_client=vision)

first_step = plan.steps[0]
print(f"   Action: {first_step.action} | Target: {first_step.target}")

# 重新截图并定位
img2, path2 = sc.auto_save(prefix="feishu_live_step1")
coords = locator.locate(first_step.target, img2, method="auto")

if coords:
    print(f"   [OK] Element located at: {coords}")
    print(f"   Ready to click at {coords}")
else:
    print(f"   [WARN] Could not locate '{first_step.target}' automatically")
    print(f"   Please locate manually or add to sample library")

# Step 5: 在截图上标记定位结果
try:
    import cv2
    annotated = img2.copy()
    if coords:
        x, y = coords
        cv2.rectangle(annotated, (x-10, y-10), (x+10, y+10), (0, 255, 0), 2)
        annotated_path = project_root / ".screenshots" / "feishu_live_annotated.png"
        cv2.imwrite(str(annotated_path), annotated)
        print(f"   Annotated screenshot: {annotated_path}")
except Exception as e:
    print(f"   Could not annotate: {e}")

print("\n" + "=" * 60)
print("Live test complete. Check .screenshots/ for results.")
print("=" * 60)
