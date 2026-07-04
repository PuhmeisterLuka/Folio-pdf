from __future__ import annotations

import logging
import os
import sys
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from PIL import Image

# tkinterdnd2 has to be the Tk base class for drops to work, fall back to
# plain CTk if it is missing (everything works except drag and drop)
try:
    from tkinterdnd2 import TkinterDnD
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

from ui import theme as T
from ui.merge_screen import MergeScreen
from ui.split_screen import SplitScreen
from ui.compress_screen import CompressScreen
from ui.rotate_reorder_screen import RotateReorderScreen
from ui.batch_screen import BatchScreen
from ui.pdf_to_image_screen import PDFToImageScreen
from ui.word_to_pdf_screen import WordToPDFScreen

logger = logging.getLogger(__name__)

# theme choice is remembered between runs
ctk.set_default_color_theme("dark-blue")
_saved_theme = T.load_prefs().get("theme", "dark")
if _saved_theme not in ("dark", "light"):
    _saved_theme = "dark"
T.apply(_saved_theme)

_ASSETS_DIR = Path(__file__).parent / "assets"
_ICONS_DIR  = _ASSETS_DIR / "icons"


def _tint_icon(img: Image.Image, color_hex: str) -> Image.Image:
    # recolor a silhouette png, the alpha channel is the actual shape
    r = int(color_hex[1:3], 16)
    g = int(color_hex[3:5], 16)
    b = int(color_hex[5:7], 16)
    tinted = Image.new("RGBA", img.size, (r, g, b, 255))
    tinted.putalpha(img.getchannel("A"))
    return tinted


def _load_ctk_icon(name: str, color_hex: str) -> ctk.CTkImage | None:
    # icons ship as 40x40, CTkImage scales them down to 20 for regular displays
    path = _ICONS_DIR / f"{name}.png"
    if not path.exists():
        return None
    try:
        img = Image.open(path).convert("RGBA")
        tinted = _tint_icon(img, color_hex)
        return ctk.CTkImage(light_image=tinted, dark_image=tinted, size=(20, 20))
    except Exception:
        return None


# (label, icon name, screen class)
_NAV = [
    ("Merge",          "merge",        MergeScreen),
    ("Split",          "split",        SplitScreen),
    ("Compress",       "compress",     CompressScreen),
    ("Rotate/Reorder", "rotate",       RotateReorderScreen),
    ("Batch",          "batch",        BatchScreen),
    ("PDF to Image",   "pdf_to_image", PDFToImageScreen),
    ("Word to PDF",    "word_to_pdf",  WordToPDFScreen),
]

_NAV_MAP: dict[str, type] = {name: cls for name, _, cls in _NAV}

_THEME_BUTTONS = [
    ("dark",  "Dark"),
    ("light", "Light"),
]

_AppBase = TkinterDnD.Tk if _DND_AVAILABLE else ctk.CTk


