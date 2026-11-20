"""Tkinter application for safe 2D G-code alignment."""

from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .alignment import AlignmentError, calculate_correction_angle, degrees
from .gcode_parser import ParsedProgram, parse_gcode
from .gcode_transform import TransformError, default_output_name, transform_gcode, validate_output_path
from .gcode_viewer import GCodeViewer


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
        self._update_job: str | None = None

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
        ttk.Button(input_frame, text="Abrir G-code…", command=self.open_file).pack(fill="x", pady=(8, 0))

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
        ttk.Button(alignment_frame, text="Atualizar transformação", command=self.update_alignment).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
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
        ttk.Button(output_frame, text="Salvar G-code transformado…", command=self.save_transformed).pack(fill="x", pady=(8, 0))

        status_frame = ttk.LabelFrame(left, text="Status / validação", padding=8)
        status_frame.pack(fill="both", expand=True)
        ttk.Label(status_frame, textvariable=self.status_var, wraplength=320, justify="left").pack(anchor="nw", fill="both", expand=True)

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
        try:
            path = Path(filename)
            text = path.read_text(encoding="utf-8-sig")
            parsed = parse_gcode(text)
        except (OSError, UnicodeError, ValueError) as error:
            messagebox.showerror("Não foi possível abrir o arquivo", str(error), parent=self)
            return

        self.input_path = path
        self.parsed_program = parsed
        self.angle_radians = None
        self.transformed_text = None
        self.point_info_var.set("—")
        self.angle_info_var.set("—")
        self.input_name_var.set(path.name)
        self.output_name_var.set(default_output_name(path))
        self.viewer.set_programs(parsed, None)
        self._set_analysis_status(parsed)
        self.update_alignment()

    def _set_analysis_status(self, program: ParsedProgram) -> None:
        if program.blocking_issues:
            first = program.blocking_issues[0]
            self.status_var.set(
                f"Exportação bloqueada ({len(program.blocking_issues)} ocorrência(s)). "
                f"Linha {first.line_number}: {first.message}"
            )
        else:
            self.status_var.set("Arquivo válido para visualização e transformação segura.")

    def update_alignment(self) -> None:
        self._update_job = None
        self.axis_info_var.set(self.axis_var.get())
        self.angle_radians = None
        self.transformed_text = None
        if self.parsed_program is None:
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
            angle = calculate_correction_angle(x, y, self.axis_var.get())
            transformed_text = transform_gcode(self.parsed_program, angle)
            transformed = parse_gcode(transformed_text)
        except (ValueError, TransformError) as error:
            self.angle_info_var.set("—")
            self.point_info_var.set("—")
            self.status_var.set(str(error))
            self.viewer.set_transformed(None)
            return

        self.angle_radians = angle
        self.transformed_text = transformed_text
        self.point_info_var.set(f"({x:g}, {y:g}) mm")
        self.angle_info_var.set(f"{degrees(angle):+.8f}°")
        self.status_var.set("Transformação calculada. Revise a visualização antes de salvar.")
        self.viewer.set_transformed(transformed)

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
        try:
            target = validate_output_path(self.input_path, target)
            if target.exists() and not messagebox.askyesno(
                "Substituir arquivo?",
                f"O arquivo {target.name} já existe. Deseja substituí-lo?",
                parent=self,
            ):
                return
            target.write_text(self.transformed_text, encoding="utf-8")
            parse_gcode(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as error:
            messagebox.showerror("Falha ao salvar", str(error), parent=self)
            return
        self.status_var.set(f"Arquivo salvo com segurança em: {target}")

    def _close(self) -> None:
        self.destroy()


def main() -> None:
    app = PCBAlignmentApp()
    app.mainloop()


if __name__ == "__main__":
    main()
