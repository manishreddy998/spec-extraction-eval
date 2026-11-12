"""Deterministic extractors for the fields that have a fixed shape.

Each rule either returns a confident value or declines (returns MISSING). Declining is the
important part: a rule that guesses is worse than no rule, because the staged pipeline trusts
what rules return and only asks the LLM about fields the rules declined.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any

from .sections import first_page, section

MISSING = object()

CAS_RE = re.compile(r"\b(\d{2,7})-(\d{2})-(\d)\b")
CAS_LIKE_RE = re.compile(r"\b[\dBOlI]{2,7}-[\dBOlI]{2}-[\dBOlI]\b")
H_RE = re.compile(r"\bH(\d{3})\b")
UN_RE = re.compile(r"\bUN\s?(\d{4})\b")
NA_RE = re.compile(r"not applicable|not available|no data|\bn\.?\s?a\.?\b|\bn\.d\.?|none|does not flash|sans objet", re.I)


def cas_checksum_ok(cas: str) -> bool:
    """CAS numbers carry a check digit: weighted sum of the other digits, mod 10."""
    digits = cas.replace("-", "")
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (i + 1) for i, d in enumerate(reversed(body)))
    return total % 10 == check


def cas_numbers(text: str) -> Any:
    sec = section(text, 3)
    if not sec:
        return MISSING
    found = ["-".join(m.groups()) for m in CAS_RE.finditer(sec)]
    lookalikes = CAS_LIKE_RE.findall(sec)
    # corrupted characters (e.g. "6B-64-1") or a failed checksum mean the text can't be trusted
    if not found or len(lookalikes) > len(found) or not all(cas_checksum_ok(c) for c in found):
        return MISSING
    return list(dict.fromkeys(found))


def hazard_statements(text: str) -> Any:
    sec = section(text, 2)
    if not sec:
        return MISSING
    return sorted({f"H{c}" for c in H_RE.findall(sec)})  # empty list is a valid answer here


def signal_word(text: str) -> Any:
    sec = section(text, 2) or first_page(text)
    m = re.search(r"signal\s*w\s*ord[^\n:]*[:\-]?\s*\n?\s*:?\s*(danger|warning|none)\b", sec, re.I)
    if m:
        return m.group(1).capitalize()
    m = re.search(r"(?m)^\s*(DANGER|WARNING)\s*!\s*$", sec)
    return m.group(1).capitalize() if m else MISSING


def un_number(text: str) -> Any:
    sec = section(text, 14)
    if not sec:
        return MISSING
    codes = UN_RE.findall(sec)
    for line in re.findall(r"UN\s*(?:number|no\.?)\s*:?\s*([^\n]*)", sec, re.I):
        codes += re.findall(r"(?<![\d.])(\d{4})(?![\d.])", line)  # tables like "UN Number: N.A. 1950 1950"
    if codes:
        return f"UN{Counter(codes).most_common(1)[0][0]}"
    if re.search(r"not regulated|not dangerous goods|not classified as hazardous", sec, re.I):
        return None
    return MISSING


def _starts_na(win: str) -> bool:
    """True when the value right after a label is a 'not applicable'-style phrase."""
    return bool(NA_RE.match(win.lstrip(" :.,\t")))


def _corrupted(win: str) -> bool:
    """Digits glued to capital letters ('-1B.8') signal a broken font map in the PDF."""
    return bool(re.search(r"\d[ABD-EG-Z]\b|\b[A-Z]\d|\d[A-Z]\d", win))  # C and F after a digit are units


def _value_window(text: str, label: str) -> str | None:
    """The rest of the line after `label`, plus the next line (values often wrap)."""
    m = re.search(label + r"(.*)\n?(.*)", text, re.I)
    if not m:
        return None
    rest, nxt = m.group(1), m.group(2)
    return rest if re.search(r"\d|" + NA_RE.pattern, rest, re.I) else f"{rest} {nxt}"


def flash_point_c(text: str) -> Any:
    win = _value_window(section(text, 9) or text, r"flash\s*point")
    if win is None:
        return MISSING
    if _starts_na(win):
        return None
    if _corrupted(win) or re.search(r"\d\s*-\s*-?\d", win):  # broken text or a range: leave it to the LLM
        return MISSING
    num = r"(?<![\w.])(-?\d+(?:\.\d+)?)"
    celsius = re.findall(num + r"\s*°\s*C\b|°\s*C\s*:?\s*" + num, win)
    celsius = [a or b for a, b in celsius]
    if len(celsius) == 1:
        return float(celsius[0])
    fahrenheit = re.findall(num + r"\s*(?:°|o)?\s*F\b", win)
    if not celsius and len(fahrenheit) == 1:
        return round((float(fahrenheit[0]) - 32) * 5 / 9, 1)
    return MISSING


def ph(text: str) -> Any:
    win = _value_window(section(text, 9) or text, r"\bpH\b")
    if win is None:
        return MISSING
    if _starts_na(win):
        return None
    m = re.match(r"\s*[:.]?\s*(\d{1,2}(?:\.\d+)?)(?!\s*%)(?![\d.])", win)  # the value must come first
    if m and 0 <= float(m.group(1)) <= 14:
        return float(m.group(1))
    return MISSING


def physical_state(text: str) -> Any:
    m = re.search(r"physical\s*state\s*[:\-]?\s*(liquid|solid|gas)\b", section(text, 9) or text, re.I)
    return m.group(1).lower() if m else MISSING


_DATE_FORMATS = ["%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%B %d,%Y", "%d.%m.%Y"]
_DATE_RE = r"(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{2}\.\d{2}\.\d{4}|[A-Z][a-z]+ \d{1,2},\s?\d{4})"


def revision_date(text: str) -> Any:
    head = first_page(text)
    for label in (r"revision\s*date", r"revised\s*(on)?", r"revision", r"issue\s*date", r"date\s*of\s*issue"):
        m = re.search(label + r"\s*[:\-]?\s*\n?\s*" + _DATE_RE, head, re.I)
        if m:
            raw = m.group(m.lastindex).strip()
            for fmt in _DATE_FORMATS:
                try:
                    return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
    return MISSING


RULES = {
    "cas_numbers": cas_numbers,
    "hazard_statements": hazard_statements,
    "signal_word": signal_word,
    "un_number": un_number,
    "flash_point_c": flash_point_c,
    "ph": ph,
    "physical_state": physical_state,
    "revision_date": revision_date,
}


def apply_rules(text: str) -> dict[str, Any]:
    """Run every rule; fields a rule declines are left out of the result."""
    out = {}
    for field, rule in RULES.items():
        value = rule(text)
        if value is not MISSING:
            out[field] = value
    return out
