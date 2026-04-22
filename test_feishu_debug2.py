"""
飞书 API 调试 - 测试各模块正确格式
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests

APP_ID = "cli_a955804b60f85bd2"
APP_SECRET = "obOr27UvyPNuI2dhDgmqjh81CPBOswX2"
BASE = "https://open.feishu.cn/open-apis"

# 获取 token
resp = requests.post(
    f"{BASE}/auth/v3/app_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10
)
token = resp.json().get("app_access_token")
headers = {"Authorization": f"Bearer {token}"}

print(f"Token: {token[:20]}...")

# Test 1: IM - 搜索群聊
# 飞书 v1 API 的 search_chats 端点可能不对，试试 /im/v1/chats
print("\n--- IM: Search Chats ---")
try:
    r = requests.get(f"{BASE}/im/v1/chats", headers=headers, params={"page_size": 5}, timeout=10)
    print(f"GET /im/v1/chats: {r.status_code} | {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: IM - 获取群列表
print("\n--- IM: List Chats ---")
try:
    r = requests.get(f"{BASE}/im/v1/chats", headers=headers, params={}, timeout=10)
    print(f"GET /im/v1/chats (no params): {r.status_code} | {r.text[:300]}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Calendar - 获取主日历
print("\n--- Calendar: Get Primary Calendar ---")
try:
    r = requests.get(f"{BASE}/calendar/v4/calendars/primary", headers=headers, timeout=10)
    print(f"GET /calendar/v4/calendars/primary: {r.status_code} | {r.text[:300]}")
except Exception as e:
    print(f"Error: {e}")

# Test 4: Calendar - 列出事件
print("\n--- Calendar: List Events ---")
try:
    r = requests.get(f"{BASE}/calendar/v4/calendars/primary/events", headers=headers, params={"page_size": 5}, timeout=10)
    print(f"GET /calendar/v4/calendars/primary/events: {r.status_code} | {r.text[:300]}")
except Exception as e:
    print(f"Error: {e}")

# Test 5: Doc - 列出文档
print("\n--- Doc: List Files ---")
try:
    r = requests.get(f"{BASE}/drive/v1/files", headers=headers, params={"page_size": 5}, timeout=10)
    print(f"GET /drive/v1/files: {r.status_code} | {r.text[:300]}")
except Exception as e:
    print(f"Error: {e}")

# Test 6: Doc - 创建文档
print("\n--- Doc: Create Doc ---")
try:
    r = requests.post(f"{BASE}/docx/v1/documents", headers=headers, json={"Title": "Test Doc"}, timeout=10)
    print(f"POST /docx/v1/documents: {r.status_code} | {r.text[:300]}")
except Exception as e:
    print(f"Error: {e}")
