"""
测试智谱 GLM-OCR 的文字定位能力
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import base64, requests

ZHIPU_API_KEY = "e539790a8240487c90e89c889f814b4f.1H5t3p9QsiOJuWn5"

# 用最近一张截图测试 OCR 文字定位
img_path = r"E:\programe\OpenClaw\feishu_hand\feishu_agent\.screenshots\exec_4_20260415_161419_252489.png"
with open(img_path, "rb") as f:
    img_bytes = f.read()
img_base64 = base64.b64encode(img_bytes).decode("utf-8")
print(f"Image: {img_path}")

# 方式1: 用 zai-sdk 风格直接调用 GLM-OCR
# 先测模型列表，看支持什么
print("\n--- Test 1: Check available models ---")
try:
    resp = requests.get(
        "https://open.bigmodel.cn/api/paas/v4/models",
        headers={"Authorization": f"Bearer {ZHIPU_API_KEY}"}, timeout=10
    )
    models = resp.json()
    for m in models.get("data", []):
        mid = m.get("id", "")
        if "ocr" in mid.lower() or "glm-4v" in mid.lower() or "glm-4" in mid.lower():
            print(f"  [OK] {mid}")
except Exception as e:
    print(f"Error: {e}")

# 方式2: 直接用 glm-4v 测文字定位，强制要求返回坐标
print("\n--- Test 2: GLM-4V with strict coordinate prompt ---")
headers = {"Authorization": f"Bearer {ZHIPU_API_KEY}", "Content-Type": "application/json"}
payload = {
    "model": "glm-4v",
    "messages": [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}},
            {"type": "text", "text": (
                'You are a screen OCR. Find ALL text elements with their EXACT pixel bounding boxes. '
                'Return a JSON array of {text, x1, y1, x2, y2} for each text found. '
                'x1,y1 is top-left corner, x2,y2 is bottom-right corner. '
                'Example: [{"text":"Send","x1":100,"y1":200,"x2":150,"y2":230}]'
            )}
        ]
    }],
    "temperature": 0.1,
    "max_tokens": 2000
}
try:
    resp = requests.post(
        "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        json=payload, headers=headers, timeout=30
    )
    result = resp.json()
    content = result["choices"][0]["message"]["content"]
    print(f"Response: {content[:600]}")
except Exception as e:
    print(f"Error: {e}")
