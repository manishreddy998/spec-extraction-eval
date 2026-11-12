"""Robustness test: how does each method behave as the source text gets more corrupted?

One real document in the set (sds_08) has a broken font map that turns "n" into "m" and "7" into
"B". This script applies the same kind of corruption to *every* document at increasing rates and
re-runs the methods. The question is not only "how accurate", but "when it's wrong, does it know?"

Usage: python scripts/stress_test.py [--levels 0 0.02 0.05 0.1]
Writes results/robustness.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import random
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from specx import extract_cascade, extract_single  # noqa: E402
from specx.schema import FIELDS  # noqa: E402
from specx.score import score_record  # noqa: E402

# character confusions seen in real broken PDF font maps and OCR output
CONFUSIONS = {"n": "m", "7": "B", "0": "O", "1": "l", "5": "S", "8": "B", "e": "c", "H": "E", "u": "v"}


def corrupt(text: str, rate: float, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(CONFUSIONS[c] if c in CONFUSIONS and rng.random() < rate else c for c in text)


def evaluate(method: str, text: str, gold: dict) -> dict:
    if method == "B_haiku_single":
        record, calls = extract_single.run(text, model=extract_cascade.SMALL_MODEL)
        review = []
    else:
        record, trace, calls = extract_cascade.run_detailed(text)
        review = [f for f, t in trace.items() if t.get("stage") == "review"]
    scores = score_record(record, gold)
    wrong = [f for f in FIELDS if not scores[f]]
    return {
        "correct": len(FIELDS) - len(wrong),
        "silent": len([f for f in wrong if f not in review]),
        "flagged": len(review),
        "flagged_wrong": len([f for f in wrong if f in review]),
        "cost": sum(c.cost_usd for c in calls),
        "errors": [c.error for c in calls if c.error],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", type=float, nargs="+", default=[0.0, 0.02, 0.05, 0.10])
    ap.add_argument("--methods", nargs="+", default=["B_haiku_single", "C_cascade"])
    args = ap.parse_args()
    golden = {r["doc_id"]: r for r in map(json.loads, (ROOT / "data" / "golden.jsonl").open())}
    texts = {d: (ROOT / "data" / "text" / f"{d}.txt").read_text() for d in golden}

    rows = []
    for level in args.levels:
        for method in args.methods:
            jobs = [(d, corrupt(texts[d], level, seed=zlib.crc32(d.encode()) + int(level * 1000))) for d in sorted(golden)]
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda j: evaluate(method, j[1], golden[j[0]]), jobs))
            errs = [e for r in results for e in r["errors"]]
            if errs:
                sys.exit(f"{len(errs)} LLM calls failed at level {level} ({method}): {errs[0]}")
            total = len(results) * len(FIELDS)
            row = {
                "corruption_rate": level,
                "method": method,
                "accuracy": round(sum(r["correct"] for r in results) / total, 4),
                "silent_errors": sum(r["silent"] for r in results),
                "flagged": sum(r["flagged"] for r in results),
                "flagged_and_wrong": sum(r["flagged_wrong"] for r in results),
                "cost_usd": round(sum(r["cost"] for r in results), 4),
            }
            rows.append(row)
            print(row)

    out = ROOT / "results" / "robustness.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
