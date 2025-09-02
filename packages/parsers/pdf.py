from __future__ import annotations

from typing import List

import fitz  # PyMuPDF


def extract_pages_from_pdf_bytes(pdf_bytes: bytes) -> List[str]:
    """Extract plain text per page from PDF bytes using PyMuPDF.

    Returns a list of page texts in order.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: List[str] = []
    try:
        for page in doc:
            text = page.get_text("text")
            pages.append(text)
    finally:
        doc.close()
    return pages


