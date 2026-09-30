"""Command line interface:  python -m ram <command> ..."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analysis import metrics, natural_key, plan_sprints, priority_score, traceability_matrix
from .classifier import classify
from .model import Level, RequirementSet
from .workup import validate, workup

DEFAULT = Path(__file__).resolve().parent.parent / "examples" / "campusconnect.json"


def _load(args) -> RequirementSet:
    return RequirementSet.load(args.file)


def cmd_classify(a):
    c = classify(a.text)
    print(f"Level      : {c.level.label} (L{int(c.level)})")
    print(f"Confidence : {c.confidence:.0%}")
    print("Scores     : " + ", ".join(f"{l.label}={s:.1f}" for l, s in c.scores.items()))
    print("Cues       : " + (", ".join(c.cues) or "-"))


def cmd_tree(a):
    rs = _load(a)

    def show(r, depth):
        tag = "" if r.status.value == "accepted" else f" <{r.status.value}>"
        print(f"{'    ' * depth}{'|- ' if depth else ''}[{r.id}] L{int(r.level)} {r.title}{tag}")
        for c in sorted(rs.children(r.id), key=lambda x: x.id):
            show(c, depth + 1)
    for r in sorted(rs.roots(), key=lambda x: (x.level, x.id)):
        show(r, 0)


def cmd_validate(a):
    issues = validate(_load(a))
    for i in issues:
        print(i)
    n = {s: sum(1 for i in issues if i.severity == s) for s in ("error", "warning", "info")}
    print(f"\n{n['error']} errors, {n['warning']} warnings, {n['info']} info")
    return 1 if n["error"] and a.strict else 0


def cmd_matrix(a):
    print(f"{'Product':10}{'Feature':10}{'Function':10}{'Component':10}")
    for row in traceability_matrix(_load(a)):
        print("".join(f"{x or '-':10}" for x in row))


def cmd_metrics(a):
    for k, v in metrics(_load(a)).items():
        print(f"{k:30}: {v}")


def cmd_plan(a):
    for s in plan_sprints(_load(a), a.capacity, a.sprints):
        label = f"Sprint {s['sprint']}" if s["sprint"] != "backlog" else "Backlog"
        cap = f"/{s['capacity']}" if s["capacity"] else ""
        print(f"{label:9} points {s['used']}{cap}: {', '.join(s['items']) or '-'}")


def cmd_workup(a):
    rs = _load(a)
    r = rs.get(a.id)
    if not r:
        sys.exit(f"unknown requirement {a.id}")
    w = workup(rs, r)
    print(f"{r.id}: {r.title}")
    print(f"  suggested level : {w.suggested_level.label} ({w.confidence:.0%})")
    print(f"  suggested parent: {w.suggested_parent or '-'} (similarity {w.parent_similarity})")
    print(f"  abstract up to  : {', '.join(l.label for l in w.missing_levels_up) or '-'}")
    print(f"  refine down to  : {', '.join(l.label for l in w.missing_levels_down) or '-'}")
    for n in w.notes:
        print(f"  note: {n}")


def cmd_rank(a):
    rs = _load(a)
    rows = sorted((r for r in rs if r.level == Level.FUNCTION), key=lambda r: (-priority_score(r), natural_key(r.id)))
    print(f"{'ID':6}{'Score':8}{'V':>3}{'C':>3}{'R':>3}  Title")
    for r in rows:
        print(f"{r.id:6}{priority_score(r):<8}{r.value:>3}{r.cost:>3}{r.risk:>3}  {r.title}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ram", description="Agile Requirements Abstraction Model toolkit")
    p.add_argument("-f", "--file", default=str(DEFAULT), help="requirement set JSON")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("classify", help="classify a requirement text")
    s.add_argument("text"); s.set_defaults(fn=cmd_classify)
    sub.add_parser("tree", help="print the abstraction tree").set_defaults(fn=cmd_tree)
    s = sub.add_parser("validate", help="check structural rules")
    s.add_argument("--strict", action="store_true"); s.set_defaults(fn=cmd_validate)
    sub.add_parser("matrix", help="traceability matrix").set_defaults(fn=cmd_matrix)
    sub.add_parser("metrics", help="model metrics").set_defaults(fn=cmd_metrics)
    sub.add_parser("rank", help="rank function-level requirements").set_defaults(fn=cmd_rank)
    s = sub.add_parser("plan", help="sprint plan")
    s.add_argument("--capacity", type=int, default=14); s.add_argument("--sprints", type=int, default=3)
    s.set_defaults(fn=cmd_plan)
    s = sub.add_parser("workup", help="work-up advice for a requirement id")
    s.add_argument("id"); s.set_defaults(fn=cmd_workup)
    a = p.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
