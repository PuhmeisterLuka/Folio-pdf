import json
import platform
import sys
from pathlib import Path

import customtkinter as ctk

_plat = platform.system()

# system fonts per platform, tk falls back to something ugly otherwise
if _plat == "Darwin":
    _DISPLAY = "SF Pro Display"
    _TEXT    = "SF Pro Text"
    _MONO    = "Menlo"
elif _plat == "Windows":
    _DISPLAY = "Segoe UI"
    _TEXT    = "Segoe UI"
    _MONO    = "Consolas"
else:
    _DISPLAY = "DejaVu Sans"
    _TEXT    = "DejaVu Sans"
    _MONO    = "DejaVu Sans Mono"

_DARK = {
    "BG_MAIN":    "#1C1A17",
    "BG_SIDEBAR": "#28251F",
    "BG_CARD":    "#2E2A23",
    "BG_INPUT":   "#2E2A23",
    "BG_HOVER":   "#332F28",
    "ACCENT":       "#C49A3C",
    "ACCENT_HOVER": "#E8C46A",
    "ACCENT_DIM":   "#3D3523",  # roughly the accent at 13% over the sidebar color
    "ACCENT_TEXT":  "#0F0C06",
    "TEXT_PRIMARY":   "#F5F0E8",
    "TEXT_SECONDARY": "#A09A8E",
    "TEXT_MUTED":     "#6B6560",
    "BORDER":  "#3A3530",
    "SUCCESS": "#4ADE80",
    "ERROR":   "#F87171",
    "WARNING": "#FBBF24",
    "APPEARANCE_MODE": "dark",
}

_LIGHT = {
    "BG_MAIN":    "#F9F5EE",
    "BG_SIDEBAR": "#EDE6DA",
    "BG_CARD":    "#FFFEFB",
    "BG_INPUT":   "#F3EDE3",
    "BG_HOVER":   "#E8DED0",
    "ACCENT":       "#9A6E1E",
    "ACCENT_HOVER": "#7D5818",
    "ACCENT_DIM":   "#F5E4BC",
    "ACCENT_TEXT":  "#FFFEFB",
    "TEXT_PRIMARY":   "#1A1510",
    "TEXT_SECONDARY": "#6B5E4E",
    "TEXT_MUTED":     "#A89880",
    "BORDER":  "#D8CFBF",
    "SUCCESS": "#16A34A",
    "ERROR":   "#DC2626",
    "WARNING": "#B45309",
    "APPEARANCE_MODE": "light",
}

_PALETTES = {"dark": _DARK, "light": _LIGHT}

# module level color constants, apply() rewrites these in place so every
# screen can just read T.ACCENT etc. without caring which theme is active
CURRENT = "dark"

BG_MAIN    = _DARK["BG_MAIN"]
BG_SIDEBAR = _DARK["BG_SIDEBAR"]
BG_CARD    = _DARK["BG_CARD"]
BG_INPUT   = _DARK["BG_INPUT"]
BG_HOVER   = _DARK["BG_HOVER"]

ACCENT       = _DARK["ACCENT"]
ACCENT_HOVER = _DARK["ACCENT_HOVER"]
ACCENT_DIM   = _DARK["ACCENT_DIM"]
ACCENT_TEXT  = _DARK["ACCENT_TEXT"]

TEXT_PRIMARY    = _DARK["TEXT_PRIMARY"]
TEXT_SECONDARY  = _DARK["TEXT_SECONDARY"]
TEXT_MUTED      = _DARK["TEXT_MUTED"]

BORDER          = _DARK["BORDER"]
SUCCESS         = _DARK["SUCCESS"]
ERROR           = _DARK["ERROR"]
WARNING         = _DARK["WARNING"]
APPEARANCE_MODE = _DARK["APPEARANCE_MODE"]

FONT_H1    = (_DISPLAY, 20, "bold")
FONT_H2    = (_DISPLAY, 15, "bold")
FONT_BODY  = (_TEXT,    13)
FONT_SMALL = (_TEXT,    11)
FONT_MONO  = (_MONO,    12)

SIDEBAR_W = 210
WIN_W     = 1100
WIN_H     = 720
RADIUS    = 8
PAD       = 16
PAD_S     = 8
THUMB_H   = 140


def apply(name: str, *, set_ctk_mode: bool = True) -> None:
    """Point every color constant at the named palette."""
    if name not in _PALETTES:
        raise ValueError(f"Unknown theme '{name}'. Choose from: {list(_PALETTES)}")
    palette = _PALETTES[name]
    module = sys.modules[__name__]
    for key, value in palette.items():
        setattr(module, key, value)
    module.CURRENT = name
    if set_ctk_mode:
        ctk.set_appearance_mode(palette["APPEARANCE_MODE"])


_PREFS_PATH = Path.home() / ".foliopdf_prefs.json"


def load_prefs() -> dict:
    try:
        return json.loads(_PREFS_PATH.read_text())
    except Exception:
        return {}


def save_prefs(data: dict) -> None:
    try:
        existing = load_prefs()
        existing.update(data)
        _PREFS_PATH.write_text(json.dumps(existing))
    except Exception:
        pass
