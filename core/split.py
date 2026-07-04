from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter, PdfReader


def parse_page_ranges(range_str: str, total_pages: int) -> list[tuple[int, int]]:
    """Turn input like "1-3, 5, 7-9" into a list of 0-indexed (start, end) tuples."""
    ranges = []
    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                a, _, b = part.partition("-")
                start, end = int(a.strip()), int(b.strip())
            else:
                start = end = int(part)
        except ValueError:
            raise ValueError(f"Can't read '{part}' as a page number or range.") from None

        if start < 1 or end < start or end > total_pages:
            raise ValueError(
                f"Invalid range '{part}' for a {total_pages}-page document."
            )
        ranges.append((start - 1, end - 1))

    if not ranges:
        raise ValueError("No valid page ranges provided.")
    return ranges


def split_by_ranges(
    input_path: str,
    output_dir: str,
    page_ranges: list[tuple[int, int]],
    progress_callback=None,
) -> list[Path]:
    """Write one PDF per range, returns the created paths."""
    reader = PdfReader(str(input_path))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(input_path).stem
    total = len(page_ranges)
    results = []

    for i, (start, end) in enumerate(page_ranges):
        writer = PdfWriter()
        for page_num in range(start, min(end + 1, len(reader.pages))):
            writer.add_page(reader.pages[page_num])

        out_path = output_dir / f"{stem}_pages_{start + 1}-{end + 1}.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)
        results.append(out_path)

        if progress_callback:
            progress_callback((i + 1) / total)

    return results


def split_into_individual(
    input_path: str,
    output_dir: str,
    progress_callback=None,
) -> list[Path]:
    """Save every page as its own PDF, returns the created paths."""
    reader = PdfReader(str(input_path))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(input_path).stem
    total = len(reader.pages)
    results = []

    for i, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        out_path = output_dir / f"{stem}_page_{i + 1:03d}.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)
        results.append(out_path)

        if progress_callback:
            progress_callback((i + 1) / total)

    return results
