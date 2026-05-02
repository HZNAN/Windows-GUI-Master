"""
截图工具 - 返回带坐标网格的截图，让模型"看见"屏幕
"""
import base64
import cv2
from pathlib import Path
from langchain_core.tools import tool

from drivers.screen_capture import get_screen_capture


def _nice_step(dimension: int) -> int:
    """返回适合该维度的网格步长（美观整数：500/200/100/50/20/10）"""
    target = max(dimension // 5, 50)
    for nice in (200, 100, 50, 20, 10):
        if target >= nice:
            return max(target // nice * nice, nice)
    return 10


def _overlay_coord_grid(img):
    """
    在截图上叠加坐标参考标记，缩放到 GRID_WIDTH × GRID_HEIGHT。
    """
    from config.settings import GRID_WIDTH, GRID_HEIGHT

    if len(img.shape) == 3 and img.shape[2] == 4:
        output = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    else:
        output = img.copy()

    orig_h, orig_w = output.shape[:2]

    output = cv2.resize(output, (GRID_WIDTH, GRID_HEIGHT), interpolation=cv2.INTER_LINEAR)
    h, w = GRID_HEIGHT, GRID_WIDTH

    # x/y 各自计算网格间距和刻度间距
    grid_step_x = _nice_step(w)
    grid_step_y = _nice_step(h)
    tick_step_x = max(grid_step_x // 2, 10)
    tick_step_y = max(grid_step_y // 2, 10)
    margin = max(max(w, h) // 25, 25)

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.6
    thickness = 1

    # 边缘半透明黑色背景
    overlay = output.copy()
    cv2.rectangle(overlay, (0, 0), (w-1, margin), (0, 0, 0), -1)          # 顶部
    cv2.rectangle(overlay, (0, h-margin), (w-1, h-1), (0, 0, 0), -1)      # 底部
    cv2.rectangle(overlay, (0, 0), (margin, h-1), (0, 0, 0), -1)          # 左侧
    cv2.rectangle(overlay, (w-margin, 0), (w-1, h-1), (0, 0, 0), -1)      # 右侧
    cv2.addWeighted(output, 0.6, overlay, 0.4, 0, output)

    # 粗黑边框
    cv2.rectangle(output, (0, 0), (w-1, h-1), (0, 0, 0), 4)

    # 灰色网格线
    grid_color = (180, 180, 180)
    for x in range(0, w, grid_step_x):
        cv2.line(output, (x, 0), (x, h), grid_color, 1)
    for y in range(0, h, grid_step_y):
        cv2.line(output, (0, y), (w, y), grid_color, 1)

    # 上下边缘 x 坐标 + 刻度
    tick_len = 12
    for x in range(0, w, tick_step_x):
        # 顶部
        cv2.line(output, (x, 0), (x, tick_len), (255, 255, 255), 1)
        label = str(x)
        (tw, th), _ = cv2.getTextSize(label, font, fontScale, thickness)
        cv2.putText(output, label, (x - tw // 2, margin - 6),
                    font, fontScale, (255, 255, 255), thickness)
        # 底部
        cv2.line(output, (x, h-1), (x, h-1-tick_len), (255, 255, 255), 1)
        cv2.putText(output, label, (x - tw // 2, h - margin + th + 4),
                    font, fontScale, (255, 255, 255), thickness)

    # 左右边缘 y 坐标 + 刻度
    for y in range(0, h, tick_step_y):
        cv2.line(output, (0, y), (tick_len, y), (255, 255, 255), 1)
        label = str(y)
        (tw, th), _ = cv2.getTextSize(label, font, fontScale, thickness)
        cv2.putText(output, label, (margin - tw - 4, y + th // 2),
                    font, fontScale, (255, 255, 255), thickness)
        # 右侧
        cv2.line(output, (w-1, y), (w-1-tick_len, y), (255, 255, 255), 1)
        cv2.putText(output, label, (w - margin + 4, y + th // 2),
                    font, fontScale, (255, 255, 255), thickness)

    # 中心红色十字
    cx, cy = w // 2, h // 2
    cv2.drawMarker(output, (cx, cy), (0, 0, 255), cv2.MARKER_CROSS, 40, 3)

    return output, orig_w, orig_h


@tool(parse_docstring=True)
def screenshot() -> dict:
    """
    捕获当前屏幕截图，返回带坐标网格的图像供分析。

    Returns:
        dict: 包含 image (base64) 和实际尺寸 info

    使用场景:
        - 任务开始时了解当前屏幕状态
        - 执行动作后验证结果
        - 每一步操作前观察屏幕
    """
    from config.settings import SCREENSHOTS_DIR

    screen = get_screen_capture()
    img, path = screen.auto_save(prefix="react", save_dir=SCREENSHOTS_DIR)

    # 生成带网格的截图
    grid_img, orig_w, orig_h = _overlay_coord_grid(img)

    # 保存网格图
    grid_path = Path(path).parent / f"{Path(path).stem}_grid.png"
    cv2.imwrite(str(grid_path), grid_img)

    # 返回 base64
    with open(str(grid_path), "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    from config.settings import GRID_WIDTH, GRID_HEIGHT
    return {
        "image": f"data:image/png;base64,{img_b64}",
        "grid_width": GRID_WIDTH,
        "grid_height": GRID_HEIGHT,
        "orig_width": orig_w,
        "orig_height": orig_h,
    }
