"""Download the SDS PDFs listed in data/manifest.csv into data/raw/.

The PDFs belong to their publishers, so they are not committed; this script fetches them on demand.
Usage: python scripts/download.py
"""
import csv
import hashlib
import pathlib
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "manifest.csv"
RAW = ROOT / "data" / "raw"
HEADERS = {"User-Agent": "Mozilla/5.0 (spec-extraction-eval research script)"}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open() as f:
        rows = list(csv.DictReader(f))
    ok = 0
    for row in rows:
        out = RAW / f"{row['doc_id']}.pdf"
        if out.exists() and out.stat().st_size > 0:
            ok += 1
            continue
        try:
            resp = requests.get(row["url"], headers=HEADERS, timeout=30)
            resp.raise_for_status()
            if not resp.content.startswith(b"%PDF"):
                print(f"skip {row['doc_id']}: not a PDF")
                continue
            out.write_bytes(resp.content)
            ok += 1
            print(f"ok   {row['doc_id']}  {len(resp.content) // 1024:>5} KB  sha1={hashlib.sha1(resp.content).hexdigest()[:10]}")
        except requests.RequestException as exc:
            print(f"fail {row['doc_id']}: {exc}")
        time.sleep(0.5)  # be polite to the hosts
    print(f"{ok}/{len(rows)} documents available in {RAW}")


if __name__ == "__main__":
    main()
