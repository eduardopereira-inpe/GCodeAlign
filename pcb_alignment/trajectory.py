"""Memory-efficient, Matplotlib-independent preparation of trajectory arrays."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
from typing import Callable

from .gcode_parser import ParsedProgram, arc_points


@dataclass(frozen=True)
class PlotSeries:
    x: array
    y: array
    segment_count: int


@dataclass(frozen=True)
class TrajectoryData:
    series: dict[int, PlotSeries]
    motion_count: int
    extent: tuple[float, float, float, float] | None


def prepare_trajectory(
    program: ParsedProgram,
    progress: Callable[[int, int], None] | None = None,
) -> TrajectoryData:
    """Aggregate many motions into three line series separated by NaN values."""
    series_buffers: dict[int, tuple[array, array, int]] = {}
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    counts = {0: 0, 1: 0, 2: 0}
    total = len(program.motions)
    progress_interval = max(1, total // 100)

    for index, motion in enumerate(program.motions, start=1):
        if progress is not None and (
            index == 1 or index == total or index % progress_interval == 0
        ):
            progress(index, total)
        group = 2 if motion.kind in {2, 3} else motion.kind
        if group not in counts:
            continue
        if group not in series_buffers:
            series_buffers[group] = (array("d"), array("d"), 0)
        xs, ys, segments = series_buffers[group]
        points = arc_points(motion) if motion.kind in {2, 3} else (motion.start, motion.end)
        for x, y in points:
            xs.append(x)
            ys.append(y)
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
        xs.append(math.nan)
        ys.append(math.nan)
        counts[group] += 1
        series_buffers[group] = (xs, ys, segments + 1)

    series = {
        group: PlotSeries(xs, ys, count)
        for group, (xs, ys, count) in series_buffers.items()
        if count
    }
    extent = None if not series else (min_x, max_x, min_y, max_y)
    return TrajectoryData(series, len(program.motions), extent)
