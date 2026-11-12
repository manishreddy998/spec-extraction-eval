"""Compare extracted records with the golden set, field by field.

Each field has its own notion of "correct": names are matched loosely, codes exactly,
numbers within a tolerance, lists as sets. Both sides being empty counts as correct,
because "the document doesn't state it" is an answer we want the extractor to give.
"""
from __future__ import annotations

import re
from typing import Any

from .schema import FIELDS

FLASH_TOL_C = 1.0
PH_TOL = 0.1


def _norm(s: Any) -> str:
    s = str(s or "").lower()
    s = re.sub(r"[®™©]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def _tokens(s: Any) -> set[str]:
    return set(_norm(s).split())


def _name_match(pred: Any, gold: Any, threshold: float) -> bool:
    if not pred and not gold:
        return True
    if not pred or not gold:
        return False
    a, b = _norm(pred), _norm(gold)
    if a in b or b in a:
        return True
    ta, tb = _tokens(pred), _tokens(gold)
    return len(ta & tb) / len(ta | tb) >= threshold


def _un(v: Any) -> str:
    return re.sub(r"\s+", "", str(v or "")).upper()


def _num_match(pred: Any, gold: Any, tol: float) -> bool:
    if pred is None and gold is None:
        return True
    if pred is None or gold is None:
        return False
    return abs(float(pred) - float(gold)) <= tol


def set_f1(pred: list, gold: list) -> float:
    p, g = set(pred or []), set(gold or [])
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    tp = len(p & g)
    return 2 * tp / (len(p) + len(g))


def field_correct(field: str, pred: Any, gold: Any) -> bool:
    if field == "product_name":
        return _name_match(pred, gold, 0.6)
    if field == "manufacturer":
        return _name_match(pred, gold, 0.5)
    if field in ("cas_numbers", "hazard_statements"):
        return set(pred or []) == set(gold or [])
    if field == "un_number":
        return _un(pred) == _un(gold)
    if field == "flash_point_c":
        return _num_match(pred, gold, FLASH_TOL_C)
    if field == "ph":
        return _num_match(pred, gold, PH_TOL)
    if field in ("signal_word", "physical_state"):
        return _norm(pred) == _norm(gold)
    return str(pred or "") == str(gold or "")  # revision_date and anything exact


def score_record(pred: dict, gold: dict) -> dict:
    out = {f: field_correct(f, pred.get(f), gold.get(f)) for f in FIELDS}
    out["cas_f1"] = set_f1(pred.get("cas_numbers"), gold.get("cas_numbers"))
    out["hazard_f1"] = set_f1(pred.get("hazard_statements"), gold.get("hazard_statements"))
    return out
