"""
获取 Agent Hands 的 chat_id
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

print("Searching for Agent Hands...")

im = IMClient()

# 搜索包含 "Hands" 的会话
try:
    # 先获取单聊列表
    chats = im._request("GET", "/im/v1/chats", params={"chat_type": "p2p"})
    items = chats.get("items", [])
    print(f"Found {len(items)} chats")
    for c in items:
        print(f"  - {c.get('name', 'N/A')} | {c.get('chat_id', 'N/A')}")
except Exception as e:
    print(f"Error: {e}")

# 也搜索群聊
try:
    group_chats = im._request("GET", "/im/v1/chats")
    items = group_chats.get("items", [])
    print(f"\nAll chats: {len(items)}")
    for c in items:
        print(f"  - {c.get('name', 'N/A')} | {c.get('chat_id', 'N/A')} | type={c.get('chat_type')}")
except Exception as e:
    print(f"Error: {e}")
