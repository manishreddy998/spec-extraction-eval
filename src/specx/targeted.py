"""Ask a model about only the fields that are still missing, showing it only the sections it needs.

Instead of paying for a 30,000-character document on every call, each field maps to the GHS
sections where its answer lives; we send those sections plus Section 1 for context.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, create_model

from .llm import CallResult, extract
from .prompts import field_instructions
from .schema import SDSRecord
from .sections import first_page, section

FIELD_SECTIONS = {
    "product_name": [1],
    "manufacturer": [1],
    "cas_numbers": [3],
    "signal_word": [2],
    "hazard_statements": [2],
    "un_number": [14],
    "flash_point_c": [9],
    "physical_state": [9],
    "ph": [9],
    "revision_date": [],  # lives in the page header/footer: send page 1
}


def build_context(text: str, fields: list[str]) -> str:
    """Section 1 + page 1 + the sections the requested fields live in. Falls back to the full text."""
    wanted = sorted({1, *[s for f in fields for s in FIELD_SECTIONS[f]]})
    parts = [first_page(text)[:4000]]
    for n in wanted:
        sec = section(text, n)
        if not sec:
            return text  # can't find a section: don't risk hiding the answer
        if sec not in parts[0]:
            parts.append(sec)
    return "\n\n...\n\n".join(parts)


def evidence_model(fields: list[str]) -> type[BaseModel]:
    """A schema where every field is {value, quote}, built from SDSRecord's own field types."""
    defs = {}
    for f in fields:
        info = SDSRecord.model_fields[f]
        item = create_model(f"{f}_evidence", value=(info.annotation, None), quote=(str, ""))
        defs[f] = (Optional[item], Field(None, description=info.description))
    return create_model("Evidence", **defs)


def ask(text: str, fields: list[str], model: str) -> tuple[dict[str, tuple[Any, str]], CallResult, str]:
    """Returns {field: (value, quote)}, the call record, and the context that was sent."""
    context = build_context(text, fields)
    result = extract(context, evidence_model(fields), field_instructions(fields, with_evidence=True), model=model)
    answers = {}
    if result.record is not None:
        for f in fields:
            item = getattr(result.record, f)
            answers[f] = (item.value, item.quote) if item is not None else (None, "")
    return answers, result, context
