"""Method A: send the whole document to the model in one call and ask for every field.

This is the baseline: simple, usually accurate, but every document pays for its full length
in input tokens, and nothing is checked before the answer is trusted.
"""
from __future__ import annotations

from .llm import MODEL, CallResult, extract
from .prompts import field_instructions
from .schema import FIELDS, SDSRecord

INSTRUCTIONS = field_instructions(FIELDS)


def run(text: str, model: str = MODEL) -> tuple[dict, list[CallResult]]:
    result = extract(text, SDSRecord, INSTRUCTIONS, model=model)
    record = result.record.model_dump() if result.record else SDSRecord().model_dump()
    return record, [result]
