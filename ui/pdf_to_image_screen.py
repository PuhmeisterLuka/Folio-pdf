from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ui import theme as T
from ui.components import (
    AccentButton, DropZone, ProgressRow, SectionHeader, StatusBanner, run_in_thread,
)
from core.pdf_to_image import pdf_to_images
from core.utils import get_page_count


class PDFToImageScreen(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=T.BG_MAIN, **kw)
        self._file: str | None = None
        self._total_pages: int = 0
        self._running = False
        self._build_ui()

    def _build_ui(self):
        pad = T.PAD

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, 8))
        SectionHeader(header, "PDF to Image",
                      subtitle="Export pages as PNG or JPEG").pack(side="left")

        self._drop = DropZone(
            self,
            on_files=self._load_file,
            label="Drop a PDF file here",
            sublabel="or click to browse",
            multiple=False,
            height=100,
        )
        self._drop.pack(fill="x", padx=pad, pady=(0, T.PAD))

        self._fname_lbl = ctk.CTkLabel(
            self, text="No file selected",
            font=T.FONT_BODY, text_color=T.TEXT_SECONDARY, anchor="w",
        )
        self._fname_lbl.pack(fill="x", padx=pad, pady=(0, T.PAD))

        card = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=T.RADIUS)
        card.pack(fill="x", padx=pad, pady=(0, T.PAD))

        fmt_row = ctk.CTkFrame(card, fg_color="transparent")
        fmt_row.pack(fill="x", padx=T.PAD, pady=(T.PAD, 8))
        ctk.CTkLabel(fmt_row, text="Format", font=T.FONT_H2,
                     text_color=T.TEXT_PRIMARY, width=100, anchor="w").pack(
            side="left")
        self._fmt_seg = ctk.CTkSegmentedButton(
            fmt_row,
            values=["PNG", "JPG"],
            fg_color=T.BG_INPUT,
            selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
            unselected_color=T.BG_INPUT, unselected_hover_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, font=T.FONT_BODY,
        )
        self._fmt_seg.set("PNG")
        self._fmt_seg.pack(side="left")

        dpi_row = ctk.CTkFrame(card, fg_color="transparent")
        dpi_row.pack(fill="x", padx=T.PAD, pady=(0, 8))
        ctk.CTkLabel(dpi_row, text="Resolution", font=T.FONT_H2,
                     text_color=T.TEXT_PRIMARY, width=100, anchor="w").pack(
            side="left")
        self._dpi_seg = ctk.CTkSegmentedButton(
            dpi_row,
            values=["72 dpi · screen", "150 dpi · default", "300 dpi · print"],
            fg_color=T.BG_INPUT,
            selected_color=T.ACCENT, selected_hover_color=T.ACCENT_HOVER,
            unselected_color=T.BG_INPUT, unselected_hover_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY, font=T.FONT_BODY,
        )
        self._dpi_seg.set("150 dpi · default")
        self._dpi_seg.pack(side="left")

        range_row = ctk.CTkFrame(card, fg_color="transparent")
        range_row.pack(fill="x", padx=T.PAD, pady=(0, T.PAD))
        ctk.CTkLabel(range_row, text="Pages", font=T.FONT_H2,
                     text_color=T.TEXT_PRIMARY, width=100, anchor="w").pack(
            side="left")
        self._all_pages_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            range_row, text="All pages", variable=self._all_pages_var,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_PRIMARY, font=T.FONT_BODY,
            command=self._toggle_page_range,
        ).pack(side="left", padx=(0, 12))
        self._page_entry = ctk.CTkEntry(
            range_row,
            placeholder_text="e.g.  1-3, 5",
            fg_color=T.BG_INPUT, text_color=T.TEXT_PRIMARY,
            border_color=T.BORDER, font=T.FONT_BODY, height=32, width=180,
            state="disabled",
        )
        self._page_entry.pack(side="left")

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=pad, pady=(0, pad), side="bottom")
        self._progress = ProgressRow(bottom)
        self._progress.pack(fill="x")
        self._status = StatusBanner(bottom)
        self._status.pack(fill="x")
        AccentButton(bottom, text="Export Images →",
                     command=self._run_export, width=180).pack(pady=(8, 0))

    def _toggle_page_range(self):
        if self._all_pages_var.get():
            self._page_entry.configure(state="disabled")
        else:
            self._page_entry.configure(state="normal")

    def _load_file(self, paths: list[str]):
        path = paths[0]
        if not path.lower().endswith(".pdf"):
            self._status.show("Please select a PDF file.", error=True)
            return
        self._file = path
        try:
            self._total_pages = get_page_count(path)
        except Exception as e:
            self._status.show(str(e), error=True)
            return
        n = self._total_pages
        self._fname_lbl.configure(
            text=f"{Path(path).name}  ·  {n} page{'s' if n != 1 else ''}",
            text_color=T.TEXT_PRIMARY,
        )

    def _run_export(self):
        if self._running:
            return
        if not self._file:
            self._status.show("Select a PDF file first.", error=True)
            return

        out_dir = filedialog.askdirectory(title="Choose folder to save images")
        if not out_dir:
            return

        fmt = self._fmt_seg.get().lower()
        dpi = int(self._dpi_seg.get().split()[0])

        pages = None
        if not self._all_pages_var.get():
            raw = self._page_entry.get().strip()
            if not raw:
                self._status.show("Enter page numbers or select 'All pages'.", error=True)
                return
            try:
                from core.split import parse_page_ranges
                ranges = parse_page_ranges(raw, self._total_pages)
                pages = []
                for start, end in ranges:
                    pages.extend(range(start, end + 1))
            except ValueError as e:
                self._status.show(str(e), error=True)
                return

        self._running = True
        n_pages = len(pages) if pages else self._total_pages
        self._progress.start(f"Exporting {n_pages} page{'s' if n_pages != 1 else ''}…")
        self._status.pack_forget()

        src = self._file

        def _do():
            return pdf_to_images(
                src, out_dir, fmt=fmt, dpi=dpi, pages=pages,
                progress_callback=self._on_progress,
            )

        def _done(result):
            self._running = False
            n = len(result)
            self._progress.finish(f"Exported {n} image{'s' if n != 1 else ''} → {out_dir}")
            self._status.show(f"Saved {n} image(s) to {out_dir}")

        def _err(exc):
            self._running = False
            self._progress.finish(str(exc), error=True)
            self._status.show(str(exc), error=True)

        run_in_thread(_do, _done, _err, self)

    def _on_progress(self, value: float):
        self.after(0, lambda v=value: self._progress.update(v))


