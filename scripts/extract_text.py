"""Convert every PDF in data/raw/ to text in data/text/ and report basic stats.

Usage: python scripts/extract_text.py
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from specx.pdf_text import pdf_to_text  # noqa: E402

RAW = ROOT / "data" / "raw"
TEXT = ROOT / "data" / "text"


def main() -> None:
    TEXT.mkdir(parents=True, exist_ok=True)
    for pdf in sorted(RAW.glob("*.pdf")):
        text = pdf_to_text(pdf)
        (TEXT / f"{pdf.stem}.txt").write_text(text)
        pages = text.count("[page ")
        flag = "  <-- little text, may be scanned" if len(text) < 2000 else ""
        print(f"{pdf.stem}: {pages:>2} pages, {len(text):>6} chars{flag}")


if __name__ == "__main__":
    main()
