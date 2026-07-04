from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ui import theme as T
from ui.components import (
    AccentButton, DropZone, ProgressRow, SectionHeader, StatusBanner, human_size, run_in_thread,
)
from core.compress import compress_pdf


_PRESETS = {
    "Low": {
        "level": "low",
        "desc": "Lossless repack  ·  minimal size reduction",
    },
    "Medium": {
        "level": "medium",
        "desc": "Repack + image optimisation  ·  good balance",
    },
    "High": {
        "level": "high",
        "desc": "Aggressive image recompression  ·  smallest file",
    },
}


class CompressScreen(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=T.BG_MAIN, **kw)
        self._file: str | None = None
        self._level: str = "medium"
        self._running = False
        self._build_ui()

    def _build_ui(self):
        pad = T.PAD

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, 8))
        SectionHeader(header, "Compress PDF",
                      subtitle="Reduce file size without splitting or merging").pack(side="left")

        self._drop = DropZone(
            self,
            on_files=self._load_file,
            label="Drop a PDF file here",
            sublabel="or click to browse",
            multiple=False,
            height=110,
        )
        self._drop.pack(fill="x", padx=pad, pady=(0, T.PAD))

        self._info_card = ctk.CTkFrame(self, fg_color=T.BG_CARD,
                                        corner_radius=T.RADIUS)
        self._info_card.pack(fill="x", padx=pad, pady=(0, T.PAD))
        self._fname_lbl = ctk.CTkLabel(
            self._info_card, text="No file selected",
            font=T.FONT_BODY, text_color=T.TEXT_SECONDARY, anchor="w",
        )
        self._fname_lbl.pack(side="left", padx=T.PAD, pady=10)
        self._fsize_lbl = ctk.CTkLabel(
            self._info_card, text="",
            font=T.FONT_SMALL, text_color=T.TEXT_MUTED, anchor="e",
        )
        self._fsize_lbl.pack(side="right", padx=T.PAD, pady=10)

        presets_lbl = ctk.CTkLabel(self, text="Compression level",
                                    font=T.FONT_H2, text_color=T.TEXT_PRIMARY,
                                    anchor="w")
        presets_lbl.pack(fill="x", padx=pad, pady=(0, 8))

        preset_row = ctk.CTkFrame(self, fg_color="transparent")
        preset_row.pack(fill="x", padx=pad)
        self._preset_btns: dict[str, ctk.CTkButton] = {}
        for name, info in _PRESETS.items():
            card = self._make_preset_card(preset_row, name, info)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))

        # before/after size card, only shown once a compress finishes
        self._result_frame = ctk.CTkFrame(self, fg_color=T.BG_CARD,
                                           corner_radius=T.RADIUS)
        self._before_lbl = ctk.CTkLabel(self._result_frame, text="Before: …",
                                         font=T.FONT_BODY, text_color=T.TEXT_SECONDARY)
        self._before_lbl.pack(side="left", padx=T.PAD, pady=10)
        self._after_lbl = ctk.CTkLabel(self._result_frame, text="After: …",
                                        font=T.FONT_BODY, text_color=T.ACCENT)
        self._after_lbl.pack(side="left", padx=T.PAD, pady=10)
        self._ratio_lbl = ctk.CTkLabel(self._result_frame, text="",
                                        font=(*T.FONT_BODY[:2], "bold"),
                                        text_color=T.SUCCESS)
        self._ratio_lbl.pack(side="right", padx=T.PAD, pady=10)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=pad, pady=(T.PAD, pad), side="bottom")
        self._progress = ProgressRow(bottom)
        self._progress.pack(fill="x")
        self._status = StatusBanner(bottom)
        self._status.pack(fill="x")
        AccentButton(bottom, text="Compress PDF →",
                     command=self._run_compress, width=180).pack(pady=(8, 0))

        self._select_preset("Medium")

    def _make_preset_card(self, master, name: str, info: dict) -> ctk.CTkFrame:
        card = ctk.CTkFrame(master, fg_color=T.BG_CARD, corner_radius=T.RADIUS,
                             border_width=2, border_color=T.BORDER, cursor="hand2")
        name_lbl = ctk.CTkLabel(card, text=name, font=T.FONT_H2,
                                 text_color=T.TEXT_PRIMARY)
        name_lbl.pack(padx=T.PAD, pady=(12, 4))
        desc_lbl = ctk.CTkLabel(card, text=info["desc"], font=T.FONT_SMALL,
                                 text_color=T.TEXT_SECONDARY, wraplength=180)
        desc_lbl.pack(padx=T.PAD, pady=(0, 12))

        for w in (card, name_lbl, desc_lbl):
            w.bind("<Button-1>", lambda _e, n=name: self._select_preset(n))

        # Keyboard bindings (focus must land here via other means; CTkFrame
        # does not accept takefocus via .configure())
        card.bind("<Return>", lambda _e, n=name: self._select_preset(n))
        card.bind("<space>",  lambda _e, n=name: self._select_preset(n))
        card.bind("<FocusIn>",  lambda _e, c=card: c.configure(border_color=T.ACCENT_HOVER))
        card.bind("<FocusOut>", lambda _e, n=name, c=card: c.configure(
            border_color=T.ACCENT if self._level == _PRESETS[n]["level"] else T.BORDER))

        self._preset_btns[name] = card
        return card

    def _select_preset(self, name: str):
        self._level = _PRESETS[name]["level"]
        for n, card in self._preset_btns.items():
            card.configure(border_color=T.ACCENT if n == name else T.BORDER)

    def _load_file(self, paths: list[str]):
        path = paths[0]
        if not path.lower().endswith(".pdf"):
            self._status.show("Please select a PDF file.", error=True)
            return
        self._file = path
        size = Path(path).stat().st_size
        self._fname_lbl.configure(
            text=Path(path).name, text_color=T.TEXT_PRIMARY)
        self._fsize_lbl.configure(text=human_size(size))
        self._result_frame.pack_forget()

    def _run_compress(self):
        if self._running:
            return
        if not self._file:
            self._status.show("Select a PDF file first.", error=True)
            return

        out = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF file", "*.pdf")],
            initialfile=Path(self._file).stem + "_compressed.pdf",
            title="Save Compressed PDF",
        )
        if not out:
            return

        self._running = True
        self._progress.start("Compressing…")
        self._result_frame.pack_forget()
        self._status.pack_forget()

        src = self._file
        level = self._level

        def _do():
            return compress_pdf(src, out, level=level,
                                 progress_callback=self._on_progress)

        def _done(stats):
            self._running = False
            self._progress.finish(f"Saved → {Path(out).name}")
            self._before_lbl.configure(text=f"Before: {human_size(stats['input_size'])}")
            self._after_lbl.configure(text=f"After:  {human_size(stats['output_size'])}")
            sign = "−" if stats["ratio"] >= 0 else "+"
            self._ratio_lbl.configure(
                text=f"{sign}{abs(stats['ratio']):.1f}% size",
                text_color=T.SUCCESS if stats["ratio"] >= 0 else T.ERROR,
            )
            self._result_frame.pack(fill="x", padx=T.PAD, pady=T.PAD)

        def _err(exc):
            self._running = False
            self._progress.finish(str(exc), error=True)
            self._status.show(str(exc), error=True)

        run_in_thread(_do, _done, _err, self)

    def _on_progress(self, value: float):
        self.after(0, lambda v=value: self._progress.update(v))


