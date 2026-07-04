from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def pdf_to_images(
    input_path: str,
    output_dir: str,
    fmt: str = "png",
    dpi: int = 150,
    pages: list[int] | None = None,
    progress_callback=None,
) -> list[Path]:
    """Render pages to png or jpg files. pages is a 0-indexed list, None means all."""
    fmt = fmt.lower().strip(".")
    if fmt == "jpeg":
        fmt = "jpg"
    if fmt not in ("png", "jpg"):
        raise ValueError("fmt must be 'png' or 'jpg'")

    doc = fitz.open(str(input_path))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(input_path).stem

    page_list = pages if pages is not None else list(range(len(doc)))
    total = len(page_list)
    results = []

    # fitz renders at 72 dpi unless you scale it
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)

    for i, page_num in enumerate(page_list):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat, alpha=False)

        out_path = output_dir / f"{stem}_page_{page_num + 1:03d}.{fmt}"

        if fmt == "jpg":
            pix.save(str(out_path), jpg_quality=90)
        else:
            pix.save(str(out_path))

        results.append(out_path)

        if progress_callback:
            progress_callback((i + 1) / total)

    doc.close()
    return results
