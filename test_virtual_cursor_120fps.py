"""虚拟光标 120 帧综合测试：click / double / drag(同步) / hold / scroll"""
import time
import win32api
import win32con
import win32gui
from core.virtual_cursor import VirtualCursor
from drivers.message_injector import MessageInjector


def _sync_drag(vcursor, injector, x1, y1, x2, y2, duration=1.0, fps=120):
    """同步拖拽：虚拟光标逐帧跟随真实拖拽路径，速度完全匹配"""
    total_frames = int(duration * fps)
    saved = win32api.GetCursorPos()
    injector._hide_real_cursor()

    try:
        # 起点：双光标同步
        win32api.SetCursorPos((x1, y1))
        vcursor.overlay.move_cursor(x1, y1)
        vcursor.overlay.show()
        time.sleep(0.02)

        # 按下
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.02)

        # 逐帧动画：虚拟光标与真实光标同步移动
        frame_delay = duration / total_frames
        for i in range(1, total_frames + 1):
            t = i / total_frames
            cx = int(x1 + (x2 - x1) * t)
            cy = int(y1 + (y2 - y1) * t)

            win32api.SetCursorPos((cx, cy))          # 真实光标（隐藏）
            vcursor.overlay.move_cursor(cx, cy)      # 虚拟光标（可见）
            time.sleep(frame_delay)

        # 释放
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.02)

        print(f"  同步拖拽: ({x1},{y1}) -> ({x2},{y2}), {total_frames}帧")
    finally:
        win32api.SetCursorPos(saved)
        injector._show_real_cursor()


def _sync_mouse_down(vcursor, injector, x, y, fps=120):
    """按住：虚拟光标待在目标位置"""
    saved = win32api.GetCursorPos()
    injector._hide_real_cursor()

    try:
        win32api.SetCursorPos((x, y))
        vcursor.overlay.move_cursor(x, y)
        vcursor.overlay.show()
        time.sleep(0.02)

        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        print(f"  按住: ({x},{y}), 虚拟光标保持在按下位置")
    except Exception:
        injector._show_real_cursor()
        raise


def _sync_mouse_up(vcursor, injector):
    """释放：恢复光标位置"""
    try:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.01)
        print(f"  释放按键")
    finally:
        if hasattr(injector, '_saved_cursor'):
            win32api.SetCursorPos(injector._saved_cursor)
        injector._show_real_cursor()


def _sync_scroll(vcursor, injector, x, y, amount, fps=120):
    """滚轮：虚拟光标定位，mouse_event 滚轮"""
    saved = win32api.GetCursorPos()
    injector._hide_real_cursor()

    try:
        vcursor.overlay.move_cursor(x, y)
        vcursor.overlay.show()
        time.sleep(0.02)

        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)
        abs_x = int(x * 65535 / screen_w)
        abs_y = int(y * 65535 / screen_h)
        win32api.mouse_event(
            win32con.MOUSEEVENTF_ABSOLUTE | win32con.MOUSEEVENTF_MOVE,
            abs_x, abs_y, 0, 0)
        time.sleep(0.01)

        import ctypes
        WHEEL_DELTA = 120
        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0,
                             amount * WHEEL_DELTA, 0)
        time.sleep(0.02)
        print(f"  滚轮: amount={amount}")
    finally:
        win32api.SetCursorPos(saved)
        injector._show_real_cursor()


# ============ 主测试 ============
print("=" * 60)
print("  虚拟光标 120fps 综合操作测试")
print("=" * 60)
print()
print("准备工作:")
print("  1. 打开一个记事本窗口，放在屏幕左侧")
print("  2. 打开资源管理器，放在屏幕右侧")
print("  3. 把真实鼠标移到最右下角，测试期间不要移动")
print()
input("准备好后按 Enter 开始...")

original_cursor = win32api.GetCursorPos()
print(f"\n基准光标位置: {original_cursor}")
print("测试期间请用余光观察虚拟光标（彩色箭头）的动作")

vc = VirtualCursor(duration=1.0, fps=120)
inj = MessageInjector()

screen_w = win32api.GetSystemMetrics(0)
screen_h = win32api.GetSystemMetrics(1)

# ============================================================
# Test 1: Click — 虚拟光标移动到目标，纯消息点击
# ============================================================
print("\n" + "=" * 60)
print("Test 1/6: Click — 虚拟光标移动 + 纯消息点击")
print("  请输入记事本编辑区的屏幕坐标 (x y):")
x, y = map(int, input("> ").split())
vc.move_to(x, y)
time.sleep(0.3)
inj.click(x, y)
print("  预期: 记事本光标跳到了点击位置，虚拟光标停在目标处")
time.sleep(0.5)

