"""
Windows 透明覆盖层 + 虚拟光标绘制
使用 win32gui 创建最顶层透明窗口，仅绘制光标不拦截鼠标事件
"""
import math
import threading
import time
from typing import Optional

import cv2
import numpy as np
import win32api
import win32con
import win32gui
from PIL import Image, ImageDraw


class Win32Overlay:
    """
    Windows 透明覆盖层
    创建最顶层透明窗口，仅绘制虚拟光标，不影响真实鼠标操作
    """

    _instance: Optional["Win32Overlay"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.hwnd: int = 0
        self.cursor_img: Optional[Image.Image] = None
        self.cursor_hicon: Optional[int] = None
        self._visible = False
        self._pos = (-100, -100)  # 初始位置在屏幕外

    @classmethod
    def get_instance(cls) -> "Win32Overlay":
        """单例模式"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = Win32Overlay()
            return cls._instance

    def _create_cursor_image(self) -> Image.Image:
        """
        创建蓝白箭头光标图像
        - 尺寸: 24x24px
        - 白色实心箭头，无柄，尖部带弧度
        - 蓝色模糊边缘 (rgba(80, 150, 255, 128))
        """
        size = 24
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 箭头形状: 无柄，尖部带弧度
        # 顶点
        tip_x, tip_y = size // 2, 3
        # 底部中心
        base_x, base_y = size // 2, size - 3
        # 箭头宽度
        half_width = 6

        # 贝塞尔曲线绘制箭头轮廓，尖部用弧线
        # 左侧点
        left_x = base_x - half_width
        left_y = base_y - 2
        # 右侧点
        right_x = base_x + half_width
        right_y = base_y - 2

        # 箭头多边形 (尖部弧线用两个点模拟)
        arrow_points = [
            (tip_x, tip_y),  # 尖顶
            (left_x + 2, left_y - 4),  # 左上弧过渡
            (left_x, left_y),  # 左下
            (base_x, base_y),  # 底中
            (right_x, right_y),  # 右下
            (right_x - 2, right_y - 4),  # 右下弧过渡
        ]

        # 绘制蓝色模糊边缘 (3px)
        for offset in range(3, 0, -1):
            alpha = int(80 * offset / 3)
            scaled_points = []
            cx, cy = size // 2, size // 2
            for px, py in arrow_points:
                dx = px - cx
                dy = py - cy
                scale = (offset + 6) / 6
                scaled_points.append((int(cx + dx * scale), int(cy + dy * scale)))
            draw.polygon(scaled_points, fill=(80, 150, 255, alpha))

        # 绘制白色填充
        draw.polygon(arrow_points, fill=(255, 255, 255, 255))

        return img

    def _create_hicon(self, img: Image.Image) -> int:
        """将 PIL Image 转换为 Windows HICON"""
        # 转换 RGBA 到 BGRA
        img_array = np.array(img)
        if img_array.shape[2] == 4:
            # BGRA
            bgra = img_array[..., [2, 1, 0, 3]]
        else:
            bgra = img_array

        # 创建 DIB
        hdc = win32gui.CreateCompatibleDC(0)
        bmp = win32gui.CreateCompatibleBitmap(win32gui.GetDC(0), img.width, img.height)
        win32gui.SelectObject(hdc, bmp)

        # 设置透明色
        win32gui.SetBkColor(hdc, win32api.RGB(0, 0, 0))
        win32gui.SetPixel(hdc, 0, 0, win32api.RGB(0, 0, 0))

        # 直接写入 bitmap
        bmp_info = win32gui.CreateBitmap()
        bmp_info.__dict__.update({
            'bmType': 0,
            'bmWidth': img.width,
            'bmHeight': img.height,
            'bmWidthBytes': img.width * 4,
            'bmPlanes': 1,
            'bmBitsPixel': 32,
            'bmBits': bgra.tobytes()
        })

        # 使用 CreateIconIndirect
        icon_info = win32gui.CreateIconIndirect()
        icon_info.__dict__.update({
            'hbmColor': bmp,
            'hbmMask': bmp,
            'fIcon': True,
            'xHotspot': img.width // 2,
            'yHotspot': img.height // 2,
        })

        win32gui.DeleteDC(hdc)
        return icon_info

    def _create_window_class(self) -> str:
        """注册窗口类"""
        class_name = "VirtualCursorOverlay"

        # 检查是否已注册
        try:
            win32gui.GetClassInfo(None, class_name)
            return class_name
        except:
            pass

        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = class_name
        wc.hbrBackground = win32con.CreateSolidBrush(win32api.RGB(0, 0, 0))
        wc.hCursor = 0  # 无光标

        atom = win32gui.RegisterClass(wc)
        return class_name

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """窗口消息处理"""
        if msg == win32con.WM_DESTROY:
            return 0
        elif msg == win32con.WM_PAINT:
            self._on_paint()
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _on_paint(self):
        """绘制光标"""
        if not self._visible or not self.cursor_hicon:
            return

        hwnd = self.hwnd
        dc, ps = win32gui.BeginPaint(hwnd)
        win32gui.DrawIconEx(dc, 0, 0, self.cursor_hicon, 24, 24, 0, None, win32con.DI_NORMAL)
        win32gui.EndPaint(hwnd, ps)

    def _ensure_window(self):
        """确保覆盖层窗口已创建"""
        if self.hwnd != 0:
            return

        class_name = self._create_window_class()

        # 获取屏幕尺寸
        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

        # 创建全屏最顶层窗口
        self.hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_TOPMOST | win32con.WS_EX_LAYERED | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TRANSPARENT,
            class_name,
            "VirtualCursor",
            win32con.WS_POPUP,
            0, 0, screen_w, screen_h,
            0, 0, 0, None
        )

        # 设置透明色 (完全透明，只显示光标)
        win32gui.SetLayeredWindowAttributes(self.hwnd, win32api.RGB(0, 0, 0), 0, win32con.LWA_COLORKEY)

        # 创建光标图像和图标
        self.cursor_img = self._create_cursor_image()
        self.cursor_hicon = self._create_hicon(self.cursor_img)

        # 初始隐藏
        win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)

    def show(self):
        """显示覆盖层"""
        self._ensure_window()
        if self.hwnd:
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)
            self._visible = True

    def hide(self):
        """隐藏覆盖层"""
        if self.hwnd:
            win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)
        self._visible = False

    def move_cursor(self, x: int, y: int):
        """
        移动虚拟光标到指定屏幕坐标
        """
        self._ensure_window()
        if not self.hwnd:
            return

        self._pos = (x, y)

        # 移动窗口到光标位置（光标居中）
        offset_x = x - 12
        offset_y = y - 12

        # WIN32API 只支持屏幕坐标
        win32gui.SetWindowPos(
            self.hwnd,
            win32con.HWND_TOPMOST,
            offset_x, offset_y, 24, 24,
            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
        )

        # 强制重绘
        win32gui.InvalidateRect(self.hwnd, None, True)

    def close(self):
        """关闭覆盖层"""
        if self.hwnd:
            win32gui.DestroyWindow(self.hwnd)
            self.hwnd = 0
            self._visible = False


# 全局单例
_overlay: Optional[Win32Overlay] = None


def get_overlay() -> Win32Overlay:
    """获取全局覆盖层实例"""
    global _overlay
    if _overlay is None:
        _overlay = Win32Overlay.get_instance()
    return _overlay