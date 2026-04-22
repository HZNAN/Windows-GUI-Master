"""
飞书 API 连通性测试
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests

FEISHU_APP_ID = "cli_a955804b60f85bd2"
FEISHU_APP_SECRET = "obOr27UvyPNuI2dhDgmqjh81CPBOswX2"
APP_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"

print("Test: Feishu App Token")
payload = {
    "app_id": FEISHU_APP_ID,
    "app_secret": FEISHU_APP_SECRET
}

try:
    resp = requests.post(APP_TOKEN_URL, json=payload, timeout=10)
    result = resp.json()
    print(f"Status: {resp.status_code}")
    print(f"Response: {result}")

    if result.get("code") == 0:
        print("[OK] Feishu API connected!")
        print(f"  App Token expires in: {result.get('data', {}).get('expire')}")
    else:
        print(f"[FAIL] Error code: {result.get('code')}, msg: {result.get('msg')}")
except Exception as e:
    print(f"[FAIL] Exception: {e}")
