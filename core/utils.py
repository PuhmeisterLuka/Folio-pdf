from pypdf import PdfReader


def get_page_count(pdf_path: str) -> int:
    return len(PdfReader(str(pdf_path)).pages)
