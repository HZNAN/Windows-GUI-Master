"""
视觉 API 调试脚本
测试 GLM-4V-Flash 的不同图片格式
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import base64
import requests
from PIL import Image
import io

ZHIPU_API_KEY = "e539790a8240487c90e89c889f814b4f.1H5t3p9QsiOJuWn5"
GLM_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

headers = {
    "Authorization": f"Bearer {ZHIPU_API_KEY}",
    "Content-Type": "application/json"
}

# 创建测试图片
img = Image.new("RGB", (400, 300), color=(100, 150, 200))
img_bytes_io = io.BytesIO()
img.save(img_bytes_io, format="PNG")
img_bytes = img_bytes_io.getvalue()
img_base64 = base64.b64encode(img_bytes).decode("utf-8")

print(f"Image size: {len(img_bytes)} bytes")
print(f"Base64 length: {len(img_base64)}")

# 方式1：image_url + base64
payload1 = {
    "model": "glm-4v-flash",
    "messages": [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}},
            {"type": "text", "text": "简单描述这张图片"}
        ]
    }],
    "temperature": 0.1,
    "max_tokens": 200
}

print("\n[Test 1] Image URL with base64...")
try:
    resp = requests.post(GLM_API_URL, json=payload1, headers=headers, timeout=30)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error: {resp.text[:300]}")
    else:
        result = resp.json()
        print(f"OK: {result['choices'][0]['message']['content'][:200]}")
except Exception as e:
    print(f"Exception: {e}")

# 方式2：直接用 url 字段（不指定 data URI）
payload2 = {
    "model": "glm-4v-flash",
    "messages": [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": img_base64}},  # 直接 base64
            {"type": "text", "text": "简单描述这张图片"}
        ]
    }],
    "temperature": 0.1,
    "max_tokens": 200
}

print("\n[Test 2] Direct base64 without data URI...")
try:
    resp = requests.post(GLM_API_URL, json=payload2, headers=headers, timeout=30)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error: {resp.text[:300]}")
    else:
        result = resp.json()
        print(f"OK: {result['choices'][0]['message']['content'][:200]}")
except Exception as e:
    print(f"Exception: {e}")

# 方式3：用 text 字段做纯文本测试（验证 API Key 正确）
payload3 = {
    "model": "glm-4v-flash",
    "messages": [{"role": "user", "content": "Hello, who are you?"}],
    "temperature": 0.1,
    "max_tokens": 100
}

print("\n[Test 3] Plain text only (verify API key)...")
try:
    resp = requests.post(GLM_API_URL, json=payload3, headers=headers, timeout=30)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error: {resp.text[:300]}")
    else:
        result = resp.json()
        print(f"OK: {result['choices'][0]['message']['content'][:200]}")
except Exception as e:
    print(f"Exception: {e}")

# 方式4：检查模型列表
print("\n[Test 4] Check available models...")
try:
    resp = requests.get(
        "https://open.bigmodel.cn/api/paas/v4/models",
        headers=headers, timeout=10
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        models = resp.json()
        for m in models.get("data", []):
            print(f"  - {m.get('id')}")
    else:
        print(f"Error: {resp.text[:200]}")
except Exception as e:
    print(f"Exception: {e}")
