"""Checks that decide whether an extracted value can be trusted without a human.

Five independent checks, all deterministic and free:
1. grounding     - the quoted evidence really exists in the source text
2. consistency   - the value can be read out of its own quote
3. validity      - the value obeys the domain's rules (CAS check digit, GHS code range, sane dates...)
4. clean source  - the quote has no corrupted characters the model would have had to guess through
5. honest nulls  - a "not stated" answer is rejected when its own quote states a value

A value that fails any check is escalated to a stronger model; if that fails too, it is flagged
for review instead of being silently trusted.
"""
from __future__ import annotations

import difflib
import re
from datetime import date, datetime
from typing import Any

from .rules import _corrupted, cas_checksum_ok


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_grounded(quote: str, source: str, min_ratio: float = 0.9) -> bool:
    """True when the quote appears in the source (whitespace-insensitive, small slack for PDF breaks)."""
    q, src = _squash(quote), _squash(source)
    if not q:
        return False
    if q in src:
        return True
    m = difflib.SequenceMatcher(None, q, src, autojunk=False).find_longest_match(0, len(q), 0, len(src))
    return m.size / len(q) >= min_ratio


def _numbers(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]


def value_in_quote(field: str, value: Any, quote: str) -> bool:
    """Can a reader get from the quote to the value?"""
    if value is None or value == []:
        return True  # "not stated" answers are judged by grounding of the nearest line only
    q = _squash(quote)
    if field in ("cas_numbers", "hazard_statements"):
        return all(_squash(v) in q for v in value)
    if field == "un_number":
        return str(value)[-4:] in q
    if field == "flash_point_c":
        nums = _numbers(q)
        return any(abs(n - value) <= 0.5 or abs((n - 32) * 5 / 9 - value) <= 0.5 for n in nums)
    if field == "ph":
        return any(abs(n - value) <= 0.1 for n in _numbers(q))
    if field in ("signal_word", "physical_state"):
        return _squash(str(value)) in q
    if field == "revision_date":
        y, m, d = (int(x) for x in str(value).split("-"))
        month = datetime(2000, m, 1).strftime("%B").lower()
        return str(y) in q and (month in q or f"{m:02d}" in q or f"{m}/" in q or f"{d:02d}" in q)
    # names: most of the value's words should be in the quote
    words = set(re.findall(r"[a-z0-9]+", _squash(str(value))))
    return bool(words) and len(words & set(re.findall(r"[a-z0-9]+", q))) / len(words) >= 0.6


def null_contradicted(field: str, value: Any, quote: str) -> bool:
    """A 'not stated' answer whose own evidence states something."""
    if value not in (None, []) or not quote:
        return False
    q = _squash(quote)
    if field == "physical_state":
        return bool(re.search(r"\b(liquid|solid|gas)\b", q))
    if field == "signal_word":
        return bool(re.search(r"\b(danger|warning)\b", q))
    if field == "un_number":
        return bool(re.search(r"\bun\s?\d{4}\b", q))
    if field == "flash_point_c":
        return bool(re.search(r"-?\d+(\.\d+)?\s*°?\s*[cf]\b", q)) and "not" not in q
    if field == "cas_numbers":
        return bool(re.search(r"\b\d{2,7}-\d{2}-\d\b", q))
    return False


def value_valid(field: str, value: Any) -> bool:
    if value is None or value == []:
        return True
    if field == "cas_numbers":
        return all(re.fullmatch(r"\d{2,7}-\d{2}-\d", c) and cas_checksum_ok(c) for c in value)
    if field == "hazard_statements":
        return all(re.fullmatch(r"H(2[0-9]{2}|3[0-7][0-9]|4[0-2][0-9])", h) for h in value)
    if field == "un_number":
        return bool(re.fullmatch(r"UN\d{4}", str(value)))
    if field == "flash_point_c":
        return -150 <= value <= 400
    if field == "ph":
        return 0 <= value <= 14
    if field == "revision_date":
        try:
            d = datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            return False
        return date(1990, 1, 1) <= d <= date.today()
    return True


def check(field: str, value: Any, quote: str, source: str) -> list[str]:
    """Return the list of failed checks (empty means trusted)."""
    failed = []
    if value not in (None, []) and not quote_grounded(quote, source):
        failed.append("quote_not_in_source")
    if not value_in_quote(field, value, quote):
        failed.append("value_not_in_quote")
    if not value_valid(field, value):
        failed.append("invalid_value")
    if null_contradicted(field, value, quote):
        failed.append("null_but_quote_has_value")
    numeric = field in ("cas_numbers", "un_number", "flash_point_c", "ph", "revision_date")
    if numeric and value not in (None, []) and _corrupted(quote):
        failed.append("corrupted_source_text")  # e.g. "-1B.8": the model had to guess what it says
    return failed
