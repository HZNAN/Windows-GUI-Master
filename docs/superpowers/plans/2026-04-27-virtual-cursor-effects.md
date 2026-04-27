# Virtual Cursor Dynamic Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add idle wobble, movement rotation, and return-to-default rotation to the virtual cursor via HICON angle cache pool and three-state animation machine.

**Architecture:** Pre-render 120 rotated HICONs at 3° increments into a lazy cache. VirtualCursor state machine: IDLE (sine-wave wobble ±6°) → MOVING (bezier tangent rotation) → RETURNING (ease-in-out back to -45°). Idle runs in daemon thread at 30fps.

**Tech Stack:** PIL (image rotation), win32gui (CreateDIBSection/CreateIconIndirect/DrawIconEx), Python threading

**Files Modified:**
- `drivers/win32_overlay.py` — HICON angle cache, `set_angle()`, `_create_hicon_from_image()`
- `core/virtual_cursor.py` — Three-state animation machine, tangent calculation, idle thread

---

### Task 1: Win32Overlay — HICON from PIL image helper (no file I/O)

**Files:**
- Modify: `drivers/win32_overlay.py` — add `_create_hicon_from_image()` after `_create_hicon()`

- [ ] **Step 1: Add `_create_hicon_from_image()` method**

Extract the CreateDIBSection + CreateIconIndirect path from `_create_hicon` into a standalone helper that skips the temp-file ICO path. Insert after `_create_hicon()` (after line 309).

```python
def _create_hicon_from_image(self, img: Image.Image) -> int:
    """从 PIL Image 直接创建 HICON（纯内存，无文件 I/O，用于批量缓存构建）"""
    from ctypes import windll, c_short, c_uint, c_long, Structure, sizeof, c_void_p, byref, cast, POINTER
    import struct

    size = 24

    # 准备 BGRA 数据（上下翻转，因为 DIB 是 bottom-up）
    pixels = []
    for y in range(size - 1, -1, -1):
        for x in range(size):
            r, g, b, a = img.getpixel((x, y))
            pixels.extend([b, g, r, a])

    class BITMAPINFOHEADER(Structure):
        _fields_ = [
            ('biSize', c_uint), ('biWidth', c_long), ('biHeight', c_long),
            ('biPlanes', c_short), ('biBitCount', c_short), ('biCompression', c_uint),
            ('biSizeImage', c_uint), ('biXPelsPerMeter', c_long),
            ('biYPelsPerMeter', c_long), ('biClrUsed', c_uint), ('biClrImportant', c_uint),
        ]

    hdc = windll.gdi32.CreateCompatibleDC(0)

    bmi_color = BITMAPINFOHEADER()
    bmi_color.biSize = 40
    bmi_color.biWidth = size
    bmi_color.biHeight = size * 2
    bmi_color.biPlanes = 1
    bmi_color.biBitCount = 32
    bmi_color.biCompression = 0  # BI_RGB
    bmi_color.biSizeImage = size * size * 4

    ppvBits = c_void_p()
    hbmColor = windll.gdi32.CreateDIBSection(hdc, byref(bmi_color), 0, byref(ppvBits), None, 0)
    if not hbmColor or not ppvBits or not ppvBits.value:
        windll.gdi32.DeleteDC(hdc)
        return 0

    # 复制像素数据到 DIB
    img_size = size * size
    pPixels = cast(ppvBits, POINTER(c_long * img_size)).contents
    for i in range(img_size):
        offset = i * 4
        pPixels[i] = struct.unpack('<I', bytes(pixels[offset:offset+4]))[0]

    # 创建 AND mask（全 0xFF 表示全不透明，由 color 的 alpha 决定）
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
    if hbmMask and ppvMask and ppvMask.value:
        from ctypes import c_ubyte
        mask_size = size * size // 8
        pMask = cast(ppvMask, POINTER(c_ubyte * mask_size)).contents
        for i in range(mask_size):
            pMask[i] = 0xFF

    class ICONINFO(Structure):
        _fields_ = [
            ('fIcon', c_uint), ('xHotspot', c_uint), ('yHotspot', c_uint),
            ('hbmMask', c_void_p), ('hbmColor', c_void_p),
        ]

    ii = ICONINFO()
    ii.fIcon = 0
    ii.xHotspot = 0
    ii.yHotspot = 0
    ii.hbmMask = hbmMask if hbmMask else None
    ii.hbmColor = hbmColor

    hicon = windll.user32.CreateIconIndirect(byref(ii))

    if hbmMask:
        windll.gdi32.DeleteObject(hbmMask)
    windll.gdi32.DeleteObject(hbmColor)
    windll.gdi32.DeleteDC(hdc)

    return hicon
```

