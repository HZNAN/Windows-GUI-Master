"""手动验证消息注入模式：打开记事本，点击并输入，确认真实光标未移动"""
import time
from drivers.message_injector import MessageInjector
from core.virtual_cursor import get_virtual_cursor
from drivers.screen_capture import get_screen_capture

injector = MessageInjector()
cursor = get_virtual_cursor()
screen = get_screen_capture()

print("=== 消息注入模式验证 ===")
print("1. 请确保记事本 (notepad) 已打开并可见")
print("2. 将真实光标移到屏幕角落（远离记事本窗口）")
print("3. 按 Enter 开始测试...")
input()

# 获取当前真实光标位置（应在角落）
import win32api
original = win32api.GetCursorPos()
print(f"真实光标位置: {original}")

# 截图查看当前画面
screen.auto_save(prefix="before_inject")

# 在记事本区域找一个可点击的位置 (假设记事本在屏幕左上区域)
# 这里使用固定坐标，测试前需根据实际情况调整
x, y = 500, 400
print(f"注入点击: ({x}, {y})")
injector.click(x, y)
time.sleep(0.5)

# 输入一些文字
print("注入文本: Hello from message injection!")
injector.type_text("Hello from message injection!")
time.sleep(0.5)

# 检查真实光标是否还在原位
after = win32api.GetCursorPos()
print(f"注入后真实光标位置: {after}")
print(f"真实光标是否未移动: {original == after}")

# 截图对比
screen.auto_save(prefix="after_inject")

print("\n=== 验证完成 ===")
print("检查 .screenshots/ 中的截图，确认:")
print("1. 记事本中出现了 'Hello from message injection!' 文本")
print("2. 真实光标仍在原始位置")
