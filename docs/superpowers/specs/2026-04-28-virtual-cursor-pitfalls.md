# Virtual Cursor Dynamic Effects — 踩坑记录

记录实现虚拟光标动态特效过程中遇到的所有问题、根因和解决方案。

---

## 1. WndProc 按类绑定导致实例销毁后回调失效

**问题：** 同一进程中多次创建/销毁 Win32Overlay 实例时，新实例无法接收窗口消息。

**根因：** 每个 `Win32Overlay` 实例注册一个 WNDCLASS（类名为 `Overlay_{id}`），WndProc 通过闭包捕获 `self`。当 `self` 被销毁后，WNDCLASS 已注册，再次创建同 ID 实例时不会重新注册，但旧闭包中的 `self` 已失效。

**解决：** 不在 `__init__` 中按实例注册窗口类。使用全局单例模式注册一次 WNDCLASS，WndProc 通过 `GWLP_USERDATA` 或全局字典查找当前实例。

---

## 2. CreateDIBSection + CreateIconIndirect 无法创建 32bpp 带 Alpha 通道的 HICON

**问题：** 用 `CreateDIBSection` 创建 32bpp BGRA 位图 + `CreateIconIndirect` 创建的 HICON，通过 `DrawIconEx` 绘制时完全不显示。

**尝试：**
- 调整 AND mask 为全 0xFF（不透明）/ 全 0x00（透明）——均无效
- 调整 BITMAPINFOHEADER 的 biHeight 为 `size` 或 `size * 2`（XOR+AND 双位图）——均无效
- 检查 DIB section 像素数据写入是否正确——数据正确但 HICON 仍无效

**根本原因：** `CreateIconIndirect` 期望的位图格式与 32bpp alpha DIB section 不兼容。Windows 图标 API 对 alpha 通道的处理在不同版本间不一致，且 `CreateIconIndirect` 文档未明确说明对 32bpp 预乘 alpha 的支持情况。

**解决：** 放弃纯内存路径，改用 `_create_hicon()` 已有的可靠路径——PIL Image → PNG 字节 → 临时 ICO 文件 → `LoadImage(IMAGE_ICON, LR_LOADFROMFILE)` → 立即删除临时文件。虽然涉及磁盘 I/O，但 HICON 创建 100% 可靠。

```python
# 最终方案：PNG → 临时 ICO → LoadImage → 清理临时文件
png_buf = io.BytesIO()
img.save(png_buf, format="PNG")
# ... 构建 ICO 文件头 + PNG 数据 ...
hicon = win32gui.LoadImage(0, ico_path, win32con.IMAGE_ICON, size, size,
    win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE)
os.unlink(ico_path)  # 立即清理
```

---

## 3. WM_ERASEBKGND 返回 1 阻止了 BeginPaint 的自动背景清除

**问题：** 光标窗口显示为黑色方块，或出现多帧图像叠加（frame accumulation）。

**根因：** `WS_EX_LAYERED` + `LWA_COLORKEY` 使用 `RGB(0,0,0)` 做透明色键。WndProc 中 `WM_ERASEBKGND` 返回 1（表示已处理，阻止默认擦除），导致 `BeginPaint` 不会填充背景。每帧的 `DrawIconEx` 直接画在上一帧内容上，产生累积叠加效果。未初始化的 DC 内存是随机值，显示为黑块。

**解决：** 在 `_on_paint()` 的 `BeginPaint` 之后、`DrawIconEx` 之前显式调用 `PatBlt(BLACKNESS)` 清空背景：

```python
def _on_paint(self):
    dc, ps = win32gui.BeginPaint(hwnd)
    win32gui.PatBlt(dc, 0, 0, self._size, self._size, win32con.BLACKNESS)
    # 黑色被 LWA_COLORKEY 视为透明，背景干净
    if self.cursor_hicon:
        win32gui.DrawIconEx(dc, 0, 0, self.cursor_hicon, ...)
```

---

## 4. 角度缓存公式必须匹配实际图片方向

