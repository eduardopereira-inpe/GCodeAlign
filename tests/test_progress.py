from pcb_alignment.gcode_parser import parse_gcode
from pcb_alignment.gcode_transform import transform_gcode


def test_parse_reports_progress() -> None:
    progress = []
    parsed = parse_gcode("G1 X1 Y1\n" * 1000, progress=lambda done, total: progress.append((done, total)))
    assert parsed.can_transform
    assert progress[0][0] == 1
    assert progress[-1] == (1000, 1000)
    assert len(progress) <= 101


def test_transform_reports_progress() -> None:
    parsed = parse_gcode("G1 X1 Y1\n" * 1000)
    progress = []
    transform_gcode(parsed, 0.0, progress=lambda done, total: progress.append((done, total)))
    assert progress[0][0] == 1
    assert progress[-1] == (1000, 1000)
    assert len(progress) <= 101
