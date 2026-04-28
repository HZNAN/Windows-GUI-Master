"""诊断：坐标映射和 EM_CHARFROMPOS"""
import ctypes
import win32gui
import win32api

user32 = ctypes.windll.user32
user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong]
user32.SendMessageW.restype = ctypes.c_longlong

EM_SETSEL = 0x00B1
EM_CHARFROMPOS = 0x00D7

def makelparam(x, y):
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)

print("请输入记事本编辑区任意一点的屏幕坐标 (x y):")
x, y = map(int, input("> ").split())

# 找窗口
hwnd = win32gui.WindowFromPoint((x, y))
print(f"\nWindowFromPoint(({x},{y}))")
print(f"  hwnd = {hwnd}")
print(f"  class = {win32gui.GetClassName(hwnd)}")
print(f"  text = {win32gui.GetWindowText(hwnd)[:50]")

# 获取窗口在屏幕上的位置
rect = win32gui.GetWindowRect(hwnd)
print(f"  screen rect = {rect}  (left, top, right, bottom)")

# ScreenToClient
cx, cy = win32gui.ScreenToClient(hwnd, (x, y))
print(f"  ScreenToClient({x},{y}) = ({cx},{cy})")

# 获取客户区大小
client_rect = win32gui.GetClientRect(hwnd)
print(f"  client rect = {client_rect}  (width, height)")

# 检查坐标是否在客户区内
if 0 <= cx <= client_rect[2] and 0 <= cy <= client_rect[3]:
    print(f"  OK: ({cx},{cy}) 在客户区内")
else:
    print(f"  BAD: ({cx},{cy}) 超出客户区 {client_rect}")

# EM_CHARFROMPOS
lparam = makelparam(cx, cy)
result = user32.SendMessageW(hwnd, EM_CHARFROMPOS, 0, lparam)
dword = result & 0xFFFFFFFF
char_idx = dword & 0xFFFF
line_idx = (dword >> 16) & 0xFFFF
print(f"\nEM_CHARFROMPOS({cx},{cy}):")
print(f"  result = {result:#x}")
print(f"  dword = {dword:#x}")
print(f"  char_idx = {char_idx}, line_idx = {line_idx}")

# 直接测试 EM_SETSEL
if char_idx != 0xFFFF:
    print(f"\n直接测试 EM_SETSEL(0, {char_idx}):")
    user32.SendMessageW(hwnd, EM_SETSEL, 0, char_idx)
    print("  检查: 记事本中从开头到点击位置是否被选中（高亮）？")
else:
    print("\nEM_CHARFROMPOS 失败，尝试遍历父窗口...")
    parent = hwnd
    while parent:
        parent = win32gui.GetParent(parent)
        if not parent:
            break
        print(f"\n父窗口: hwnd={parent}")
        print(f"  class = {win32gui.GetClassName(parent)}")
        print(f"  text = {win32gui.GetWindowText(parent)[:50]}")
        p_rect = win32gui.GetWindowRect(parent)
        print(f"  screen rect = {p_rect}")
        pcx, pcy = win32gui.ScreenToClient(parent, (x, y))
        print(f"  ScreenToClient({x},{y}) = ({pcx},{pcy})")

        lparam = makelparam(pcx, pcy)
        result = user32.SendMessageW(parent, EM_CHARFROMPOS, 0, lparam)
        dword = result & 0xFFFFFFFF
        char_idx = dword & 0xFFFF
        print(f"  EM_CHARFROMPOS: char_idx={char_idx}")

        if char_idx != 0xFFFF:
            print(f"\n  找到正确的父窗口！EM_SETSEL(0, {char_idx})")
            user32.SendMessageW(parent, EM_SETSEL, 0, char_idx)
            print("  检查: 是否有文本被选中？")
            break