**问题：** 旋转后的光标指向错误——指向水平左侧而非左上，或指向右上而非左上。

**根因链：**
1. 设计文档假设光标源图（arrow.png）的箭头指向 -45°（左上），并以该假设推导出缓存公式 `source.rotate(deg + 45)`
2. **实际 arrow.png 的箭头朝上（↑）并略向左倾斜**，偏移量约 45°
3. 屏幕坐标系 Y 轴向下，而 PIL `Image.rotate()` 是逆时针旋转（数学坐标系）
4. 需要将"屏幕上显示角度 deg"映射为"对源图施加的 PIL 旋转角度"

**调试过程：**
- `source.rotate(deg + 45)` → 指向错误（假设不对）
- `source.rotate(-deg - 90)` → 指向水平左侧
- `source.rotate(225 - deg)` → ✓ 正确

**最终公式推导（PIL rotate 角度 = `225 - deg`）：**

| 目标指向 (deg) | PIL rotate 角度 | 效果 |
|---|---|---|
| 225° (左上, 默认) | 0° (不旋转) | 保持源图自然朝向 |
| 0° (右) | 225° | 箭头朝右 |
| 90° (下) | 135° | 箭头朝下 |
| 180° (左) | 45° | 箭头朝左 |
| 270° (上) | -45° | 箭头朝上 |

**教训：** 不要假设图片资源的方向。先检查实际图片，再推导坐标变换公式。

---

## 5. 旋转裁剪 2.0 — 数学约束

**原问题（Pitfall #5 初版修复）：** 72×72 画布 + `expand=False` → 中心裁回 24×24 时切掉 5px。

**尝试修复：** 增大画布到 96×96。**结果：无效。**

**根因是数学约束，不是画布不够大：**

24×24 的图，旋转 45° 后对角 = 24√2 ≈ 34px。从中心到任意边的最短距离固定为 12px（半宽），而从中心到旋转后顶点的最长距离为 17px（半对角）。**17 > 12 恒成立**，与画布大小无关——无论画布多大，只要最终 crop 回 24×24，就必然裁掉 5px。

```
24×24 @ 0°:   ████              24×24 @ 45°:    ██
               ████                             ████
               ████                            ██████
               ████                             ████
                ← 24 →                           ██
                                               ← 34 →
                                               crop 24 框装不下
```

**尝试 expand=True + resize 回 24：** 旋转后 34px 强制缩回 24px（71%），光标在 45° 明显变小，产生"忽大忽小"效果——**比裁剪更糟。**

**最终方案：接受自然展开**

| 改动 | 之前 | 之后 |
|------|------|------|
| 窗口尺寸 | 24×24 | **48×48** |
| 光标图标尺寸 | 固定 24×24 | **24~34×24~34（实际尺寸）** |
| 旋转方式 | canvas + expand=False | **expand=True** |
| 是否裁剪 | 45° 时被切 | **不裁剪** |
| 是否缩水 | 强制 crop 回 24 | **不缩水** |

关键代码改动：
```python
# _build_angle_cache: expand=True + 方形 padding + 存实际尺寸
rotated = source.rotate(225 - deg, resample=Image.BICUBIC, expand=True)
rw, rh = rotated.size
use_size = max(rw, rh)
if rw != rh:
    square = Image.new("RGBA", (use_size, use_size), (0, 0, 0, 0))
    square.paste(rotated, ((use_size - rw) // 2, (use_size - rh) // 2))
    rotated = square
cache[deg] = (hicon, use_size)  # 存 (hicon, 实际尺寸)

# set_angle: 更新当前图标尺寸
self._current_icon_size = icon_size

# _paint_direct: 用实际尺寸居中绘制
icon_sz = self._current_icon_size
offset = (self._size - icon_sz) // 2
DrawIconEx(dc, offset, offset, hicon, icon_sz, icon_sz, ...)
```

40° 时光标比 0° 稍"宽"（34 vs 24），但视觉上这是自然的"展开"，远好过裁剪或缩水。

