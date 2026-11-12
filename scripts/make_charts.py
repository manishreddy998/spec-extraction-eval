"""Draw the README charts from results/summary runs and results/robustness.csv.

Usage: python scripts/make_charts.py   (writes docs/img/*.png)
"""
import csv
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
COLORS = {"A_opus_single": "#2a78d6", "B_haiku_single": "#eb6834", "C_cascade": "#1baf7a"}  # fixed slot order
LABELS = {"A_opus_single": "A · Opus, whole doc", "B_haiku_single": "B · Haiku, whole doc", "C_cascade": "C · Verified cascade"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK, "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "axes.spines.top": False, "axes.spines.right": False,
})


def load_runs():
    out = {}
    for m in COLORS:
        rows = [json.loads(line) for line in (ROOT / "runs" / f"{m}.jsonl").open()]
        n_fields = len(rows) * 10
        out[m] = {
            "cost_per_1k": sum(r["cost_usd"] for r in rows) / len(rows) * 1000,
            "accuracy": sum(sum(r["scores"][f] for f in r["prediction"]) for r in rows) / n_fields,
            "silent": sum(len(r["silent_errors"]) for r in rows),
        }
    return out


def cost_chart(runs):
    fig, ax = plt.subplots(figsize=(8.5, 2.8))
    methods = list(COLORS)[::-1]
    vals = [runs[m]["cost_per_1k"] for m in methods]
    ax.barh([LABELS[m] for m in methods], vals, color=[COLORS[m] for m in methods], height=0.5, edgecolor=SURFACE, linewidth=2)
    for i, m in enumerate(methods):
        r = runs[m]
        ax.text(vals[i] + 0.8, i, f"${vals[i]:.2f}   ·   {r['accuracy']:.1%} accurate   ·   {r['silent']} silent errors",
                va="center", color=INK, fontsize=9.5)
    ax.set_xlim(0, max(vals) * 2.15)
    ax.set_xticks([0, 20, 40, 60])
    ax.set_xlabel("Cost per 1,000 safety data sheets (USD)")
    ax.set_title("Same accuracy as the big model, at about 1/24 of the cost", loc="left", fontsize=11.5, pad=10)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    fig.savefig(OUT / "cost_accuracy.png", dpi=200)


def robustness_chart():
    rows = list(csv.DictReader((ROOT / "results" / "robustness.csv").open()))
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.3))
    panels = [("accuracy", "Accuracy", lambda v: float(v) * 100, "%"), ("silent_errors", "Silent errors (wrong, not flagged)", float, "")]
    for ax, (key, title, conv, unit) in zip(axes, panels):
        for m in ("C_cascade", "B_haiku_single"):  # draw B last so it stays visible where the lines overlap
            pts = [(float(r["corruption_rate"]) * 100, conv(r[key])) for r in rows if r["method"] == m]
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color=COLORS[m], linewidth=2, marker="o", markersize=7, markeredgecolor=SURFACE, markeredgewidth=2)
            dy = (9 if m == "C_cascade" else -9) if key == "accuracy" else 0  # the accuracy lines meet at the end
            ax.annotate(LABELS[m].split(" · ")[1], (xs[-1], ys[-1]), xytext=(6, dy), textcoords="offset points",
                        va="center", color=INK, fontsize=9)
        ax.set_title(title, loc="left", fontsize=10.5)
        ax.set_xlabel("Characters corrupted (%)")
        ax.set_xticks([0, 2, 5, 10])
        ax.set_xlim(-0.5, 14)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        if unit == "%":
            ax.set_ylim(96, 100.5)
        else:
            ax.set_ylim(0, 6)
    fig.legend([plt.Line2D([], [], color=COLORS[m], linewidth=2) for m in ("B_haiku_single", "C_cascade")],
               [LABELS[m] for m in ("B_haiku_single", "C_cascade")], loc="upper right", frameon=False, ncol=2, fontsize=9)
    fig.suptitle("Under corrupted text, the cascade makes fewer silent errors", x=0.01, ha="left", fontsize=11.5, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(OUT / "robustness.png", dpi=200)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    cost_chart(load_runs())
    robustness_chart()
    print("wrote", *sorted(p.name for p in OUT.glob("*.png")))
