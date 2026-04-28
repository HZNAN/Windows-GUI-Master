"""诊断：纯消息 drag（mouse_event 设按键状态 + PostMessage 坐标，零光标移动）"""
import time
import win32gui
import win32api
import win32con

print("=== 零光标移动 drag 测试 ===")
print("1. 打开记事本，输入几行文字")
print("2. 将真实鼠标移到桌面角落（右下角）")
time.sleep(1)

original = win32api.GetCursorPos()
print(f"原始光标: {original}")

print("请输入记事本编辑区拖拽起点 (x y):")
x1, y1 = map(int, input("> ").split())
print("请输入拖拽终点 (x2 y2):")
x2, y2 = map(int, input("> ").split())

# 先用 injector 点击激活
from drivers.message_injector import MessageInjector
m = MessageInjector()
m.click(x1, y1)
time.sleep(0.3)
print(f"点击后光标: {win32api.GetCursorPos()} (应仍在原位)")

# 拖拽
print(f"\ndrag: ({x1},{y1}) -> ({x2},{y2})")
m.drag(x1, y1, x2, y2, duration=0.8)
time.sleep(0.5)

after = win32api.GetCursorPos()
print(f"\n最终光标: {after}")
print(f"光标从未移动: {original == after}")
print(f"\n检查: 记事本中是否有文本被选中（高亮显示）？")
