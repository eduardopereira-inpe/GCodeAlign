"""Geometry for alignment around the fixed PCB origin."""

from __future__ import annotations

import math
from typing import Literal

ReferenceAxis = Literal["X", "Y"]


class AlignmentError(ValueError):
    """Raised when an alignment cannot be calculated safely."""


def calculate_correction_angle(
    measured_x: float, measured_y: float, axis: ReferenceAxis
) -> float:
    """Return the correction angle in radians for the selected nominal axis."""
    x = float(measured_x)
    y = float(measured_y)
    if not math.isfinite(x) or not math.isfinite(y):
        raise AlignmentError("Coordinates must be finite numbers.")
    if math.hypot(x, y) <= 1e-12:
        raise AlignmentError("The measured reference point cannot be at the origin.")

    if axis == "X":
        return -math.atan2(y, x)
    if axis == "Y":
        return -math.atan2(-x, y)
    raise AlignmentError("The reference axis must be X or Y.")


def rotate_point(x: float, y: float, angle_radians: float) -> tuple[float, float]:
    """Rotate a point around (0, 0)."""
    cosine = math.cos(angle_radians)
    sine = math.sin(angle_radians)
    rotated_x = x * cosine - y * sine
    rotated_y = x * sine + y * cosine
    if abs(rotated_x) < 1e-12:
        rotated_x = 0.0
    if abs(rotated_y) < 1e-12:
        rotated_y = 0.0
    return rotated_x, rotated_y


def degrees(angle_radians: float) -> float:
    """Convert radians to degrees for display."""
    return math.degrees(angle_radians)
