# Labeling guide

The golden set (`data/golden.jsonl`) holds the correct answer for every field in every document.
Labels come from reading the PDF itself, not the extracted text, because text extraction can corrupt
characters (see `sds_08`, where the PDF's font maps "n" to "m" and "7" to "B", so "67-64-1" comes out as "6B-64-1").

Each record has `verified: false` until it has been checked line by line against the PDF.
`python scripts/label_helper.py sds_10` prints the relevant passages for a document to speed this up.

## Rules per field

| Field | Rule |
|---|---|
| `product_name` | The name a buyer sees. Prefer "Name on Label" or "Trade name" over internal SKU names; fall back to "Product name" when nothing else is given. Scored with normalized fuzzy matching. |
| `manufacturer` | The company that issued the SDS, as written in Section 1. |
| `cas_numbers` | Every CAS number in the Section 3 ingredient table, in document order. CAS numbers that appear only in other sections (Prop 65 notices, exposure limits) are excluded. |
| `signal_word` | `Danger`, `Warning`, or `None` when the product is not classified. |
| `hazard_statements` | H-codes printed in Section 2. Combined codes such as `H315+H320` are split. If Section 2 lists the statement text without codes (WD-40, CRC), the list is empty. Ingredient-level codes in Section 3 are excluded. |
| `un_number` | The UN number from Section 14 for the packaged product, e.g. `UN1950`. When different transport modes disagree, the number used by any mode counts. `null` when not regulated for all modes. |
| `flash_point_c` | Degrees Celsius. Converted from °F when only °F is given. For a range or a "<" / ">" value, the stated bound is recorded. `null` for "none", "does not flash" or "not applicable". |
| `physical_state` | `solid`, `liquid` or `gas` as stated in Section 9. `null` when the document only says "aerosol". |
| `ph` | The stated value; for a range, the lower bound. `null` when not applicable or not available. |
| `revision_date` | Revision date if given, otherwise issue date, as `YYYY-MM-DD`. EU documents use `DD.MM.YYYY`. |

## Dataset notes

- 25 documents from WD-40, Rust-Oleum, Simple Green, CRC, Zep, GOJO (Purell) and Henkel (Loctite).
- Layouts include bilingual English/French Canadian sheets, EU REACH format (`sds_20`), and one PDF with a broken font map (`sds_08`).
- `sds_19` was removed: it was the same SDS version as `sds_18`, hosted on a different site.