# ============================================================
# Test 2: Double-click — 虚拟光标在位置，双击
# ============================================================
print("\n" + "=" * 60)
print("Test 2/6: Double-click — 双击选中")
print("  请输入记事本中一行文字的屏幕坐标 (x y):")
x, y = map(int, input("> ").split())
vc.move_to(x, y)
time.sleep(0.3)
inj.double_click(x, y)
print("  预期: 记事本中该行被选中（高亮）")
time.sleep(0.5)

# ============================================================
# Test 3: Type Text — 中文输入
# ============================================================
print("\n" + "=" * 60)
print("Test 3/6: Type Text — 输入文本")
print("  请输入记事本编辑区的屏幕坐标 (x y) 用于 click 定位:")
x, y = map(int, input("> ").split())
vc.move_to(x, y)
time.sleep(0.3)
inj.click(x, y)
time.sleep(0.3)
inj.type_text("虚拟光标 120 帧测试 Test")
inj.press_key("enter")
inj.type_text("你好世界！中文输入测试")
print("  预期: 记事本中输入了中英文文本")
time.sleep(0.5)

# ============================================================
# Test 4: Drag — 虚拟光标同步跟随拖拽路径
# ============================================================
print("\n" + "=" * 60)
print("Test 4/6: Drag (同步) — 虚拟光标跟随拖拽轨迹")
print("  请输入拖拽起点 (x1 y1):")
x1, y1 = map(int, input("> ").split())
print("  请输入拖拽终点 (x2 y2)（同一行文字内）:")
x2, y2 = map(int, input("> ").split())

# 先用虚拟光标移动到起点
vc.move_to(x1, y1)
time.sleep(0.2)
# 然后同步拖拽（虚拟光标逐帧跟随）
_sync_drag(vc, inj, x1, y1, x2, y2, duration=1.0, fps=120)
print("  预期: 虚拟光标平滑移动，记事本中文本被选中")
time.sleep(0.5)

# ============================================================
# Test 5: Mouse Down/Up — 虚拟光标定位 + 按住/释放
# ============================================================
print("\n" + "=" * 60)
print("Test 5/6: Mouse Down/Up — 按住与释放")
print("  请输入按住坐标 (x y):")
x, y = map(int, input("> ").split())

vc.move_to(x, y)
time.sleep(0.2)
_sync_mouse_down(vc, inj, x, y)
print("  虚拟光标停在按下位置，按住 2 秒...")
time.sleep(2.0)
_sync_mouse_up(vc, inj)
print("  预期: 虚拟光标留在原位，真实光标回到右下角")
time.sleep(0.5)

# ============================================================
# Test 6: Scroll — 虚拟光标定位 + 滚轮
# ============================================================
print("\n" + "=" * 60)
print("Test 6/6: Scroll — 滚轮")
print("  请输入记事本编辑区的屏幕坐标 (x y):")
x, y = map(int, input("> ").split())

vc.move_to(x, y)
time.sleep(0.3)
_sync_scroll(vc, inj, x, y, amount=5)
print("  预期: 记事本向上滚动")
time.sleep(0.3)

_sync_scroll(vc, inj, x, y, amount=-5)
print("  预期: 记事本向下滚动")
time.sleep(0.5)

# ============================================================
# Summary
# ============================================================
final_cursor = win32api.GetCursorPos()
print("\n" + "=" * 60)
print("  测试完成")
print("=" * 60)
print(f"  真实光标: {original_cursor} -> {final_cursor}")
print(f"  偏离: {final_cursor[0] - original_cursor[0]}, {final_cursor[1] - original_cursor[1]}")
print()
print("检查清单:")
print("  [ ] 1. Click — 虚拟光标移动到目标，记事本光标跳到点击处")
print("  [ ] 2. Double-click — 虚拟光标在目标，选中文行")
print("  [ ] 3. Type Text — 中英文文本输入成功")
print("  [ ] 4. Drag — 虚拟光标平滑跟随拖拽轨迹，文本被选中")
print("  [ ] 5. Hold — 虚拟光标停在按下位置，不闪不跳")
print("  [ ] 6. Scroll — 虚拟光标在目标，页面滚动")
print(f"  [ ] 真实光标几乎未移动 (< 5px 偏差正常)")

vc.hide()
