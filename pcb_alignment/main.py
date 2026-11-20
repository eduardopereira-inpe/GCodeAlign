"""Tkinter application for safe 2D G-code alignment."""

from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .alignment import AlignmentError, calculate_correction_angle, degrees
from .background import BackgroundTasks, TaskMessage, drain_latest
from .gcode_parser import ParsedProgram
from .gcode_transform import default_output_name
from .gcode_viewer import GCodeViewer
from .jobs import LoadResult, SaveResult, TransformResult, load_gcode, save_gcode, transform_program
from .trajectory import TrajectoryData


class PCBAlignmentApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PCB G-code Alignment Tool")
        self.geometry("1180x760")
        self.minsize(960, 640)

        self.input_path: Path | None = None
        self.parsed_program: ParsedProgram | None = None
        self.angle_radians: float | None = None
        self.transformed_text: str | None = None
        self._original_trajectory: TrajectoryData | None = None
        self._update_job: str | None = None
        self._poll_job: str | None = None
        self._active_task_id: int | None = None
        self._active_task_kind: str | None = None
        self.tasks = BackgroundTasks()

        self.axis_var = tk.StringVar(value="X")
        self.measured_x_var = tk.StringVar()
        self.measured_y_var = tk.StringVar()
        self.input_name_var = tk.StringVar(value="Nenhum arquivo carregado")
        self.output_name_var = tk.StringVar()
        self.axis_info_var = tk.StringVar(value="X")
        self.point_info_var = tk.StringVar(value="—")
        self.angle_info_var = tk.StringVar(value="—")
        self.status_var = tk.StringVar(value="Carregue um arquivo G-code para começar.")

        self._build_ui()
        for variable in (self.axis_var, self.measured_x_var, self.measured_y_var):
            variable.trace_add("write", lambda *_: self._schedule_update())
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self) -> None:
        outer = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        outer.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(outer, width=360)
        right = ttk.Frame(outer)
        outer.add(left, weight=0)
        outer.add(right, weight=1)

        input_frame = ttk.LabelFrame(left, text="Arquivo de entrada", padding=8)
        input_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(input_frame, textvariable=self.input_name_var, wraplength=320).pack(anchor="w", fill="x")
        self.open_button = ttk.Button(input_frame, text="Abrir G-code…", command=self.open_file)
        self.open_button.pack(fill="x", pady=(8, 0))

        alignment_frame = ttk.LabelFrame(left, text="Configuração do alinhamento", padding=8)
        alignment_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(alignment_frame, text="Eixo nominal de referência:").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(alignment_frame, text="X", variable=self.axis_var, value="X").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(alignment_frame, text="Y", variable=self.axis_var, value="Y").grid(row=1, column=1, sticky="w")
        ttk.Label(alignment_frame, text="X medido (mm)").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(alignment_frame, text="Y medido (mm)").grid(row=2, column=1, sticky="w", pady=(8, 0))
        ttk.Entry(alignment_frame, textvariable=self.measured_x_var).grid(row=3, column=0, sticky="ew", padx=(0, 4))
        ttk.Entry(alignment_frame, textvariable=self.measured_y_var).grid(row=3, column=1, sticky="ew")
        ttk.Label(alignment_frame, text="A origem permanece fixa em X0 Y0.").grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.transform_button = ttk.Button(alignment_frame, text="Atualizar transformação", command=self.update_alignment)
        self.transform_button.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        alignment_frame.columnconfigure(0, weight=1)
        alignment_frame.columnconfigure(1, weight=1)

        info_frame = ttk.LabelFrame(left, text="Informações da transformação", padding=8)
        info_frame.pack(fill="x", pady=(0, 8))
        rows = (
            ("Eixo:", self.axis_info_var),
            ("Ponto medido:", self.point_info_var),
            ("Correção:", self.angle_info_var),
        )
        for row, (label, variable) in enumerate(rows):
            ttk.Label(info_frame, text=label).grid(row=row, column=0, sticky="w")
            ttk.Label(info_frame, textvariable=variable, wraplength=230).grid(row=row, column=1, sticky="w")
        info_frame.columnconfigure(1, weight=1)

        output_frame = ttk.LabelFrame(left, text="Arquivo de saída", padding=8)
        output_frame.pack(fill="x", pady=(0, 8))
        ttk.Entry(output_frame, textvariable=self.output_name_var).pack(fill="x")
        self.save_button = ttk.Button(output_frame, text="Salvar G-code transformado…", command=self.save_transformed)
        self.save_button.pack(fill="x", pady=(8, 0))

        status_frame = ttk.LabelFrame(left, text="Status / validação", padding=8)
        status_frame.pack(fill="both", expand=True)
        ttk.Label(status_frame, textvariable=self.status_var, wraplength=320, justify="left").pack(anchor="nw", fill="x")
        self.progress = ttk.Progressbar(status_frame, mode="indeterminate", maximum=100)
        self.progress.pack(fill="x", pady=(8, 0))
        self.progress.pack_forget()

        self.viewer = GCodeViewer(right)
        self.viewer.pack(fill="both", expand=True)

    def _schedule_update(self) -> None:
        if self._update_job is not None:
            self.after_cancel(self._update_job)
        self._update_job = self.after(350, self.update_alignment)

    def open_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="Abrir G-code",
            filetypes=[
                ("G-code", "*.gcode *.nc *.tap"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not filename:
            return
        path = Path(filename)
        self.input_path = path
        self.parsed_program = None
        self._original_trajectory = None
        self.angle_radians = None
        self.transformed_text = None
        self.input_name_var.set(path.name)
        self.output_name_var.set(default_output_name(path))
        self.point_info_var.set("—")
        self.angle_info_var.set("—")
        self.viewer.set_plot_data(None, None)
        self._start_task("load", lambda report: load_gcode(path, report))

    def _set_analysis_status(self, program: ParsedProgram) -> None:
        if program.blocking_issues:
            first = program.blocking_issues[0]
            self.status_var.set(
                f"Exportação bloqueada ({len(program.blocking_issues)} ocorrência(s)). "
                f"Linha {first.line_number}: {first.message}"
            )
        else:
            self.status_var.set("Arquivo válido para visualização e transformação segura.")

    def _start_task(self, kind: str, operation) -> None:
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        self._active_task_kind = kind
        self._active_task_id = self.tasks.submit(kind, operation)
        self._set_processing(True)
        self.status_var.set({
            "load": "Carregando G-code…",
            "transform": "Aplicando transformação…",
            "save": "Salvando G-code…",
        }.get(kind, "Processando…"))
        self._poll_job = self.after(50, self._poll_tasks)

    def _set_processing(self, processing: bool) -> None:
        self.transform_button.state(["disabled" if processing else "!disabled"])
        self.save_button.state(["disabled" if processing or self.transformed_text is None else "!disabled"])
        if processing:
            if not self.progress.winfo_ismapped():
                self.progress.pack(fill="x", pady=(8, 0))
            self.progress.configure(mode="indeterminate", value=0)
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def _poll_tasks(self) -> None:
        self._poll_job = None
        messages = drain_latest(self.tasks.messages)
        for message in messages:
            if message.task_id != self._active_task_id:
                continue
            if message.phase == "progress":
                self.status_var.set(message.status)
                if message.progress is not None:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=message.progress * 100)
                else:
                    self.progress.configure(mode="indeterminate")
                    self.progress.start(12)
            elif message.phase == "error":
                self._finish_task()
                self.status_var.set(message.status or "Falha durante o processamento.")
            elif message.phase == "result":
                self._handle_result(message)
        if self._active_task_id is not None:
            self._poll_job = self.after(75, self._poll_tasks)

    def _finish_task(self) -> None:
        self._active_task_id = None
        self._active_task_kind = None
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        self._set_processing(False)

    def _handle_result(self, message: TaskMessage) -> None:
        self.status_var.set("Atualizando visualização…")
        if message.kind == "load" and isinstance(message.result, LoadResult):
            result = message.result
            self.after_idle(lambda: self._render_loaded(result, message.task_id))
        elif message.kind == "transform" and isinstance(message.result, TransformResult):
            result = message.result
            self.after_idle(lambda: self._render_transformed(result, message.task_id))
        elif message.kind == "save" and isinstance(message.result, SaveResult):
            self._finish_task()
            self.status_var.set(f"Arquivo salvo com segurança em: {message.result.path}")

    def _render_loaded(self, result: LoadResult, task_id: int) -> None:
        if self._active_task_id != task_id or self._active_task_kind != "load":
            return
        self.input_path = result.path
        self.parsed_program = result.parsed
        self._original_trajectory = result.trajectory
        self.viewer.set_plot_data(result.trajectory, None)
        self._finish_task()
        self._set_analysis_status(result.parsed)
        if result.parsed.can_transform and self.measured_x_var.get().strip() and self.measured_y_var.get().strip():
            self._schedule_update()

    def _render_transformed(self, result: TransformResult, task_id: int) -> None:
        if self._active_task_id != task_id or self._active_task_kind != "transform":
            return
        self.viewer.set_plot_data(self._original_trajectory, result.trajectory)
        self.angle_radians = result.angle
        self.transformed_text = result.text
        self.point_info_var.set(f"({result.measured_x:g}, {result.measured_y:g}) mm")
        self.angle_info_var.set(f"{degrees(result.angle):+.8f}°")
        self._finish_task()
        self.status_var.set("Transformação calculada. Revise a visualização antes de salvar.")

    def update_alignment(self) -> None:
        self._update_job = None
        self.axis_info_var.set(self.axis_var.get())
        self.angle_radians = None
        self.transformed_text = None
        self.save_button.state(["disabled"])
        if self.parsed_program is None:
            if self._active_task_kind != "load":
                self.status_var.set("Carregue um arquivo G-code para começar.")
            self.viewer.set_transformed(None)
            return
        if self.parsed_program.blocking_issues:
            self.viewer.set_transformed(None)
            self._set_analysis_status(self.parsed_program)
            return
        try:
            x_text = self.measured_x_var.get().strip()
            y_text = self.measured_y_var.get().strip()
            if not x_text or not y_text:
                raise AlignmentError("Informe X e Y do ponto medido.")
            x = float(x_text)
            y = float(y_text)
            if not math.isfinite(x) or not math.isfinite(y):
                raise AlignmentError("As coordenadas devem ser números finitos.")
            axis = self.axis_var.get()
            angle = calculate_correction_angle(x, y, axis)
        except (ValueError, AlignmentError) as error:
            self.angle_info_var.set("—")
            self.point_info_var.set("—")
            self.status_var.set(str(error))
            self.viewer.set_transformed(None)
            return

        self.angle_info_var.set("—")
        self.point_info_var.set("—")
        self.viewer.set_transformed(None)
        parsed = self.parsed_program
        self._start_task(
            "transform",
            lambda report: transform_program(parsed, angle, x, y, report),
        )

    def save_transformed(self) -> None:
        if self.transformed_text is None or self.input_path is None:
            messagebox.showwarning("Transformação indisponível", "Calcule uma transformação válida antes de salvar.", parent=self)
            return
        initial_name = self.output_name_var.get().strip()
        if not initial_name or Path(initial_name).name != initial_name:
            messagebox.showerror("Nome inválido", "Informe somente um nome de arquivo válido, sem diretórios.", parent=self)
            return

        filename = filedialog.asksaveasfilename(
            title="Salvar G-code transformado",
            defaultextension=self.input_path.suffix,
            initialfile=initial_name,
            initialdir=str(self.input_path.parent),
            filetypes=[("G-code", "*.gcode *.nc *.tap"), ("Todos os arquivos", "*.*")],
        )
        if not filename:
            return
        target = Path(filename)
        if target.exists() and not messagebox.askyesno(
            "Substituir arquivo?",
            f"O arquivo {target.name} já existe. Deseja substituí-lo?",
            parent=self,
        ):
            return
        source = self.input_path
        text = self.transformed_text
        self._start_task(
            "save",
            lambda report: save_gcode(source, target, text, report),
        )

    def _close(self) -> None:
        if self._update_job is not None:
            self.after_cancel(self._update_job)
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
        self.tasks.shutdown()
        self.destroy()


def main() -> None:
    app = PCBAlignmentApp()
    app.mainloop()


if __name__ == "__main__":
    main()
