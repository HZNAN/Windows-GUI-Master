"""诊断 drag 和 mouse_down/up 为什么不生效"""
import ctypes
import time
import win32gui
import win32api

user32 = ctypes.windll.user32
user32.PostMessageW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong,
]
user32.PostMessageW.restype = ctypes.c_int
user32.SendMessageW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong,
]
user32.SendMessageW.restype = ctypes.c_longlong

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSEMOVE = 0x0200
MK_LBUTTON = 0x0001

print("将真实鼠标移到右下角...")
time.sleep(1)

print("请输入记事本编辑区坐标 (x y):")
x, y = map(int, input("> ").split())
print(f"请输入拖拽终点坐标 (x2 y2)（在记事本编辑区内，往右下方拖 200px）:")
x2, y2 = map(int, input("> ").split())

# 找到窗口
hwnd = win32gui.WindowFromPoint((x, y))
print(f"WindowFromPoint(({x},{y})) → hwnd={hwnd}")
print(f"窗口标题: {win32gui.GetWindowText(hwnd)}")
print(f"窗口类名: {win32gui.GetClassName(hwnd)}")

cx, cy = win32gui.ScreenToClient(hwnd, (x, y))
cx2, cy2 = win32gui.ScreenToClient(hwnd, (x2, y2))
print(f"客户坐标: start=({cx},{cy}), end=({cx2},{cy2})")

def lparam(x, y):
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)

def send_msg(hwnd, msg, wp, lp, label):
    ctypes.set_last_error(0)
    r = user32.PostMessageW(hwnd, msg, wp, lp)
    err = ctypes.get_last_error()
    print(f"  PostMessage({label}) hwnd={hwnd} msg=0x{msg:X} wp={wp:#x} lp={lp:#x} → ret={r} err={err}")
    if not r:
        ctypes.set_last_error(0)
        r = user32.SendMessageW(hwnd, msg, wp, lp)
        err = ctypes.get_last_error()
        print(f"  SendMessage({label}) → ret={r} err={err}")
    return r

# Test 1: click (should work, sets baseline)
print("\n=== Test 1: 点击（基准测试） ===")
send_msg(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam(cx, cy), "DOWN")
time.sleep(0.05)
send_msg(hwnd, WM_LBUTTONUP, 0, lparam(cx, cy), "UP")
time.sleep(0.5)
print("点击后检查: 记事本光标是否移到了点击位置？")

# Test 2: mouse_down + mouse_move + mouse_up (simulated drag)
print("\n=== Test 2: drag 模拟 ===")

steps = 10
print(f"按下 -> 移动 {steps} 帧 -> 释放")

send_msg(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam(cx, cy), "DOWN")
time.sleep(0.05)
for i in range(1, steps + 1):
    t = i / steps
    mx = int(cx + (cx2 - cx) * t)
    my = int(cy + (cy2 - cy) * t)
    send_msg(hwnd, WM_MOUSEMOVE, MK_LBUTTON, lparam(mx, my), f"MOVE({i})")
    time.sleep(0.05)

send_msg(hwnd, WM_LBUTTONUP, 0, lparam(cx2, cy2), "UP")
time.sleep(0.5)

after = win32api.GetCursorPos()
print(f"\n真实光标位置: {after}")
print("检查: 记事本中是否有文本被选中（高亮）？")
