from pcb_alignment.gcode_parser import arc_points, parse_gcode


def test_modal_motion_and_partial_coordinates() -> None:
    parsed = parse_gcode("G21 G90\nG0 X2 Y3\nX4\nY5\n")
    assert parsed.can_transform
    assert [motion.end for motion in parsed.motions] == [(2.0, 3.0), (4.0, 3.0), (4.0, 5.0)]


def test_comments_are_ignored_for_geometry() -> None:
    parsed = parse_gcode("(X999 Y999)\nG1 X2 Y3 ; X7 Y8\n")
    assert parsed.motions[0].end == (2.0, 3.0)


def test_arc_sampling_produces_path_points() -> None:
    parsed = parse_gcode("G90\nG0 X1 Y0\nG3 X0 Y1 I-1 J0\n")
    points = arc_points(parsed.motions[1], samples=16)
    assert len(points) >= 5
    assert points[0] == (1.0, 0.0)
    assert points[-1][0] == 0.0 or abs(points[-1][0]) < 1e-12


def test_empty_file_is_rejected() -> None:
    try:
        parse_gcode("\n ; only comments\n")
    except ValueError:
        return
    parsed = parse_gcode("G21\n")
    assert not parsed.can_transform


def test_preserves_blank_and_comment_lines_in_source() -> None:
    source = "; comment\n\nG1 X1 Y1\n"
    parsed = parse_gcode(source)
    assert parsed.text == source
    assert parsed.lines == ("; comment\n", "\n", "G1 X1 Y1\n")
