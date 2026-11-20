"""Unit-testable work units executed by the background task runner."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

from .background import StatusCallback
from .gcode_parser import ParsedProgram, parse_gcode
from .gcode_transform import transform_gcode, validate_output_path
from .trajectory import TrajectoryData, prepare_trajectory


@dataclass(frozen=True)
class LoadResult:
    path: Path
    parsed: ParsedProgram
    trajectory: TrajectoryData


@dataclass(frozen=True)
class TransformResult:
    angle: float
    measured_x: float
    measured_y: float
    text: str
    parsed: ParsedProgram
    trajectory: TrajectoryData


@dataclass(frozen=True)
class SaveResult:
    path: Path


def load_gcode(path: Path, report: StatusCallback) -> LoadResult:
    report("Carregando G-code", 0.05)
    text = path.read_text(encoding="utf-8-sig")
    report("Analisando trajetórias", 0.15)

    def parse_progress(completed: int, total: int) -> None:
        report("Analisando trajetórias", 0.15 + 0.60 * completed / max(total, 1))

    parsed = parse_gcode(text, progress=parse_progress)
    report("Preparando visualização", 0.78)
    trajectory = prepare_trajectory(
        parsed,
        progress=lambda completed, total: report(
            "Preparando visualização", 0.78 + 0.21 * completed / max(total, 1)
        ),
    )
    report("Leitura concluída", 1.0)
    return LoadResult(path, parsed, trajectory)


def transform_program(
    parsed: ParsedProgram,
    angle: float,
    measured_x: float,
    measured_y: float,
    report: StatusCallback,
) -> TransformResult:
    report("Aplicando transformação", 0.05)

    def transform_progress(completed: int, total: int) -> None:
        report("Aplicando transformação", 0.05 + 0.60 * completed / max(total, 1))

    text = transform_gcode(parsed, angle, progress=transform_progress)
    report("Validando G-code transformado", 0.68)
    transformed = parse_gcode(
        text,
        progress=lambda completed, total: report(
            "Validando G-code transformado", 0.68 + 0.14 * completed / max(total, 1)
        ),
    )
    report("Preparando visualização", 0.82)
    trajectory = prepare_trajectory(
        transformed,
        progress=lambda completed, total: report(
            "Preparando visualização", 0.82 + 0.17 * completed / max(total, 1)
        ),
    )
    report("Transformação concluída", 1.0)
    return TransformResult(angle, measured_x, measured_y, text, transformed, trajectory)


def save_gcode(
    source: Path, target: Path, text: str, report: StatusCallback
) -> SaveResult:
    target = validate_output_path(source, target)
    report("Validando arquivo de saída", 0.15)
    parsed = parse_gcode(text)
    if not parsed.can_transform:
        first = parsed.blocking_issues[0]
        raise ValueError(f"Saída inválida na linha {first.line_number}: {first.message}")

    report("Salvando G-code", 0.40)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, target)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
    report("Arquivo salvo", 1.0)
    return SaveResult(target)
