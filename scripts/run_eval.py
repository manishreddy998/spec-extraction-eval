"""Run one or both extraction methods over every document and score them against the golden set.

Usage:
    python scripts/run_eval.py                 # all methods
    python scripts/run_eval.py --method C_cascade

Writes per-document predictions to runs/<method>.jsonl, loads everything into DuckDB
(results/eval.duckdb) and writes a summary table to results/summary.md.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from specx import extract_single  # noqa: E402
from specx.llm import EFFORT, MODEL  # noqa: E402
from specx.schema import FIELDS  # noqa: E402
from specx.score import score_record  # noqa: E402

from specx import extract_cascade  # noqa: E402


def _single(model: str):
    def fn(text: str):
        record, calls = extract_single.run(text, model=model)
        return record, calls, {}  # no verification: every value is trusted as-is
    return fn


def _cascade(text: str):
    record, trace, calls = extract_cascade.run_detailed(text)
    return record, calls, trace


# A: big model, whole document.  B: small model, whole document.  C: verified cascade.
METHODS = {
    "A_opus_single": _single(MODEL),
    "B_haiku_single": _single(extract_cascade.SMALL_MODEL),
    "C_cascade": _cascade,
}

TEXT = ROOT / "data" / "text"
RUNS = ROOT / "runs"
RESULTS = ROOT / "results"


def load_golden() -> dict[str, dict]:
    with (ROOT / "data" / "golden.jsonl").open() as f:
        return {r["doc_id"]: r for r in map(json.loads, f)}


def run_method(name: str, golden: dict[str, dict], workers: int) -> list[dict]:
    fn = METHODS[name]

    def one(doc_id: str) -> dict:
        text = (TEXT / f"{doc_id}.txt").read_text()
        t0 = time.perf_counter()
        record, calls, trace = fn(text)
        scores = score_record(record, golden[doc_id])
        review = [f for f, t in trace.items() if t.get("stage") == "review"]
        return {
            "method": name,
            "doc_id": doc_id,
            "prediction": record,
            "trace": trace,
            "scores": scores,
            "review": review,
            "silent_errors": [f for f in FIELDS if not scores[f] and f not in review],
            "llm_calls": len(calls),
            "input_tokens": sum(c.input_tokens for c in calls),
            "output_tokens": sum(c.output_tokens for c in calls),
            "cost_usd": sum(c.cost_usd for c in calls),
            "latency_s": time.perf_counter() - t0,
            "errors": [c.error for c in calls if c.error],
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(one, sorted(golden)))
    RUNS.mkdir(exist_ok=True)
    with (RUNS / f"{name}.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return rows


def summarize(all_rows: dict[str, list[dict]]) -> str:
    names = list(all_rows)
    lines = [
        f"Model: `{MODEL}` (effort `{EFFORT}`), {len(next(iter(all_rows.values())))} documents.",
        "",
        "| Field | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]
    for f in FIELDS:
        cells = []
        for n in names:
            rows = all_rows[n]
            cells.append(f"{sum(r['scores'][f] for r in rows) / len(rows):.0%}")
        lines.append(f"| {f} | " + " | ".join(cells) + " |")

    def stat(n: str, fn) -> str:
        return fn(all_rows[n])

    extra = [
        ("**All fields**", lambda rows: f"**{sum(sum(r['scores'][f] for f in FIELDS) for r in rows) / (len(rows) * len(FIELDS)):.1%}**"),
        ("Silent errors (wrong and not flagged)", lambda rows: f"**{sum(len(r['silent_errors']) for r in rows)}**"),
        ("Values flagged for review", lambda rows: str(sum(len(r['review']) for r in rows))),
        ("CAS set F1 (mean)", lambda rows: f"{sum(r['scores']['cas_f1'] for r in rows) / len(rows):.3f}"),
        ("LLM calls", lambda rows: str(sum(r["llm_calls"] for r in rows))),
        ("Input tokens", lambda rows: f"{sum(r['input_tokens'] for r in rows):,}"),
        ("Output tokens", lambda rows: f"{sum(r['output_tokens'] for r in rows):,}"),
        ("Total cost (USD)", lambda rows: f"${sum(r['cost_usd'] for r in rows):.3f}"),
        ("Cost per document", lambda rows: f"${sum(r['cost_usd'] for r in rows) / len(rows):.4f}"),
        ("Median latency per document", lambda rows: f"{sorted(r['latency_s'] for r in rows)[len(rows) // 2]:.1f}s"),
    ]
    for label, fn in extra:
        lines.append(f"| {label} | " + " | ".join(stat(n, fn) for n in names) + " |")
    return "\n".join(lines) + "\n"


def to_duckdb(all_rows: dict[str, list[dict]]) -> None:
    import duckdb

    RESULTS.mkdir(exist_ok=True)
    con = duckdb.connect(str(RESULTS / "eval.duckdb"))
    con.execute("""CREATE TABLE IF NOT EXISTS field_scores (
        run_at TIMESTAMP, method VARCHAR, doc_id VARCHAR, field VARCHAR, correct BOOLEAN,
        predicted VARCHAR, cost_usd DOUBLE)""")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    for name, rows in all_rows.items():
        for r in rows:
            for f in FIELDS:
                con.execute("INSERT INTO field_scores VALUES (?, ?, ?, ?, ?, ?, ?)",
                            [now, name, r["doc_id"], f, bool(r["scores"][f]),
                             json.dumps(r["prediction"].get(f)), r["cost_usd"] / len(FIELDS)])
    con.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=[*METHODS, "all"], default="all")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    names = list(METHODS) if args.method == "all" else [args.method]
    golden = load_golden()
    all_rows = {}
    for n in names:
        print(f"running {n} on {len(golden)} documents ...")
        all_rows[n] = run_method(n, golden, args.workers)
    errors = [(n, r["doc_id"], e) for n, rows in all_rows.items() for r in rows for e in r["errors"]]
    if errors:
        print(f"{len(errors)} LLM calls failed, results not saved. First: {errors[0]}")
        sys.exit(1)
    summary = summarize(all_rows)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "summary.md").write_text(summary)
    to_duckdb(all_rows)
    print(summary)
    for n, rows in all_rows.items():
        misses = [(r["doc_id"], f) for r in rows for f in FIELDS if not r["scores"][f]]
        print(f"{n} misses ({len(misses)}):", ", ".join(f"{d}:{f}" for d, f in misses))
        print(f"{n} flagged:", ", ".join(f"{r['doc_id']}:{f}" for r in rows for f in r["review"]) or "none")


if __name__ == "__main__":
    main()
