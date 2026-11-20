import math

import pytest

from pcb_alignment.alignment import AlignmentError, calculate_correction_angle, rotate_point


def test_origin_is_invariant() -> None:
    assert rotate_point(0.0, 0.0, math.pi / 3) == pytest.approx((0.0, 0.0))


def test_x_axis_no_rotation() -> None:
    angle = calculate_correction_angle(25.0, 0.0, "X")
    assert math.degrees(angle) == pytest.approx(0.0)
    assert rotate_point(12.0, 0.0, angle) == pytest.approx((12.0, 0.0))


def test_x_axis_positive_deviation_is_corrected() -> None:
    angle = calculate_correction_angle(10.0, 1.0, "X")
    x, y = rotate_point(10.0, 1.0, angle)
    assert math.degrees(angle) < 0
    assert x == pytest.approx(math.hypot(10.0, 1.0))
    assert y == pytest.approx(0.0, abs=1e-12)


def test_x_axis_negative_deviation_is_corrected() -> None:
    angle = calculate_correction_angle(10.0, -1.0, "X")
    x, y = rotate_point(10.0, -1.0, angle)
    assert math.degrees(angle) > 0
    assert x == pytest.approx(math.hypot(10.0, 1.0))
    assert y == pytest.approx(0.0, abs=1e-12)


def test_y_axis_is_aligned_to_positive_y() -> None:
    angle = calculate_correction_angle(1.0, 10.0, "Y")
    x, y = rotate_point(1.0, 10.0, angle)
    assert math.degrees(angle) > 0
    assert x == pytest.approx(0.0, abs=1e-12)
    assert y == pytest.approx(math.hypot(1.0, 10.0))


def test_quadrants_are_handled_with_atan2() -> None:
    assert math.degrees(calculate_correction_angle(-10.0, 0.0, "X")) == pytest.approx(-180.0)
    assert math.degrees(calculate_correction_angle(1.0, -1.0, "Y")) == pytest.approx(135.0)


@pytest.mark.parametrize("x,y", [(0.0, 0.0), (math.inf, 1.0), (1.0, math.nan)])
def test_invalid_reference_point_is_rejected(x: float, y: float) -> None:
    with pytest.raises(AlignmentError):
        calculate_correction_angle(x, y, "X")
