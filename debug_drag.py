"""诊断新 drag 方案：mouse_event 设置系统按键状态 + PostMessage 中间帧"""
import time
import win32gui
import win32api
import win32con

from drivers.message_injector import MessageInjector

print("将真实鼠标移到右下角...")
time.sleep(1)
original = win32api.GetCursorPos()
print(f"原始光标位置: {original}")

print("请输入记事本编辑区坐标 (x y):")
x, y = map(int, input("> ").split())
print("请输入拖拽终点坐标 (x2 y2)（往右下方拖 200px）:")
x2, y2 = map(int, input("> ").split())

injector = MessageInjector()

# 先点击激活
print("\n=== 先点击激活记事本光标 ===")
injector.click(x, y)
time.sleep(0.3)

# 用 injector 的新 drag 方法
print(f"\n=== drag: ({x},{y}) -> ({x2},{y2}) ===")
injector.drag(x, y, x2, y2, duration=0.8)
time.sleep(0.5)

after = win32api.GetCursorPos()
print(f"\n拖拽后真实光标位置: {after}")
print(f"光标已恢复: {original == after}")
print("\n检查: 记事本中是否有文本被选中（高亮显示）？")
