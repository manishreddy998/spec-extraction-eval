"""Method C: a verified cascade.

    rules (free)  ->  small model on targeted sections  ->  verify  ->  large model for failures  ->  verify
                                                                              \\-> still failing: flag for review

Every output value carries its provenance (which stage produced it), its evidence quote,
and the checks it passed, so the record can be audited field by field.
"""
from __future__ import annotations

import os

from .evidence import check
from .llm import MODEL, CallResult
from .rules import apply_rules
from .schema import FIELDS
from .targeted import ask

SMALL_MODEL = os.getenv("SPECX_SMALL_MODEL", "claude-haiku-5-5")
LARGE_MODEL = MODEL


def run_detailed(text: str) -> tuple[dict, dict, list[CallResult]]:
    calls: list[CallResult] = []
    record: dict = {}
    trace: dict = {}

    for field, value in apply_rules(text).items():
        record[field] = value
        trace[field] = {"stage": "rule", "quote": None, "failed": []}

    pending = [f for f in FIELDS if f not in record]
    for stage, model in (("small", SMALL_MODEL), ("large", LARGE_MODEL)):
        if not pending:
            break
        answers, call, _ = ask(text, pending, model)
        calls.append(call)
        still = []
        for f in pending:
            value, quote = answers.get(f, (None, ""))
            failed = check(f, value, quote, text) if f in answers else ["no_answer"]
            if not failed or stage == "large":
                record[f] = value
                trace[f] = {"stage": stage if not failed else "review", "model": model, "quote": quote, "failed": failed}
            if failed:
                still.append(f)
        pending = still if stage == "small" else []

    for f in FIELDS:
        record.setdefault(f, [] if f in ("cas_numbers", "hazard_statements") else None)
    return record, trace, calls


def run(text: str) -> tuple[dict, list[CallResult]]:
    record, _, calls = run_detailed(text)
    return record, calls
