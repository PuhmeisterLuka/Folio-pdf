from __future__ import annotations


import fitz  # PyMuPDF, only used for rendering thumbnails
from pypdf import PdfReader, PdfWriter
from PIL import Image


def get_page_thumbnail(pdf_path: str, page_index: int, size: int = 160) -> Image.Image:
    doc = fitz.open(str(pdf_path))
    page = doc[page_index]
    rect = page.rect
    scale = size / max(rect.width, rect.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    doc.close()
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def get_all_thumbnails(pdf_path: str, size: int = 160):
    """Yield (page_index, PIL image) for every page, opens the document once."""
    doc = fitz.open(str(pdf_path))
    try:
        for i, page in enumerate(doc):
            rect = page.rect
            scale = size / max(rect.width, rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            yield i, Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()


class ThumbnailLoader:
    """Keeps a document open so pages can be rendered one at a time.

    Not thread safe, use one loader per thread.
    """

    def __init__(self, pdf_path: str, size: int = 160):
        self._doc = fitz.open(str(pdf_path))
        self._size = size

    def render(self, page_index: int) -> Image.Image:
        page = self._doc[page_index]
        rect = page.rect
        scale = self._size / max(rect.width, rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def close(self):
        self._doc.close()


def rotate_and_reorder(
    input_path: str,
    output_path: str,
    new_order: list[int],
    rotations: dict[int, int],
    progress_callback=None,
) -> None:
    """Write a new PDF with pages in new_order (0-indexed original page numbers).

    rotations maps original page number to clockwise degrees, pages not in the
    dict are left alone.
    """
    reader = PdfReader(str(input_path))
    writer = PdfWriter()
    total = len(new_order)

    for i, page_idx in enumerate(new_order):
        page = reader.pages[page_idx]
        rotation = rotations.get(page_idx, 0)
        if rotation:
            page.rotate(rotation)
        writer.add_page(page)

        if progress_callback:
            progress_callback((i + 1) / total)

    with open(str(output_path), "wb") as f:
        writer.write(f)