- [ ] **Step 2: Commit**

```bash
git add drivers/win32_overlay.py
git commit -m "feat: add _create_hicon_from_image() — in-memory HICON creation for angle cache"
```

---

### Task 2: Win32Overlay — angle cache pool + set_angle()

**Files:**
- Modify: `drivers/win32_overlay.py` — add fields, `_build_angle_cache()`, `_get_cached_hicon()`, `set_angle()`

- [ ] **Step 1: Add new fields to `__init__`**

Add after `self._size = 24` (line 35):

```python
self._source_images: dict = {}     # cursor_type → PIL Image (原始未旋转)
self._angle_cache: dict[str, dict[int, int]] = {}  # cursor_type → {snapped_angle: HICON}
self._current_angle: float = -45.0
```

- [ ] **Step 2: Add `_build_angle_cache()` method**

Insert before `_create_window_class()`:

```python
def _build_angle_cache(self, cursor_type: str):
    """为一个光标类型预生成 120 个旋转 HICON（每 3° 一个）"""
    if cursor_type not in self._source_images:
        img = self._create_cursor_image(cursor_type)
        self._source_images[cursor_type] = img
    source = self._source_images[cursor_type]

    cache: dict[int, int] = {}
    for deg in range(0, 360, 3):
        # 源图 tip 指向 -45°（左上），要转到 deg 需要旋转 (deg + 45)°
        rotated = source.rotate(deg + 45, resample=Image.BICUBIC, expand=False)
        hicon = self._create_hicon_from_image(rotated)
        if hicon:
            cache[deg] = hicon
    self._angle_cache[cursor_type] = cache
```

- [ ] **Step 3: Add `_get_cached_hicon()` and `set_angle()`**

Insert after `_build_angle_cache()`:

```python
def _get_cached_hicon(self, cursor_type: str, angle: float) -> int:
    """获取最接近角度的缓存 HICON，必要时懒构建缓存"""
    if cursor_type not in self._angle_cache:
        self._build_angle_cache(cursor_type)
    cache = self._angle_cache[cursor_type]
    snapped = round(angle / 3) * 3
    snapped = snapped % 360
    return cache.get(snapped, 0)

def set_angle(self, angle: float):
    """设置光标显示角度并触发重绘"""
    self._current_angle = angle
    hicon = self._get_cached_hicon(self._cursor_type, angle)
    if hicon:
        self.cursor_hicon = hicon
        if self.hwnd:
            win32gui.InvalidateRect(self.hwnd, None, False)
```

- [ ] **Step 4: Commit**

```bash
git add drivers/win32_overlay.py
git commit -m "feat: add angle cache pool + set_angle() to Win32Overlay"
```

---

### Task 3: Win32Overlay — integrate cache into lifecycle

**Files:**
- Modify: `drivers/win32_overlay.py` — `_ensure_window()`, `set_cursor_type()`, `close()`

- [ ] **Step 1: Modify `_ensure_window()` to preserve source images**

Replace the icon pre-loading block (lines 390-401) with:

```python
# 预加载两种光标的源图和默认 HICON
for cursor_type in ["arrow", "hand"]:
    img = self._create_cursor_image(cursor_type)
    self._source_images[cursor_type] = img  # 保存源图供 angle cache 使用
    hicon = self._create_hicon(img, cursor_type)
    if hicon:
        self._hicons[cursor_type] = hicon
        logger.info(f"Loaded cursor type '{cursor_type}': hicon={hicon}")
```

- [ ] **Step 2: Modify `set_cursor_type()` to use angle cache**

Replace the method (lines 409-419) with:

```python
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
```

- [ ] **Step 3: Modify `close()` to destroy cached HICONs**

Replace `close()` (lines 459-463) with:

```python
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
```

- [ ] **Step 4: Commit**