---

## 6. 角度回绕 (Angle Wrapping) 打断插值

**问题：** 当贝塞尔曲线切线方向跨越 ±180° 边界时（如从 179° 变到 -179°），角度突然跳变约 358° 而非平滑过渡 2°。

**根因：** 角度值范围是 [-180°, 180°)，而切线计算返回的 `atan2` 值可跨越此边界。直接的线性插值 `last + (target - last) * factor` 在跨越边界时走的是远路。

**解决：** 在计算差值后做 ±360° 归一化，使差值始终在 [-180°, 180°] 范围内，确保插值走最短路径：

```python
target_angle = self._calc_tangent_angle(curve, t_raw)
diff = target_angle - last_angle
if diff > 180:
    diff -= 360
elif diff < -180:
    diff += 360
angle = last_angle + diff * 0.15  # 走最短路径
```

---

## 7. 移动旋转瞬变（无平滑过程）

**问题：** 光标在移动过程中角度瞬间切换，没有平滑旋转动画。

**根因：** 最初直接设置角度 `angle = tangent_angle`，后改为全时长 t_eased 插值。但旋转持续整个移动过程（"边移动边旋转"），视觉上不自然——光标还没朝向移动方向就已经走到一半了。

**解决方案演进：**
1. `angle = last + diff * 0.15`（lerp 因子）→ 大角度差时首帧仍跳变明显
2. `angle = start_angle + diff * t_eased`（全时长插值）→ 旋转拖得太长，与移动同步不自然
3. **最终方案——wind-up 模式**：旋转集中在移动前 0.25s（`ROTATE_LEAD_DURATION`），用 cubic 缓动从起点角度旋转到初始切线方向。之后保持方向跟随路径：

```python
# 前 0.25s: wind-up 旋转
if frame <= rotate_lead_frames:
    angle = start_angle + diff * ease_in_out_cubic(rot_t)
# 之后: 直接跟随切线
else:
    angle = self._calc_tangent_angle(curve, t_raw)
```

---

## 8. Daemon 线程 UpdateWindow 不触发 idle wobble 重绘

**问题：** idle wobble 在 daemon 线程中运行，看似代码正确但光标完全不晃动。

**根因：** `set_angle()` 调用 `InvalidateRect` + `UpdateWindow` 来触发重绘。`UpdateWindow` 内部直接调用窗口过程 `_wnd_proc` → `_on_paint()` → `BeginPaint`。当 `UpdateWindow` 从 daemon 线程（非窗口创建线程）调用时，`BeginPaint` 的行为是未定义的——它可能静默失败，导致 HICON 已更新但画面不刷新。

**解决：** 放弃 WM_PAINT 路径，改用 `GetDC` + 直接 GDI 绘制。`GetDC`/`ReleaseDC` 在 Windows 文档中明确支持跨线程调用，不需要消息泵：

```python
def _paint_direct(self):
    """直接绘制到窗口 DC（不依赖消息泵，任何线程安全）"""
    dc = win32gui.GetDC(self.hwnd)
    try:
        win32gui.PatBlt(dc, 0, 0, self._size, self._size, win32con.BLACKNESS)
        if self.cursor_hicon:
            win32gui.DrawIconEx(dc, 0, 0, self.cursor_hicon,
                self._size, self._size, 0, None, win32con.DI_NORMAL)
    finally:
        win32gui.ReleaseDC(self.hwnd, dc)
```

| 对比 | InvalidateRect + UpdateWindow | GetDC + 直接绘制 |
|---|---|---|
| 绘制路径 | 投递 WM_PAINT → 窗口过程 → BeginPaint | 直接获取 DC → GDI 绘制 |
| 消息泵 | 依赖 | 不需要 |
| 跨线程 | UpdateWindow/BeginPaint 行为未定义 | GetDC/ReleaseDC 文档保证安全 |

---

## 9. 归位弧线漂移离开操作位置

