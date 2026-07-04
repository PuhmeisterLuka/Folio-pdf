from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from ui import theme as T
from ui.components import (
    AccentButton, DropZone, GhostButton,
    ProgressRow, SectionHeader, StatusBanner, run_in_thread,
)
from core.split import parse_page_ranges, split_by_ranges, split_into_individual
from core.rotate_reorder import get_page_thumbnail
from core.utils import get_page_count

_MODE_RANGES = "ranges"
_MODE_VISUAL = "visual"
_MODE_INDIV  = "individual"

_SEG_RANGES = "Page ranges"
_SEG_VISUAL = "Visual selector"
_SEG_INDIV  = "Individual pages"


class SplitScreen(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=T.BG_MAIN, **kw)
        self._file: str | None = None
        self._total_pages: int = 0
        self._selected: set[int] = set()   # 0-indexed pages picked in the visual selector
        self._thumb_imgs: list = []         # tk drops images that lose their python reference
        self._thumb_widgets: list[ctk.CTkFrame] = []
        self._thumb_num_lbls: list[ctk.CTkLabel] = []
        self._mode: str = _MODE_RANGES
        self._running = False
        self._build_ui()

    def _build_ui(self):
        pad = T.PAD

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, 8))
        SectionHeader(header, "Split PDF",
                      subtitle="Extract page ranges or individual pages").pack(
            side="left")

        self._drop = DropZone(
            self,
            on_files=self._load_file,
            label="Drop a PDF file here",
            sublabel="or click to browse",
            multiple=False,
            height=100,
        )
        self._drop.pack(fill="x", padx=pad, pady=(0, T.PAD))

        info_row = ctk.CTkFrame(self, fg_color="transparent")
        info_row.pack(fill="x", padx=pad, pady=(0, 8))
        self._fname_lbl = ctk.CTkLabel(
            info_row, text="No file selected",
            font=T.FONT_BODY, text_color=T.TEXT_SECONDARY, anchor="w",
        )
        self._fname_lbl.pack(side="left")
        self._page_lbl = ctk.CTkLabel(
            info_row, text="",
            font=T.FONT_SMALL, text_color=T.TEXT_MUTED, anchor="e",
        )
        self._page_lbl.pack(side="right")

        mode_row = ctk.CTkFrame(self, fg_color="transparent")
        mode_row.pack(fill="x", padx=pad, pady=(0, T.PAD))
        self._mode_seg = ctk.CTkSegmentedButton(
            mode_row,
            values=[_SEG_RANGES, _SEG_VISUAL, _SEG_INDIV],
            command=self._on_mode_change,
            fg_color=T.BG_CARD,
            selected_color=T.ACCENT,
            selected_hover_color=T.ACCENT_HOVER,
            unselected_color=T.BG_CARD,
            unselected_hover_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY,
            font=T.FONT_BODY,
        )
        self._mode_seg.pack(side="left")
        self._mode_seg.set(_SEG_RANGES)

        # panel 1, type the ranges by hand
        self._ranges_panel = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(
            self._ranges_panel,
            text="Enter page ranges  (e.g.  1-3, 5, 7-9)",
            font=T.FONT_SMALL, text_color=T.TEXT_SECONDARY, anchor="w",
        ).pack(fill="x", padx=pad, pady=(0, 4))
        self._range_entry = ctk.CTkEntry(
            self._ranges_panel,
            placeholder_text="1-3, 5, 7-9",
            fg_color=T.BG_INPUT, text_color=T.TEXT_PRIMARY,
            border_color=T.BORDER, font=T.FONT_BODY, height=38,
        )
        self._range_entry.pack(fill="x", padx=pad)

        # panel 2, click thumbnails to pick pages
        self._visual_panel = ctk.CTkFrame(self, fg_color="transparent")
        sel_header = ctk.CTkFrame(self._visual_panel, fg_color="transparent")
        sel_header.pack(fill="x", padx=pad, pady=(0, 6))
        self._sel_lbl = ctk.CTkLabel(
            sel_header, text="Click pages to select them for export",
            font=T.FONT_SMALL, text_color=T.TEXT_SECONDARY, anchor="w",
        )
        self._sel_lbl.pack(side="left")
        GhostButton(sel_header, text="Select all", width=90, height=26,
                    font=T.FONT_SMALL,
                    command=self._select_all).pack(side="right", padx=(4, 0))
        GhostButton(sel_header, text="Clear", width=60, height=26,
                    font=T.FONT_SMALL,
                    command=self._clear_selection).pack(side="right")

        self._thumb_scroll = ctk.CTkScrollableFrame(
            self._visual_panel, fg_color="transparent",
            scrollbar_button_color=T.BORDER,
            scrollbar_button_hover_color=T.ACCENT,
            height=260,
        )
        self._thumb_scroll.pack(fill="both", expand=True, padx=pad)

        # panel 3, nothing to configure
        self._indiv_panel = ctk.CTkFrame(self, fg_color=T.BG_CARD,
                                          corner_radius=T.RADIUS)
        ctk.CTkLabel(
            self._indiv_panel,
            text="Every page will be saved as a separate PDF file.",
            font=T.FONT_BODY, text_color=T.TEXT_SECONDARY,
        ).pack(padx=T.PAD, pady=T.PAD)

        self._ranges_panel.pack(fill="x", pady=(0, T.PAD))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=pad, pady=(0, pad), side="bottom")
        self._progress = ProgressRow(bottom)
        self._progress.pack(fill="x")
        self._status = StatusBanner(bottom)
        self._status.pack(fill="x")
        AccentButton(bottom, text="Split PDF →",
                     command=self._run_split, width=160).pack(pady=(8, 0))

    def _on_mode_change(self, value: str):
        self._ranges_panel.pack_forget()
        self._visual_panel.pack_forget()
        self._indiv_panel.pack_forget()

        if value == _SEG_RANGES:
            self._mode = _MODE_RANGES
            self._ranges_panel.pack(fill="x", pady=(0, T.PAD))
        elif value == _SEG_VISUAL:
            self._mode = _MODE_VISUAL
            self._visual_panel.pack(fill="x", pady=(0, T.PAD))
            if self._file and not self._thumb_widgets:
                self._load_thumbnails()
        else:
            self._mode = _MODE_INDIV
            self._indiv_panel.pack(fill="x", pady=(0, T.PAD))

    def _load_file(self, paths: list[str]):
        path = paths[0]
        if not path.lower().endswith(".pdf"):
            self._status.show("Please select a PDF file.", error=True)
            return
        self._file = path
        self._selected.clear()
        self._thumb_widgets.clear()
        self._thumb_num_lbls.clear()
        self._thumb_imgs.clear()
        try:
            self._total_pages = get_page_count(path)
        except Exception as e:
            self._status.show(str(e), error=True)
            return
        self._fname_lbl.configure(text=Path(path).name,
                                   text_color=T.TEXT_PRIMARY)
        self._page_lbl.configure(
            text=f"{self._total_pages} page{'s' if self._total_pages != 1 else ''}")
        if self._mode == _MODE_VISUAL:
            self._load_thumbnails()

    def _load_thumbnails(self):
        if not self._file:
            return
        for w in self._thumb_scroll.winfo_children():
            w.destroy()
        self._thumb_widgets.clear()
        self._thumb_num_lbls.clear()
        self._thumb_imgs.clear()
        self._sel_lbl.configure(text="Loading thumbnails…")

        def _do():
            imgs = []
            for i in range(self._total_pages):
                try:
                    img = get_page_thumbnail(self._file, i, size=100)
                except Exception:
                    img = Image.new("RGB", (80, 110), color="#333333")
                imgs.append(img)
            self.after(0, lambda: self._render_thumbnails(imgs))

        threading.Thread(target=_do, daemon=True).start()

    def _render_thumbnails(self, imgs: list[Image.Image]):
        self._thumb_imgs.clear()
        self._thumb_num_lbls.clear()
        for i, img in enumerate(imgs):
            tk_img = ctk.CTkImage(light_image=img, dark_image=img,
                                  size=(img.width, img.height))
            self._thumb_imgs.append(tk_img)

            card = ctk.CTkFrame(
                self._thumb_scroll, fg_color=T.BG_CARD,
                corner_radius=6, border_width=2, border_color=T.BORDER,
                width=110, height=140,
            )
            card.pack_propagate(False)

            lbl = ctk.CTkLabel(card, image=tk_img, text="")
            lbl.pack(pady=(6, 2))
            num_lbl = ctk.CTkLabel(card, text=str(i + 1), font=T.FONT_SMALL,
                                    text_color=T.TEXT_MUTED)
            num_lbl.pack()

            for w in (card, lbl, num_lbl):
                w.bind("<Button-1>", lambda _e, idx=i, c=card, nl=num_lbl:
                       self._toggle_page(idx, c, nl))

            # 5 thumbnails per row
            col = i % 5
            row = i // 5
            card.grid_forget()
            card.pack_forget()
            card.place_forget()
            card.grid(in_=self._thumb_scroll, row=row, column=col,
                      padx=4, pady=4, sticky="nw")
            self._thumb_widgets.append(card)
            self._thumb_num_lbls.append(num_lbl)

        self._sel_lbl.configure(text="Click pages to include in the split")

    def _toggle_page(self, idx: int, card: ctk.CTkFrame, num_lbl: ctk.CTkLabel):
        if idx in self._selected:
            self._selected.discard(idx)
            card.configure(border_color=T.BORDER)
            num_lbl.configure(text_color=T.TEXT_MUTED)
        else:
            self._selected.add(idx)
            card.configure(border_color=T.ACCENT)
            num_lbl.configure(text_color=T.ACCENT)
        n = len(self._selected)
        self._sel_lbl.configure(
            text=f"{n} page{'s' if n != 1 else ''} selected"
            if n else "Click pages to include in the split"
        )

    def _select_all(self):
        for i, (card, num_lbl) in enumerate(
            zip(self._thumb_widgets, self._thumb_num_lbls)
        ):
            self._selected.add(i)
            card.configure(border_color=T.ACCENT)
            num_lbl.configure(text_color=T.ACCENT)
        self._sel_lbl.configure(text=f"All {self._total_pages} pages selected")

    def _clear_selection(self):
        self._selected.clear()
        for card, num_lbl in zip(self._thumb_widgets, self._thumb_num_lbls):
            card.configure(border_color=T.BORDER)
            num_lbl.configure(text_color=T.TEXT_MUTED)
        self._sel_lbl.configure(text="Click pages to include in the split")

    def _run_split(self):
        if self._running:
            return
        if not self._file:
            self._status.show("Select a PDF file first.", error=True)
            return

        out_dir = filedialog.askdirectory(title="Choose output folder for split PDFs")
        if not out_dir:
            return

        try:
            _do = self._build_split_task(out_dir)
        except ValueError as e:
            self._status.show(str(e), error=True)
            return

        self._running = True
        self._progress.start("Splitting…")
        self._status.pack_forget()

        def _done(result):
            self._running = False
            n = len(result)
            self._progress.finish(f"Saved {n} file{'s' if n != 1 else ''} → {out_dir}")
            self._status.show(f"Done. {n} file(s) written to {out_dir}")

        def _err(exc):
            self._running = False
            self._progress.finish(str(exc), error=True)
            self._status.show(str(exc), error=True)

        run_in_thread(_do, _done, _err, self)

    def _build_split_task(self, out_dir: str):
        # returns the work function for the current mode, raises ValueError
        # if the inputs make no sense
        src = self._file

        if self._mode == _MODE_RANGES:
            raw = self._range_entry.get().strip()
            if not raw:
                raise ValueError("Enter page ranges first.")
            ranges = parse_page_ranges(raw, self._total_pages)

            def _do():
                return split_by_ranges(src, out_dir, ranges,
                                       progress_callback=self._on_progress)

        elif self._mode == _MODE_VISUAL:
            if not self._selected:
                raise ValueError("Select at least one page first.")
            pages = sorted(self._selected)

            def _do():
                from pypdf import PdfReader, PdfWriter
                reader = PdfReader(src)
                writer = PdfWriter()
                for p in pages:
                    writer.add_page(reader.pages[p])
                out_path = Path(out_dir) / f"{Path(src).stem}_selection.pdf"
                with open(out_path, "wb") as f:
                    writer.write(f)
                self.after(0, lambda: self._on_progress(1.0))
                return [out_path]

        else:  # _MODE_INDIV
            def _do():
                return split_into_individual(src, out_dir,
                                             progress_callback=self._on_progress)

        return _do

    def _on_progress(self, value: float):
        self.after(0, lambda v=value: self._progress.update(v))


