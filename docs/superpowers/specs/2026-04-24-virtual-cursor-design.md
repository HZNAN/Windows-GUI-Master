# Virtual Cursor Design — 2026-04-24

## Context

用户希望优化光标移动效果：
1. 光标移动不平滑 — 想要先加速后减速的动态效果，轨迹带随机弧度更像人类操作
2. 不想控制主控鼠标，而是生成一个与主控鼠标图案不同的虚拟光标

参考：Anthropic Codex / Computer Use 中的虚拟光标实现

---

## Design

### Architecture

```
drivers/input_control.py        # 保持不变，不调用 pyautogui.moveTo()
    ↓
core/execution_engine.py        # 新增 VirtualCursor 调度，移除 move_to 中的 pyautogui
    ↓
core/virtual_cursor.py          # 新模块：贝塞尔曲线生成 + 缓动动画
    ↓
drivers/win32_overlay.py        # 新模块：Windows 透明覆盖层 + 光标绘制
```

### 核心组件

#### 1. `core/virtual_cursor.py` — 曲线生成器 + 动画驱动器

- 输入：起点 `(x1, y1)`、终点 `(x2, y2)`、幅度扰动 `amplitude`
- 输出：一串 `(x, y)` 坐标点（60 个点/秒）
- 算法：
  1. 随机选取幅度 `amplitude = 15px`，扰动方向随机
  2. 计算控制点：`P1 = (x1 ± amplitude, y1)`, `P2 = (x2 ∓ amplitude, y2)`
  3. 三次贝塞尔曲线采样：`P(t) = (1-t)³P0 + 3(1-t)²tP1 + 3(1-t)t²P2 + t³P3`
  4. 每帧应用缓动函数：`ease_in_out_cubic(t)`
- 缓动函数（cubic ease in/out，1s 总时长）：
  ```python
  def ease_in_out_cubic(t):
      if t < 0.5:
          return 4 * t * t * t
      else:
          return 1 - (-2 * t + 2) ** 3 / 2
  ```
- 动画帧率：60fps，每帧从曲线采样点中取对应 t，经缓动函数计算实际位置

#### 2. `drivers/win32_overlay.py` — Windows 透明覆盖层

- 使用 `win32gui` 创建**最顶层透明窗口**（`CreateWindowEx` with `WS_EX_TRANSPARENT` + `WS_EX_LAYERED`）
- 窗口特性：
  - 全屏覆盖，不拦截鼠标事件（`SetWindowLong` 设置 `WS_EX_NOACTIVATE`）
  - 完全透明（通过 `SetLayeredWindowAttributes` 设置 `LWA_COLORKEY` 或 `LWA_ALPHA=0`）
- 光标绘制：
  - 使用 `PIL` 生成蓝白箭头图像（24×24px），存储在缓存中
  - 通过 `win32gui.DrawIconEx` 或 `win32api.BitBlt` 将图像绘制到覆盖层
  - 每帧移动光标时，调用 `SetWindowPos` 更新覆盖层位置
- 图像：白色实心箭头 + 蓝色模糊边缘（3px，`rgba(80, 150, 255, 128)`），无柄，尖部带弧度

#### 3. `core/execution_engine.py` — 修改

- `move_to` 中的 `self.input.move_to()` 改为调用 `VirtualCursor.move_to(x, y)`
- `click` 中的 `move_to` 也通过 `VirtualCursor` 执行动画
- 其他操作（type、press、scroll 等）不受影响

### 光标外观（蓝白箭头）

- 尺寸：24×24 px（略大于系统光标约 20×20）
- 形状：箭头，无柄，尖部带弧度
  - 中心：白色填充
  - 外围：蓝色模糊边缘，3px 宽度
- 用 PIL 的 `ImageDraw` 绘制自定义箭头形状

### 参数汇总

| 参数 | 值 |
|------|-----|
| 总时长 | 1s |
| 帧率 | 60fps |
| 曲线幅度 | 10-20px（随机 15px±5） |
| 缓动函数 | cubic ease in/out |
| 光标尺寸 | 24×24px |

---

## Files to Create

- `core/virtual_cursor.py` — 贝塞尔曲线 + 动画控制
- `drivers/win32_overlay.py` — Windows 透明覆盖层

---

## Files to Modify

- `core/execution_engine.py` — 替换 `move_to` 使用 VirtualCursor

---

## Notes

- 不修改 system prompt 和 agent 执行流程
- 测试由用户自行负责
- 覆盖层创建在首次移动时延迟初始化，避免启动时窗口闪烁