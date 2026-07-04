from __future__ import annotations

from pathlib import Path
from typing import Callable


def get_pdfs_in_folder(folder_path: str) -> list[Path]:
    """Sorted .pdf files in a folder, not recursive."""
    return sorted(Path(folder_path).glob("*.pdf"))


def batch_compress(
    folder_path: str,
    output_dir: str,
    level: str = "medium",
    progress_callback=None,
) -> tuple[list[Path], list[tuple[Path, str]]]:
    from .compress import compress_pdf
    return _run_batch(
        folder_path, output_dir,
        compress_pdf,
        op_kwargs={"level": level},
        progress_callback=progress_callback,
    )


def batch_rotate(
    folder_path: str,
    output_dir: str,
    rotation: int = 90,
    progress_callback=None,
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Rotate every page of every PDF by the same angle."""
    from pypdf import PdfReader, PdfWriter

    def _rotate_all(input_path, output_path, rotation=90, **_):
        reader = PdfReader(str(input_path))
        writer = PdfWriter()
        for page in reader.pages:
            page.rotate(rotation)
            writer.add_page(page)
        with open(str(output_path), "wb") as f:
            writer.write(f)

    return _run_batch(
        folder_path, output_dir,
        _rotate_all,
        op_kwargs={"rotation": rotation},
        progress_callback=progress_callback,
    )


def batch_to_images(
    folder_path: str,
    output_dir: str,
    fmt: str = "png",
    dpi: int = 150,
    progress_callback=None,
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Export every page of every PDF as images, one subfolder per PDF."""
    from .pdf_to_image import pdf_to_images

    pdfs = get_pdfs_in_folder(folder_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(pdfs)
    results, errors = [], []

    for i, pdf in enumerate(pdfs):
        sub_dir = output_dir / pdf.stem
        try:
            created = pdf_to_images(str(pdf), str(sub_dir), fmt=fmt, dpi=dpi)
            results.extend(created)
        except Exception as exc:
            errors.append((pdf, str(exc)))

        if progress_callback:
            progress_callback((i + 1) / total)

    return results, errors


def _run_batch(
    folder_path: str,
    output_dir: str,
    operation: Callable,
    op_kwargs: dict | None = None,
    progress_callback=None,
) -> tuple[list[Path], list[tuple[Path, str]]]:
    # run operation(input, output, **kwargs) on every PDF, collect failures
    # instead of dying on the first bad file
    op_kwargs = op_kwargs or {}
    pdfs = get_pdfs_in_folder(folder_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(pdfs)
    results, errors = [], []

    for i, pdf in enumerate(pdfs):
        out_path = output_dir / pdf.name
        try:
            operation(str(pdf), str(out_path), **op_kwargs)
            results.append(out_path)
        except Exception as exc:
            errors.append((pdf, str(exc)))

        if progress_callback:
            progress_callback((i + 1) / total)

    return results, errors
