from pcb_alignment.gcode_parser import parse_gcode


def test_g80_cancels_modal_motion() -> None:
    parsed = parse_gcode("G90\nG1 X1 Y1\nG80\nX2 Y2\n")
    assert parsed.motions[-1].end == (1.0, 1.0)
    assert any(issue.code == "coordinate-without-motion" for issue in parsed.blocking_issues)


def test_special_state_changes_block_export_even_without_xy() -> None:
    parsed = parse_gcode("G1 X1 Y1\nG28\nG1 X2 Y2\n")
    assert not parsed.can_transform


def test_duplicate_xy_fields_are_rejected() -> None:
    parsed = parse_gcode("G1 X1 X2 Y3\n")
    assert any(issue.code == "duplicate-coordinate" for issue in parsed.blocking_issues)


def test_inconsistent_arc_radius_is_rejected() -> None:
    parsed = parse_gcode("G0 X1 Y0\nG2 X0 Y2 I-1 J0\n")
    assert any(issue.code == "inconsistent-arc-radius" for issue in parsed.blocking_issues)
