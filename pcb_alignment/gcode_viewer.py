"""Matplotlib trajectory viewer embedded in Tkinter."""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from .gcode_parser import ParsedProgram
from .trajectory import TrajectoryData, prepare_trajectory


class GCodeViewer(ttk.Frame):
    """Render aggregated paths with a bounded number of Matplotlib artists."""

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

        self._original: TrajectoryData | None = None
        self._transformed: TrajectoryData | None = None
        self._configure_axes()
        self.canvas.draw_idle()

    def _configure_axes(self) -> None:
        self.axes.clear()
        self.axes.axhline(0, color="#6b7280", linewidth=0.8)
        self.axes.axvline(0, color="#6b7280", linewidth=0.8)
        self.axes.scatter([0], [0], color="#111827", marker="+", s=80, label="Origem X0 Y0")
        self.axes.set_xlabel("X (mm)")
        self.axes.set_ylabel("Y (mm)")
        self.axes.set_aspect("equal", adjustable="box")
        self.axes.grid(True, linestyle=":", alpha=0.55)
        self.axes.set_title("Trajetória G-code")

    def set_programs(
        self, original: ParsedProgram | None, transformed: ParsedProgram | None = None
    ) -> None:
        """Convenience synchronous API; the application uses prepared trajectories."""
        self.set_plot_data(
            prepare_trajectory(original) if original is not None else None,
            prepare_trajectory(transformed) if transformed is not None else None,
        )

    def set_plot_data(
        self, original: TrajectoryData | None, transformed: TrajectoryData | None = None
    ) -> None:
        self._original = original
        self._transformed = transformed
        self.redraw()

    def set_transformed(self, transformed: TrajectoryData | None) -> None:
        self._transformed = transformed
        self.redraw()

    def redraw(self) -> None:
        self._configure_axes()
        if self._original is not None:
            self._plot_trajectory(self._original, transformed=False)
        if self._transformed is not None:
            self._plot_trajectory(self._transformed, transformed=True)
        handles, _ = self.axes.get_legend_handles_labels()
        if handles:
            self.axes.legend(loc="best", fontsize="small")
        self.fit_to_view()

    def _plot_trajectory(self, trajectory: TrajectoryData, transformed: bool) -> None:
        source = "Transformado" if transformed else "Original"
        styles = {
            0: ("#94a3b8" if not transformed else "#c4b5fd", "--", "G0 rápido"),
            1: ("#2563eb" if not transformed else "#dc2626", "-", "G1 usinagem"),
            2: ("#059669" if not transformed else "#ea580c", "-", "G2/G3 arco"),
        }
        for group, series in trajectory.series.items():
            color, linestyle, name = styles[group]
            self.axes.plot(
                series.x,
                series.y,
                color=color,
                linestyle=linestyle,
                linewidth=1.7,
                solid_capstyle="round",
                label=f"{source} — {name}",
            )

    def fit_to_view(self) -> None:
        extents = [
            trajectory.extent
            for trajectory in (self._original, self._transformed)
            if trajectory is not None and trajectory.extent is not None
        ]
        if extents:
            min_x = min(0.0, *(extent[0] for extent in extents))
            max_x = max(0.0, *(extent[1] for extent in extents))
            min_y = min(0.0, *(extent[2] for extent in extents))
            max_y = max(0.0, *(extent[3] for extent in extents))
            x_padding = max((max_x - min_x) * 0.05, 0.1)
            y_padding = max((max_y - min_y) * 0.05, 0.1)
            self.axes.set_xlim(min_x - x_padding, max_x + x_padding)
            self.axes.set_ylim(min_y - y_padding, max_y + y_padding)
        else:
            self.axes.set_xlim(-1, 1)
            self.axes.set_ylim(-1, 1)
        self.canvas.draw_idle()