```bash
git add drivers/win32_overlay.py
git commit -m "feat: integrate angle cache into overlay lifecycle"
```

---

### Task 4: VirtualCursor — animation constants, tangent calc, and init

**Files:**
- Modify: `core/virtual_cursor.py` — add module-level constants, new fields, `_calc_tangent_angle()`

- [ ] **Step 1: Add constants after imports (after line 13)**

```python
# 动画效果常量
DEFAULT_ANGLE = -45.0       # 光标默认指向（左上）
IDLE_AMPLITUDE = 6.0        # 静止晃动幅度（±度）
IDLE_PERIOD = 1.0           # 静止晃动周期（秒）
IDLE_FPS = 30               # 静止晃动帧率
RETURN_DURATION = 0.3       # 归位旋转时长（秒）
```

- [ ] **Step 2: Add new fields to `VirtualCursor.__init__`**

Add after `self._lock = threading.Lock()` (line 63):

```python
self._current_angle = DEFAULT_ANGLE
self._idle_thread: Optional[threading.Thread] = None
self._idle_running = False
```

- [ ] **Step 3: Add `_calc_tangent_angle()` static method**

Insert before `def _generate_curve()`:

```python
@staticmethod
def _calc_tangent_angle(curve: BezierCurve, t: float) -> float:
    """计算贝塞尔曲线上 t 点的切线方向角度（数学坐标系，CCW from x-axis）"""
    import math
    delta = 0.001
    t1 = max(0.0, t - delta)
    t2 = min(1.0, t + delta)
    x1, y1 = curve.point_at(t1)
    x2, y2 = curve.point_at(t2)
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 0.001 and abs(dy) < 0.001:
        return DEFAULT_ANGLE
    return math.degrees(math.atan2(-dy, dx))
```

- [ ] **Step 4: Write unit test for tangent angle**

Create `test_virtual_cursor_effects.py`:

```python
"""测试虚拟光标特效的数学函数"""
import math
from core.virtual_cursor import (
    VirtualCursor, BezierCurve,
    DEFAULT_ANGLE, IDLE_AMPLITUDE, IDLE_PERIOD
)


def test_tangent_angle_horizontal():
    """水平向右移动 → 切线角度应为 0°"""
    curve = BezierCurve(0, 0, 33, 0, 66, 0, 100, 0)
    angle = VirtualCursor._calc_tangent_angle(curve, 0.5)
    assert abs(angle - 0) < 1, f"Expected ~0°, got {angle}°"


def test_tangent_angle_vertical_up():
    """垂直向上移动 → 切线角度应为 90°"""
    curve = BezierCurve(0, 100, 0, 66, 0, 33, 0, 0)
    angle = VirtualCursor._calc_tangent_angle(curve, 0.5)
    assert abs(angle - 90) < 1, f"Expected ~90°, got {angle}°"


def test_tangent_angle_diagonal():
    """对角线右上移动 → 切线角度应为 ~45°"""
    curve = BezierCurve(0, 100, 33, 66, 66, 33, 100, 0)
    angle = VirtualCursor._calc_tangent_angle(curve, 0.5)
    assert 40 < angle < 50, f"Expected ~45°, got {angle}°"


def test_tangent_angle_at_start():
    """t=0 时应返回合理角度"""
    curve = BezierCurve(0, 0, 33, 20, 66, 20, 100, 0)
    angle = VirtualCursor._calc_tangent_angle(curve, 0.0)
    assert -90 <= angle <= 90, f"Expected reasonable angle, got {angle}°"


def test_idle_wobble_formula():
    """验证 idle wobble 公式在合理范围内"""
    import time
    elapsed = 0.25  # 四分之一周期
    angle = DEFAULT_ANGLE + IDLE_AMPLITUDE * math.sin(elapsed * 2 * math.pi / IDLE_PERIOD)
    # 1/4 周期时 sin(π/2) = 1，角度应为 -45 + 6 = -39
    assert abs(angle - (-39.0)) < 0.1, f"Expected ~-39°, got {angle}°"

    elapsed = 0.5  # 半周期
    angle = DEFAULT_ANGLE + IDLE_AMPLITUDE * math.sin(elapsed * 2 * math.pi / IDLE_PERIOD)
    # 半周期时 sin(π) = 0，角度应为 -45
    assert abs(angle - DEFAULT_ANGLE) < 0.1, f"Expected ~{DEFAULT_ANGLE}°, got {angle}°"
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest test_virtual_cursor_effects.py -v
```
Expected: 5 tests pass

