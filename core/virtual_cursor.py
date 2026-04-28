"""
虚拟光标动画引擎
使用贝塞尔曲线 + 缓动函数生成平滑的人类风格移动轨迹
"""
import ctypes
import random
import threading
import time
from typing import Callable, Optional

from loguru import logger

from drivers.win32_overlay import get_overlay

# 动画效果常量
DEFAULT_ANGLE = -135.0      # 光标默认指向（左上）
IDLE_AMPLITUDE = 12.0       # 静止晃动幅度（+-度）
IDLE_PERIOD = 1.2           # 静止晃动周期（秒）
IDLE_FPS = 30               # 静止晃动帧率
RETURN_DURATION = 0.3       # 归位旋转时长（秒）
ROTATE_LEAD_DURATION = 0.25 # 移动前旋转预备时长（秒）
ARC_STEP = 3.0              # 归位弧线每帧前进像素


class BezierCurve:
    """三次贝塞尔曲线"""

    def __init__(self, x0: float, y0: float, x1: float, y1: float,
                 x2: float, y2: float, x3: float, y3: float):
        self.x0, self.y0 = x0, y0
        self.x1, self.y1 = x1, y1
        self.x2, self.y2 = x2, y2
        self.x3, self.y3 = x3, y3

    def point_at(self, t: float) -> tuple[float, float]:
        """计算 t 时刻的坐标 (t ∈ [0, 1])"""
        u = 1 - t
        tt = t * t
        uu = u * u
        uuu = uu * u
        ttt = tt * t

        x = uuu * self.x0 + 3 * uu * t * self.x1 + 3 * u * tt * self.x2 + ttt * self.x3
        y = uuu * self.y0 + 3 * uu * t * self.y1 + 3 * u * tt * self.y2 + ttt * self.y3
        return x, y


def ease_in_out_cubic(t: float) -> float:
    """Cubic ease-in-out 缓动函数"""
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 1 - (-2 * t + 2) ** 3 / 2