**问题：** `_return_rotation` 每帧沿指向方向前进 3px，18 帧漂移约 54px。弧线结束时光标停在漂移位置，而实际操作（点击）在目标位置，光标显示与实际操作位置不一致。

**尝试：**
- 弧线结束后瞬跳回目标 → 54px 瞬移肉眼可见，不自然
- 弧线结束后 0.12s 缓动滑回目标 → 多了额外动画阶段

**最终解决——弹簧力约束弧线：** 每帧在前进的同时用弹簧力拉向目标，弧线始终围绕目标 ±10px 展开，动画结束时自然收束：

```python
# 每帧：前向+弹簧
x += ARC_STEP * cos(angle)      # 沿指向方向前进一步
y += ARC_STEP * sin(angle)
x += (target_x - x) * SPRING     # 弹簧拉回 30% 距离
y += (target_y - y) * SPRING     # 平衡距离 ≈ ARC_STEP / SPRING = 10px
```

弹簧系数 `SPRING = 0.3` 产生平衡距离 10px（3 / 0.3），弧线在这个范围内自然展开。动画结尾一行 `move_cursor(target)` 做精确收束（距离 < 2px）。

对比三种方案：

| | 方案 A（纯前向） | 方案 B（前向+滑回） | 方案 C（弹簧约束） |
|---|---|---|---|
| 弧线范围 | ~54px 漂移 | 漂移后滑回 | ±10px 围绕目标 |
| 额外阶段 | 需要滑回动画 | 需要滑回动画 | 无需 |
| 收束精度 | 需手动修正 | 需手动修正 | 天然收束 |

---

## 10. 动画架构演进总结

整个特效系统的三阶段动画流水线最终形态：

```
move_to 调用
  ├── Wind-up (0.25s): 集中旋转 + 前向弧线，漂移逐步汇入贝塞尔路径
  ├── Movement (剩余时长): 贝塞尔位移 + 切线方向跟随
  ├── 精确落点: set_angle + move_cursor 到目标
  ├── Return Rotation (0.3s): 归位旋转 + 弹簧约束弧线，围绕目标展开
  └── Idle Wobble (持续): daemon 线程，正弦波 ±12°，GetDC 直接绘制
```

关键设计决策：
- **Wind-up 而非全时长旋转**：旋转集中在前期，避免"边转边走"的不自然感
- **前向弧线而非原地振荡**：光标真正移动出弧线，而非围绕一个点绕圈
- **弹簧约束而非事后修正**：弧线天然收束，避免额外的滑回阶段
- **GetDC 直接绘制而非 WM_PAINT 路径**：使 idle wobble 在 daemon 线程可靠工作

---

## 总结

| # | 坑点 | 类别 | 根因一句话 |
|---|------|------|-----------|
| 1 | WndProc 回调失效 | Win32 API | 按实例注册窗口类 + 闭包捕获导致生命周期问题 |
| 2 | HICON 不可见 | Win32 API | CreateIconIndirect 不兼容 32bpp alpha 位图 |
| 3 | 黑块/图像叠加 | Win32 GDI | WM_ERASEBKGND 返回 1 跳过了背景清除 |
| 4 | 指向方向错误 | 坐标变换 | 设计假设的图片朝向与实际图片不符 |
| 5 | 旋转裁剪 | 图像处理/数学约束 | 24×24 对角 34px 恒 > 12px 半宽，任意画布 crop 回 24 必裁 5px；最终用 expand=True + 自然展开尺寸 |
| 6 | 角度跳变 | 数值计算 | ±180° 边界处插值走了远路 |
| 7 | 旋转瞬变 | 动画设计 | 全时长旋转"边转边走"不自然，改为 wind-up |
| 8 | idle wobble 不晃动 | Win32 GDI | daemon 线程 UpdateWindow→BeginPaint 行为未定义 |
| 9 | 弧线漂离操作位置 | 动画设计 | 纯前向步进累积漂移，需弹簧力约束 |
| 10 | 动画架构迭代 | 整体设计 | 四次演进：lerp→全时长→wind-up→弹簧弧线 |
