"""Matplotlib trajectory viewer embedded in Tkinter."""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from .gcode_parser import ParsedProgram, arc_points


class GCodeViewer(ttk.Frame):
    """Display original and transformed tool paths with basic navigation."""

    def __init__(self, master: Any) -> None:
        super().__init__(master)
        self.figure = Figure(figsize=(7.2, 5.0), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        controls = ttk.Frame(self)
        controls.pack(fill="x")
        self.toolbar = NavigationToolbar2Tk(self.canvas, controls, pack_toolbar=False)
        self.toolbar.pack(side="left", fill="x", expand=True)
        ttk.Button(controls, text="Ajustar à vista", command=self.fit_to_view).pack(side="right")

        self._original: ParsedProgram | None = None
        self._transformed: ParsedProgram | None = None
        self._configure_axes()
        self.canvas.draw_idle()

    def _configure_axes(self) -> None:
        self.axes.clear()
        self.axes.axhline(0, color="#6b7280", linewidth=0.8)
        self.axes.axvline(0, color="#6b7280", linewidth=0.8)
        self.axes.scatter([0], [0], color="#111827", marker="+", s=80, label="Origem X0 Y0")
        self.axes.set_xlabel("X (mm)")
        self.axes.set_ylabel("Y (mm)")
        self.axes.set_aspect("equal", adjustable="datalim")
        self.axes.grid(True, linestyle=":", alpha=0.55)
        self.axes.set_title("Trajetória G-code")

    def set_programs(
        self, original: ParsedProgram | None, transformed: ParsedProgram | None = None
    ) -> None:
        self._original = original
        self._transformed = transformed
        self.redraw()

    def set_transformed(self, transformed: ParsedProgram | None) -> None:
        self._transformed = transformed
        self.redraw()

    def redraw(self) -> None:
        self._configure_axes()
        if self._original is not None:
            self._plot_program(self._original, transformed=False)
        if self._transformed is not None:
            self._plot_program(self._transformed, transformed=True)
        handles, labels = self.axes.get_legend_handles_labels()
        if handles:
            self.axes.legend(loc="best", fontsize="small")
        self.fit_to_view()

    def _plot_program(self, program: ParsedProgram, transformed: bool) -> None:
        labels_used: set[str] = set()
        source = "Transformado" if transformed else "Original"
        styles = {
            0: ("#94a3b8" if not transformed else "#c4b5fd", "--"),
            1: ("#2563eb" if not transformed else "#dc2626", "-"),
            2: ("#059669" if not transformed else "#ea580c", "-"),
            3: ("#059669" if not transformed else "#ea580c", "-"),
        }
        names = {0: "G0 rápido", 1: "G1 usinagem", 2: "G2/G3 arco"}
        for motion in program.motions:
            points = arc_points(motion) if motion.kind in {2, 3} else [motion.start, motion.end]
            xs, ys = zip(*points)
            color, linestyle = styles[motion.kind]
            name = f"{source} — {names.get(motion.kind, names[2])}"
            label = name if name not in labels_used else "_nolegend_"
            self.axes.plot(xs, ys, color=color, linestyle=linestyle, linewidth=1.7, label=label)
            labels_used.add(name)

    def fit_to_view(self) -> None:
        self.axes.relim(visible_only=True)
        self.axes.autoscale_view()
        self.canvas.draw_idle()
