"""测试虚拟光标特效的数学函数"""
import math
from core.virtual_cursor import (
    VirtualCursor, BezierCurve,
    DEFAULT_ANGLE, IDLE_AMPLITUDE, IDLE_PERIOD
)


def test_tangent_angle_horizontal():
    """水平向右移动 -> 切线角度应为 0度"""
    curve = BezierCurve(0, 0, 33, 0, 66, 0, 100, 0)
    angle = VirtualCursor._calc_tangent_angle(curve, 0.5)
    assert abs(angle - 0) < 1, f"Expected ~0 degrees, got {angle}degrees"


def test_tangent_angle_vertical_up():
    """垂直向上移动 -> 切线角度应为 90度"""
    curve = BezierCurve(0, 100, 0, 66, 0, 33, 0, 0)
    angle = VirtualCursor._calc_tangent_angle(curve, 0.5)
    assert abs(angle - 90) < 1, f"Expected ~90 degrees, got {angle}degrees"


def test_tangent_angle_diagonal():
    """对角线右上移动 -> 切线角度应为 ~45度"""
    curve = BezierCurve(0, 100, 33, 66, 66, 33, 100, 0)
    angle = VirtualCursor._calc_tangent_angle(curve, 0.5)
    assert 40 < angle < 50, f"Expected ~45 degrees, got {angle}degrees"


def test_tangent_angle_at_start():
    """t=0 时应返回合理角度"""
    curve = BezierCurve(0, 0, 33, 20, 66, 20, 100, 0)
    angle = VirtualCursor._calc_tangent_angle(curve, 0.0)
    assert -90 <= angle <= 90, f"Expected reasonable angle, got {angle}degrees"


def test_idle_wobble_formula():
    """验证 idle wobble 公式在合理范围内"""
    elapsed = 0.25  # 四分之一周期
    angle = DEFAULT_ANGLE + IDLE_AMPLITUDE * math.sin(elapsed * 2 * math.pi / IDLE_PERIOD)
    # 1/4 周期时 sin(pi/2) = 1，角度应为 -45 + 6 = -39
    assert abs(angle - (-39.0)) < 0.1, f"Expected ~-39 degrees, got {angle}degrees"

    elapsed = 0.5  # 半周期
    angle = DEFAULT_ANGLE + IDLE_AMPLITUDE * math.sin(elapsed * 2 * math.pi / IDLE_PERIOD)
    # 半周期时 sin(pi) = 0，角度应为 -45
    assert abs(angle - DEFAULT_ANGLE) < 0.1, f"Expected ~{DEFAULT_ANGLE} degrees, got {angle}degrees"
