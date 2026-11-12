"""Turn SDS PDFs into plain text that both extraction methods share."""
from __future__ import annotations

import pathlib
import re

from pypdf import PdfReader


def pdf_to_text(path: pathlib.Path) -> str:
    """Extract text page by page, keeping page markers so evidence can be traced back."""
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"[page {i}]\n{normalize(text)}")
    return "\n\n".join(pages)


def normalize(text: str) -> str:
    """Light cleanup: unify whitespace and common PDF artifacts without changing content."""
    text = text.replace(" ", " ").replace("‐", "-").replace("‑", "-").replace("–", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
