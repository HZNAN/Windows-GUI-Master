"""
优化后的视觉坐标测试
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import base64
import requests

ZHIPU_API_KEY = "e539790a8240487c90e89c889f814b4f.1H5t3p9QsiOJuWn5"
GLM_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
headers = {"Authorization": f"Bearer {ZHIPU_API_KEY}", "Content-Type": "application/json"}

# 使用最近一张截图
img_path = r"E:\programe\OpenClaw\feishu_hand\feishu_agent\.screenshots\exec_1_20260415_161104_989564.png"

with open(img_path, "rb") as f:
    img_bytes = f.read()
img_base64 = base64.b64encode(img_bytes).decode("utf-8")
print(f"Image: {img_path}")
print(f"Size: {len(img_bytes)} bytes")

# 优化 prompt：明确要求返回像素坐标
payload = {
    "model": "glm-4v",
    "messages": [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}},
            {"type": "text", "text": (
                "You are a screen coordinate extractor. "
                "Find the 'Agent Hands' icon in this Feishu screenshot. "
                "Return ONLY valid JSON with exact pixel coordinates of its center: "
                '{"x": number, "y": number, "description": "brief description"}'
                "If you cannot find it, return: {\"found\": false}"
            )}
        ]
    }],
    "temperature": 0.1,
    "max_tokens": 200
}

print("\nOptimized prompt test:")
resp = requests.post(GLM_API_URL, json=payload, headers=headers, timeout=30)
result = resp.json()
content = result["choices"][0]["message"]["content"]
print(f"Response: {content}")

# 解析坐标
import re, json
m = re.search(r'\{.*\}', content, re.DOTALL)
if m:
    try:
        data = json.loads(m.group(0))
        print(f"Parsed: {data}")
        if "x" in data and "y" in data:
            print(f"  Coordinates: ({data['x']}, {data['y']})")
    except:
        print("JSON parse failed")
