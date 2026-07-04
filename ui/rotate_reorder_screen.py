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
from core.rotate_reorder import ThumbnailLoader, rotate_and_reorder
from core.utils import get_page_count


class ThumbnailCard(ctk.CTkFrame):
    """One page in the grid, with its own rotate buttons."""

    def __init__(self, master, page_idx: int, img: Image.Image,
                 on_select, on_rotate_cw, on_rotate_ccw, **kw):
        super().__init__(
            master, fg_color=T.BG_CARD, corner_radius=6,
            border_width=2, border_color=T.BORDER,
            width=120, height=168, **kw
        )
        self.pack_propagate(False)
        self.orig_idx = page_idx   # page number in the source PDF, never changes
        self.slot_idx = page_idx   # where the card currently sits in the grid
        self._rotation = 0         # accumulated rotation, 0/90/180/270
        self._selected = False
        self._on_select = on_select

        self._tk_img = ctk.CTkImage(light_image=img, dark_image=img,
                                    size=(img.width, img.height))
        self._img_lbl = ctk.CTkLabel(self, image=self._tk_img, text="",
                                      cursor="fleur")
        self._img_lbl.pack(pady=(6, 2))

        self._num_lbl = ctk.CTkLabel(self, text=str(page_idx + 1),
                                      font=T.FONT_SMALL, text_color=T.TEXT_MUTED)
        self._num_lbl.pack()

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(2, 4))
        ctk.CTkButton(btn_row, text="↺", width=30, height=22,
                      fg_color="transparent", hover_color=T.BG_HOVER,
                      text_color=T.TEXT_SECONDARY, font=("SF Pro Text", 14),
                      command=on_rotate_ccw).pack(side="left", padx=1)
        ctk.CTkButton(btn_row, text="↻", width=30, height=22,
                      fg_color="transparent", hover_color=T.BG_HOVER,
                      text_color=T.TEXT_SECONDARY, font=("SF Pro Text", 14),
                      command=on_rotate_cw).pack(side="left", padx=1)

        for w in (self, self._img_lbl, self._num_lbl):
            w.bind("<Button-1>", self._click)

    def _click(self, _e=None):
        self._on_select(self)

    def set_selected(self, selected: bool):
        self._selected = selected
        self.configure(border_color=T.ACCENT if selected else T.BORDER)

    def update_image(self, img: Image.Image):
        self._tk_img = ctk.CTkImage(light_image=img, dark_image=img,
                                    size=(img.width, img.height))
        self._img_lbl.configure(image=self._tk_img)

    def update_slot(self, slot: int):
        self.slot_idx = slot
        self._num_lbl.configure(text=str(slot + 1))

    @property
    def rotation(self) -> int:
        return self._rotation

    def apply_rotation(self, delta: int, raw_img: Image.Image):
        self._rotation = (self._rotation + delta) % 360
        rotated = raw_img.rotate(-self._rotation, expand=True)
        rotated.thumbnail((100, 130), Image.LANCZOS)
        self.update_image(rotated)


