"""诊断：mouse_event 真实输入 + PostMessage 中间帧 = <2ms 光标闪烁"""
import time
import win32gui
import win32api
import win32con

from drivers.message_injector import MessageInjector

print("=== drag 测试（<2ms 光标闪烁 + PostMessage 中间帧）===")
print("1. 打开记事本，输入几行文字")
print("2. 将真实鼠标移到桌面右下角")
time.sleep(1)

original = win32api.GetCursorPos()
print(f"原始光标: {original}")

print("请输入拖拽起点 (x y):")
x, y = map(int, input("> ").split())
print("请输入拖拽终点 (x2 y2):")
x2, y2 = map(int, input("> ").split())

m = MessageInjector()
m.click(x, y)
time.sleep(0.3)

# 拖拽
print(f"\ndrag: ({x},{y}) -> ({x2},{y2})")
m.drag(x, y, x2, y2, duration=0.8)
time.sleep(0.5)

after = win32api.GetCursorPos()
print(f"\n最终光标: {after}")
print(f"光标已恢复原位: {original == after}")
print("\n检查记事本: 是否有文本被选中（高亮）？")
