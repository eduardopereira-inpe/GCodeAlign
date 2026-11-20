import math
from pathlib import Path

from pcb_alignment.background import TaskMessage
from pcb_alignment.jobs import load_gcode, transform_program
from pcb_alignment.trajectory import prepare_trajectory


def build_large_gcode(count: int = 50_000) -> str:
    lines = ["G21", "G90", "G0 X0 Y0", "G1 F100"]
    lines.extend(f"X{index % 500} Y{index % 317}" for index in range(count))
    return "\n".join(lines) + "\n"


def test_large_file_processing_preserves_all_motions(tmp_path: Path) -> None:
    path = tmp_path / "large.gcode"
    path.write_text(build_large_gcode(), encoding="utf-8")
    progress: list[tuple[str, float | None]] = []
    loaded = load_gcode(path, lambda status, value: progress.append((status, value)))

    assert loaded.parsed.can_transform
    assert len(loaded.parsed.motions) == 50_001
    assert len(loaded.trajectory.series) == 2
    assert progress[-1] == ("Leitura concluída", 1.0)


def test_large_transform_and_aggregated_plot_data() -> None:
    from pcb_alignment.gcode_parser import parse_gcode

    parsed = parse_gcode(build_large_gcode(25_000))
    transformed = transform_program(parsed, math.radians(-1), 100.0, 1.0, lambda *_: None)
    trajectory = transformed.trajectory

    assert len(transformed.parsed.motions) == 25_001
    assert sum(series.segment_count for series in trajectory.series.values()) == 25_001
    assert len(trajectory.series[1].x) == 3 * 25_000
    assert transformed.parsed.can_transform
