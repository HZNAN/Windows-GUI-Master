"""诊断：纯消息 drag/mouse_down（EM_SETSEL / WM_LBUTTONDOWN，零光标移动）"""
import time
import win32gui
import win32api

from drivers.message_injector import MessageInjector

print("=== 纯消息 drag/mouse_down 测试（零光标移动）===")
print("1. 打开记事本，输入几行文字")
print("2. 真实光标放在任何位置（不会移动）")
time.sleep(1)

original = win32api.GetCursorPos()
print(f"原始光标: {original}")

print("请输入拖拽起点 (x y):")
x, y = map(int, input("> ").split())
print("请输入拖拽终点 (x2 y2):")
x2, y2 = map(int, input("> ").split())

m = MessageInjector()
hwnd = win32gui.WindowFromPoint((x, y))
class_name = win32gui.GetClassName(hwnd)
print(f"目标窗口: hwnd={hwnd}, class={class_name}")

# 先点击激活
m.click(x, y)
time.sleep(0.3)

# Test 1: drag
print(f"\n=== drag ===")
m.drag(x, y, x2, y2, duration=0.8)
time.sleep(0.5)

print(f"最终光标: {win32api.GetCursorPos()} (应 = {original})")
print("检查: 记事本中是否有文本被选中？")

# Test 2: mouse_down + mouse_up
print(f"\n=== mouse_down/up ===")
print("请输入 mouse_down 坐标 (x y):")
mx, my = map(int, input("> ").split())
m.mouse_down(mx, my)
print("按住 1 秒...")
time.sleep(1.0)
m.mouse_up()
print(f"最终光标: {win32api.GetCursorPos()} (应 = {original})")
print("检查: 记事本光标是否移到了点击位置？")
