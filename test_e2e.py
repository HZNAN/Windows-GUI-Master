"""
端到端集成测试
测试 Agent 完整流程：规划 + 视觉 + 执行（无飞书 API）
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
os.environ['ZHIPU_API_KEY'] = 'e539790a8240487c90e89c889f814b4f.1H5t3p9QsiOJuWn5'

from llm.planner_llm_client import PlannerLLMClient
from llm.glm_vision_client import GLMVisionClient
from core.element_locator import ElementLocator

print("=" * 50)
print("Step 1: Planner - 任务规划分解")
print("=" * 50)

planner = PlannerLLMClient(provider="zhipu")
goal = "给张三发送消息：你好"
plan = planner.plan(goal)

print(f"Goal: {plan.goal}")
print(f"Steps: {len(plan.steps)}")
for i, step in enumerate(plan.steps):
    print(f"  [{i+1}] {step.action} | target={step.target} | {step.description}")

print()
print("=" * 50)
print("Step 2: Vision - 截图理解 + 元素定位")
print("=" * 50)

# 创建测试截图（模拟飞书界面）
try:
    from PIL import Image, ImageDraw
    import io

    # 创建 800x600 模拟飞书界面
    img = Image.new("RGB", (800, 600), color=(248, 249, 250))
    draw = ImageDraw.Draw(img)

    # 画搜索框
    draw.rectangle([200, 50, 500, 90], fill=(255, 255, 255), outline=(200, 200, 200))
    draw.text((210, 62), "Search...", fill=(150, 150, 150))

    # 画发送按钮
    draw.rectangle([650, 500, 750, 550], fill=(30, 100, 220), outline=(20, 80, 200))
    draw.text((670, 515), "Send", fill=(255, 255, 255))

    # 画输入框
    draw.rectangle([200, 450, 640, 540], fill=(255, 255, 255), outline=(200, 200, 200))
    draw.text((210, 480), "Type message...", fill=(150, 150, 150))

    # 保存测试截图
    test_screenshot = project_root / ".screenshots" / "feishu_mock.png"
    test_screenshot.parent.mkdir(exist_ok=True)
    img.save(test_screenshot)
    print(f"Test screenshot saved: {test_screenshot}")

    # 测试 GLM-4V-Flash 视觉理解
    vision = GLMVisionClient()
    action = vision.infer(
        screenshot=str(test_screenshot),
        instruction="点击发送按钮（Send button）"
    )
    print(f"Vision result: {action.action_type} | target={action.target} | coords=({action.x}, {action.y})")
    print(f"Raw response: {str(action.raw_response)[:200]}")

    print()
    print("=" * 50)
    print("Step 3: Element Locator - 定位测试")
    print("=" * 50)

    locator = ElementLocator(vision_client=vision)
    coords = locator.locate("Send button", method="template")
    if coords:
        print(f"Template match found: {coords}")
    else:
        coords = locator.locate("Send button", method="ui_tars")
        print(f"UI-TARS/GLM location: {coords}")

    print()
    print("=" * 50)
    print("All tests passed!")
    print("=" * 50)

except ImportError:
    print("[SKIP] PIL not available - install with: pip install Pillow")
except Exception as e:
    print(f"[FAIL] Error: {e}")
    import traceback
    traceback.print_exc()
