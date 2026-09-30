"""Work-up engine: placement, validation and abstraction/refinement advice for requirements.

In RAM, every incoming requirement is (1) classified to an abstraction level, (2) abstracted
upwards until it is linked to a product-level statement, and (3) broken down until at
least one level of implementable detail exists. `workup` automates the advice; `validate`
checks the resulting model against structural rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

from .classifier import classify
from .model import Level, Requirement, RequirementSet, Status

STOP = set("the a an of to and or in on for with by is are be shall can user system it that this as at from".split())


def tokens(text: str) -> Set[str]:
    words = re.findall(r"[a-z][a-z\-]+", text.lower())
    return {w.rstrip("s") for w in words if w not in STOP and len(w) > 2}


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


@dataclass
class Issue:
    code: str
    severity: str        # "error" | "warning" | "info"
    req_id: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.upper():7}] {self.code} {self.req_id}: {self.message}"


RULES = {
    "R001": "Non-product requirement has no parent (orphan)",
    "R002": "Parent id does not exist",
    "R003": "Parent is not exactly one level above (level skipped or inverted)",
    "R004": "Cycle in the parent chain",
    "R005": "Stated level disagrees with classifier (confident)",
    "R006": "Product/feature-level requirement has no children (unrefined)",
    "R007": "Function/component requirement lacks acceptance criteria",
    "R008": "Near-duplicate of another requirement at the same level",
    "R009": "Title too long (>90 chars) or empty",
    "R010": "Requirement still in 'new' status and outside the model",
}


def validate(rs: RequirementSet, dup_threshold: float = 0.6, confidence: float = 0.55) -> List[Issue]:
    issues: List[Issue] = []
    reqs = list(rs)
    for r in reqs:
        if not r.title.strip() or len(r.title) > 90:
            issues.append(Issue("R009", "warning", r.id, "title empty or longer than 90 characters"))
        if r.status == Status.NEW:
            issues.append(Issue("R010", "info", r.id, "not yet worked up; excluded from planning"))
            continue
        if r.parent is not None and rs.get(r.parent) is not None and _in_cycle(rs, r):
            issues.append(Issue("R004", "error", r.id, "cyclic parent chain"))
        elif r.level != Level.PRODUCT and r.parent is None:
            issues.append(Issue("R001", "error", r.id, f"{r.level.label} requirement has no parent"))
        elif r.parent is not None:
            p = rs.get(r.parent)
            if p is None:
                issues.append(Issue("R002", "error", r.id, f"parent '{r.parent}' not found"))
            elif p.level != r.level - 1:
                issues.append(Issue("R003", "warning", r.id,
                                    f"{r.level.label} linked to {p.level.label} ({p.id}); "
                                    f"expected {Level(max(1, r.level - 1)).label}"))
        c = classify(r.text)
        if c.level != r.level and c.confidence >= confidence:
            issues.append(Issue("R005", "warning", r.id,
                                f"stated {r.level.label} but text reads like {c.level.label} ({c.confidence:.0%})"))
        if r.level in (Level.PRODUCT, Level.FEATURE) and not rs.children(r.id):
            issues.append(Issue("R006", "info", r.id, "no refinement below this requirement yet"))
        if r.level >= Level.FUNCTION and not r.acceptance:
            issues.append(Issue("R007", "warning", r.id, "no acceptance criteria recorded"))
    for i, a in enumerate(reqs):
        for b in reqs[i + 1:]:
            if a.level == b.level and similarity(a.text, b.text) >= dup_threshold:
                issues.append(Issue("R008", "warning", b.id, f"near-duplicate of {a.id}"))
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(issues, key=lambda x: (order[x.severity], x.req_id, x.code))


def _in_cycle(rs: RequirementSet, r: Requirement) -> bool:
    seen, cur = {r.id}, rs.get(r.parent)
    while cur is not None:
        if cur.id in seen:
            return True
        seen.add(cur.id)
        cur = rs.get(cur.parent) if cur.parent else None
    return False


@dataclass
class WorkupReport:
    req_id: str
    suggested_level: Level
    confidence: float
    suggested_parent: Optional[str]
    parent_similarity: float
    missing_levels_up: List[Level] = field(default_factory=list)      # abstraction needed
    missing_levels_down: List[Level] = field(default_factory=list)    # refinement needed
    notes: List[str] = field(default_factory=list)


def suggest_parent(rs: RequirementSet, text: str, level: Level, exclude: str = ""):
    if level == Level.PRODUCT:
        return None, 0.0
    cands = [r for r in rs if r.level == level - 1 and r.id != exclude and r.status != Status.NEW]
    if not cands:
        return None, 0.0
    best = max(cands, key=lambda r: (similarity(text, r.text), r.id))
    return best.id, round(similarity(text, best.text), 3)


def workup(rs: RequirementSet, req: Requirement) -> WorkupReport:
    """Produce RAM work-up advice for one requirement (does not mutate the set)."""
    c = classify(req.text)
    parent, sim = suggest_parent(rs, req.text, c.level, req.id)
    rep = WorkupReport(req.id, c.level, c.confidence, parent, sim)
    if c.level > Level.PRODUCT:
        if parent:
            present = {rs.get(parent).level} | {a.level for a in rs.ancestors(parent)}
            rep.missing_levels_up = [Level(l) for l in range(c.level - 1, 0, -1) if Level(l) not in present]
        else:
            rep.missing_levels_up = [Level(l) for l in range(c.level - 1, 0, -1)]
            rep.notes.append("no plausible parent found; write an abstracted statement one level up")
    if c.level < Level.FUNCTION:
        rep.missing_levels_down = [Level(l) for l in range(c.level + 1, Level.FUNCTION + 1)]
        rep.notes.append("requirement is too abstract for a sprint; refine to function level")
    if c.level == Level.COMPONENT:
        rep.notes.append("component-level detail: attach to a function-level parent as a constraint")
    if c.confidence < 0.4:
        rep.notes.append("low classifier confidence; confirm level manually")
    if parent and sim < 0.1:
        rep.notes.append("suggested parent has weak lexical overlap; verify link")
    return rep
