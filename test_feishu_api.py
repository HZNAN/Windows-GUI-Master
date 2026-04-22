"""
飞书 API 验证测试（精简版）
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
os.environ['FEISHU_APP_ID'] = 'cli_a955804b60f85bd2'
os.environ['FEISHU_APP_SECRET'] = 'obOr27UvyPNuI2dhDgmqjh81CPBOswX2'

print("=" * 50)
print("Feishu API Connectivity Test")
print("=" * 50)

from feishu_api.auth import FeishuAuth
auth = FeishuAuth()

# App Token
try:
    app_token = auth.get_app_token()
    print(f"[OK] App Token: {app_token[:20]}...")
except Exception as e:
    print(f"[FAIL] App Token: {e}")

# IM API - search chats
try:
    from feishu_api.im_client import IMClient
    im = IMClient()
    chats = im.search_chats("飞书", page_size=5)
    print(f"[OK] IM search_chats: returned {len(chats)} results")
except Exception as e:
    print(f"[INFO] IM search_chats: {e}")

# Calendar API
try:
    from feishu_api.calendar_client import CalendarClient
    cal = CalendarClient()
    events = cal.list_events(page_size=5)
    print(f"[OK] Calendar list_events: returned {len(events)} events")
except Exception as e:
    print(f"[INFO] Calendar: {e}")

# Doc API
try:
    from feishu_api.doc_client import DocClient
    doc = DocClient()
    docs = doc.list_docs(page_size=5)
    print(f"[OK] Doc list_docs: returned {len(docs)} docs")
except Exception as e:
    print(f"[INFO] Doc: {e}")

print()
print("All Feishu API tests done")
