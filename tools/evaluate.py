"""Evaluate the level classifier on the labelled sets and on the sample model.

Sets:
  labelled  examples/labelled_requirements.csv  (48 statements, written alongside the lexicon)
  heldout   examples/heldout_requirements.csv   (16 statements, differently phrased, never used for tuning)

Usage: python tools/evaluate.py [--json out.json]
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ram import Level, RequirementSet, classify  # noqa: E402
from ram.model import Status  # noqa: E402


def score(rows):
    levels = list(Level)
    cm = {a: {b: 0 for b in levels} for a in levels}
    wrong = []
    for r in rows:
        gold = Level(int(r["level"]))
        pred = classify(r["text"]).level
        cm[gold][pred] += 1
        if gold != pred:
            wrong.append((gold.label, pred.label, r["text"]))
    n = len(rows)
    correct = sum(cm[l][l] for l in levels)
    per = {}
    for l in levels:
        tp = cm[l][l]
        fp = sum(cm[o][l] for o in levels if o != l)
        fn = sum(cm[l][o] for o in levels if o != l)
        p = tp / (tp + fp) if tp + fp else 0
        rc = tp / (tp + fn) if tp + fn else 0
        per[l.label] = dict(precision=round(p, 3), recall=round(rc, 3),
                            f1=round(2 * p * rc / (p + rc), 3) if p + rc else 0)
    return dict(n=n, accuracy=round(correct / n, 3),
                confusion={a.label: {b.label: cm[a][b] for b in levels} for a in levels},
                per_level=per, misclassified=wrong)


def evaluate():
    out = {}
    for key, fn in (("labelled", "labelled_requirements.csv"), ("heldout", "heldout_requirements.csv")):
        with open(ROOT / "examples" / fn, encoding="utf-8") as f:
            out[key] = score(list(csv.DictReader(f)))
    rs = RequirementSet.load(ROOT / "examples" / "campusconnect.json")
    acc = [r for r in rs if r.status == Status.ACCEPTED]
    hit = sum(1 for r in acc if classify(r.text).level == r.level)
    out["sample"] = dict(n=len(acc), accuracy=round(hit / len(acc), 3))
    return out


if __name__ == "__main__":
    res = evaluate()
    for key in ("labelled", "heldout"):
        s = res[key]
        print(f"{key}: n={s['n']} accuracy={s['accuracy']:.1%}")
        for k, v in s["per_level"].items():
            print(f"  {k:10} P={v['precision']:.2f} R={v['recall']:.2f} F1={v['f1']:.2f}")
        for g, p, t in s["misclassified"]:
            print(f"  MISS gold={g} pred={p}: {t}")
    print(f"sample model: n={res['sample']['n']} accuracy={res['sample']['accuracy']:.1%}")
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(res, indent=2), encoding="utf-8")
