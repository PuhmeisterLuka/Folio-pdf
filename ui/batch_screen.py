from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ui import theme as T
from ui.components import (
    AccentButton, GhostButton, ProgressRow, SectionHeader, StatusBanner, run_in_thread,
)
from core.batch import (
    get_pdfs_in_folder, batch_compress, batch_rotate,
    batch_to_images,
)


_OPS = ["Compress", "Rotate all pages", "Export to Images", "Merge all → one PDF"]


class BatchScreen(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=T.BG_MAIN, **kw)
        self._in_dir: str | None = None
        self._out_dir: str | None = None
        self._running = False
        self._build_ui()

    def _build_ui(self):
        pad = T.PAD

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, 8))
        SectionHeader(header, "Batch Process",
                      subtitle="Apply one operation to every PDF in a folder").pack(
            side="left")

        in_card = self._folder_card(
            "Input folder", "Choose the folder containing PDF files",
            self._pick_input,
        )
        in_card.pack(fill="x", padx=pad, pady=(0, 6))
        self._in_lbl = ctk.CTkLabel(
            in_card, text="No folder selected",
            font=T.FONT_SMALL, text_color=T.TEXT_MUTED, anchor="w",
        )
        self._in_lbl.pack(fill="x", padx=T.PAD, pady=(0, T.PAD))
        self._file_count_lbl = ctk.CTkLabel(
            in_card, text="",
            font=T.FONT_SMALL, text_color=T.ACCENT, anchor="w",
        )
        self._file_count_lbl.pack(fill="x", padx=T.PAD, pady=(0, 8))

        out_card = self._folder_card(
            "Output folder", "Where to save processed files",
            self._pick_output,
        )
        out_card.pack(fill="x", padx=pad, pady=(0, T.PAD))
        self._out_lbl = ctk.CTkLabel(
            out_card, text="No folder selected",
            font=T.FONT_SMALL, text_color=T.TEXT_MUTED, anchor="w",
        )
        self._out_lbl.pack(fill="x", padx=T.PAD, pady=(0, T.PAD))

        ctk.CTkLabel(self, text="Operation", font=T.FONT_H2,
                     text_color=T.TEXT_PRIMARY, anchor="w").pack(
            fill="x", padx=pad, pady=(0, 6))

        op_row = ctk.CTkFrame(self, fg_color="transparent")
        op_row.pack(fill="x", padx=pad, pady=(0, T.PAD))
        self._op_var = ctk.StringVar(value=_OPS[0])
        for op in _OPS:
            rb = ctk.CTkRadioButton(
                op_row, text=op, value=op,
                variable=self._op_var,
                fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                text_color=T.TEXT_PRIMARY, font=T.FONT_BODY,
                command=self._on_op_change,
            )
            rb.pack(side="left", padx=(0, 24))

        self._settings_frame = ctk.CTkFrame(self, fg_color=T.BG_CARD,
                                             corner_radius=T.RADIUS)
        self._settings_frame.pack(fill="x", padx=pad, pady=(0, T.PAD))
        self._settings_widgets: dict[str, ctk.CTkFrame] = {}
        self._build_settings_panels()
        self._on_op_change()

        # results list stays hidden until a batch actually ran
        self._results_lbl = ctk.CTkLabel(self, text="Results", font=T.FONT_H2,
                                          text_color=T.TEXT_PRIMARY, anchor="w")
        self._results_scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=T.BORDER,
            scrollbar_button_hover_color=T.ACCENT,
            height=130,
        )

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=pad, pady=(8, pad), side="bottom")
        self._progress = ProgressRow(bottom)
        self._progress.pack(fill="x")
        self._status = StatusBanner(bottom)
        self._status.pack(fill="x")
        AccentButton(bottom, text="Process Folder →",
                     command=self._run_batch, width=180).pack(pady=(8, 0))

    def _folder_card(self, title: str, subtitle: str, cmd) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=T.RADIUS)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=T.PAD, pady=(T.PAD, 4))
        ctk.CTkLabel(row, text=title, font=T.FONT_H2,
                     text_color=T.TEXT_PRIMARY).pack(side="left")
        GhostButton(row, text="Browse…", width=80, height=26,
                    font=T.FONT_SMALL, command=cmd).pack(side="right")
        ctk.CTkLabel(card, text=subtitle, font=T.FONT_SMALL,
                     text_color=T.TEXT_MUTED, anchor="w").pack(
            fill="x", padx=T.PAD, pady=(0, 2))
        return card

    def _build_settings_panels(self):
        # every operation gets its own settings row, _on_op_change swaps them
        sf = self._settings_frame

        comp = ctk.CTkFrame(sf, fg_color="transparent")
        ctk.CTkLabel(comp, text="Compression level",
                     font=T.FONT_BODY, text_color=T.TEXT_SECONDARY).pack(
            side="left", padx=T.PAD, pady=10)
        self._compress_seg = ctk.CTkSegmentedButton(
            comp, values=["Low", "Medium", "High"],
            fg_color=T.BG_INPUT,
            selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
            unselected_color=T.BG_INPUT, unselected_hover_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, font=T.FONT_BODY,
        )
        self._compress_seg.set("Medium")
        self._compress_seg.pack(side="left", padx=(0, T.PAD))
        self._settings_widgets["Compress"] = comp

        rot = ctk.CTkFrame(sf, fg_color="transparent")
        ctk.CTkLabel(rot, text="Rotate each page",
                     font=T.FONT_BODY, text_color=T.TEXT_SECONDARY).pack(
            side="left", padx=T.PAD, pady=10)
        self._rotate_seg = ctk.CTkSegmentedButton(
            rot, values=["90° CW", "180°", "90° CCW"],
            fg_color=T.BG_INPUT,
            selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
            unselected_color=T.BG_INPUT, unselected_hover_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, font=T.FONT_BODY,
        )
        self._rotate_seg.set("90° CW")
        self._rotate_seg.pack(side="left", padx=(0, T.PAD))
        self._settings_widgets["Rotate all pages"] = rot

        img = ctk.CTkFrame(sf, fg_color="transparent")
        ctk.CTkLabel(img, text="Format", font=T.FONT_BODY,
                     text_color=T.TEXT_SECONDARY).pack(side="left", padx=T.PAD, pady=10)
        self._batch_fmt_seg = ctk.CTkSegmentedButton(
            img, values=["PNG", "JPG"],
            fg_color=T.BG_INPUT,
            selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
            unselected_color=T.BG_INPUT, unselected_hover_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, font=T.FONT_BODY,
        )
        self._batch_fmt_seg.set("PNG")
        self._batch_fmt_seg.pack(side="left")
        ctk.CTkLabel(img, text="DPI", font=T.FONT_BODY,
                     text_color=T.TEXT_SECONDARY).pack(side="left", padx=(T.PAD, 4), pady=10)
        self._batch_dpi_seg = ctk.CTkSegmentedButton(
            img, values=["72", "150", "300"],
            fg_color=T.BG_INPUT,
            selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
            unselected_color=T.BG_INPUT, unselected_hover_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, font=T.FONT_BODY,
        )
        self._batch_dpi_seg.set("150")
        self._batch_dpi_seg.pack(side="left", padx=(0, T.PAD))
        self._settings_widgets["Export to Images"] = img

        # merge has nothing to configure
        merge = ctk.CTkFrame(sf, fg_color="transparent")
        ctk.CTkLabel(
            merge,
            text="All PDFs in the folder will be merged alphabetically into one file.",
            font=T.FONT_BODY, text_color=T.TEXT_SECONDARY,
        ).pack(padx=T.PAD, pady=10)
        self._settings_widgets["Merge all → one PDF"] = merge

    def _on_op_change(self):
        op = self._op_var.get()
        for name, w in self._settings_widgets.items():
            if name == op:
                w.pack(fill="x")
            else:
                w.pack_forget()

    def _pick_input(self):
        d = filedialog.askdirectory(title="Choose input folder")
        if not d:
            return
        self._in_dir = d
        self._in_lbl.configure(text=Path(d).name, text_color=T.TEXT_PRIMARY)
        pdfs = get_pdfs_in_folder(d)
        n = len(pdfs)
        self._file_count_lbl.configure(
            text=f"{n} PDF file{'s' if n != 1 else ''} found" if n
            else "No PDF files found in this folder"
        )

    def _pick_output(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if not d:
            return
        self._out_dir = d
        self._out_lbl.configure(text=Path(d).name, text_color=T.TEXT_PRIMARY)

    def _run_batch(self):
        if self._running:
            return
        if not self._in_dir:
            self._status.show("Choose an input folder first.", error=True)
            return
        if not self._out_dir:
            self._status.show("Choose an output folder first.", error=True)
            return

        pdfs = get_pdfs_in_folder(self._in_dir)
        if not pdfs:
            self._status.show("No PDF files found in the input folder.", error=True)
            return

        op = self._op_var.get()
        self._running = True
        self._progress.start(f"Processing {len(pdfs)} files…")
        self._status.pack_forget()
        for w in self._results_scroll.winfo_children():
            w.destroy()

        in_dir = self._in_dir
        out_dir = self._out_dir

        def _do():
            if op == "Compress":
                level = self._compress_seg.get().lower()
                return batch_compress(in_dir, out_dir, level=level,
                                      progress_callback=self._on_progress)
            elif op == "Rotate all pages":
                label = self._rotate_seg.get()
                angle = {"90° CW": 90, "180°": 180, "90° CCW": 270}[label]
                return batch_rotate(in_dir, out_dir, rotation=angle,
                                    progress_callback=self._on_progress)
            elif op == "Export to Images":
                fmt = self._batch_fmt_seg.get().lower()
                dpi = int(self._batch_dpi_seg.get())
                return batch_to_images(in_dir, out_dir, fmt=fmt, dpi=dpi,
                                       progress_callback=self._on_progress)
            else:  # Merge all
                from core.merge import merge_pdfs
                stem = Path(in_dir).name or "merged"
                out_path = Path(out_dir) / f"{stem}_merged.pdf"
                paths = [str(p) for p in pdfs]
                merge_pdfs(paths, str(out_path),
                           progress_callback=self._on_progress)
                return [out_path], []

        def _done(result):
            ok, errors = result
            self._running = False
            self._progress.finish(
                f"{len(ok)} succeeded, {len(errors)} failed" if errors
                else f"All {len(ok)} file(s) processed"
            )
            self._render_results(ok, errors)
            if errors:
                self._status.show(
                    f"{len(errors)} error(s), see list above", error=True)
            else:
                self._status.show(f"Done. Output saved to {out_dir}")

        def _err(exc):
            self._running = False
            self._progress.finish(str(exc), error=True)
            self._status.show(str(exc), error=True)

        run_in_thread(_do, _done, _err, self)

    def _render_results(self, ok: list, errors: list):
        pad = T.PAD
        self._results_lbl.pack(fill="x", padx=pad, pady=(T.PAD, 4))
        self._results_scroll.pack(fill="x", padx=pad)
        for w in self._results_scroll.winfo_children():
            w.destroy()
        for path in ok:
            name = Path(path).name
            display = name if len(name) <= 48 else name[:45] + "…"
            row = ctk.CTkFrame(self._results_scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text="✓", font=T.FONT_BODY,
                         text_color=T.SUCCESS, width=20).pack(side="left")
            ctk.CTkLabel(row, text=display, font=T.FONT_SMALL,
                         text_color=T.TEXT_SECONDARY, anchor="w").pack(
                side="left", fill="x", expand=True)
        for path, err in errors:
            name = Path(path).name if hasattr(path, "name") else Path(str(path)).name
            display = name if len(name) <= 40 else name[:37] + "…"
            row = ctk.CTkFrame(self._results_scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text="✕", font=T.FONT_BODY,
                         text_color=T.ERROR, width=20).pack(side="left")
            ctk.CTkLabel(row, text=f"{display}: {err}", font=T.FONT_SMALL,
                         text_color=T.ERROR, anchor="w").pack(
                side="left", fill="x", expand=True)

    def _on_progress(self, value: float):
        self.after(0, lambda v=value: self._progress.update(v))


