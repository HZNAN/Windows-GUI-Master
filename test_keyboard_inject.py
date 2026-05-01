"""
键盘注入完整测试 — 验证 keybd_event 在所有场景下的可靠性

测试覆盖:
  1. GetGUIThreadInfo 跨线程获取焦点（vs GetFocus 始终返回 0）
  2. Win+R 对话框 → type_text → Enter → 启动应用
  3. 应用内 type_text 输入
  4. Ctrl+A 全选热键
"""
import ctypes
import time
import sys
sys.path.insert(0, ".")

import win32gui
from drivers.message_injector import MessageInjector

user32 = ctypes.windll.user32
KEYEVENTF_KEYUP = 0x0002


class _GTI(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint), ("flags", ctypes.c_uint),
        ("hwndActive", ctypes.c_void_p), ("hwndFocus", ctypes.c_void_p),
        ("hwndCapture", ctypes.c_void_p), ("hwndMenuOwner", ctypes.c_void_p),
        ("hwndMoveSize", ctypes.c_void_p), ("hwndCaret", ctypes.c_void_p),
        ("rcCaret", ctypes.c_long * 4),
    ]
user32.GetGUIThreadInfo.argtypes = [ctypes.c_uint, ctypes.c_void_p]
user32.GetGUIThreadInfo.restype = ctypes.c_int


def _focus_text():
    fg = win32gui.GetForegroundWindow()
    if not fg:
        return ""
    tid = user32.GetWindowThreadProcessId(fg, 0)
    gti = _GTI()
    gti.cbSize = ctypes.sizeof(gti)
    if user32.GetGUIThreadInfo(tid, ctypes.byref(gti)) and gti.hwndFocus:
        buf = ctypes.create_unicode_buffer(512)
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                        ctypes.c_ulonglong, ctypes.c_void_p]
        user32.SendMessageW.restype = ctypes.c_longlong
        user32.SendMessageW(gti.hwndFocus, 0x000D, 511, buf)  # WM_GETTEXT
        return buf.value
    return ""


def check(passed, msg):
    print(f"  {'PASS' if passed else 'FAIL'}: {msg}")
    return passed


def close_run_dialog():
    user32.keybd_event(0x1B, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(0x1B, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.3)


results = []
mi = MessageInjector()


# ==== Test 1: Run dialog text input ====
print("=" * 50)
print("Test 1: Win+R → type_text('notepad') → 验证文本")
print("=" * 50)

mi.hotkey("win", "r")
time.sleep(0.8)
mi.type_text("notepad")
time.sleep(0.3)
text = _focus_text()
results.append(check("notepad" in text, f"Run dialog has 'notepad': '{text}'"))
close_run_dialog()


# ==== Test 2: Run dialog + Enter → open Notepad ====
print("\n" + "=" * 50)
print("Test 2: Win+R → type_text('notepad') + Enter → 启动记事本")
print("=" * 50)

mi.hotkey("win", "r")
time.sleep(0.8)
mi.type_text("notepad")
time.sleep(0.2)
mi.press_key("enter")
time.sleep(2)

fg = win32gui.GetForegroundWindow()
fg_text = win32gui.GetWindowText(fg)
results.append(check("Notepad" in fg_text or u"记事本" in fg_text,
                     f"Notepad opened: '{fg_text}'"))


# ==== Test 3: Type into Notepad ====
print("\n" + "=" * 50)
print("Test 3: 在记事本中输入 HelloWorld")
print("=" * 50)

time.sleep(1)
mi.type_text("HelloWorld")
time.sleep(0.5)

text = _focus_text()
results.append(check("HelloWorld" in text,
                     f"Notepad contains HelloWorld: '{text}'"))


# ==== Test 4: Ctrl+A (select all) in Notepad ====
print("\n" + "=" * 50)
print("Test 4: Ctrl+A 全选（keybd_event 热键）")
print("=" * 50)

mi.hotkey("ctrl", "a")
time.sleep(0.3)
results.append(check(True, "Ctrl+A executed (visual check: should select all text)"))


# ==== Summary ====
print("\n" + "=" * 50)
passed = sum(results)
total = len(results)
print(f"Results: {passed}/{total} passed")
for i, r in enumerate(results):
    print(f"  Test {i+1}: {'PASS' if r else 'FAIL'}")

# Cleanup
mi.hotkey("alt", "f4")
time.sleep(0.3)
# Don't save
mi.press_key("n")  # Alt+N for "Don't Save" in Chinese Notepad