class VirtualCursor:
    """
    虚拟光标控制器
    - 生成贝塞尔曲线路径
    - 执行缓动动画
    - 通过 Win32Overlay 绘制光标
    """

    def __init__(self, amplitude: int = None, duration: float = None, fps: int = None):
        from config.settings import VIRTUAL_CURSOR_AMPLITUDE, VIRTUAL_CURSOR_DURATION, VIRTUAL_CURSOR_FPS
        self.amplitude = amplitude if amplitude is not None else VIRTUAL_CURSOR_AMPLITUDE  # 曲线幅度扰动 (px)
        self.duration = duration if duration is not None else VIRTUAL_CURSOR_DURATION  # 总时长 (s)
        self.fps = fps if fps is not None else VIRTUAL_CURSOR_FPS
        self._overlay = None
        self._current_pos = (0, 0)
        self._running = False
        self._lock = threading.Lock()
        self._current_angle = DEFAULT_ANGLE
        self._idle_thread: Optional[threading.Thread] = None
        self._idle_running = False

    @property
    def overlay(self):
        if self._overlay is None or (hasattr(self._overlay, 'hwnd') and self._overlay.hwnd == 0):
            self._overlay = get_overlay()
        return self._overlay

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
        return -math.degrees(math.atan2(-dy, dx))

    def _generate_curve(self, x1: float, y1: float, x2: float, y2: float) -> BezierCurve:
        """
        生成贝塞尔曲线控制点
        起点 P0 -> 终点 P3，控制点 P1/P2 横向扰动 amplitude
        """
        # 随机扰动方向和幅度
        direction = random.choice([-1, 1])
        magnitude = random.uniform(self.amplitude * 0.7, self.amplitude * 1.3)

        # 控制点: P1 偏移起点，P2 偏移终点
        # 确保曲线平滑: P1 和 P2 在起点和终点之间
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2

        # 法向量方向扰动
        dx = x2 - x1
        dy = y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1:
            length = 1

        # 垂直方向扰动 (产生弧线效果)
        nx = -dy / length * magnitude * direction
        ny = dx / length * magnitude * direction

        # 控制点 P1: 起点侧，带扰动
        p1x = x1 + dx * 0.33 + nx
        p1y = y1 + dy * 0.33 + ny

        # 控制点 P2: 终点侧，带扰动
        p2x = x2 - dx * 0.33 + nx
        p2y = y2 - dy * 0.33 + ny

        return BezierCurve(x1, y1, p1x, p1y, p2x, p2y, x2, y2)

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

        import math
        start_angle = self._current_angle
        rotate_lead_frames = int(ROTATE_LEAD_DURATION * self.fps)
        init_tangent = None  # 首帧延迟计算（避开 t=0 切线不稳定）
        drift_x, drift_y = float(start_x), float(start_y)  # 漂移累积位置

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

            # 旋转：集中在移动前期（wind-up），之后跟随切线
            if frame <= rotate_lead_frames and rotate_lead_frames > 0:
                if init_tangent is None:
                    init_tangent = self._calc_tangent_angle(curve, 0.02)
                rot_t = frame / rotate_lead_frames
                diff = init_tangent - start_angle
                if diff > 180: diff -= 360
                elif diff < -180: diff += 360
                angle = start_angle + diff * ease_in_out_cubic(rot_t)
            else:
                angle = self._calc_tangent_angle(curve, t_raw)

            self._current_angle = angle

            # 圆弧：wind-up 期间顺指向前进，逐步汇入贝塞尔路径
            if frame <= rotate_lead_frames and rotate_lead_frames > 0:
                rot_t = frame / rotate_lead_frames
                # 沿当前指向前进一步（累积漂移）
                rad = math.radians(angle)
                drift_x += ARC_STEP * math.cos(rad)
                drift_y += ARC_STEP * math.sin(rad)
                # 随 wind-up 推进，从漂移路径汇入贝塞尔路径
                arc_x = int(final_x * rot_t + drift_x * (1 - rot_t))
                arc_y = int(final_y * rot_t + drift_y * (1 - rot_t))
            else:
                arc_x, arc_y = final_x, final_y
            drift_x, drift_y = float(arc_x), float(arc_y)

            self._current_pos = (arc_x, arc_y)
            start_time = time.perf_counter()

            self.overlay.set_angle(angle)
            self.overlay.move_cursor(arc_x, arc_y)

            elapsed = time.perf_counter() - start_time
            remaining = frame_duration - elapsed
            if remaining > 0:
                time.sleep(remaining)

        final_angle = self._current_angle

        self._running = False
        self._current_pos = (x, y)
        self.overlay.set_angle(final_angle)
        self.overlay.move_cursor(x, y)

        # 归位旋转（弧线始终围绕目标，弹簧力收束回原位）
        self._return_rotation(final_angle, target_x=x, target_y=y)
        self._start_idle_animation()

        if callback:
            callback()

    def _return_rotation(self, from_angle: float, target_x: int = 0, target_y: int = 0):
        """从当前角度平滑旋转回默认角度。
        每帧沿指向方向前进一小步，同时弹簧力拉向目标位置，
        弧线围绕目标展开，动画结束时自然收束回目标。"""
        import math
        total_frames = int(RETURN_DURATION * self.fps)
        if total_frames < 1:
            total_frames = 1
        frame_duration = 1.0 / self.fps
        x, y = float(target_x), float(target_y)
        SPRING = 0.3  # 弹簧系数：每帧拉回 30% 距离

        for frame in range(total_frames + 1):
            t_raw = frame / total_frames
            t_eased = ease_in_out_cubic(t_raw)
            angle = from_angle + (DEFAULT_ANGLE - from_angle) * t_eased

            # 沿指向方向前进一步
            rad = math.radians(angle)
            x += ARC_STEP * math.cos(rad)
            y += ARC_STEP * math.sin(rad)

            # 弹簧力拉回目标：产生围绕目标的弧线，结束时收束
            x += (target_x - x) * SPRING
            y += (target_y - y) * SPRING

            self._current_angle = angle
            self._current_pos = (int(x), int(y))
            self.overlay.set_angle(angle)

            start_time = time.perf_counter()
            self.overlay.move_cursor(int(x), int(y))
            elapsed = time.perf_counter() - start_time
            remaining = frame_duration - elapsed
            if remaining > 0:
                time.sleep(remaining)

        # 精确收束到目标位置
        self.overlay.move_cursor(target_x, target_y)
        self._current_pos = (target_x, target_y)

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

    def set_position(self, x: int, y: int):
        """直接设置光标位置（无动画），之后启动 idle 晃动"""
        self._stop_idle_animation()
        self._current_pos = (x, y)
        self.overlay.show()
        self.overlay.set_angle(DEFAULT_ANGLE)
        self.overlay.move_cursor(x, y)
        self._start_idle_animation()

    def hide(self):
        """隐藏虚拟光标"""
        self._stop_idle_animation()
        self.overlay.hide()

    def get_position(self) -> tuple[int, int]:
        """获取当前光标位置"""
        return self._current_pos

    def stop(self):
        """立即停止当前动画和 idle 晃动"""
        self._running = False
        self._stop_idle_animation()
        time.sleep(0.1)

    def _pump_messages(self):
        """处理 Windows 消息（非阻塞）"""
        import ctypes
        from ctypes import windll, byref

        PM_REMOVE = 0x0001
        msg = ctypes.wintypes.MSG()
        while windll.user32.PeekMessageW(byref(msg), None, 0, 0, PM_REMOVE):
            if msg.message == 0x0100 or msg.message == 0x0101:  # WM_KEYDOWN/WM_KEYUP
                windll.user32.TranslateMessage(byref(msg))
            windll.user32.DispatchMessageW(byref(msg))


# 全局单例
_virtual_cursor: Optional[VirtualCursor] = None
_cursor_lock = threading.Lock()


def get_virtual_cursor() -> VirtualCursor:
    """获取全局虚拟光标实例"""
    global _virtual_cursor
    with _cursor_lock:
        if _virtual_cursor is None:
            from config.settings import VIRTUAL_CURSOR_AMPLITUDE, VIRTUAL_CURSOR_DURATION, VIRTUAL_CURSOR_FPS
            _virtual_cursor = VirtualCursor(
                amplitude=VIRTUAL_CURSOR_AMPLITUDE,
                duration=VIRTUAL_CURSOR_DURATION,
                fps=VIRTUAL_CURSOR_FPS
            )
        return _virtual_cursor