class App(_AppBase):
    def __init__(self):
        super().__init__()
        if _DND_AVAILABLE:
            ctk.set_appearance_mode(T.APPEARANCE_MODE)

        self.title("Folio PDF")
        self.geometry(f"{T.WIN_W}x{T.WIN_H}")
        self.minsize(900, 600)
        self.configure(bg=T.BG_MAIN)
        self._set_icon()

        # macOS sends "open document" apple events during Word automation,
        # which can re-activate this app mid conversion. Swallow them.
        if sys.platform == "darwin":
            try:
                self.tk.createcommand("::tk::mac::OpenDocument", lambda *_: None)
            except Exception:
                pass

        self._screens: dict[str, ctk.CTkFrame] = {}
        self._active: str | None = None
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        self._nav_icons: dict[str, tuple] = {}   # name -> (normal_img, active_img)
        self._theme_btns: dict[str, ctk.CTkButton] = {}

        self._build_layout()
        self._navigate("Merge")

    def _set_icon(self):
        if sys.platform == "win32":
            ico_path = _ASSETS_DIR / "logo.ico"
            if ico_path.exists():
                try:
                    self.iconbitmap(str(ico_path))
                except Exception as e:
                    logger.warning("Icon load failed: %s", e)
        else:
            png_path = _ASSETS_DIR / "logo.png"
            if png_path.exists():
                try:
                    img = tk.PhotoImage(file=str(png_path))
                    self.iconphoto(True, img)
                except Exception as e:
                    logger.warning("Icon load failed: %s", e)

    def _build_layout(self):
        self._sidebar = ctk.CTkFrame(
            self, width=T.SIDEBAR_W, fg_color=T.BG_SIDEBAR,
            corner_radius=0,
        )
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        self._content = ctk.CTkFrame(self, fg_color=T.BG_MAIN, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()

    def _build_sidebar(self):
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(20, 8))
        ctk.CTkLabel(
            logo_frame, text="Folio",
            font=(T._DISPLAY, 22, "bold"),
            text_color=T.ACCENT,
        ).pack(side="left")
        ctk.CTkLabel(
            logo_frame, text="PDF",
            font=(T._DISPLAY, 22),
            text_color=T.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkFrame(self._sidebar, fg_color=T.BORDER, height=1).pack(
            fill="x", padx=12, pady=(4, 12))

        self._nav_icons = {}
        for name, icon_name, _ in _NAV:
            normal = _load_ctk_icon(icon_name, T.TEXT_SECONDARY)
            active = _load_ctk_icon(icon_name, T.ACCENT)
            self._nav_icons[name] = (normal, active)
            btn = ctk.CTkButton(
                self._sidebar,
                text=f"  {name}",
                image=normal,
                compound="left",
                anchor="w",
                height=40,
                fg_color="transparent",
                hover_color=T.BG_HOVER,
                text_color=T.TEXT_SECONDARY,
                font=T.FONT_BODY,
                corner_radius=8,
                command=lambda n=name: self._navigate(n),
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._nav_btns[name] = btn

        # after a theme switch the sidebar is rebuilt, restore the active button
        if self._active and self._active in self._nav_btns:
            _, active_img = self._nav_icons.get(self._active, (None, None))
            self._nav_btns[self._active].configure(
                fg_color=T.ACCENT_DIM,
                text_color=T.ACCENT,
                image=active_img,
            )

        # spacer pushes the theme switcher to the bottom
        ctk.CTkFrame(self._sidebar, fg_color="transparent").pack(
            fill="y", expand=True)

        ctk.CTkFrame(self._sidebar, fg_color=T.BORDER, height=1).pack(
            fill="x", padx=12, pady=(0, 8))

        self._build_theme_switcher()

        ctk.CTkLabel(
            self._sidebar,
            text="Everything stays\non your device",
            font=T.FONT_SMALL,
            text_color=T.TEXT_MUTED,
            justify="center",
        ).pack(pady=(4, 16))

    def _build_theme_switcher(self):
        row = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(0, 4))

        self._theme_btns = {}
        for theme_name, label in _THEME_BUTTONS:
            is_active = T.CURRENT == theme_name
            btn = ctk.CTkButton(
                row,
                text=label,
                width=54,
                height=28,
                fg_color=T.ACCENT_DIM if is_active else "transparent",
                hover_color=T.BG_HOVER,
                text_color=T.ACCENT if is_active else T.TEXT_SECONDARY,
                font=T.FONT_SMALL,
                corner_radius=6,
                command=lambda n=theme_name: self._set_theme(n),
            )
            btn.pack(side="left", padx=2)
            self._theme_btns[theme_name] = btn

    def _set_theme(self, name: str):
        if T.CURRENT == name:
            return

        T.apply(name, set_ctk_mode=False)
        T.save_prefs({"theme": name})

        # go through tk.Tk.configure directly. CTk monkey patches configure and
        # keeps references to destroyed sidebar widgets, so the patched version
        # throws TclError on every theme switch after the first one
        tk.Tk.configure(self, bg=T.BG_MAIN)
        self._content.configure(fg_color=T.BG_MAIN)

        # cheaper to rebuild the sidebar than to restyle every widget in it
        self._sidebar.destroy()
        self._sidebar = ctk.CTkFrame(
            self, width=T.SIDEBAR_W, fg_color=T.BG_SIDEBAR, corner_radius=0,
        )
        self._sidebar.pack(side="left", fill="y", before=self._content)
        self._sidebar.pack_propagate(False)
        self._nav_btns = {}
        self._theme_btns = {}
        self._build_sidebar()

        # cached screens hold old colors, drop them and let navigation rebuild
        for screen in self._screens.values():
            screen.destroy()
        self._screens.clear()

        active = self._active
        self._active = None
        self._navigate(active or "Merge")

        # tell CTk about the mode last, otherwise it redraws widgets that are
        # about to be destroyed
        ctk.set_appearance_mode(T.APPEARANCE_MODE)

    def _navigate(self, name: str):
        if self._active == name:
            return

        if self._active and self._active in self._nav_btns:
            normal_img, _ = self._nav_icons.get(self._active, (None, None))
            self._nav_btns[self._active].configure(
                fg_color="transparent",
                text_color=T.TEXT_SECONDARY,
                image=normal_img,
            )

        _, active_img = self._nav_icons.get(name, (None, None))
        self._nav_btns[name].configure(
            fg_color=T.ACCENT_DIM,
            text_color=T.ACCENT,
            image=active_img,
        )
        self._active = name

        for screen in self._screens.values():
            screen.pack_forget()

        if name not in self._screens:
            try:
                screen = _NAV_MAP[name](self._content)
                self._screens[name] = screen
            except Exception as e:
                logger.error("Failed to load screen '%s': %s", name, e)
                self._nav_btns[name].configure(
                    fg_color="transparent",
                    text_color=T.TEXT_SECONDARY,
                )
                self._active = None
                return

        self._screens[name].pack(fill="both", expand=True)


_LOCK_FILE = None  # must stay open for the lifetime of the process


def _acquire_single_instance_lock() -> bool:
    # returns False if another instance already holds the lock. fcntl only
    # exists on unix, which is fine since this is only called on macOS
    global _LOCK_FILE
    import fcntl

    lock_path = Path(os.path.expanduser("~")) / ".folio_pdf.lock"
    try:
        _LOCK_FILE = open(lock_path, "w")
        fcntl.flock(_LOCK_FILE, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def main():
    if sys.platform == "darwin" and not _acquire_single_instance_lock():
        sys.exit(0)

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
