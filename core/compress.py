import io
from pathlib import Path

import fitz  # PyMuPDF


# save() kwargs per compression level
_SAVE_OPTS = {
    "low": dict(garbage=1, deflate=True),
    "medium": dict(garbage=3, deflate=True, clean=True),
    "high": dict(garbage=4, deflate=True, clean=True, deflate_images=True, deflate_fonts=True),
}

# jpeg quality when re-encoding embedded images
_IMAGE_QUALITY = {"low": 85, "medium": 65, "high": 45}

# downscale images whose longer edge is above this
_MAX_DIM = {"low": 2000, "medium": 1600, "high": 1200}


def compress_pdf(
    input_path: str,
    output_path: str,
    level: str = "medium",
    progress_callback=None,
) -> dict:
    """Compress a PDF, returns input_size / output_size / ratio in a dict."""
    if level not in _SAVE_OPTS:
        raise ValueError(f"level must be one of {list(_SAVE_OPTS.keys())}")

    input_path = Path(input_path)
    input_size = input_path.stat().st_size

    doc = fitz.open(str(input_path))
    total_pages = len(doc)

    if progress_callback:
        progress_callback(0.05)

    # low is just a lossless repack, medium and high also touch the images
    if level in ("medium", "high"):
        _recompress_images(doc, level, total_pages, progress_callback)

    if progress_callback:
        progress_callback(0.85)

    doc.save(str(output_path), **_SAVE_OPTS[level])
    doc.close()

    if progress_callback:
        progress_callback(1.0)

    output_size = Path(output_path).stat().st_size
    ratio = (1 - output_size / input_size) * 100 if input_size else 0
    return {"input_size": input_size, "output_size": output_size, "ratio": ratio}


def _recompress_images(doc: fitz.Document, level: str, total_pages: int, progress_callback):
    # re-encode big raster images at lower jpeg quality, in place
    from PIL import Image

    quality = _IMAGE_QUALITY[level]
    max_dim = _MAX_DIM[level]

    for page_num in range(total_pages):
        page = doc[page_num]
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                base = doc.extract_image(xref)
                ext = base.get("ext", "")
                if ext not in ("jpeg", "jpg", "png", "bmp", "tiff"):
                    continue

                img = Image.open(io.BytesIO(base["image"]))

                w, h = img.size
                if w > max_dim or h > max_dim:
                    scale = min(max_dim / w, max_dim / h)
                    img = img.resize(
                        (int(w * scale), int(h * scale)), Image.LANCZOS
                    )

                # jpeg can't do alpha
                if img.mode in ("RGBA", "P", "L"):
                    img = img.convert("RGB")

                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                doc.update_stream(xref, buf.getvalue())
            except Exception:
                # some images just won't cooperate, skip them
                continue

        if progress_callback:
            # image pass owns the 0.05 to 0.85 slice of the bar
            progress_callback(0.05 + 0.80 * (page_num + 1) / total_pages)
