"""Field-level extraction rules, shared by every method so they all answer the same question."""

FIELD_RULES = {
    "product_name": 'the name a buyer sees ("Name on Label" or "Trade name" if given, else "Product name").',
    "manufacturer": "the company that issued the SDS (Section 1).",
    "cas_numbers": "every CAS number in the Section 3 ingredient table, in order. Ignore CAS numbers elsewhere.",
    "signal_word": "Danger, Warning, or None if the product is not classified.",
    "hazard_statements": "H-codes printed in Section 2 (split combined codes like H315+H320). Empty if only text is given.",
    "un_number": "Section 14 UN number like UN1950; null if not regulated for every mode.",
    "flash_point_c": 'in Celsius (convert from Fahrenheit if needed); for "<", ">" or a range give the stated bound (lower bound of a range); null for none/not applicable.',
    "physical_state": "solid, liquid or gas from Section 9; null if it only says aerosol.",
    "ph": "the value, or the lower bound of a range; null if not applicable.",
    "revision_date": "revision date, else issue date, as YYYY-MM-DD (EU sheets write DD.MM.YYYY).",
}


def field_instructions(fields: list[str], with_evidence: bool = False) -> str:
    lines = [f"- {f}: {FIELD_RULES[f]}" for f in fields]
    head = "Extract these fields from the safety data sheet above:\n"
    tail = ""
    if with_evidence:
        tail = (
            "\n\nFor every field return `value` and `quote`. `quote` must be copied verbatim from the "
            "document (a short span, under 200 characters) and must contain the text that the value "
            "comes from. If the value is null because the document says nothing, quote the closest "
            "relevant line or leave quote empty. Do not fix typos or characters inside quotes."
        )
    return head + "\n".join(lines) + tail
