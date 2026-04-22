"""
飞书 API 调试
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests

FEISHU_APP_ID = "cli_a955804b60f85bd2"
FEISHU_APP_SECRET = "obOr27UvyPNuI2dhDgmqjh81CPBOswX2"
APP_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"

print("Testing Feishu Auth API directly...")
resp = requests.post(APP_TOKEN_URL, json={
    "app_id": FEISHU_APP_ID,
    "app_secret": FEISHU_APP_SECRET
}, timeout=10)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")
