"""A conservative parser and trajectory interpreter for common FlatCAM G-code."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Callable


_WORD_RE = re.compile(
    r"([A-Za-z])\s*([+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[Ee][+-]?\d+)?)"
)
_INCOMPLETE_GEOMETRY_RE = re.compile(r"([XYIJ])\s*(?=$|[A-Za-z])", re.IGNORECASE)
_SUPPORTED_MOTIONS = {0, 1, 2, 3}
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class Word:
    letter: str
    value: float
    raw: str
    start: int
    end: int


@dataclass(frozen=True)
class Issue:
    line_number: int
    code: str
    message: str
    blocking: bool = True


@dataclass(frozen=True)
class Motion:
    kind: int
    start: tuple[float, float]
    end: tuple[float, float]
    line_number: int
    center: tuple[float, float] | None = None


@dataclass(frozen=True)
class ParsedProgram:
    text: str
    motions: tuple[Motion, ...]
    issues: tuple[Issue, ...]
    lines: tuple[str, ...]

    @property
    def blocking_issues(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.blocking)

    @property
    def can_transform(self) -> bool:
        return not self.blocking_issues


def _active_code(line: str) -> str:
    """Return a line with comments replaced by spaces, retaining positions."""
    chars = list(line)
    depth = 0
    semicolon = False
    for index, char in enumerate(chars):
        if semicolon:
            chars[index] = " "
        elif char == ";" and depth == 0:
            semicolon = True
            chars[index] = " "
        elif char == "(":
            depth += 1
            chars[index] = " "
        elif char == ")" and depth:
            chars[index] = " "
            depth -= 1
        elif depth:
            chars[index] = " "
    return "".join(chars)


def words_in_line(line: str) -> tuple[Word, ...]:
    code = _active_code(line)
    return tuple(
        Word(match.group(1).upper(), float(match.group(2)), match.group(0), match.start(), match.end())
        for match in _WORD_RE.finditer(code)
    )


def _code_number(word: Word) -> float:
    return round(word.value, 6)


def _words_by_letter(words: tuple[Word, ...], letter: str) -> list[Word]:
    return [word for word in words if word.letter == letter]


def _one_word_value(words: tuple[Word, ...], letter: str) -> float | None:
    matches = _words_by_letter(words, letter)
    return matches[-1].value if matches else None


def parse_gcode(
    text: str, progress: ProgressCallback | None = None
) -> ParsedProgram:
    """Parse motions and identify constructs that cannot be safely transformed."""
    if not text.strip():
        raise ValueError("The G-code file is empty.")

    lines = tuple(text.splitlines(keepends=True))
    if not lines and text:
        lines = (text,)

    position = [0.0, 0.0]
    unit_scale = 1.0
    absolute = True
    arc_center_absolute = False
    modal_motion: int | None = None
    plane = 17
    motions: list[Motion] = []
    issues: list[Issue] = []
    saw_motion = False
    total_lines = len(lines)
    progress_interval = max(1, total_lines // 100)

    for line_number, line in enumerate(lines, start=1):
        if progress is not None and (
            line_number == 1 or line_number == total_lines or line_number % progress_interval == 0
        ):
            progress(line_number, total_lines)
        words = words_in_line(line)
        g_values = [_code_number(word) for word in words if word.letter == "G"]
        active_code = _active_code(line)
        parsed_spans = [(word.start, word.end) for word in words]
        leftover_code = list(active_code)
        for start, end in parsed_spans:
            leftover_code[start:end] = [" "] * (end - start)
        if _INCOMPLETE_GEOMETRY_RE.search("".join(leftover_code)):
            issues.append(Issue(line_number, "invalid-coordinate", "A geometry field is missing its numeric value."))
        for letter in ("X", "Y", "I", "J", "R"):
            if len(_words_by_letter(words, letter)) > 1:
                issues.append(Issue(line_number, "duplicate-coordinate", f"Coordinate {letter} appears more than once in a block."))

        state_changing_codes = [code for code in (10, 28, 30, 53, 92) if code in g_values]
        if state_changing_codes:
            issues.append(Issue(
                line_number,
                "coordinate-state",
                f"G{state_changing_codes[0]} changes coordinate state and cannot be transformed safely.",
            ))
        if any(code in {18, 19} for code in g_values):
            plane = int(next(code for code in g_values if code in {18, 19}))
            issues.append(Issue(line_number, "unsupported-plane", "Only the XY plane (G17) is supported."))
        if 17 in g_values:
            plane = 17
        if 90.1 in g_values:
            arc_center_absolute = True
            issues.append(Issue(line_number, "absolute-arc-center", "Absolute arc centers (G90.1) are not supported."))
        if 91.1 in g_values:
            arc_center_absolute = False

        g90 = 90.0 in g_values
        g91 = 91.0 in g_values
        if g90 and g91:
            issues.append(Issue(line_number, "conflicting-distance-mode", "A block cannot contain both G90 and G91."))
        elif g90:
            absolute = True
        elif g91:
            absolute = False

        g20 = 20.0 in g_values
        g21 = 21.0 in g_values
        if g20 and g21:
            issues.append(Issue(line_number, "conflicting-units", "A block cannot contain both G20 and G21."))
        elif g20:
            unit_scale = 25.4
        elif g21:
            unit_scale = 1.0

        explicit_motion_codes = sorted({int(code) for code in g_values if code in _SUPPORTED_MOTIONS})
        unsupported_motion_codes = sorted({
            code for code in g_values
            if (
                code in {4, 5, 5.1, 33, 33.1, 73, 76, 80}
                or 38 <= code < 39
                or 81 <= code <= 89
            )
        })
        if 80 in g_values:
            modal_motion = None
        if len(explicit_motion_codes) > 1:
            issues.append(Issue(line_number, "multiple-motion-codes", "A block contains multiple motion commands."))
        elif explicit_motion_codes:
            modal_motion = explicit_motion_codes[0]

        has_xy = any(word.letter in {"X", "Y"} for word in words)
        has_ij = any(word.letter in {"I", "J"} for word in words)
        has_r = any(word.letter == "R" for word in words)
        unsupported_with_geometry = unsupported_motion_codes and (has_xy or has_ij or has_r)
        if unsupported_with_geometry:
            issues.append(
                Issue(
                    line_number,
                    "unsupported-motion",
                    f"Motion G{unsupported_motion_codes[0]} cannot be transformed safely.",
                )
            )

        motion = modal_motion if not unsupported_with_geometry else None
        if motion is None and (has_xy or has_ij or has_r):
            issues.append(Issue(line_number, "coordinate-without-motion", "Geometry fields are present without a supported modal motion."))
        if motion is None or not (has_xy or (motion in {2, 3} and has_ij)):
            continue

        start = (position[0], position[1])
        x_word = _one_word_value(words, "X")
        y_word = _one_word_value(words, "Y")
        if absolute:
            end = (
                x_word * unit_scale if x_word is not None else start[0],
                y_word * unit_scale if y_word is not None else start[1],
            )
        else:
            end = (
                start[0] + (x_word * unit_scale if x_word is not None else 0.0),
                start[1] + (y_word * unit_scale if y_word is not None else 0.0),
            )

        center: tuple[float, float] | None = None
        if motion in {2, 3}:
            if plane != 17:
                issues.append(Issue(line_number, "arc-plane", "Arcs can only be interpreted in the G17 XY plane."))
            if has_r:
                issues.append(Issue(line_number, "radius-arc", "R-format arcs are blocked; I/J arcs are required for safe rotation."))
            i_value = _one_word_value(words, "I")
            j_value = _one_word_value(words, "J")
            if i_value is None and j_value is None:
                issues.append(Issue(line_number, "arc-center-missing", "An arc requires at least one I/J center offset."))
            elif arc_center_absolute:
                center = ((i_value or 0.0) * unit_scale, (j_value or 0.0) * unit_scale)
            else:
                center = (start[0] + (i_value or 0.0) * unit_scale, start[1] + (j_value or 0.0) * unit_scale)
            if center is not None:
                start_radius = math.hypot(start[0] - center[0], start[1] - center[1])
                end_radius = math.hypot(end[0] - center[0], end[1] - center[1])
                tolerance = max(1e-5, start_radius * 1e-4)
                if start_radius <= 1e-12:
                    issues.append(Issue(line_number, "zero-radius-arc", "The arc has a zero radius."))
                elif abs(start_radius - end_radius) > tolerance and not (end == start):
                    issues.append(Issue(line_number, "inconsistent-arc-radius", "Arc start and end radii do not match within tolerance."))
        elif has_ij:
            issues.append(Issue(line_number, "center-outside-arc", "I/J center offsets are only valid in G2/G3 blocks."))

        motions.append(Motion(motion, start, end, line_number, center))
        position[:] = end
        saw_motion = True

    if not saw_motion:
        issues.append(Issue(1, "no-movements", "No supported XY movements were found."))

    deduplicated: list[Issue] = []
    seen: set[tuple[int, str]] = set()
    for issue in issues:
        marker = (issue.line_number, issue.code)
        if marker not in seen:
            seen.add(marker)
            deduplicated.append(issue)
    return ParsedProgram(text, tuple(motions), tuple(deduplicated), lines)


def arc_points(motion: Motion, samples: int = 48) -> list[tuple[float, float]]:
    """Sample an I/J arc for plotting without altering its G-code semantics."""
    if motion.kind not in {2, 3} or motion.center is None:
        return [motion.start, motion.end]
    cx, cy = motion.center
    radius = math.hypot(motion.start[0] - cx, motion.start[1] - cy)
    start_angle = math.atan2(motion.start[1] - cy, motion.start[0] - cx)
    end_angle = math.atan2(motion.end[1] - cy, motion.end[0] - cx)
    if motion.kind == 2:
        sweep = (end_angle - start_angle) % (2.0 * math.pi)
        if sweep <= 1e-12:
            sweep = 2.0 * math.pi
        sweep = -sweep
    else:
        sweep = (end_angle - start_angle) % (2.0 * math.pi)
        if sweep <= 1e-12:
            sweep = 2.0 * math.pi
    count = max(2, int(samples * abs(sweep) / (2.0 * math.pi)))
    return [
        (cx + radius * math.cos(start_angle + sweep * step / count), cy + radius * math.sin(start_angle + sweep * step / count))
        for step in range(count + 1)
    ]
