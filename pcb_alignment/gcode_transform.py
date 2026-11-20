"""Loss-conscious G-code transformation that preserves unrelated command text."""

from __future__ import annotations

import math
from pathlib import Path

from .alignment import rotate_point
from .gcode_parser import ParsedProgram, words_in_line, parse_gcode


class TransformError(ValueError):
    """Raised when a program cannot be exported without geometric risk."""


def _format_number(value: float) -> str:
    if abs(value) < 5e-10:
        value = 0.0
    rendered = f"{value:.9f}".rstrip("0").rstrip(".")
    return rendered if rendered not in {"", "-0"} else "0"


def default_output_name(input_path: str | Path) -> str:
    path = Path(input_path)
    suffix = path.suffix
    stem = path.stem
    if not stem.endswith("_rotated"):
        stem = f"{stem}_rotated"
    return f"{stem}{suffix}"


def validate_output_path(input_path: str | Path, output_path: str | Path) -> Path:
    """Reject output targets that would overwrite the source file."""
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    if source == target:
        raise TransformError("O arquivo original não pode ser sobrescrito.")
    return Path(output_path)


def _set_words(
    line: str,
    replacements: dict[int, tuple[int, str, str]],
    insertions: list[tuple[int, str]],
) -> str:
    edits = [
        (word_start, word_end, f"{letter}{value}")
        for word_start, (word_end, letter, value) in replacements.items()
    ]
    edits.extend((at, at, text) for at, text in insertions)
    for start, end, replacement in sorted(edits, reverse=True):
        line = line[:start] + replacement + line[end:]
    return line


def transform_gcode(parsed: ParsedProgram, angle_radians: float) -> str:
    """Rotate all supported XY moves after a successful safety analysis."""
    if not math.isfinite(angle_radians):
        raise TransformError("The rotation angle must be a finite number.")
    if parsed.blocking_issues:
        reasons = "; ".join(
            f"line {issue.line_number}: {issue.message}" for issue in parsed.blocking_issues[:6]
        )
        raise TransformError(f"The file cannot be transformed safely: {reasons}")

    output_lines: list[str] = []
    position = [0.0, 0.0]
    unit_scale = 1.0
    absolute = True
    modal_motion: int | None = None

    for line in parsed.lines:
        words = words_in_line(line)
        g_values = [round(word.value, 6) for word in words if word.letter == "G"]
        if 20.0 in g_values:
            unit_scale = 25.4
        if 21.0 in g_values:
            unit_scale = 1.0
        if 90.0 in g_values:
            absolute = True
        if 91.0 in g_values:
            absolute = False
        motion_values = sorted({int(code) for code in g_values if code in {0.0, 1.0, 2.0, 3.0}})
        if 80.0 in g_values:
            modal_motion = None
        if motion_values:
            modal_motion = motion_values[0]

        xy_words = {word.letter: word for word in words if word.letter in {"X", "Y"}}
        ij_words = {word.letter: word for word in words if word.letter in {"I", "J"}}
        has_geometry = bool(xy_words) or (modal_motion in {2, 3} and bool(ij_words))
        if modal_motion is None or not has_geometry:
            output_lines.append(line)
            continue

        start = (position[0], position[1])
        x_mm = xy_words["X"].value * unit_scale if "X" in xy_words else None
        y_mm = xy_words["Y"].value * unit_scale if "Y" in xy_words else None
        if absolute:
            end = (x_mm if x_mm is not None else start[0], y_mm if y_mm is not None else start[1])
        else:
            end = (start[0] + (x_mm or 0.0), start[1] + (y_mm or 0.0))

        if absolute and xy_words:
            new_vector = rotate_point(end[0], end[1], angle_radians)
        elif not absolute and xy_words:
            delta = (end[0] - start[0], end[1] - start[1])
            new_vector = rotate_point(delta[0], delta[1], angle_radians)
        else:
            new_vector = rotate_point(0.0, 0.0, angle_radians)

        replacements: dict[int, tuple[int, str, str]] = {}
        insertions: list[tuple[int, str]] = []
        if xy_words:
            coordinates = (
                ("X", new_vector[0] / unit_scale),
                ("Y", new_vector[1] / unit_scale),
            )
            for letter, value in coordinates:
                if letter in xy_words:
                    word = xy_words[letter]
                    replacements[word.start] = (word.end, letter, _format_number(value))
            missing = [letter for letter in ("X", "Y") if letter not in xy_words]
            if missing:
                last = max(xy_words.values(), key=lambda word: word.end)
                values = {letter: value for letter, value in coordinates}
                insertions.append((last.end, "".join(f" {letter}{_format_number(values[letter])}" for letter in missing)))

        if modal_motion in {2, 3} and ij_words:
            i_mm = ij_words["I"].value * unit_scale if "I" in ij_words else 0.0
            j_mm = ij_words["J"].value * unit_scale if "J" in ij_words else 0.0
            new_i, new_j = rotate_point(i_mm, j_mm, angle_radians)
            for letter, value in (("I", new_i / unit_scale), ("J", new_j / unit_scale)):
                if letter in ij_words:
                    word = ij_words[letter]
                    replacements[word.start] = (word.end, letter, _format_number(value))
            missing_centers = [letter for letter in ("I", "J") if letter not in ij_words]
            if missing_centers:
                last_center = max(ij_words.values(), key=lambda word: word.end)
                center_values = {"I": new_i / unit_scale, "J": new_j / unit_scale}
                insertions.append((last_center.end, "".join(
                    f" {letter}{_format_number(center_values[letter])}" for letter in missing_centers
                )))

        output_lines.append(_set_words(line, replacements, insertions))
        position[:] = end

    transformed = "".join(output_lines)
    verification = parse_gcode(transformed)
    if verification.blocking_issues:
        reasons = "; ".join(issue.message for issue in verification.blocking_issues[:3])
        raise TransformError(f"Transformed output failed validation: {reasons}")
    return transformed
