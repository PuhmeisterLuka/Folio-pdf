from pypdf import PdfWriter, PdfReader


def merge_pdfs(input_paths: list, output_path: str, progress_callback=None) -> None:
    """Merge PDFs into a single file, in the order given."""
    writer = PdfWriter()
    total = len(input_paths)

    for i, path in enumerate(input_paths):
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)
        if progress_callback:
            progress_callback((i + 1) / total)

    with open(str(output_path), "wb") as f:
        writer.write(f)
