"""Locate GHS sections inside SDS text.

Every SDS follows the same 16-section order, but headings are written many ways:
"2. Hazard(s) identification", "SECTION 2: Hazards identification", "2 HAZARDS IDENTIFICATION".
We find a section by its number plus a keyword from its title, and end it at the next section.
"""
from __future__ import annotations

import re

HEADINGS: dict[int, str] = {
    1: r"identification|product and company",
    2: r"hazards? identification|hazard\(s\) identification|e?azard\(s\) idemtificatiom|eazard\(s\) identification",
    3: r"composition|information on ingredients",
    4: r"first[- ]aid",
    9: r"physical and chemical",
    10: r"stability and reactivity",
    14: r"transport(ation)? information",
    15: r"regulatory information",
}
_NEXT = {1: 2, 2: 3, 3: 4, 9: 10, 14: 15}


def _heading(n: int) -> re.Pattern:
    return re.compile(rf"(?im)^\s*(section\s*)?{n}\s*[\.:)\-]?\s*(\d+\.\s*)?({HEADINGS[n]})")


def section(text: str, n: int, fallback_chars: int = 8000, strict: bool = False) -> str:
    """Return the text of GHS section n, or '' when its heading can't be found.

    With strict=True the next section's heading must be found too; otherwise we can't tell where
    this section ends (corrupted headings), and a rule reading past the end would trust the wrong text.
    """
    start = _heading(n).search(text)
    if not start:
        return ""
    nxt = _NEXT.get(n)
    end = _heading(nxt).search(text, start.end()) if nxt else None
    if strict and nxt and not end:
        return ""
    stop = end.start() if end else start.start() + fallback_chars
    return text[start.start(): stop]


def first_page(text: str) -> str:
    """Text of page 1 (pages are marked with '[page N]' by pdf_text)."""
    parts = text.split("[page 2]", 1)
    return parts[0]
