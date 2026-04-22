"""
智谱 API 端到端测试
测试完整的 Planner + Vision 流程
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests

ZHIPU_API_KEY = "e539790a8240487c90e89c889f814b4f.1H5t3p9QsiOJuWn5"
GLM_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

headers = {
    "Authorization": f"Bearer {ZHIPU_API_KEY}",
    "Content-Type": "application/json"
}

# ==================== Planner Test ====================
print("=" * 50)
print("Test: Planner (GLM-4-Flash)")
print("=" * 50)

SYSTEM_PROMPT = """You are a task planning assistant. Decompose high-level goals into ordered executable steps.

Output format: Strict JSON object with 'goal' field and 'steps' array.
Each step MUST contain these exact fields:
- action: action type (click / type / press / scroll / wait)
- target: semantic target name (e.g. "search box", "send button"), null if using coordinates
- x, y: pixel coordinates (only when action=click with known coordinates), null otherwise
- text: input text (only when action=type)
- key: key name (only when action=press)
- description: Chinese description of the step

Rules:
1. Steps must be minimal atomic operations
2. Return empty steps array if task is impossible
3. Output ONLY the JSON, no markdown, no explanation"""

FEW_SHOT = '''
Input: Send a message to Zhang San saying 'Hello'
Output:
{"goal": "Send a message to Zhang San saying 'Hello'", "steps": [{"action": "click", "target": "Feishu icon", "x": null, "y": null, "text": null, "description": "Open Feishu app"}, {"action": "click", "target": "Search box", "x": null, "y": null, "text": null, "description": "Click search box"}, {"action": "type", "target": "Search box", "x": null, "y": null, "text": "Zhang San", "description": "Search for Zhang San"}, {"action": "click", "target": "Zhang San chat", "x": null, "y": null, "text": null, "description": "Open chat with Zhang San"}, {"action": "type", "target": "Input box", "x": null, "y": null, "text": "Hello", "description": "Type message content"}, {"action": "click", "target": "Send button", "x": null, "y": null, "text": null, "description": "Click send"}]}
'''

goal = "Send a message to Zhang San saying 'Hello'"
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": f"{FEW_SHOT}\n\nInput: {goal}\nOutput:"}
]

payload = {
    "model": "glm-4-flash",
    "messages": messages,
    "temperature": 0.1,
    "max_tokens": 1000
}

try:
    resp = requests.post(GLM_API_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    raw_content = result["choices"][0]["message"]["content"]
    print(f"[OK] Response: {raw_content[:400]}")

    # 解析 JSON
    import json
    text = raw_content.strip()
    # 去 markdown
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    data = json.loads(text)
    print(f"[OK] Parsed {len(data.get('steps', []))} steps")
    for i, step in enumerate(data.get("steps", [])):
        print(f"  Step {i+1}: {step.get('action')} -> {step.get('target')} | {step.get('description')}")
except Exception as e:
    print(f"[FAIL] Error: {e}")
    if hasattr(e, 'response'):
        print(f"   Response: {getattr(e, 'response', None) and e.response.text[:300]}")

# ==================== Vision Test ====================
print()
print("=" * 50)
print("Test: Vision (GLM-4V-Flash)")
print("=" * 50)

try:
    from PIL import Image
    import io
    import base64

    # 创建模拟飞书界面的测试图（简单灰度图）
    img = Image.new("RGB", (800, 600), color=(240, 240, 245))
    # 画一个蓝色矩形模拟按钮
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.rectangle([650, 520, 750, 570], fill=(30, 100, 220), outline=(20, 80, 200))
    draw.text((665, 535), "Send", fill=(255, 255, 255))

    img_bytes_io = io.BytesIO()
    img.save(img_bytes_io, format="PNG")
    img_bytes = img_bytes_io.getvalue()
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")

    vision_messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}},
                {"type": "text", "text": '''分析这张飞书截图。用户要求：点击发送按钮（Send button）。

请用 JSON 格式返回动作指令：
{"action": "click", "target": "按钮语义名称", "x": 像素x坐标(如果有), "y": 像素y坐标(如果有), "thought": "推理过程"}

注意：如果能看出按钮的位置，请在 x,y 中给出像素坐标。'''}
            ]
        }
    ]

    vision_payload = {
        "model": "glm-4v-flash",
        "messages": vision_messages,
        "temperature": 0.1,
        "max_tokens": 500
    }

    resp = requests.post(GLM_API_URL, json=vision_payload, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    content = result["choices"][0]["message"]["content"]
    print(f"[OK] Vision Response: {content[:400]}")

    # 解析
    json_match = __import__('re').search(r'\{.*\}', content, __import__('re').DOTALL)
    if json_match:
        action_data = json.loads(json_match.group(0))
        print(f"[OK] Parsed action: {action_data.get('action')} -> {action_data.get('target')} at ({action_data.get('x')}, {action_data.get('y')})")
    else:
        print(f"[WARN] No JSON found in response")

except ImportError as e:
    print(f"[SKIP] PIL not available: {e}")
except Exception as e:
    print(f"[FAIL] Error: {e}")
    if hasattr(e, 'response'):
        print(f"   Response: {getattr(e, 'response', None) and e.response.text[:300]}")

print()
print("=" * 50)
print("All tests complete")
print("=" * 50)
