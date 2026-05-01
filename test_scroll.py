"""
滚动注入测试 — 直接测试 MessageInjector.scroll()
"""
import time
import sys
sys.path.insert(0, ".")

import win32api
import win32gui
from drivers.message_injector import MessageInjector


def check_focus():
    fg = win32gui.GetForegroundWindow()
    if fg:
        return f"{win32gui.GetWindowText(fg)[:40]} ({win32gui.GetClassName(fg)})"
    return "N/A"


def test_scroll(injector, label, x, y, amounts):
    print(f"\n{'='*55}")
    print(f"  {label} | 位置: ({x}, {y}) | 目标: {check_focus()}")
    print(f"{'='*55}")

    for amount in amounts:
        direction = "UP  " if amount > 0 else "DOWN"
        print(f"  scroll({amount:>4}) {direction} ...", end=" ", flush=True)
        start = time.perf_counter()
        injector.scroll(x, y, amount)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"OK ({elapsed:.0f}ms)")
        time.sleep(0.15)


def main():
    injector = MessageInjector()
    w = win32api.GetSystemMetrics(0)
    h = win32api.GetSystemMetrics(1)
    cx, cy = w // 2, h // 2
    half_w = w // 4

    print("滚动注入测试 (mouse_event WHEEL + 透明光标)")
    print(f"屏幕: {w}x{h}, 中心: ({cx},{cy})")

    # 小步测试
    test_scroll(injector, "小步上滚", cx, cy, [1, 2, 3])
    time.sleep(0.5)
    test_scroll(injector, "小步下滚", cx, cy, [-1, -2, -3])
    time.sleep(0.5)

    # 大步测试
    test_scroll(injector, "大步上滚", cx, cy, [5, 10])
    time.sleep(0.5)
    test_scroll(injector, "大步下滚", cx, cy, [-5, -10])

    # 不同位置
    test_scroll(injector, "左侧滚动", half_w, cy, [3])
    test_scroll(injector, "右侧滚动", w - half_w, cy, [3])

    print(f"\n{'='*55}")
    print("  Done. Check if the area under cursor scrolled.")
    print("  Cursor should be back at original position.")
    print(f"{'='*55}")


if __name__ == "__main__":
    print("3s to prepare — place mouse over scrollable area (browser/feishu/notepad)")
    time.sleep(3)
    main()