class RotateReorderScreen(ctk.CTkFrame):
    _COLS = 6

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=T.BG_MAIN, **kw)
        self._file: str | None = None
        self._cards: list[ThumbnailCard] = []
        self._raw_imgs: list[Image.Image] = []   # unrotated originals, rotations re-render from these
        self._selected_card: ThumbnailCard | None = None
        self._drag_card: ThumbnailCard | None = None
        self._drag_start_slot: int = -1
        self._running = False
        self._load_gen = 0   # bumped on every load so a stale thumbnail thread knows to stop
        self._build_ui()

    def _build_ui(self):
        pad = T.PAD

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, 8))
        AccentButton(header, text="Save PDF →",
                     command=self._run_save, width=130).pack(side="right")
        SectionHeader(header, "Rotate & Reorder",
                      subtitle="Drag pages to reorder · click ↺↻ to rotate").pack(
            side="left", fill="x", expand=True)

        self._drop = DropZone(
            self,
            on_files=self._load_file,
            label="Drop a PDF file here",
            sublabel="or click to browse",
            multiple=False,
            height=90,
        )
        self._drop.pack(fill="x", padx=pad, pady=(0, 8))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=pad, pady=(0, 6))
        self._info_lbl = ctk.CTkLabel(
            toolbar, text="No file loaded",
            font=T.FONT_SMALL, text_color=T.TEXT_SECONDARY, anchor="w",
        )
        self._info_lbl.pack(side="left")

        GhostButton(toolbar, text="Rotate all ↺", width=110, height=28,
                    font=T.FONT_SMALL,
                    command=lambda: self._rotate_all(-90)).pack(side="right", padx=(4, 0))
        GhostButton(toolbar, text="Rotate all ↻", width=110, height=28,
                    font=T.FONT_SMALL,
                    command=lambda: self._rotate_all(90)).pack(side="right", padx=(4, 0))
        GhostButton(toolbar, text="Reset order", width=90, height=28,
                    font=T.FONT_SMALL,
                    command=self._reset_order).pack(side="right", padx=(4, 0))

        self._canvas_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=T.BORDER,
            scrollbar_button_hover_color=T.ACCENT,
        )
        self._canvas_frame.pack(fill="both", expand=True, padx=pad)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=pad, pady=(8, pad))
        self._progress = ProgressRow(bottom)
        self._progress.pack(fill="x")
        self._status = StatusBanner(bottom)
        self._status.pack(fill="x")

    def _load_file(self, paths: list[str]):
        path = paths[0]
        if not path.lower().endswith(".pdf"):
            self._status.show("Please select a PDF file.", error=True)
            return
        self._file = path
        self._selected_card = None
        try:
            n = get_page_count(path)
        except Exception as e:
            self._status.show(str(e), error=True)
            return

        noun = "page" if n == 1 else "pages"
        self._info_lbl.configure(text=f"Loading {n} {noun} thumbnail{'s' if n != 1 else ''}…")
        for w in self._canvas_frame.winfo_children():
            w.destroy()
        self._cards.clear()
        self._raw_imgs.clear()

        self._load_gen += 1
        gen = self._load_gen

        BATCH = 6

        def _worker():
            try:
                loader = ThumbnailLoader(path, size=T.THUMB_H)
            except Exception as e:
                self.after(0, lambda err=e: self._status.show(str(err), error=True))
                return

            start = 0
            while start < n:
                if gen != self._load_gen:
                    loader.close()
                    return
                end = min(start + BATCH, n)
                imgs: list[Image.Image] = []
                try:
                    for i in range(start, end):
                        imgs.append(loader.render(i))
                except Exception as e:
                    loader.close()
                    self.after(0, lambda err=e: self._status.show(str(err), error=True))
                    return
                batch_imgs = list(imgs)
                batch_start = start
                self.after(
                    0,
                    lambda bi=batch_imgs, bs=batch_start:
                        self._add_cards(bi, bs, n) if gen == self._load_gen else None,
                )
                start = end

            loader.close()

        threading.Thread(target=_worker, daemon=True).start()

    def _add_cards(self, imgs: list[Image.Image], start: int, total: int):
        for j, img in enumerate(imgs):
            i = start + j
            self._raw_imgs.append(img.copy())
            thumb = img.copy()
            thumb.thumbnail((100, 130), Image.LANCZOS)
            card = ThumbnailCard(
                self._canvas_frame, page_idx=i, img=thumb,
                on_select=self._on_card_select,
                on_rotate_cw=lambda idx=i: self._rotate_card(idx, 90),
                on_rotate_ccw=lambda idx=i: self._rotate_card(idx, -90),
            )
            row, col = i // self._COLS, i % self._COLS
            card.grid(row=row, column=col, padx=5, pady=5, sticky="nw")
            card._img_lbl.bind("<ButtonPress-1>", lambda e, c=card: self._drag_start(e, c))
            card._img_lbl.bind("<B1-Motion>", self._drag_motion)
            card._img_lbl.bind("<ButtonRelease-1>", self._drag_end)
            self._cards.append(card)

        loaded = start + len(imgs)
        if loaded < total:
            self._info_lbl.configure(text=f"Loading… {loaded}/{total} pages")
        else:
            self._info_lbl.configure(
                text=f"{total} page{'s' if total != 1 else ''}  ·  drag to reorder  ·  click ↺↻ to rotate"
            )

    def _on_card_select(self, card: ThumbnailCard):
        if self._selected_card and self._selected_card is not card:
            self._selected_card.set_selected(False)
        card.set_selected(True)
        self._selected_card = card

    def _rotate_card(self, orig_idx: int, delta: int):
        card = next((c for c in self._cards if c.orig_idx == orig_idx), None)
        if card is None:
            return
        raw = self._raw_imgs[orig_idx]
        card.apply_rotation(delta, raw)

    def _rotate_all(self, delta: int):
        for card in self._cards:
            card.apply_rotation(delta, self._raw_imgs[card.orig_idx])

    def _drag_start(self, event, card: ThumbnailCard):
        self._drag_card = card
        self._drag_start_slot = card.slot_idx
        card.configure(border_color=T.ACCENT, fg_color=T.BG_HOVER)

    def _drag_motion(self, event):
        if not self._drag_card:
            return
        # swap with whatever card the pointer is over right now
        x_root, y_root = event.x_root, event.y_root
        target = self._card_at(x_root, y_root)
        if target and target is not self._drag_card:
            self._swap_cards(self._drag_card, target)

    def _drag_end(self, _event):
        if self._drag_card:
            sel = self._selected_card is self._drag_card
            self._drag_card.configure(
                border_color=T.ACCENT if sel else T.BORDER,
                fg_color=T.BG_CARD,
            )
            self._drag_card = None

    def _card_at(self, x_root: int, y_root: int) -> ThumbnailCard | None:
        # walk up from the widget under the pointer until a card is found
        widget = self.winfo_containing(x_root, y_root)
        while widget is not None:
            if isinstance(widget, ThumbnailCard):
                return widget
            widget = getattr(widget, "master", None)
        return None

    def _swap_cards(self, a: ThumbnailCard, b: ThumbnailCard):
        slot_a, slot_b = a.slot_idx, b.slot_idx
        row_a, col_a = slot_a // self._COLS, slot_a % self._COLS
        row_b, col_b = slot_b // self._COLS, slot_b % self._COLS

        idx_a = self._cards.index(a)
        idx_b = self._cards.index(b)
        self._cards[idx_a], self._cards[idx_b] = self._cards[idx_b], self._cards[idx_a]

        a.update_slot(slot_b)
        b.update_slot(slot_a)

        a.grid(row=row_b, column=col_b, padx=5, pady=5, sticky="nw")
        b.grid(row=row_a, column=col_a, padx=5, pady=5, sticky="nw")

    def _reset_order(self):
        if not self._cards:
            return
        self._cards.sort(key=lambda c: c.orig_idx)
        for i, card in enumerate(self._cards):
            card.update_slot(i)
            row, col = i // self._COLS, i % self._COLS
            card.grid(row=row, column=col, padx=5, pady=5, sticky="nw")

    def _run_save(self):
        if self._running:
            return
        if not self._file:
            self._status.show("Load a PDF file first.", error=True)
            return

        out = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF file", "*.pdf")],
            initialfile=Path(self._file).stem + "_reordered.pdf",
            title="Save Reordered PDF",
        )
        if not out:
            return

        self._running = True
        self._progress.start("Saving…")
        self._status.pack_forget()

        src = self._file
        new_order = [c.orig_idx for c in self._cards]
        rotations = {c.orig_idx: c.rotation for c in self._cards if c.rotation != 0}

        def _do():
            rotate_and_reorder(src, out, new_order, rotations,
                                progress_callback=self._on_progress)

        def _done(_):
            self._running = False
            self._progress.finish(f"Saved → {Path(out).name}")
            self._status.show(f"Saved: {out}")

        def _err(exc):
            self._running = False
            self._progress.finish(str(exc), error=True)
            self._status.show(str(exc), error=True)

        run_in_thread(_do, _done, _err, self)

    def _on_progress(self, value: float):
        self.after(0, lambda v=value: self._progress.update(v))


