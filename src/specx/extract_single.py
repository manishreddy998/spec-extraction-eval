"""Method A: send the whole document to the model in one call and ask for every field.

This is the baseline: simple, usually accurate, but every document pays for its full length
in input tokens, and nothing is checked before the model sees it.
"""
from __future__ import annotations

from .llm import CallResult, extract
from .schema import SDSRecord

INSTRUCTIONS = """Extract these fields from the safety data sheet above:
- product_name: the name a buyer sees ("Name on Label" or "Trade name" if given, else "Product name").
- manufacturer: the company that issued the SDS (Section 1).
- cas_numbers: every CAS number in the Section 3 ingredient table, in order. Ignore CAS numbers elsewhere.
- signal_word: Danger, Warning, or None if the product is not classified.
- hazard_statements: H-codes printed in Section 2 (split combined codes like H315+H320). Empty if only text is given.
- un_number: Section 14 UN number like UN1950; null if not regulated for every mode.
- flash_point_c: in Celsius (convert from Fahrenheit if needed); for "<" or ">" or a range give the stated bound; null for none/not applicable.
- physical_state: solid, liquid or gas from Section 9; null if it only says aerosol.
- ph: the value, or the lower bound of a range; null if not applicable.
- revision_date: revision date, else issue date, as YYYY-MM-DD (EU sheets write DD.MM.YYYY)."""


def run(text: str) -> tuple[dict, list[CallResult]]:
    result = extract(text, SDSRecord, INSTRUCTIONS)
    record = result.record.model_dump() if result.record else SDSRecord().model_dump()
    return record, [result]
