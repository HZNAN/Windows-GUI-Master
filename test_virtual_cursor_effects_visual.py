"""视觉验证：虚拟光标动态特效

测试流程：
1. 创建虚拟光标，移动到位置 A
2. 观察 idle wobble 效果（光标应在 ±6° 范围内晃动）
3. 移动到位置 B，观察移动过程中光标是否跟随方向旋转
4. 观察归位旋转效果（到达后 0.3s 缓慢转回 -45°）
5. 观察 idle wobble 恢复
"""
import time
import os

# 确保 .env 被加载
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

from core.virtual_cursor import VirtualCursor


def main():
    # 获取屏幕尺寸
    from drivers.screen_capture import get_screen_capture
    screen = get_screen_capture()
    img, _ = screen.auto_save(prefix="temp")
    h, w = img.shape[:2]

    print("=== 虚拟光标动态特效测试 ===")
    print(f"屏幕尺寸: {w}x{h}")

    vc = VirtualCursor(amplitude=15, duration=1.0, fps=60)

    # 测试 1: 设置初始位置，观察 idle wobble
    print("\n1. 设置初始位置 (500, 300)，观察 idle wobble...")
    vc.set_position(500, 300)
    print("   观察 5 秒 idle 晃动（±6° 正弦波摆动）...")
    time.sleep(5)

    # 测试 2: 向右下移动，观察旋转
    print("\n2. 移动到 (1200, 700)，观察移动方向旋转...")
    vc.move_to(1200, 700)
    print("   移动完成，观察归位旋转 + idle wobble...")
    time.sleep(5)

    # 测试 3: 向左上移动，观察反向旋转
    print("\n3. 移动到 (400, 200)，观察反向旋转...")
    vc.move_to(400, 200)
    time.sleep(5)

    # 测试 4: 水平移动
    print("\n4. 水平移动到 (1500, 200)，观察水平方向旋转...")
    vc.move_to(1500, 200)
    time.sleep(5)

    # 测试 5: 垂直移动
    print("\n5. 垂直移动到 (1500, 600)，观察垂直方向旋转...")
    vc.move_to(1500, 600)
    time.sleep(5)

    print("\n=== 测试完成，隐藏光标 ===")
    vc.hide()
    time.sleep(1)
    print("退出。")


if __name__ == "__main__":
    main()
