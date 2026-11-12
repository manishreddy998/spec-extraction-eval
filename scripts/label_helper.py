"""Show the parts of an SDS that matter for labeling, so the golden set can be checked quickly.

Usage: python scripts/label_helper.py sds_10 [sds_11 ...]   (no args = all documents)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEXT = ROOT / "data" / "text"
sys.path.insert(0, str(ROOT / "src"))

from specx.sections import section  # noqa: E402

PATTERNS = {
    "identity": r"(product name|name on label|trade name|product identifier|manufacturer|supplier|company)",
    "signal": r"signal word|\bdanger\b|\bwarning\b",
    "dates": r"(revision|revised|issue|prepared|date of preparation|supersed)\w*[^\n]{0,60}\d",
    "flash": r"flash ?point",
    "state": r"(physical state|appearance|form)\b",
    "ph": r"\bph\b",
    "un": r"\bUN ?\d{4}\b|un number|un no\b|not regulated",
}
CAS_RE = re.compile(r"\b\d{2,7}-\d{2}-\d\b")
H_RE = re.compile(r"\bH\d{3}[A-Za-z]{0,2}\b")


def show(doc_id: str) -> None:
    text = (TEXT / f"{doc_id}.txt").read_text()
    lines = text.splitlines()
    print(f"\n==================== {doc_id} ({len(text)} chars)")
    for name, pat in PATTERNS.items():
        hits = [ln.strip() for ln in lines if re.search(pat, ln, re.I)]
        print(f"-- {name}:")
        for ln in hits[:6]:
            print(f"   {ln[:150]}")
    sec2, sec3 = section(text, 2), section(text, 3)
    print(f"-- H-codes in Section 2 ({len(sec2)} chars):", sorted(set(H_RE.findall(sec2))))
    print(f"-- CAS in Section 3 ({len(sec3)} chars):", list(dict.fromkeys(CAS_RE.findall(sec3))))
    print("-- CAS anywhere:", list(dict.fromkeys(CAS_RE.findall(text))))


if __name__ == "__main__":
    ids = sys.argv[1:] or sorted(p.stem for p in TEXT.glob("*.txt"))
    for doc in ids:
        show(doc)
