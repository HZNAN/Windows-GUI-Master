"""
将应用机器人添加到测试群
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
os.environ['FEISHU_APP_ID'] = 'cli_a955804b60f85bd2'
os.environ['FEISHU_APP_SECRET'] = 'obOr27UvyPNuI2dhDgmqjh81CPBOswX2'

from feishu_api.im_client import IMClient

CHAT_ID = "oc_29e94daf1fe37c39645a3a47e7391e3a"

print("=" * 50)
print("Add Bot to Group")
print("=" * 50)

im = IMClient()

# 获取应用自身的信息（验证 bot 是否可用）
print("\n1. Get bot info...")
try:
    bot_info = im._request("GET", "/im/v1/bots")
    print(f"[OK] Bot info: {bot_info}")
except Exception as e:
    print(f"[INFO] Bot info: {e}")

# 将 bot 添加到群聊
print("\n2. Add bot to group...")
try:
    result = im._request(
        "POST",
        f"/im/v1/chats/{CHAT_ID}/members",
        json={
            "id_list": [],
            "member_id_list": [],
            "member_id_type": "open_id"
        }
    )
    print(f"[OK] Add bot: {result}")
except Exception as e:
    print(f"[INFO] Add bot: {e}")

# 获取群成员列表
print("\n3. List group members...")
try:
    result = im._request("GET", f"/im/v1/chats/{CHAT_ID}/members")
    members = result.get("items", [])
    print(f"[OK] Members: {len(members)}")
    for m in members:
        print(f"  - {m.get('name', 'N/A')} | {m.get('member_id', 'N/A')} | {m.get('tenant_id', 'N/A')}")
except Exception as e:
    print(f"[INFO] List members: {e}")

print("\nDone.")
