"""
创建测试群聊并添加机器人的脚本
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

print("=" * 50)
print("Create Test Group + Bot")
print("=" * 50)

im = IMClient()

# 创建群聊
print("\n1. Creating group chat...")
try:
    result = im._request(
        "POST",
        "/im/v1/chats",
        json={
            "name": "AI Agent Test Group",
            "chat_mode": "group",
            "chat_type": "private",
            "user_id_list": []
        }
    )
    chat_id = result.get("chat_id")
    print(f"[OK] Group created! chat_id: {chat_id}")
    print(f"  Group name: AI Agent Test Group")
except Exception as e:
    print(f"[FAIL] Create group: {e}")
    import traceback
    traceback.print_exc()
    chat_id = None

if chat_id:
    # 保存 chat_id 到文件供后续使用
    config_path = project_root / "feishu_agent" / ".test_config.json"
    import json
    config = {"test_chat_id": chat_id, "test_group_name": "AI Agent Test Group"}
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    print(f"\n[OK] chat_id saved to {config_path}")
    print(f"  请在飞书中打开该群，添加机器人 'FeishuTestBot' 后即可测试")

print("\nDone.")
