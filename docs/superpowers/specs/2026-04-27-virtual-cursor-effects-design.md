# Virtual Cursor Dynamic Effects Design

## Overview

给虚拟光标添加三种动态特效：静止晃动、移动旋转、归位旋转。

## Current State

- 光标以固定角度（-45°，左上指向）渲染
- 使用 `DrawIconEx` 绘制 HICON，不支持旋转
- `move_to()` 做贝塞尔曲线 + 缓动位移动画，无角度变化

## Design

### HICON 角度缓存池

新增 `Win32Overlay._build_angle_cache(cursor_type)`：

1. 保留原始 PIL Image（`_source_image`），不销毁
2. 对 0°~357° 每 3° 一个角度（共 120 个），PIL 旋转后通过 `CreateDIBSection` + `CreateIconIndirect` 生成 HICON
3. 存入 `_angle_cache: dict[int, int]`，key=度数，value=HICON handle
4. 切换 cursor_type 时重建缓存

新增 `Win32Overlay.set_angle(angle: float)`：

1. `round(angle / 3) * 3` 取最近缓存角度
2. 更新 `self.cursor_hicons[cursor_type]`
3. `InvalidateRect` 触发重绘

新增 `Win32Overlay._current_angle: float` 记录当前角度。

### 三状态动画机

VirtualCursor 新增三个状态：

```
IDLE ──move_to()调用──► MOVING ──move_to()结束──► RETURNING ──归位完成──► IDLE
```

#### MOVING（改造 move_to）

每帧额外计算旋转角度：

1. 从贝塞尔曲线取当前点 `p(t)` 和下一个微步点 `p(t + 0.01)`
2. `atan2(dy, dx)` 得到切线方向角度（弧度转度数）
3. 调用 `overlay.set_angle(angle)` 更新光标朝向

#### RETURNING（新增）

`_return_rotation(from_angle: float)`：

- 帧率 60fps，总时长 0.3s
- 用 `ease_in_out_cubic` 从 `from_angle` 插值到 `-45.0`
- 完成后启动 IDLE

#### IDLE（新增）

`_idle_loop()` 后台线程：

- 正弦波：`angle = -45 + 6 * sin(time * 2π / 1.0)`
- 帧率 30fps
- 通过 `_idle_running` 标志控制启停
- `move_to()` 开始时调用 `_stop_idle_animation()`，阻止重叠

### 线程安全

- `_lock`（已有）保护 `_running` 和角度变更
- `_idle_running` 原子标志，`move_to()` 开始时置 False
- Idle 线程在 `_idle_running=False` 时退出循环

## Parameters

| 参数 | 值 | 说明 |
|------|-----|------|
| 晃动幅度 | ±6° | 正弦波振幅 |
| 晃动周期 | 1.0s | 正弦波周期 |
| 晃动帧率 | 30fps | idle 重绘频率 |
| 归位时长 | 0.3s | 缓动归位总时间 |
| 归位缓动 | ease_in_out_cubic | 缓动函数 |
| 缓存精度 | 3° | HICON 角度间隔 |
| 默认角度 | -45° | 光标默认指向 |

## Files Changed

- `drivers/win32_overlay.py` — 新增 HICON 角度缓存池、`set_angle()`、`_source_image`
- `core/virtual_cursor.py` — 三状态动画机、切线角度计算、idle 线程、归位动画

## Risks

- Idle 线程在 Windows 消息循环中的稳定性（需处理 WM_PAINT 同步）
- HICON 缓存生成 (~50ms) 会阻塞首帧，但只在 switch cursor_type 时触发
