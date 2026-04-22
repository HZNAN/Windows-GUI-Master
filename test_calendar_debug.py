"""
Calendar API 调试
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests

APP_ID = "cli_a955804b60f85bd2"
APP_SECRET = "obOr27UvyPNuI2dhDgmqjh81CPBOswX2"
BASE = "https://open.feishu.cn/open-apis"

resp = requests.post(
    f"{BASE}/auth/v3/app_access_token/internal",
    json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10
)
token = resp.json().get("app_access_token")
headers = {"Authorization": f"Bearer {token}"}

# 直接测 list_events，不带任何参数
print("Test 1: Calendar events list - no params")
r = requests.get(f"{BASE}/calendar/v4/calendars/primary/events", headers=headers, timeout=10)
print(f"  {r.status_code}: {r.text[:300]}")

# 带 page_size
print("\nTest 2: Calendar events list - with page_size=5")
r = requests.get(f"{BASE}/calendar/v4/calendars/primary/events",
    headers=headers, params={"page_size": 5}, timeout=10)
print(f"  {r.status_code}: {r.text[:300]}")

# 只带 start_time
print("\nTest 3: Calendar events list - with start_time only")
import time
ts = int(time.time())
r = requests.get(f"{BASE}/calendar/v4/calendars/primary/events",
    headers=headers, params={"start_time": ts, "start_time_type": "UTC"}, timeout=10)
print(f"  {r.status_code}: {r.text[:300]}")

# 完整格式
print("\nTest 4: Calendar events list - full params")
r = requests.get(f"{BASE}/calendar/v4/calendars/primary/events",
    headers=headers,
    params={"start_time": ts, "start_time_type": "UTC", "page_size": 5}, timeout=10)
print(f"  {r.status_code}: {r.text[:300]}")
