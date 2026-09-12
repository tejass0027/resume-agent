"""PDF text extraction utilities."""

from __future__ import annotations

from typing import Optional

import pymupdf


def extract_text_from_pdf(file_bytes: bytes, filename: str) -> tuple[str, Optional[str]]:
    """Extract plain text from a PDF's raw bytes.

    Returns a (text, error) tuple. On success, error is None. On failure
    (corrupted file, password-protected, or a scanned image with no text
    layer), text is "" and error holds a human-readable reason.
    """
    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        return "", f"Could not open PDF: {exc}"

    try:
        if doc.is_encrypted and not doc.authenticate(""):
            return "", "PDF is password-protected."
        pages_text = [page.get_text("text") for page in doc]
    except Exception as exc:
        return "", f"Failed to extract text: {exc}"
    finally:
        doc.close()

    text = "\n".join(pages_text).strip()
    if not text:
        return "", "No extractable text found (likely a scanned image PDF without OCR)."

    return text, None
