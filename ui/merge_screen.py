from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ui import theme as T
from ui.components import (
    AccentButton, DropZone, FileRow, GhostButton,
    ProgressRow, SectionHeader, StatusBanner, run_in_thread,
)
from core.merge import merge_pdfs
from core.utils import get_page_count


class MergeScreen(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=T.BG_MAIN, **kw)
        self._files: list[str] = []
        self._rows: list[FileRow] = []
        self._running = False
        self._build_ui()

    def _build_ui(self):
        pad = T.PAD
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, 8))
        AccentButton(header, text="Merge PDFs →", command=self._run_merge,
                     width=140).pack(side="right")
        SectionHeader(header, "Merge PDFs",
                      subtitle="Combine multiple files into one").pack(
            side="left", fill="x", expand=True)

        self._drop = DropZone(
            self,
            on_files=self._add_files,
            label="Drop PDF files here",
            sublabel="or click to browse, add as many as you like",
            multiple=True,
            height=100,
        )
        self._drop.pack(fill="x", padx=pad, pady=(0, 8))

        list_frame = ctk.CTkFrame(self, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=pad)

        list_header = ctk.CTkFrame(list_frame, fg_color="transparent")
        list_header.pack(fill="x", pady=(0, 4))
        self._count_lbl = ctk.CTkLabel(
            list_header, text="No files added", font=T.FONT_SMALL,
            text_color=T.TEXT_SECONDARY, anchor="w",
        )
        self._count_lbl.pack(side="left")
        GhostButton(list_header, text="Clear all", width=80, height=26,
                    font=T.FONT_SMALL, command=self._clear_all).pack(side="right")

        self._scroll = ctk.CTkScrollableFrame(
            list_frame, fg_color="transparent",
            scrollbar_button_color=T.BORDER,
            scrollbar_button_hover_color=T.ACCENT,
        )
        self._scroll.pack(fill="both", expand=True)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=pad, pady=(8, pad))
        self._progress = ProgressRow(bottom)
        self._progress.pack(fill="x")
        self._status = StatusBanner(bottom)
        self._status.pack(fill="x")

    def _add_files(self, paths: list[str]):
        added = 0
        for p in paths:
            if p.lower().endswith(".pdf") and p not in self._files:
                self._files.append(p)
                added += 1
        if added:
            self._rebuild_rows()

    def _rebuild_rows(self):
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        for i, path in enumerate(self._files):
            row = FileRow(
                self._scroll, path=path, index=i,
                on_remove=lambda p=path: self._remove_file(p),
                on_up=lambda i=i: self._move(i, -1),
                on_down=lambda i=i: self._move(i, 1),
            )
            row.pack(fill="x", pady=2)
            self._rows.append(row)

        total_pages = sum(
            _safe_page_count(p) for p in self._files
        )
        n = len(self._files)
        self._count_lbl.configure(
            text=f"{n} file{'s' if n != 1 else ''} · {total_pages} total pages"
            if n else "No files added"
        )

    def _remove_file(self, path: str):
        if path in self._files:
            self._files.remove(path)
            self._rebuild_rows()

    def _move(self, index: int, direction: int):
        new_idx = index + direction
        if 0 <= new_idx < len(self._files):
            self._files[index], self._files[new_idx] = (
                self._files[new_idx], self._files[index]
            )
            self._rebuild_rows()

    def _clear_all(self):
        self._files.clear()
        self._rebuild_rows()

    def _run_merge(self):
        if self._running:
            return
        if len(self._files) < 2:
            self._status.show("Add at least 2 PDF files to merge.", error=True)
            return

        out = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF file", "*.pdf")],
            initialfile="merged.pdf",
            title="Save Merged PDF",
        )
        if not out:
            return

        self._running = True
        self._progress.start("Merging…")
        self._status.pack_forget()

        files = list(self._files)

        def _do():
            merge_pdfs(files, out, progress_callback=self._on_progress)

        def _done(_):
            self._running = False
            self._progress.finish(f"Saved → {Path(out).name}")
            self._status.show(f"Saved: {out}", error=False)

        def _err(exc):
            self._running = False
            self._progress.finish(str(exc), error=True)
            self._status.show(str(exc), error=True)

        run_in_thread(_do, _done, _err, self)

    def _on_progress(self, value: float):
        self.after(0, lambda v=value: self._progress.update(v))


_page_count_cache: dict[str, int] = {}


def _safe_page_count(path: str) -> int:
    if path in _page_count_cache:
        return _page_count_cache[path]
    try:
        count = get_page_count(path)
        _page_count_cache[path] = count
        return count
    except Exception:
        return 0


