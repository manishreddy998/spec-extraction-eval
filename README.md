# spec-extraction-eval

Extracting structured product attributes from safety data sheets (SDS), and measuring how well it works.

Work in progress. The plan:

1. Collect a set of public SDS PDFs and hand-label 10 attributes per document (the golden set).
2. Extract the same attributes two ways: one LLM call per document, and a staged pipeline that uses
   deterministic parsing first and calls the LLM only for what's left.
3. Score both per field for accuracy, coverage, cost and latency.
