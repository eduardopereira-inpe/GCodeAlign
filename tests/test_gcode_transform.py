import math
from pathlib import Path

import pytest

from pcb_alignment.gcode_parser import parse_gcode
from pcb_alignment.gcode_transform import (
    TransformError,
    default_output_name,
    transform_gcode,
    validate_output_path,
)


def transform(source: str, angle: float = math.pi / 2) -> tuple[str, object]:
    original = parse_gcode(source)
    output = transform_gcode(original, angle)
    return output, parse_gcode(output)


def test_no_rotation_keeps_trajectory() -> None:
    source = "G21\nG90\nG0 X1 Y2\nG1 X4 Y8\n"
    output, parsed = transform(source, 0.0)
    assert [motion.end for motion in parsed.motions] == [ (1.0, 2.0), (4.0, 8.0) ]
    assert "G21\nG90\n" in output


def test_absolute_partial_coordinates_reconstruct_full_point() -> None:
    _, parsed = transform("G21\nG90\nG0 X0 Y2\nG1 X10\n")
    assert parsed.motions[1].end == pytest.approx((-2.0, 10.0))


def test_incremental_vectors_are_rotated_without_translation() -> None:
    _, parsed = transform("G21\nG91\nG0 X1 Y2\nG1 X1\n")
    assert parsed.motions[0].end == pytest.approx((-2.0, 1.0))
    assert parsed.motions[1].end == pytest.approx((-2.0, 2.0))


def test_z_feed_spindle_and_comments_are_preserved() -> None:
    source = "; header\nG90 G21\nM3 S10000\nG1 X10 Y5 Z-0.2 F120 (cut)\nM5 ; end\n"
    output, _ = transform(source)
    assert "; header" in output
    assert "M3 S10000" in output
    assert "Z-0.2" in output
    assert "F120 (cut)" in output
    assert "M5 ; end" in output


def test_arc_center_offsets_are_rotated_and_direction_is_preserved() -> None:
    source = "G21\nG90\nG0 X1 Y0\nG2 X0 Y1 I-1 J0\n"
    output, parsed = transform(source)
    arc = parsed.motions[1]
    assert "G2" in output
    assert arc.kind == 2
    assert arc.end == pytest.approx((-1.0, 0.0))
    assert arc.center == pytest.approx((0.0, 0.0))


def test_partial_arc_fields_are_completed_safely() -> None:
    output, parsed = transform("G90\nG0 X1 Y0\nG3 X0 Y1 I-1\n")
    assert "I0 J-1" in output
    assert parsed.motions[1].center == pytest.approx((0.0, 0.0))


def test_inch_units_are_preserved_while_internal_coordinates_are_mm() -> None:
    output, parsed = transform("G20\nG90\nG0 X1 Y2\nG1 X2\n", 0.0)
    assert "G20" in output
    assert parsed.motions[0].end == pytest.approx((25.4, 50.8))
    assert parsed.motions[1].end == pytest.approx((50.8, 50.8))


@pytest.mark.parametrize(
    "source, message",
    [
        ("G2 X1 Y1 R2\n", "R-format arcs"),
        ("G90.1\nG2 X1 Y1 I1 J0\n", "Absolute arc centers"),
        ("G92 X0 Y0\n", "G92 changes coordinate state"),
        ("G1 X\n", "missing its numeric value"),
        ("G81 X1 Y1 Z-2 R0\n", "Motion G81"),
    ],
)
def test_unsafe_programs_block_transformation(source: str, message: str) -> None:
    parsed = parse_gcode(source)
    assert any(message in issue.message for issue in parsed.blocking_issues)
    with pytest.raises(TransformError):
        transform_gcode(parsed, 0.0)


def test_output_name_is_rotated_once() -> None:
    assert default_output_name("board_top.gcode") == "board_top_rotated.gcode"
    assert default_output_name("board_top_rotated.nc") == "board_top_rotated.nc"


def test_output_cannot_equal_source(tmp_path: Path) -> None:
    source = tmp_path / "board.gcode"
    with pytest.raises(TransformError):
        validate_output_path(source, source)
    target = tmp_path / "board_rotated.gcode"
    assert validate_output_path(source, target) == target
