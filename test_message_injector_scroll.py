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
# Test 8: drag in Explorer (文件拖拽)
# ============================================================
prompt("Test 8: 资源管理器中 scroll 滚轮")

print("请输入资源管理器文件列表区域的屏幕坐标 (x y)：")
coords = input("> ").strip().split()
ex, ey = int(coords[0]), int(coords[1])

print(f"注入 click ({ex}, {ey}) 激活资源管理器")
injector.click(ex, ey)
time.sleep(0.3)

print("注入 scroll down x3")
injector.scroll(ex, ey, -3)
time.sleep(0.3)

print("注入 scroll up x3")
injector.scroll(ex, ey, 3)
time.sleep(0.3)

screen.auto_save(prefix="test8_explorer_scroll")
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
print("  [ ] 8. Explorer scroll — 资源管理器中文件列表滚动了")
print()
print("截图保存在 .screenshots/ 目录，可查看对比")
print(f"基准光标位置: {original}")
