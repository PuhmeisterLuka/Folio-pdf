"""Regenerate the sidebar icon PNGs from the SVG sources in assets/icons/.

Only needed when adding or swapping an icon, the PNGs are committed.

    pip install cairosvg pillow
    python setup_icons.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

try:
    import cairosvg
except ImportError:
    sys.exit("cairosvg not installed. Run: pip install cairosvg")

from PIL import Image

ICONS_DIR = Path(__file__).parent / "assets" / "icons"

# output name -> source svg (the svgs are Feather icons)
ICON_MAP = {
    "merge":        "merge.svg",
    "split":        "scissors.svg",
    "compress":     "minimize-2.svg",
    "rotate":       "rotate-cw.svg",
    "batch":        "layers.svg",
    "pdf_to_image": "image.svg",
    "word_to_pdf":  "file-text.svg",
}


def _svg_to_png(src: Path, size: int) -> Image.Image:
    png_bytes = cairosvg.svg2png(
        url=str(src), output_width=size, output_height=size
    )
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")


def main() -> None:
    missing = []

    for name, svg_file in ICON_MAP.items():
        src = ICONS_DIR / svg_file
        if not src.exists():
            print(f"  WARNING: {src} not found, skipping {name}")
            missing.append(name)
            continue

        # render at 40x40, CTkImage downscales to 20 on regular displays
        # and uses the full 40 on retina
        dest = ICONS_DIR / f"{name}.png"
        _svg_to_png(src, 40).save(dest, "PNG")
        print(f"  {dest.relative_to(Path(__file__).parent)}")

    if missing:
        print(f"\n{len(missing)} icon(s) skipped: {', '.join(missing)}")
        print("Add the missing SVGs to assets/icons/ and run this again.")
    else:
        print(f"\nAll {len(ICON_MAP)} icons written to {ICONS_DIR}/")


if __name__ == "__main__":
    main()
