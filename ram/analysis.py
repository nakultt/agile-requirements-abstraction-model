"""Traceability, metrics and sprint planning over a RAM requirement set."""
from __future__ import annotations

import re
from typing import Dict, List

from .model import Level, Requirement, RequirementSet, Status

ACTIVE = (Status.ACCEPTED, Status.IN_SPRINT, Status.DONE, Status.WORKUP)


def natural_key(s: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def priority_score(r: Requirement) -> float:
    """Cost-value ratio (Karlsson & Ryan, 1997) with a half-weighted risk penalty."""
    return round(r.value / (r.cost + 0.5 * r.risk), 3)


def traceability_matrix(rs: RequirementSet) -> List[List[str]]:
    """One row per leaf-to-root chain: [product, feature, function, component]; '' when absent."""
    rows = []
    leaves = [r for r in rs if r.status in ACTIVE and not rs.children(r.id)]
    for leaf in leaves:
        chain = {leaf.level: leaf.id}
        for a in rs.ancestors(leaf.id):
            chain.setdefault(a.level, a.id)
        rows.append([chain.get(l, "") for l in Level])
    rows.sort(key=lambda row: tuple(x or "~" for x in row))
    return rows


def metrics(rs: RequirementSet) -> Dict[str, object]:
    active = [r for r in rs if r.status in ACTIVE]
    per_level = {l.label: sum(1 for r in active if r.level == l) for l in Level}
    implementable = [r for r in active if r.level >= Level.FUNCTION]
    traced = [r for r in implementable
              if any(a.level == Level.PRODUCT for a in rs.ancestors(r.id))]
    products = rs.at_level(Level.PRODUCT)
    refined = [p for p in products if rs.descendants(p.id)]
    with_ac = [r for r in implementable if r.acceptance]
    ratio = lambda a, b: round(a / b, 3) if b else 0.0
    return {
        "total": len(rs),
        "new_unprocessed": sum(1 for r in rs if r.status == Status.NEW),
        "per_level": per_level,
        "traceability_coverage": ratio(len(traced), len(implementable)),
        "product_refinement_coverage": ratio(len(refined), len(products)),
        "acceptance_coverage": ratio(len(with_ac), len(implementable)),
        "remaining_value": sum(r.value for r in implementable if r.status != Status.DONE),
    }


def plan_sprints(rs: RequirementSet, capacity: int, sprints: int = 3) -> List[Dict[str, object]]:
    """Greedy cost-value packing of function-level requirements into fixed-capacity sprints.

    Component-level children travel with their function-level parent (their cost is added).
    Only requirements that trace up to a product goal are planned.
    """
    def total_cost(r):
        return r.cost + sum(c.cost for c in rs.children(r.id) if c.level == Level.COMPONENT)

    def traced(r):
        return any(a.level == Level.PRODUCT for a in rs.ancestors(r.id))

    pool = [r for r in rs.at_level(Level.FUNCTION) if r.status == Status.ACCEPTED and traced(r)]
    pool.sort(key=lambda r: (-priority_score(r), natural_key(r.id)))   # ties: FN5 before FN12
    plan = []
    for n in range(1, sprints + 1):
        used, items = 0, []
        for r in list(pool):
            c = total_cost(r)
            if used + c <= capacity:
                items.append(r.id)
                used += c
                pool.remove(r)
        plan.append({"sprint": n, "capacity": capacity, "used": used, "items": items})
    plan.append({"sprint": "backlog", "capacity": None,
                 "used": sum(total_cost(r) for r in pool), "items": [r.id for r in pool]})
    return plan
