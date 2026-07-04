from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ui import theme as T
from ui.components import (
    AccentButton, DropZone, ProgressRow, SectionHeader, StatusBanner, run_in_thread,
)
from core.word_to_pdf import word_to_pdf, is_word_available


class WordToPDFScreen(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=T.BG_MAIN, **kw)
        self._files: list[str] = []
        self._running = False
        self._word_ok = is_word_available()
        self._build_ui()

    def _build_ui(self):
        pad = T.PAD

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, 8))
        SectionHeader(header, "Word to PDF",
                      subtitle="Convert .docx files locally, no internet").pack(
            side="left")

        self._badge_lbl = ctk.CTkLabel(
            self, text="", font=T.FONT_SMALL, anchor="w",
        )
        self._badge_lbl.pack(fill="x", padx=pad, pady=(0, 8))
        self._refresh_badge()

        self._drop = DropZone(
            self,
            on_files=self._add_files,
            label="Drop .docx files here",
            sublabel="or click to browse",
            filetypes=[("Word documents", "*.docx"), ("All files", "*.*")],
            multiple=True,
            height=100,
        )
        self._drop.pack(fill="x", padx=pad, pady=(0, T.PAD))

        list_header = ctk.CTkFrame(self, fg_color="transparent")
        list_header.pack(fill="x", padx=pad, pady=(0, 4))
        self._count_lbl = ctk.CTkLabel(
            list_header, text="No files added",
            font=T.FONT_SMALL, text_color=T.TEXT_SECONDARY, anchor="w",
        )
        self._count_lbl.pack(side="left")
        ctk.CTkButton(
            list_header, text="Clear all", width=72, height=26,
            fg_color="transparent", hover_color=T.BG_HOVER,
            text_color=T.TEXT_SECONDARY, border_color=T.BORDER,
            border_width=1, font=T.FONT_SMALL, corner_radius=6,
            command=self._clear,
        ).pack(side="right")

        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=T.BORDER,
            scrollbar_button_hover_color=T.ACCENT,
        )
        self._list_frame.pack(fill="both", expand=True, padx=pad)

        out_row = ctk.CTkFrame(self, fg_color="transparent")
        out_row.pack(fill="x", padx=pad, pady=(T.PAD, 0))
        ctk.CTkLabel(out_row, text="Output folder:", font=T.FONT_BODY,
                     text_color=T.TEXT_SECONDARY).pack(side="left")
        self._out_lbl = ctk.CTkLabel(out_row, text="Same as source file",
                                      font=T.FONT_BODY, text_color=T.TEXT_MUTED)
        self._out_lbl.pack(side="left", padx=8)
        self._out_dir: str | None = None
        ctk.CTkButton(
            out_row, text="Change…", width=80, height=28,
            fg_color="transparent", hover_color=T.BG_HOVER,
            text_color=T.TEXT_SECONDARY, border_color=T.BORDER,
            border_width=1, font=T.FONT_SMALL, corner_radius=6,
            command=self._pick_out_dir,
        ).pack(side="left")

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=pad, pady=(8, pad), side="bottom")
        self._progress = ProgressRow(bottom)
        self._progress.pack(fill="x")
        self._status = StatusBanner(bottom)
        self._status.pack(fill="x")
        AccentButton(bottom, text="Convert to PDF →",
                     command=self._run_convert, width=190).pack(pady=(8, 0))

    def _add_files(self, paths: list[str]):
        added = 0
        for p in paths:
            if p.lower().endswith(".docx") and p not in self._files:
                self._files.append(p)
                added += 1
        if added:
            self._rebuild_list()

    def _rebuild_list(self):
        for w in self._list_frame.winfo_children():
            w.destroy()
        for p in self._files:
            row = ctk.CTkFrame(self._list_frame, fg_color=T.BG_CARD,
                                corner_radius=6)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=Path(p).name, font=T.FONT_BODY,
                         text_color=T.TEXT_PRIMARY, anchor="w").pack(
                side="left", fill="x", expand=True, padx=4)
            ctk.CTkButton(
                row, text="✕", width=28, height=26,
                fg_color="transparent", hover_color="#4A1A1A",
                text_color=T.TEXT_MUTED, font=T.FONT_BODY,
                command=lambda fp=p: self._remove(fp),
            ).pack(side="right", padx=6)
        n = len(self._files)
        self._count_lbl.configure(
            text=f"{n} file{'s' if n != 1 else ''} queued" if n else "No files added"
        )

    def _remove(self, path: str):
        if path in self._files:
            self._files.remove(path)
            self._rebuild_list()

    def _clear(self):
        self._files.clear()
        self._rebuild_list()

    def _pick_out_dir(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if d:
            self._out_dir = d
            self._out_lbl.configure(text=d, text_color=T.TEXT_PRIMARY)

    def _refresh_badge(self):
        self._word_ok = is_word_available()
        if self._word_ok:
            self._badge_lbl.configure(
                text="✓  Microsoft Word detected", text_color=T.SUCCESS)
        else:
            self._badge_lbl.configure(
                text="⚠  Microsoft Word not found, conversion may fail",
                text_color=T.WARNING)

    def _run_convert(self):
        self._refresh_badge()
        if self._running:
            return
        if not self._files:
            self._status.show("Add at least one .docx file.", error=True)
            return

        self._running = True
        self._progress.start(f"Converting 0 / {len(self._files)}…")
        self._status.pack_forget()

        files = list(self._files)
        out_dir = self._out_dir

        def _do():
            ok, fail = 0, []
            for i, src in enumerate(files):
                dest_dir = Path(out_dir) if out_dir else Path(src).parent
                dest = dest_dir / (Path(src).stem + ".pdf")
                success, err = word_to_pdf(
                    src, str(dest),
                    progress_callback=None,
                )
                if success:
                    ok += 1
                else:
                    fail.append((Path(src).name, err))
                self.after(
                    0,
                    lambda i=i: self._progress.update(
                        (i + 1) / len(files),
                        f"Converting {i + 1} / {len(files)}…",
                    ),
                )
            return ok, fail

        def _done(result):
            ok, fail = result
            self._running = False
            if fail:
                msgs = "\n".join(f"{n}: {e}" for n, e in fail)
                self._progress.finish(
                    f"{ok} converted, {len(fail)} failed", error=bool(fail))
                self._status.show_persistent(
                    f"{len(fail)} error(s):\n{msgs}", error=True)
            else:
                self._progress.finish(f"Converted {ok} file{'s' if ok != 1 else ''}")
                self._status.show(f"All {ok} file(s) converted successfully.")

        def _err(exc):
            self._running = False
            self._progress.finish(str(exc), error=True)
            self._status.show(str(exc), error=True)

        run_in_thread(_do, _done, _err, self)

    def _on_progress(self, value: float):
        self.after(0, lambda v=value: self._progress.update(v))