- [ ] **Step 6: Commit**

```bash
git add core/virtual_cursor.py test_virtual_cursor_effects.py
git commit -m "feat: add tangent angle calculation + unit tests"
```

---

### Task 5: VirtualCursor — move_to() rotation + return rotation

**Files:**
- Modify: `core/virtual_cursor.py` — modify `move_to()`, add `_return_rotation()`

- [ ] **Step 1: Add `_return_rotation()` method**

Insert after `move_to()` (after line 173):

```python
def _return_rotation(self, from_angle: float):
    """从当前角度平滑旋转回默认角度"""
    total_frames = int(RETURN_DURATION * self.fps)
    if total_frames < 1:
        total_frames = 1
    frame_duration = 1.0 / self.fps

    for frame in range(total_frames + 1):
        t_raw = frame / total_frames
        t_eased = ease_in_out_cubic(t_raw)
        angle = from_angle + (DEFAULT_ANGLE - from_angle) * t_eased
        self._current_angle = angle
        self.overlay.set_angle(angle)
        start_time = time.perf_counter()
        self.overlay.move_cursor(self._current_pos[0], self._current_pos[1])
        elapsed = time.perf_counter() - start_time
        remaining = frame_duration - elapsed
        if remaining > 0:
            time.sleep(remaining)
```

- [ ] **Step 2: Modify `move_to()` to integrate rotation per frame and call return/idle**

Replace the move_to frame loop body (lines 138-165) to add angle set per frame, and add return-idle transition after the loop. The full modified `move_to()`:

```python
def move_to(self, x: int, y: int, callback: Optional[Callable] = None):
    """移动虚拟光标到目标坐标（带动画 + 方向旋转）"""
    with self._lock:
        if self._running:
            self._running = False
            time.sleep(0.05)
        self._idle_running = False  # 停止 idle 动画
        start_x, start_y = self._current_pos
        self._target_pos = (x, y)

    curve = self._generate_curve(start_x, start_y, x, y)

    total_frames = int(self.duration * self.fps)
    if total_frames < 1:
        total_frames = 1

    self.overlay.show()

    self._running = True
    frame_duration = 1.0 / self.fps

    last_angle = self._current_angle

    for frame in range(total_frames + 1):
        if not self._running:
            break

        t_raw = frame / total_frames
        t_eased = ease_in_out_cubic(t_raw)

        px, py = curve.point_at(t_raw)
        actual_x = start_x + (x - start_x) * t_eased
        actual_y = start_y + (y - start_y) * t_eased

        final_x = int(px * t_eased + actual_x * (1 - t_eased))
        final_y = int(py * t_eased + actual_y * (1 - t_eased))

        # 计算并设置切线方向旋转角度
        angle = self._calc_tangent_angle(curve, t_raw)
        self._current_angle = angle
        last_angle = angle

        self._current_pos = (final_x, final_y)
        start_time = time.perf_counter()

        self.overlay.set_angle(angle)
        self.overlay.move_cursor(final_x, final_y)

        elapsed = time.perf_counter() - start_time
        remaining = frame_duration - elapsed
        if remaining > 0:
            time.sleep(remaining)

    self._running = False
    self._current_pos = (x, y)
    self.overlay.set_angle(last_angle)
    self.overlay.move_cursor(x, y)

    # 归位旋转 → 启动 idle 晃动
    self._return_rotation(last_angle)
    self._start_idle_animation()

    if callback:
        callback()
```

- [ ] **Step 3: Commit**

```bash
git add core/virtual_cursor.py
git commit -m "feat: integrate rotation into move_to() + return-to-default animation"
```

---

### Task 6: VirtualCursor — idle wobble animation thread

**Files:**
- Modify: `core/virtual_cursor.py` — add `_idle_loop()`, `_start_idle_animation()`, `_stop_idle_animation()`

- [ ] **Step 1: Add idle control methods**

Insert after `_return_rotation()`:

