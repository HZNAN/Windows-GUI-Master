"""
截图工具 - 返回带坐标网格的截图，让模型"看见"屏幕
"""
import base64
import cv2
from pathlib import Path
from langchain_core.tools import tool

from drivers.screen_capture import get_screen_capture


def _overlay_coord_grid(img):
    """
    在截图上叠加坐标参考标记，缩放到 GRID_SIZE × GRID_SIZE。
    """
    from config.settings import GRID_SIZE

    if len(img.shape) == 3 and img.shape[2] == 4:
        output = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    else:
        output = img.copy()

    orig_h, orig_w = output.shape[:2]

    TARGET_W = TARGET_H = GRID_SIZE
    output = cv2.resize(output, (TARGET_W, TARGET_H), interpolation=cv2.INTER_LINEAR)
    h, w = TARGET_H, TARGET_W

    # 网格线和刻度间距（与 GRID_SIZE 成比例）
    grid_step = max(GRID_SIZE // 5, 50)
    tick_step = max(GRID_SIZE // 10, 25)
    margin = max(GRID_SIZE // 20, 25)

    font = cv2.FONT_HERSHEY_SIMPLEX

    # 边缘半透明黑色背景
    overlay = output.copy()
    cv2.rectangle(overlay, (0, 0), (w-1, margin), (0, 0, 0), -1)
    cv2.rectangle(overlay, (0, h-margin), (w-1, h-1), (0, 0, 0), -1)
    cv2.rectangle(overlay, (0, 0), (margin, h-1), (0, 0, 0), -1)
    cv2.rectangle(overlay, (w-margin, 0), (w-1, h-1), (0, 0, 0), -1)
    cv2.addWeighted(output, 0.6, overlay, 0.4, 0, output)

    fontScale = 0.8
    thickness = 2
    tick_len = 15

    # 粗黑边框
    cv2.rectangle(output, (0, 0), (w-1, h-1), (0, 0, 0), 4)

    # 灰色网格线
    grid_color = (180, 180, 180)
    for x in range(0, w, grid_step):
        cv2.line(output, (x, 0), (x, h), grid_color, 1)
    for y in range(0, h, grid_step):
        cv2.line(output, (0, y), (w, y), grid_color, 1)

    # 上下边缘 x 坐标
    for x in range(0, w, tick_step):
        cv2.line(output, (x, 0), (x, tick_len), (255, 255, 255), 2)
        cv2.putText(output, str(x), (x-15, margin-15), font, fontScale, (255, 255, 255), thickness)
        cv2.line(output, (x, h-1), (x, h-1-tick_len), (255, 255, 255), 2)
        cv2.putText(output, str(x), (x-15, h-8), font, fontScale, (255, 255, 255), thickness)

    # 左右边缘 y 坐标
    for y in range(0, h, tick_step):
        cv2.line(output, (0, y), (tick_len, y), (255, 255, 255), 2)
        cv2.putText(output, str(y), (15, y+7), font, fontScale, (255, 255, 255), thickness)
        cv2.line(output, (w-1, y), (w-1-tick_len, y), (255, 255, 255), 2)
        cv2.putText(output, str(y), (w-40, y+7), font, fontScale, (255, 255, 255), thickness)

    # 中心红色十字
    cx, cy = w // 2, h // 2
    cv2.drawMarker(output, (cx, cy), (0, 0, 255), cv2.MARKER_CROSS, 40, 3)

    return output, orig_w, orig_h


@tool
def screenshot() -> dict:
    """
    捕获当前屏幕截图，返回带坐标网格的图像供分析。

    返回:
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

    from config.settings import GRID_SIZE
    return {
        "image": f"data:image/png;base64,{img_b64}",
        "grid_width": GRID_SIZE,
        "grid_height": GRID_SIZE,
        "orig_width": orig_w,
        "orig_height": orig_h,
    }
