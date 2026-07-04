"""Widgets shared by more than one screen."""
from __future__ import annotations

import re
from threading import Thread
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ui import theme as T


def parse_drop_paths(data: str) -> list[str]:
    # tkinterdnd2 hands over one string, paths with spaces come wrapped in {}
    paths = re.findall(r"\{([^}]+)\}|(\S+)", data)
    return [p[0] or p[1] for p in paths]


def human_size(n_bytes: int) -> str:
    size = float(n_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def run_in_thread(fn, on_done, on_err, root):
    """Run fn() on a daemon thread, hand the result or exception back on the main thread."""
    def _target():
        try:
            result = fn()
            root.after(0, lambda: on_done(result))
        except BaseException as exc:
            root.after(0, lambda e=exc: on_err(e))
    Thread(target=_target, daemon=True).start()


class SectionHeader(ctk.CTkFrame):
    def __init__(self, master, title: str, subtitle: str = "", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        ctk.CTkLabel(
            self, text=title, font=T.FONT_H1,
            text_color=T.TEXT_PRIMARY, anchor="w",
        ).pack(side="left")
        if subtitle:
            ctk.CTkLabel(
                self, text=subtitle, font=T.FONT_SMALL,
                text_color=T.TEXT_SECONDARY, anchor="w",
            ).pack(side="left", padx=(12, 0), pady=(4, 0))


class DropZone(ctk.CTkFrame):
    """File target that takes both clicks and drops, calls on_files(paths)."""

    def __init__(
        self,
        master,
        on_files,
        label: str = "Drop PDF files here",
        sublabel: str = "or click to browse",
        filetypes: list[tuple] | None = None,
        multiple: bool = True,
        height: int = 120,
        **kw,
    ):
        super().__init__(
            master,
            fg_color=T.BG_CARD,
            border_color=T.BORDER,
            border_width=2,
            corner_radius=T.RADIUS,
            height=height,
            **kw,
        )
        self._on_files = on_files
        self._filetypes = filetypes or [("PDF files", "*.pdf")]
        self._multiple = multiple
        self._active = False

        self._icon = ctk.CTkLabel(self, text="⊕", font=(T._DISPLAY, 34, "bold"),
                                   text_color=T.ACCENT)
        self._icon.pack(pady=(18, 2))
        self._lbl = ctk.CTkLabel(self, text=label, font=T.FONT_BODY,
                                  text_color=T.TEXT_PRIMARY)
        self._lbl.pack()
        self._sub = ctk.CTkLabel(self, text=sublabel, font=T.FONT_SMALL,
                                  text_color=T.TEXT_SECONDARY)
        self._sub.pack(pady=(2, 14))

        # the child labels swallow clicks, so bind everything
        for w in (self, self._icon, self._lbl, self._sub):
            w.bind("<Button-1>", self._browse)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

        try:
            from tkinterdnd2 import DND_FILES
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
            self.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self.dnd_bind("<<DragLeave>>", self._on_drag_leave)
        except Exception:
            # no tkinterdnd2, clicking still works
            pass

    def _browse(self, _event=None):
        if self._multiple:
            paths = filedialog.askopenfilenames(filetypes=self._filetypes)
            if paths:
                self._on_files(list(paths))
        else:
            path = filedialog.askopenfilename(filetypes=self._filetypes)
            if path:
                self._on_files([path])

    def _on_drop(self, event):
        paths = parse_drop_paths(event.data)
        if paths:
            self._on_files(paths)
        self._reset_highlight()
        return event.action

    def _on_drag_enter(self, event):
        self.configure(border_color=T.ACCENT, fg_color=T.BG_HOVER)
        return event.action

    def _on_drag_leave(self, event):
        self._reset_highlight()
        return event.action

    def _reset_highlight(self):
        self.configure(border_color=T.BORDER, fg_color=T.BG_CARD)

    def _on_enter(self, _event=None):
        self.configure(fg_color=T.BG_HOVER, border_color=T.ACCENT)

    def _on_leave(self, _event=None):
        self.configure(fg_color=T.BG_CARD, border_color=T.BORDER)


class AccentButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", T.ACCENT)
        kw.setdefault("hover_color", T.ACCENT_HOVER)
        kw.setdefault("text_color", T.ACCENT_TEXT)
        kw.setdefault("font", (*T.FONT_BODY[:2], "bold"))
        kw.setdefault("corner_radius", T.RADIUS)
        kw.setdefault("height", 38)
        super().__init__(master, **kw)


class GhostButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("hover_color", T.BG_HOVER)
        kw.setdefault("text_color", T.TEXT_SECONDARY)
        kw.setdefault("border_color", T.BORDER)
        kw.setdefault("border_width", 1)
        kw.setdefault("font", T.FONT_BODY)
        kw.setdefault("corner_radius", T.RADIUS)
        kw.setdefault("height", 38)
        super().__init__(master, **kw)


class ProgressRow(ctk.CTkFrame):
    """Progress bar with a status line under it, hidden until start() is called."""

    def __init__(self, master, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._bar = ctk.CTkProgressBar(self, progress_color=T.ACCENT,
                                        fg_color=T.BG_INPUT, height=6,
                                        corner_radius=3)
        self._bar.set(0)
        self._bar.pack(fill="x")
        self._lbl = ctk.CTkLabel(self, text="", font=T.FONT_SMALL,
                                  text_color=T.TEXT_SECONDARY)
        self._lbl.pack(anchor="w", pady=(4, 0))
        self.pack_forget()

    def start(self, message: str = "Processing…"):
        self._bar.set(0)
        self._bar.configure(progress_color=T.ACCENT)
        self._lbl.configure(text=message, text_color=T.TEXT_SECONDARY)
        self.pack(fill="x", pady=(8, 0))

    def update(self, value: float, message: str = ""):
        self._bar.set(value)
        if message:
            self._lbl.configure(text=message)

    def finish(self, message: str = "Done", error: bool = False):
        self._bar.set(1.0)
        color = T.ERROR if error else T.SUCCESS
        self._bar.configure(progress_color=color)
        self._lbl.configure(text=message, text_color=color)

    def reset(self):
        # call this when a new file is loaded so old results don't linger
        self.pack_forget()
        self._bar.set(0)
        self._bar.configure(progress_color=T.ACCENT)
        self._lbl.configure(text="", text_color=T.TEXT_SECONDARY)

    def hide(self):
        self.pack_forget()


class StatusBanner(ctk.CTkFrame):
    """One-line result message. Successes fade after a few seconds, errors stay."""

    def __init__(self, master, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._lbl = ctk.CTkLabel(self, text="", font=T.FONT_BODY,
                                  text_color=T.SUCCESS, anchor="w",
                                  wraplength=700)
        self._lbl.pack(fill="x")
        self.pack_forget()
        self._after_id = None

    def show(self, message: str, error: bool = False, duration_ms: int | None = None):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        color = T.ERROR if error else T.SUCCESS
        self._lbl.configure(text=message, text_color=color)
        self.pack(fill="x", pady=(6, 0))
        if not error:
            ms = duration_ms if duration_ms is not None else 6000
            self._after_id = self.after(ms, self.pack_forget)

    def show_persistent(self, message: str, error: bool = False):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        color = T.ERROR if error else T.SUCCESS
        self._lbl.configure(text=message, text_color=color)
        self.pack(fill="x", pady=(6, 0))


class Divider(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=T.BORDER, height=1, **kw)


class FileRow(ctk.CTkFrame):
    """One entry in the merge list."""

    def __init__(self, master, path: str, index: int, on_remove, on_up, on_down, **kw):
        super().__init__(master, fg_color=T.BG_CARD, corner_radius=6, **kw)
        self.path = path
        self.index = index

        handle = ctk.CTkLabel(self, text="⠿", font=(T._TEXT, 18),
                               text_color=T.TEXT_MUTED, width=28, cursor="fleur")
        handle.pack(side="left", padx=(8, 4))

        self._idx_lbl = ctk.CTkLabel(self, text=f"{index + 1}", width=22,
                                      font=T.FONT_SMALL, text_color=T.ACCENT)
        self._idx_lbl.pack(side="left", padx=4)

        name = Path(path).name
        name_disp = name if len(name) <= 48 else name[:45] + "…"
        ctk.CTkLabel(self, text=name_disp, font=T.FONT_BODY,
                     text_color=T.TEXT_PRIMARY, anchor="w").pack(
            side="left", fill="x", expand=True, padx=4)

        # buttons are a bit oversized on purpose, small click targets are annoying
        ctk.CTkButton(self, text="↑", width=36, height=32,
                      fg_color="transparent", hover_color=T.BG_HOVER,
                      text_color=T.TEXT_SECONDARY, font=T.FONT_BODY,
                      command=on_up).pack(side="right", padx=2)
        ctk.CTkButton(self, text="↓", width=36, height=32,
                      fg_color="transparent", hover_color=T.BG_HOVER,
                      text_color=T.TEXT_SECONDARY, font=T.FONT_BODY,
                      command=on_down).pack(side="right", padx=2)
        ctk.CTkButton(self, text="✕", width=36, height=32,
                      fg_color="transparent", hover_color="#4A1A1A",
                      text_color=T.TEXT_MUTED, font=T.FONT_BODY,
                      command=on_remove).pack(side="right", padx=(2, 6))

    def update_index(self, index: int):
        self.index = index
        self._idx_lbl.configure(text=f"{index + 1}")