```python
def _start_idle_animation(self):
    """启动静止晃动后台线程"""
    self._idle_running = True
    self._idle_thread = threading.Thread(target=self._idle_loop, daemon=True)
    self._idle_thread.start()

def _stop_idle_animation(self):
    """停止静止晃动线程"""
    self._idle_running = False
    if self._idle_thread and self._idle_thread.is_alive():
        self._idle_thread.join(timeout=0.5)
    self._idle_thread = None

def _idle_loop(self):
    """静止晃动循环（在 daemon 线程中运行）"""
    import math
    start_time = time.perf_counter()
    while self._idle_running:
        elapsed = time.perf_counter() - start_time
        angle = DEFAULT_ANGLE + IDLE_AMPLITUDE * math.sin(
            elapsed * 2 * math.pi / IDLE_PERIOD
        )
        self._current_angle = angle
        self.overlay.set_angle(angle)
        time.sleep(1.0 / IDLE_FPS)
```

- [ ] **Step 2: Modify `hide()` to stop idle animation**

Replace `hide()` (lines 182-184) with:

```python
def hide(self):
    """隐藏虚拟光标"""
    self._stop_idle_animation()
    self.overlay.hide()
```

- [ ] **Step 3: Modify `stop()` to also stop idle**

Replace `stop()` (lines 190-194) with:

```python
def stop(self):
    """立即停止当前动画和 idle 晃动"""
    self._running = False
    self._stop_idle_animation()
    time.sleep(0.1)
```

- [ ] **Step 4: Modify `set_position()` to restart idle after manual positioning**

Replace `set_position()` (lines 176-180) with:

```python
def set_position(self, x: int, y: int):
    """直接设置光标位置（无动画），之后启动 idle 晃动"""
    self._stop_idle_animation()
    self._current_pos = (x, y)
    self.overlay.show()
    self.overlay.set_angle(DEFAULT_ANGLE)
    self.overlay.move_cursor(x, y)
    self._start_idle_animation()
```

- [ ] **Step 5: Commit**

```bash
git add core/virtual_cursor.py
git commit -m "feat: add idle wobble animation thread"
```

---

### Task 7: Visual verification test script

**Files:**
- Create: `test_virtual_cursor_effects_visual.py`

- [ ] **Step 1: Write visual verification script**

```python
"""视觉验证：虚拟光标动态特效

测试流程：
1. 创建虚拟光标，移动到位置 A
2. 观察 idle wobble 效果（光标应在 ±6° 范围内晃动）
3. 移动到位置 B，观察移动过程中光标是否跟随方向旋转
4. 观察归位旋转效果（到达后 0.3s 缓慢转回 -45°）
5. 观察 idle wobble 恢复
"""
import time
from core.virtual_cursor import VirtualCursor, get_virtual_cursor

def main():
    import os
    os.environ.setdefault("VIRTUAL_CURSOR_PATH", "universe")
    os.environ.setdefault("VIRTUAL_CURSOR_DURATION", "1.0")
    os.environ.setdefault("VIRTUAL_CURSOR_FPS", "60")

    vc = VirtualCursor(amplitude=15, duration=1.0, fps=60)

    # 获取屏幕尺寸
    from drivers.screen_capture import get_screen_capture
    screen = get_screen_capture()
    img, _ = screen.auto_save(prefix="temp")
    h, w = img.shape[:2]

    print("=== 虚拟光标动态特效测试 ===")
    print(f"屏幕尺寸: {w}x{h}")

    # 测试 1: 设置初始位置，观察 idle wobble
    print("\n1. 设置初始位置 (500, 300)，观察 idle wobble...")
    vc.set_position(500, 300)
    time.sleep(5)  # 观察 5 秒 idle 晃动

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

    print("\n=== 测试完成，隐藏光标 ===")
    vc.hide()
    time.sleep(1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run visual test**

```bash
python test_virtual_cursor_effects_visual.py
```

Verify manually:
- [ ] Idle wobble: 光标在 ±6° 范围晃动，周期约 1 秒
- [ ] Movement rotation: 光标箭头指向移动方向
- [ ] Return rotation: 到达后平滑转回 -45°
- [ ] Idle resume: 归位后恢复晃动

- [ ] **Step 3: Commit**

```bash
git add test_virtual_cursor_effects_visual.py
git commit -m "test: add visual verification script for cursor effects"
```

---

