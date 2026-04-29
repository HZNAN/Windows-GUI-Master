"""
Windows 透明覆盖层 + 虚拟光标绘制
使用 24x24 小窗口 + HICON 绘制虚拟光标
"""
import os
import ctypes
import tempfile
import threading
from typing import Optional

import win32api
import win32con
import win32gui
from PIL import Image, ImageDraw
from loguru import logger


class Win32Overlay:
    """
    Windows 透明覆盖层
    创建 24x24 小窗口绘制虚拟光标，不影响真实鼠标操作
    """

    _instance: Optional["Win32Overlay"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.hwnd: int = 0
        self.cursor_hicon: Optional[int] = None
        self._visible = False
        self._pos = (-100, -100)
        self._cursor_png_path: Optional[str] = None
        self._cursor_type: str = "arrow"
        self._hicons: dict = {}  # 缓存不同类型的 HICON
        self._size = 48          # 窗口尺寸（需足够大容纳旋转后的光标）
        self._icon_size = 24     # 光标图标默认尺寸
        self._current_icon_size = 24  # 当前帧的实际图标尺寸（旋转后会变大）
        self._source_images: dict = {}     # cursor_type -> PIL Image (原始未旋转)
        self._angle_cache: dict[str, dict[int, int]] = {}  # cursor_type -> {snapped_angle: HICON}
        self._current_angle: float = -45.0

    @classmethod
    def get_instance(cls) -> "Win32Overlay":
        with cls._lock:
            if cls._instance is None:
                cls._instance = Win32Overlay()
            return cls._instance

    def _get_cursor_base_dir(self) -> str:
        """获取光标目录路径"""
        import os as _os
        from config.settings import PROJECT_ROOT, VIRTUAL_CURSOR_PATH

        cursor_cfg = VIRTUAL_CURSOR_PATH.strip()

        # 判断是绝对路径还是相对路径
        # 绝对路径: Windows 以盘符(C:)或UNC(\\)开头，Linux 以 / 开头
        if cursor_cfg.startswith('/') or cursor_cfg.startswith('\\\\') or (len(cursor_cfg) > 1 and cursor_cfg[1] == ':'):
            # 绝对路径
            return cursor_cfg
        else:
            # 相对路径: 相对于 PROJECT_ROOT/cursors/
            return str(PROJECT_ROOT / "cursor" / cursor_cfg)

    def _create_cursor_image(self, cursor_type: str = "arrow") -> Image.Image:
        """加载自定义光标图像"""
        import os as _os

        cursor_base = self._get_cursor_base_dir()
        cursor_path = _os.path.join(cursor_base, f"{cursor_type}.png")

        if _os.path.exists(cursor_path):
            img = Image.open(cursor_path).convert("RGBA")
            # 确保尺寸正确
            if img.size != (24, 24):
                img = img.resize((24, 24), Image.LANCZOS)
            return img

        logger.warning(f"Cursor image not found: {cursor_path}, using default")

        # 如果文件不存在，使用默认蓝白箭头
        size = 24
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        tip_x, tip_y = size // 2, 3
        base_x, base_y = size // 2, size - 3
        half_width = 6

        left_x = base_x - half_width
        left_y = base_y - 2
        right_x = base_x + half_width
        right_y = base_y - 2

        arrow_points = [
            (tip_x, tip_y),
            (left_x + 2, left_y - 4),
            (left_x, left_y),
            (base_x, base_y),
            (right_x, right_y),
            (right_x - 2, right_y - 4),
        ]

        # 蓝色模糊边缘 (3px)
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

        # 白色填充
        draw.polygon(arrow_points, fill=(255, 255, 255, 255))

        return img

    def _create_hicon(self, img: Image.Image, cursor_type: str = "arrow") -> int:
        """将 PIL RGBA 图像转换为 HICON"""
        from ctypes import windll, c_short, c_uint, c_long, Structure, sizeof, c_void_p, byref, cast, POINTER
        import struct

        size = 24

        logger.info(f"Starting _create_hicon, image size: {img.size}, mode: {img.mode}, type: {cursor_type}")

        # 保存 PNG 到临时文件
        temp_dir = tempfile.gettempdir()
        png_path = os.path.join(temp_dir, f"virtual_cursor_{cursor_type}.png")
        img.save(png_path, format="PNG")
        self._cursor_png_path = png_path
        logger.info(f"Saved cursor PNG to: {png_path}")

        # ICO 文件路径
        ico_path = os.path.join(temp_dir, f"virtual_cursor_{cursor_type}.ico")

        # ICO Header: 6 bytes
        # - Reserved (2 bytes): 0
        # - Type (2 bytes): 1 for icon
        # - Count (2 bytes): 1 image
        ico_header = struct.pack('<HHH', 0, 1, 1)

        # 准备 PNG 数据
        png_data = open(png_path, 'rb').read()
        png_size = len(png_data)

        # ICO Directory Entry: 16 bytes
        # - Width (1 byte): 0 means 256
        # - Height (1 byte): 0 means 256
        # - ColorCount (1 byte): 0 for 32bpp
        # - Reserved (1 byte): 0
        # - Planes (2 bytes): 1
        # - BitCount (2 bytes): 32
        # - BytesInRes (4 bytes): size of image data
        # - ImageOffset (4 bytes): offset to image data (6 + 16 = 22)
        ico_entry = struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, png_size, 22)

        # 写入 ICO 文件
        with open(ico_path, 'wb') as f:
            f.write(ico_header)
            f.write(ico_entry)
            f.write(png_data)

        logger.info(f"Created ICO file: {ico_path}, size: {os.path.getsize(ico_path)}")

        # 尝试加载 ICO 文件
        hicon = win32gui.LoadImage(
            0,
            ico_path,
            win32con.IMAGE_ICON,
            size, size,
            win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
        )

        if hicon:
            logger.info(f"LoadImage from ICO success: {hicon}")
            return hicon

        # 如果失败，尝试方案2: 使用 CreateIconIndirect
        logger.info("LoadImage from ICO failed, trying CreateIconIndirect...")

        try:
            # 准备 BGRA 数据（上下翻转，因为 DIB 是 bottom-up）
            pixels = []
            for y in range(size - 1, -1, -1):
                for x in range(size):
                    r, g, b, a = img.getpixel((x, y))
                    # 转为 BGRA
                    pixels.extend([b, g, r, a])

            logger.info(f"Prepared {len(pixels)} bytes of pixel data")

            # 使用 BITMAPINFO 结构
            class RGBQUAD(Structure):
                _fields_ = [('rgbBlue', c_uint), ('rgbGreen', c_uint), ('rgbRed', c_uint), ('rgbAlpha', c_uint)]

            class BITMAPINFOHEADER(Structure):
                _fields_ = [
                    ('biSize', c_uint),
                    ('biWidth', c_long),
                    ('biHeight', c_long),
                    ('biPlanes', c_short),
                    ('biBitCount', c_short),
                    ('biCompression', c_uint),
                    ('biSizeImage', c_uint),
                    ('biXPelsPerMeter', c_long),
                    ('biYPelsPerMeter', c_long),
                    ('biClrUsed', c_uint),
                    ('biClrImportant', c_uint),
                ]

            # 创建颜色位图
            bmi_color = BITMAPINFOHEADER()
            bmi_color.biSize = 40  # 固定 40 bytes
            bmi_color.biWidth = size
            bmi_color.biHeight = size * 2  # 双倍高度：color + mask
            bmi_color.biPlanes = 1
            bmi_color.biBitCount = 32
            bmi_color.biCompression = 0  # BI_RGB
            bmi_color.biSizeImage = size * size * 4

            hdc = windll.gdi32.CreateCompatibleDC(0)
            logger.info(f"Created HDC: {hdc}")

            ppvBits = c_void_p()
            hbmColor = windll.gdi32.CreateDIBSection(hdc, byref(bmi_color), 0, byref(ppvBits), None, 0)
            logger.info(f"CreateDIBSection color: hbmColor={hbmColor}")

            if not hbmColor:
                err = windll.kernel32.GetLastError()
                logger.warning(f"CreateDIBSection color failed, error: {err}")
                windll.gdi32.DeleteDC(hdc)
                return 0

            if not ppvBits or not ppvBits.value:
                logger.warning("ppvBits is null")
                windll.gdi32.DeleteObject(hbmColor)
                windll.gdi32.DeleteDC(hdc)
                return 0

            # 复制像素数据到 DIB
            img_size = size * size
            pPixels = cast(ppvBits, POINTER(c_long * img_size)).contents
            for i in range(img_size):
                offset = i * 4
                pPixels[i] = struct.unpack('<I', bytes(pixels[offset:offset+4]))[0]

            logger.info("Copied pixel data to DIB")

            # 创建 AND mask（全 0 表示全透明）
            bmi_mask = BITMAPINFOHEADER()
            bmi_mask.biSize = 40
            bmi_mask.biWidth = size
            bmi_mask.biHeight = size
            bmi_mask.biPlanes = 1
            bmi_mask.biBitCount = 1
            bmi_mask.biCompression = 0
            bmi_mask.biSizeImage = size * size // 8

            ppvMask = c_void_p()
            hbmMask = windll.gdi32.CreateDIBSection(hdc, byref(bmi_mask), 0, byref(ppvMask), None, 0)
            logger.info(f"CreateDIBSection mask: hbmMask={hbmMask}")

            # 将 mask 数据全部设为 1（表示全部不透明，由 color 的 alpha 决定）
            if hbmMask and ppvMask and ppvMask.value:
                from ctypes import c_ubyte
                mask_size = size * size // 8
                pMask = cast(ppvMask, POINTER(c_ubyte * mask_size)).contents
                for i in range(mask_size):
                    pMask[i] = 0xFF  # 全部设为 1（不透明）

            # 创建 ICONINFO
            class ICONINFO(Structure):
                _fields_ = [
                    ('fIcon', c_uint),
                    ('xHotspot', c_uint),
                    ('yHotspot', c_uint),
                    ('hbmMask', c_void_p),
                    ('hbmColor', c_void_p),
                ]

            ii = ICONINFO()
            ii.fIcon = 0  # 鼠标指针
            ii.xHotspot = 0
            ii.yHotspot = 0
            ii.hbmMask = hbmMask if hbmMask else None
            ii.hbmColor = hbmColor

            hicon = windll.user32.CreateIconIndirect(byref(ii))
            logger.info(f"CreateIconIndirect returned: {hicon}")

            if hicon:
                logger.info(f"CreateIconIndirect SUCCESS: {hicon}")
            else:
                err = windll.kernel32.GetLastError()
                logger.warning(f"CreateIconIndirect FAILED: error={err}")

            if hbmMask:
                windll.gdi32.DeleteObject(hbmMask)
            windll.gdi32.DeleteObject(hbmColor)
            windll.gdi32.DeleteDC(hdc)

            if hicon:
                return hicon

        except Exception as e:
            logger.warning(f"CreateIconIndirect exception: {e}")
            import traceback
            logger.warning(f"Traceback: {traceback.format_exc()}")

        return 0

    def _create_hicon_from_image(self, img: Image.Image, size: int = None) -> int:
        """从 PIL Image 通过 PNG→ICO 文件 + LoadImage 创建 HICON"""
        import io
        import struct

        if size is None:
            size = self._icon_size

        # 将 PIL Image 保存为 PNG 字节流
        png_buf = io.BytesIO()
        img.save(png_buf, format="PNG")
        png_data = png_buf.getvalue()

        # 构建 ICO 文件（ICO header + directory entry + PNG 数据）
        ico_header = struct.pack('<HHH', 0, 1, 1)
        ico_entry = struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, len(png_data), 22)

        # 写入临时 ICO 文件
        fd, ico_path = tempfile.mkstemp(suffix='.ico', prefix='vc_cache_')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(ico_header)
                f.write(ico_entry)
                f.write(png_data)

            # 通过 LoadImage 加载 HICON（与 _create_hicon 相同路径）
            hicon = win32gui.LoadImage(
                0, ico_path, win32con.IMAGE_ICON,
                size, size,
                win32con.LR_LOADFROMFILE
            )
        finally:
            try:
                os.unlink(ico_path)
            except OSError:
                pass

        return hicon if hicon else 0

    def _build_angle_cache(self, cursor_type: str):
        """为一个光标类型预生成旋转 HICON（每 3° 一个，expand=True 保留完整边界）"""
        logger.info(f"Building angle cache for '{cursor_type}' (120 HICONs)...")
        if cursor_type not in self._source_images:
            img = self._create_cursor_image(cursor_type)
            self._source_images[cursor_type] = img
        source = self._source_images[cursor_type]

        cache: dict[int, tuple[int, int]] = {}  # deg -> (hicon, actual_size)
        for deg in range(0, 360, 3):
            rotated = source.rotate(225 - deg, resample=Image.BICUBIC, expand=True)
            rw, rh = rotated.size
            use_size = max(rw, rh)
            # ICO 要求方形，非方形需 padding
            if rw != rh:
                square = Image.new("RGBA", (use_size, use_size), (0, 0, 0, 0))
                square.paste(rotated, ((use_size - rw) // 2, (use_size - rh) // 2))
                rotated = square
            hicon = self._create_hicon_from_image(rotated, size=use_size)
            if hicon:
                cache[deg] = (hicon, use_size)
        self._angle_cache[cursor_type] = cache
        logger.info(f"Angle cache for '{cursor_type}' built: {len(cache)} HICONs cached")

    def _get_cached_hicon(self, cursor_type: str, angle: float) -> tuple[int, int]:
        """获取最接近角度的缓存 HICON + 实际尺寸，必要时懒构建缓存"""
        if cursor_type not in self._angle_cache:
            self._build_angle_cache(cursor_type)
        cache = self._angle_cache[cursor_type]
        snapped = round(angle / 3) * 3
        snapped = snapped % 360
        return cache.get(snapped, (0, self._icon_size))

    def set_angle(self, angle: float):
        """设置光标显示角度并重绘（GetDC 直接绘制，跨线程安全）"""
        self._current_angle = angle
        hicon, icon_size = self._get_cached_hicon(self._cursor_type, angle)
        if hicon:
            self.cursor_hicon = hicon
            self._current_icon_size = icon_size
            if self.hwnd:
                self._paint_direct()

    def _paint_direct(self):
        """直接绘制到窗口 DC（不依赖消息泵，任何线程安全）"""
        dc = win32gui.GetDC(self.hwnd)
        try:
            win32gui.PatBlt(dc, 0, 0, self._size, self._size, win32con.BLACKNESS)
            if self.cursor_hicon:
                icon_sz = getattr(self, '_current_icon_size', self._icon_size)
                offset = (self._size - icon_sz) // 2
                win32gui.DrawIconEx(dc, offset, offset, self.cursor_hicon,
                    icon_sz, icon_sz, 0, None, win32con.DI_NORMAL)
        finally:
            win32gui.ReleaseDC(self.hwnd, dc)

    def _create_window_class(self) -> str:
        """注册窗口类"""
        class_name = "VirtualCursorOverlay"

        try:
            win32gui.GetClassInfo(None, class_name)
            return class_name
        except:
            pass

        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = class_name
        wc.hbrBackground = win32gui.CreateSolidBrush(win32api.RGB(0, 0, 0))  # 黑色背景
        wc.hCursor = 0

        win32gui.RegisterClass(wc)
        return class_name

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_DESTROY:
            return 0
        elif msg == win32con.WM_PAINT:
            self._on_paint()
            return 0
        elif msg == win32con.WM_ERASEBKGND:
            return 1
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _on_paint(self):
        """绘制光标"""
        if not self._visible:
            return

        hwnd = self.hwnd
        dc, ps = win32gui.BeginPaint(hwnd)

        # 填充黑色背景（LWA_COLORKEY 使黑色透明），清除上一帧残留
        win32gui.PatBlt(dc, 0, 0, self._size, self._size, win32con.BLACKNESS)

        icon_sz = getattr(self, '_current_icon_size', self._icon_size)
        offset = (self._size - icon_sz) // 2

        # 使用当前光标类型的 HICON
        if self.cursor_hicon:
            win32gui.DrawIconEx(dc, offset, offset, self.cursor_hicon,
                icon_sz, icon_sz, 0, None, win32con.DI_NORMAL)
        else:
            # 备用：加载对应的 ICO 文件
            ico_path = os.path.join(tempfile.gettempdir(), f"virtual_cursor_{self._cursor_type}.ico")
            if os.path.exists(ico_path):
                try:
                    hicon = win32gui.LoadImage(
                        0,
                        ico_path,
                        win32con.IMAGE_ICON,
                        icon_sz, icon_sz,
                        win32con.LR_LOADFROMFILE
                    )
                    if hicon:
                        win32gui.DrawIconEx(dc, offset, offset, hicon,
                            icon_sz, icon_sz, 0, None, win32con.DI_NORMAL)
                        win32gui.DestroyIcon(hicon)
                except Exception as e:
                    logger.warning(f"LoadImage ICO failed: {e}")

        win32gui.EndPaint(hwnd, ps)

    def _ensure_window(self):
        if self.hwnd != 0:
            return

        class_name = self._create_window_class()

        self.hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_LAYERED | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST,
            class_name,
            "VirtualCursor",
            win32con.WS_POPUP,
            0, 0, self._size, self._size,
            0, 0, 0, None
        )

        # 设置透明色键
        win32gui.SetLayeredWindowAttributes(self.hwnd, win32api.RGB(0, 0, 0), 0, win32con.LWA_COLORKEY)

        # 预加载两种光标的源图和默认 HICON
        for cursor_type in ["arrow", "hand"]:
            img = self._create_cursor_image(cursor_type)
            self._source_images[cursor_type] = img  # 保存源图供 angle cache 使用
            hicon = self._create_hicon(img, cursor_type)
            if hicon:
                self._hicons[cursor_type] = hicon
                logger.info(f"Loaded cursor type '{cursor_type}': hicon={hicon}")

        # 使用默认光标类型
        self.cursor_hicon = self._hicons.get(self._cursor_type)
        if not self.cursor_hicon and self._hicons:
            self.cursor_hicon = next(iter(self._hicons.values()))

        # 初始隐藏
        win32gui.SetWindowPos(
            self.hwnd, win32con.HWND_TOPMOST,
            -100, -100, self._size, self._size,
            win32con.SWP_NOACTIVATE | win32con.SWP_HIDEWINDOW
        )

    def set_cursor_type(self, cursor_type: str):
        """设置光标类型（arrow 或 hand）"""
        if cursor_type not in ("arrow", "hand"):
            return

        self._cursor_type = cursor_type

        # 确保该类型的源图已加载
        if cursor_type not in self._source_images:
            self._source_images[cursor_type] = self._create_cursor_image(cursor_type)

        # 使用当前角度的缓存 HICON（懒构建）
        if self.hwnd:
            hicon = self._get_cached_hicon(cursor_type, self._current_angle)
            if hicon:
                self.cursor_hicon = hicon
                win32gui.InvalidateRect(self.hwnd, None, False)
        elif cursor_type in self._hicons:
            self.cursor_hicon = self._hicons[cursor_type]

    def show(self):
        self._ensure_window()
        if self.hwnd:
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)
            self._visible = True

    def hide(self):
        if self.hwnd:
            win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)
        self._visible = False

    def move_cursor(self, x: int, y: int, cursor_type: str = "arrow"):
        """移动虚拟光标到指定屏幕坐标"""
        self._ensure_window()
        if not self.hwnd:
            return

        # 如果光标类型改变，切换 HICON
        if cursor_type != self._cursor_type:
            self._cursor_type = cursor_type
            if cursor_type in self._hicons:
                self.cursor_hicon = self._hicons[cursor_type]

        self._pos = (x, y)
        self._visible = True

        # 移动窗口到光标位置
        win32gui.SetWindowPos(
            self.hwnd,
            win32con.HWND_TOPMOST,
            x - self._size // 2, y - self._size // 2, self._size, self._size,
            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
        )

        # 强制立即重绘（同步等待）
        win32gui.InvalidateRect(self.hwnd, None, False)
        win32gui.UpdateWindow(self.hwnd)  # 阻塞直到 WM_PAINT 处理完成

    def close(self):
        # 销毁所有角度缓存的 HICON
        for cache in self._angle_cache.values():
            for hicon in cache.values():
                if hicon:
                    win32gui.DestroyIcon(hicon)
        self._angle_cache.clear()
        # 销毁默认 HICON
        for hicon in self._hicons.values():
            if hicon:
                win32gui.DestroyIcon(hicon)
        self._hicons.clear()
        if self.hwnd:
            win32gui.DestroyWindow(self.hwnd)
            self.hwnd = 0
        self._visible = False


_overlay: Optional[Win32Overlay] = None


def get_overlay() -> Win32Overlay:
    global _overlay
    if _overlay is None or _overlay.hwnd == 0:
        _overlay = Win32Overlay()  # 直接创建，绕过类级单例的缓存问题
    return _overlay