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
# Test 1: click + type_text
# ============================================================
prompt("Test 1: click 记事本 + type_text 输入英文")

print("请输入记事本标题栏的屏幕坐标 (x y)，例如 200 20：")
coords = input("> ").strip().split()
nx, ny = int(coords[0]), int(coords[1])

print(f"注入 click ({nx}, {ny}) 激活记事本")
injector.click(nx, ny)
time.sleep(0.3)

print("注入 type_text + Enter")
injector.type_text("Hello from message injection!")
injector.press_key("enter")
time.sleep(0.2)
injector.type_text("Line 2: scroll and drag test ahead.")
injector.press_key("enter")
time.sleep(0.3)

screen.auto_save(prefix="test1_click_type")
all_pass &= check_cursor_unchanged(original, "未移动")

# ============================================================
# Test 2: scroll
# ============================================================
prompt("Test 2: scroll 滚轮注入")

print("请输入记事本编辑区域的屏幕坐标 (x y)，例如 300 400：")
coords = input("> ").strip().split()
sx, sy = int(coords[0]), int(coords[1])

# 先输入足够多的行
for i in range(20):
    injector.type_text(f"Scroll test line {i+1}")
    injector.press_key("enter")
    time.sleep(0.02)
time.sleep(0.3)

print(f"注入 scroll up x3 在 ({sx}, {sy})")
injector.scroll(sx, sy, 3)
time.sleep(0.3)

print(f"注入 scroll down x5 在 ({sx}, {sy})")
injector.scroll(sx, sy, -5)
time.sleep(0.3)

screen.auto_save(prefix="test2_scroll")
all_pass &= check_cursor_unchanged(original, "未移动")

# ============================================================
# Test 3: drag (文本选择)
# ============================================================
prompt("Test 3: drag 拖拽（文本选择）")

print("请输入拖拽起点的屏幕坐标 (x1 y1)：")
coords = input("> ").strip().split()
dx1, dy1 = int(coords[0]), int(coords[1])

print("请输入拖拽终点的屏幕坐标 (x2 y2)：")
coords = input("> ").strip().split()
dx2, dy2 = int(coords[0]), int(coords[1])

print(f"注入 drag: ({dx1},{dy1}) -> ({dx2},{dy2}), duration=0.8s")
injector.drag(dx1, dy1, dx2, dy2, duration=0.8)
time.sleep(0.5)

screen.auto_save(prefix="test3_drag")
all_pass &= check_cursor_unchanged(original, "未移动")

# ============================================================
# Test 4: hotkey (Ctrl+A/C/V)
# ============================================================
prompt("Test 4: hotkey 组合键注入")

print("注入 Ctrl+A (全选)")
injector.hotkey("ctrl", "a")
time.sleep(0.3)

print("注入 Ctrl+C (复制)")
injector.hotkey("ctrl", "c")
time.sleep(0.3)

print("注入 press_key End x5 + Enter (跳到末尾)")
for _ in range(5):
    injector.press_key("end")
    time.sleep(0.02)
time.sleep(0.1)
injector.press_key("enter")
time.sleep(0.1)

print("注入 Ctrl+V (粘贴)")
injector.hotkey("ctrl", "v")
time.sleep(0.5)

screen.auto_save(prefix="test4_hotkey")
all_pass &= check_cursor_unchanged(original, "未移动")

# ============================================================
# Test 5: double_click
# ============================================================
prompt("Test 5: double_click 双击选中文本行")

print("请输入记事本中某行文本的屏幕坐标 (x y)：")
coords = input("> ").strip().split()
dcx, dcy = int(coords[0]), int(coords[1])

print(f"注入 double_click 在 ({dcx}, {dcy})")
injector.double_click(dcx, dcy)
time.sleep(0.5)

screen.auto_save(prefix="test5_double_click")
all_pass &= check_cursor_unchanged(original, "未移动")

# ============================================================
# Test 6: right_click
# ============================================================
prompt("Test 6: right_click 右键菜单")

print("请输入记事本编辑区域的屏幕坐标 (x y)：")
coords = input("> ").strip().split()
rcx, rcy = int(coords[0]), int(coords[1])

print(f"注入 right_click 在 ({rcx}, {rcy})（应弹出右键菜单）")
injector.click(rcx, rcy, button="right")
time.sleep(1.0)

screen.auto_save(prefix="test6_right_click")
injector.press_key("escape")
time.sleep(0.3)

all_pass &= check_cursor_unchanged(original, "未移动")

# ============================================================
# Test 7: mouse_down + mouse_up
# ============================================================
prompt("Test 7: mouse_down / mouse_up 分离操作")

print("请输入按下坐标 (x y)：")
coords = input("> ").strip().split()
mdx, mdy = int(coords[0]), int(coords[1])

print(f"注入 mouse_down 在 ({mdx}, {mdy})，按住 1.5 秒...")
injector.mouse_down(mdx, mdy)
time.sleep(1.5)

print("注入 mouse_up")
injector.mouse_up()
time.sleep(0.3)

screen.auto_save(prefix="test7_mouse_down_up")
all_pass &= check_cursor_unchanged(original, "未移动")

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
# Test 9: 中文输入
# ============================================================
prompt("Test 9: 中文文本注入（剪贴板粘贴）")

print("请输入记事本标题栏的屏幕坐标 (x y)（切换回记事本）：")
coords = input("> ").strip().split()
nx, ny = int(coords[0]), int(coords[1])

print(f"注入 click ({nx}, {ny}) 重新激活记事本")
injector.click(nx, ny)
time.sleep(0.3)

print("注入 Enter 换行 + 中文 type_text")
injector.press_key("enter")
time.sleep(0.1)
injector.press_key("enter")
time.sleep(0.1)
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
print("  [ ] 1. click + type_text — 记事本中有英文文本")
print("  [ ] 2. scroll — 文本上下滚动了")
print("  [ ] 3. drag — 选中了一段文本（高亮显示）")
print("  [ ] 4. hotkey — Ctrl+A/C/V 全选/复制/粘贴正常")
print("  [ ] 5. double_click — 双击选中了一个词或行")
print("  [ ] 6. right_click — 右键菜单弹出")
print("  [ ] 7. mouse_down+up — 无异常")
print("  [ ] 8. Explorer scroll — 资源管理器中文件列表滚动了")
print("  [ ] 9. 中文输入 — 记事本中出现了中文")
print()
print("截图保存在 .screenshots/ 目录，可查看对比")
print(f"基准光标位置: {original}")
