"""Generate report figures into docs/figures/ (RAM pyramid, architecture, confusion matrices, metrics)."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.evaluate import evaluate  # noqa: E402
from ram import RequirementSet, metrics, plan_sprints  # noqa: E402

OUT = ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
C = ["#6d4bd8", "#0a7ea4", "#15803d", "#b45309"]
LV = ["Product", "Feature", "Function", "Component"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})


def pyramid():
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    ax.set_xlim(0, 19); ax.set_ylim(0, 9); ax.axis("off")
    desc = ["Goals and strategy\n(organisation, market)", "Product features that\nrealise the goals",
            "Functions / user stories\n(backlog-ready)", "Detailed, measurable,\ndesign-near constraints"]
    tops = [8.6, 6.5, 4.4, 2.3]
    for i in range(4):
        y1, y0 = tops[i], tops[i] - 1.9
        w1, w0 = 1.7 + i * 1.0, 1.7 + (i + 1) * 1.0
        ax.add_patch(Polygon([(5.8 - w1, y1), (5.8 + w1, y1), (5.8 + w0, y0), (5.8 - w0, y0)], color=C[i], ec="white", lw=2))
        ax.text(5.8, (y0 + y1) / 2, f"L{i+1}  {LV[i]}", ha="center", va="center", color="white", fontweight="bold", fontsize=12)
        ax.text(12.0, (y0 + y1) / 2, desc[i], ha="left", va="center", fontsize=10.5)
    ax.annotate("", xy=(17.9, 1.0), xytext=(17.9, 8.4), arrowprops=dict(arrowstyle="<->", color="#555", lw=1.5))
    ax.text(18.25, 8.4, "abstract", rotation=90, ha="left", va="top", color="#555", fontsize=9)
    ax.text(18.25, 1.0, "detailed", rotation=90, ha="left", va="bottom", color="#555", fontsize=9)
    fig.savefig(OUT / "fig1-ram-pyramid.png", dpi=200, bbox_inches="tight"); plt.close(fig)


def architecture():
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.set_xlim(0, 18); ax.set_ylim(0, 9); ax.axis("off")

    def box(x, y, w, h, t, col, sub=""):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.25", fc=col, ec="none", alpha=.95))
        ax.text(x + w / 2, y + h / 2 + (.25 if sub else 0), t, ha="center", va="center", color="white", fontweight="bold", fontsize=10)
        if sub:
            ax.text(x + w / 2, y + h / 2 - .45, sub, ha="center", va="center", color="white", fontsize=8)

    box(0.3, 6.6, 4.6, 1.8, "Requirement sources", "#64748b", "workshops · surveys · tickets")
    box(0.3, 3.6, 4.6, 1.8, "JSON repository", "#64748b", "examples/*.json")
    box(6.2, 6.6, 5.0, 1.8, "Classifier", C[1], "lexicon.json · cue weights")
    box(6.2, 3.6, 5.0, 1.8, "Work-up engine", C[0], "parent link · abstraction advice")
    box(6.2, 0.6, 5.0, 1.8, "Validator (R001-R010)", C[3], "structure · duplicates · criteria")
    box(12.6, 6.6, 5.0, 1.8, "Analysis", C[2], "traceability · metrics · ranking")
    box(12.6, 3.6, 5.0, 1.8, "Sprint planner", C[2], "cost-value greedy packing")
    box(12.6, 0.6, 5.0, 1.8, "Interfaces", "#334155", "CLI · RAM Studio web app")
    for a, b in [((4.9, 7.5), (6.2, 7.5)), ((8.7, 6.6), (8.7, 5.4)), ((4.9, 4.5), (6.2, 4.5)),
                 ((8.7, 3.6), (8.7, 2.4)), ((11.2, 4.5), (12.6, 7.3)), ((15.1, 6.6), (15.1, 5.4)),
                 ((15.1, 3.6), (15.1, 2.4)), ((11.2, 1.5), (12.6, 1.5))]:
        ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="-|>", color="#374151", lw=1.4))
    fig.savefig(OUT / "fig2-architecture.png", dpi=200, bbox_inches="tight"); plt.close(fig)


def confusion(res):
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for ax, key, title in zip(axes, ("labelled", "heldout"), ("Labelled set (n=48)", "Held-out set (n=16)")):
        cm = res[key]["confusion"]
        data = [[cm[a][b] for b in LV] for a in LV]
        ax.imshow(data, cmap="Blues", vmin=0, vmax=12)
        ax.set_xticks(range(4)); ax.set_yticks(range(4))
        ax.set_xticklabels(LV, rotation=30, ha="right"); ax.set_yticklabels(LV)
        ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
        ax.set_title(f"{title}\naccuracy {res[key]['accuracy']:.1%}", fontsize=10)
        for i in range(4):
            for j in range(4):
                ax.text(j, i, data[i][j], ha="center", va="center", color="white" if data[i][j] > 6 else "black", fontweight="bold")
    fig.tight_layout(); fig.savefig(OUT / "fig3-confusion.png", dpi=200); plt.close(fig)


def model_metrics():
    rs = RequirementSet.load(ROOT / "examples" / "campusconnect.json")
    m = metrics(rs)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    vals = [m["per_level"][l] for l in LV]
    axes[0].bar(LV, vals, color=C)
    for i, v in enumerate(vals):
        axes[0].text(i, v + .3, v, ha="center", fontweight="bold")
    axes[0].set_title("Active requirements per level"); axes[0].set_ylim(0, max(vals) + 4)
    names = ["Traceability", "Product\nrefinement", "Acceptance\ncriteria"]
    cov = [m["traceability_coverage"], m["product_refinement_coverage"], m["acceptance_coverage"]]
    axes[1].barh(names, [c * 100 for c in cov], color="#3356e0")
    for i, c in enumerate(cov):
        axes[1].text(c * 100 + 1, i, f"{c:.0%}", va="center", fontweight="bold")
    axes[1].set_xlim(0, 115); axes[1].set_title("Coverage metrics (%)"); axes[1].invert_yaxis()
    for ax in axes:
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "fig4-metrics.png", dpi=200); plt.close(fig)


def sprint_chart():
    rs = RequirementSet.load(ROOT / "examples" / "campusconnect.json")
    plan = plan_sprints(rs, 14, 3)
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    names = [f"Sprint {p['sprint']}" if p["sprint"] != "backlog" else "Backlog" for p in plan]
    used = [p["used"] for p in plan]
    ax.bar(names, used, color=[C[2]] * 3 + ["#94a3b8"])
    ax.axhline(14, ls="--", color="#b91c1c", lw=1); ax.text(3.45, 14.4, "capacity 14", color="#b91c1c", ha="right", fontsize=9)
    for i, v in enumerate(used):
        ax.text(i, v + .4, f"{v} pts", ha="center", fontweight="bold")
    ax.set_ylim(0, max(used) + 5); ax.set_title("Story points per sprint (capacity 14)")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "fig5-sprints.png", dpi=200); plt.close(fig)


if __name__ == "__main__":
    res = evaluate()
    pyramid(); architecture(); confusion(res); model_metrics(); sprint_chart()
    print("figures written to", OUT)
