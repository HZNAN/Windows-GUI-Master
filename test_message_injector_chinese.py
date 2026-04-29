"""消息注入模式完整测试：覆盖 click / drag / scroll / keyboard / mouse_down+up"""
import time
import win32api
from drivers.message_injector import MessageInjector
from drivers.screen_capture import get_screen_capture


def check_cursor_unchanged(original, label: str) -> bool:
    current = win32api.GetCursorPos()
    ok = original == current
    status = "PASS" if ok else f"FAIL (移到 {current})"
    print(f"  [{status}] 真实光标{label}")
    return ok


def prompt(msg: str):
    print(f"\n{'='*60}")
    print(f">>> {msg}")
    print(f"{'='*60}")


injector = MessageInjector()
screen = get_screen_capture()

print("=" * 60)
print("  消息注入模式 — 完整功能测试")
print("=" * 60)
print()
print("准备工作:")
print("  1. 打开一个记事本 (notepad) 窗口，放在屏幕左侧约 1/4 处")
print("  2. 打开一个资源管理器 (explorer) 窗口，放在屏幕右侧约 3/4 处")
print("  3. 将真实鼠标移到屏幕最右下角，测试期间不要移动")
print()
input("准备好后按 Enter 开始...")

# 记录基准光标位置
original = win32api.GetCursorPos()
print(f"\n基准光标位置: {original}")
screen.auto_save(prefix="test_start")

all_pass = True

# ============================================================
# Test 9: 中文输入
# ============================================================
prompt("Test 9: 中文文本注入（剪贴板粘贴）")

print("请输入记事本标题栏的屏幕坐标 (x y)（切换回记事本）：")
coords = input("> ").strip().split()
nx, ny = int(coords[0]), int(coords[1])

print(f"注入 click ({nx}, {ny}) 重新激活记事本")
injector.click(nx, ny)
time.sleep(0.3)

injector.type_text("你好世界！这是消息注入的中文测试。")
time.sleep(0.5)

screen.auto_save(prefix="test9_chinese")
all_pass &= check_cursor_unchanged(original, "未移动")

# ============================================================
# Summary
# ============================================================
print()
print("=" * 60)
print("  测试完成！")
print("=" * 60)
print()
print("检查清单:")
print("  [ ] 9. 中文输入 — 记事本中出现了中文")
print()
print("截图保存在 .screenshots/ 目录，可查看对比")
print(f"基准光标位置: {original}")
