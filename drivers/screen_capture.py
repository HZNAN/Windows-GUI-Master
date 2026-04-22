"""
屏幕截图驱动
使用 MSS 实现高速截图，比 PyAutoGUI 快约 10x
"""
import mss
import numpy as np
from pathlib import Path
from datetime import datetime
from loguru import logger

from config.settings import SCREENSHOTS_DIR


class ScreenCapture:
    """屏幕截图器，封装 MSS"""

    def __init__(self, monitor_index: int = 1):
        """
        Args:
            monitor_index: 显示器索引，1 为主屏，2 为副屏（如果有）
        """
        self.monitor_index = monitor_index
        self._sct = mss.mss()

    def capture(self, save_path: str | Path | None = None) -> np.ndarray:
        """
        截取当前屏幕

        Args:
            save_path: 可选，截图保存路径

        Returns:
            numpy.ndarray，BGRA 格式图像
        """
        monitor = self._sct.monitors[self.monitor_index]
        screenshot = self._sct.grab(monitor)

        if save_path:
            self._save_screenshot(screenshot, save_path)

        return np.array(screenshot)

    def capture_region(
        self, x: int, y: int, width: int, height: int,
        save_path: str | Path | None = None
    ) -> np.ndarray:
        """
        截取屏幕指定区域

        Args:
            x, y: 左上角坐标
            width, height: 区域宽高
            save_path: 可选，截图保存路径

        Returns:
            numpy.ndarray，BGRA 格式图像
        """
        monitor = {
            "left": x,
            "top": y,
            "width": width,
            "height": height
        }
        screenshot = self._sct.grab(monitor)

        if save_path:
            self._save_screenshot(screenshot, save_path)

        return np.array(screenshot)

    def _save_screenshot(self, screenshot, save_path: Path | str):
        """保存截图到文件"""
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(save_path))
        logger.debug(f"截图已保存: {save_path}")

    def auto_save(self, prefix: str = "screen", save_dir: Path | str | None = None) -> tuple[np.ndarray, Path]:
        """
        自动生成带时间戳的文件名并保存

        Args:
            prefix: 文件名前缀
            save_dir: 保存目录，默认使用 SCREENSHOTS_DIR

        Returns:
            (图像数组, 文件路径)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{prefix}_{timestamp}.png"
        save_dir = Path(save_dir) if save_dir else SCREENSHOTS_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename
        img = self.capture(save_path=save_path)
        return img, save_path

    def get_monitor_info(self) -> dict:
        """获取显示器信息"""
        monitors = []
        for i, m in enumerate(self._sct.monitors):
            monitors.append({
                "index": i,
                "left": m["left"],
                "top": m["top"],
                "width": m["width"],
                "height": m["height"]
            })
        return monitors

    def close(self):
        """关闭 MSS 实例"""
        self._sct.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# 全局单例
_default_capture: ScreenCapture | None = None


def get_screen_capture() -> ScreenCapture:
    """获取全局 ScreenCapture 实例"""
    global _default_capture
    if _default_capture is None:
        _default_capture = ScreenCapture()
    return _default_capture
