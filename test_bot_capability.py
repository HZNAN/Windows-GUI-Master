"""
检查现有应用是否支持机器人
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests

APP_ID = "cli_a955804b60f85bd2"
APP_SECRET = "obOr27UvyPNuI2dhDgmqjh81CPBOswX2"
BASE = "https://open.feishu.cn/open-apis"

# 获取 token
resp = requests.post(f"{BASE}/auth/v3/app_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
token = resp.json().get("app_access_token")
headers = {"Authorization": f"Bearer {token}"}

print("Checking bot capability...\n")

# 测试1: 获取机器人信息
print("1. GET /im/v1/bots")
r = requests.get(f"{BASE}/im/v1/bots", headers=headers, timeout=10)
print(f"   Status: {r.status_code}")
print(f"   Response: {r.text[:200]}")

# 测试2: 往群里发消息（用 app token）
CHAT_ID = "oc_29e94daf1fe37c39645a3a47e7391e3a"
print(f"\n2. POST /im/v1/messages to chat {CHAT_ID}")
r = requests.post(f"{BASE}/im/v1/messages",
    headers=headers,
    json={
        "receive_id_type": "chat_id",
        "receive_id": CHAT_ID,
        "msg_type": "text",
        "content": '{"text":"Hello from AI Agent!"}'
    }, timeout=10)
print(f"   Status: {r.status_code}")
print(f"   Response: {r.text[:300]}")
