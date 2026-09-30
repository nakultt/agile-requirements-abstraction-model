"""Core data model: the four RAM abstraction levels and a requirement repository."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import IntEnum, Enum
from pathlib import Path
from typing import Dict, Iterator, List, Optional


class Level(IntEnum):
    """Abstraction levels of the Requirements Abstraction Model (Gorschek & Wohlin, 2006)."""
    PRODUCT = 1    # goals and strategy of the product / organisation
    FEATURE = 2    # features the product offers to fulfil the goals
    FUNCTION = 3   # what a user can do / what the system does (backlog-ready story)
    COMPONENT = 4  # detailed, measurable, design-near statements

    @property
    def label(self) -> str:
        return self.name.capitalize()


class Status(str, Enum):
    NEW = "new"            # raw, not yet through work-up
    WORKUP = "workup"      # being abstracted / refined
    ACCEPTED = "accepted"  # placed in the model, ready for planning
    IN_SPRINT = "in_sprint"
    DONE = "done"
    REJECTED = "rejected"


@dataclass
class Requirement:
    id: str
    title: str
    description: str = ""
    level: Level = Level.FUNCTION
    parent: Optional[str] = None
    status: Status = Status.ACCEPTED
    value: int = 5          # business value, 1-10
    cost: int = 5           # estimated effort, 1-10 (story points proxy)
    risk: int = 3           # delivery/technical risk, 1-10
    source: str = ""
    rationale: str = ""
    acceptance: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return f"{self.title}. {self.description}".strip()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["level"] = int(self.level)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Requirement":
        d = dict(d)
        d["level"] = Level(int(d.get("level", 3)))
        d["status"] = Status(d.get("status", "accepted"))
        return cls(**d)


class RequirementSet:
    """An in-memory repository of requirements arranged as a level-structured forest."""

    def __init__(self, name: str = "Untitled", requirements: Optional[List[Requirement]] = None):
        self.name = name
        self._items: Dict[str, Requirement] = {}
        for r in requirements or []:
            self.add(r)

    # -- basic collection API -------------------------------------------------
    def add(self, req: Requirement) -> None:
        if req.id in self._items:
            raise ValueError(f"duplicate requirement id: {req.id}")
        self._items[req.id] = req

    def get(self, rid: str) -> Optional[Requirement]:
        return self._items.get(rid)

    def __iter__(self) -> Iterator[Requirement]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, rid: str) -> bool:
        return rid in self._items

    def at_level(self, level: Level) -> List[Requirement]:
        return [r for r in self if r.level == level]

    # -- hierarchy ------------------------------------------------------------
    def children(self, rid: str) -> List[Requirement]:
        return [r for r in self if r.parent == rid]

    def ancestors(self, rid: str) -> List[Requirement]:
        """Chain from the direct parent up to the root. Stops on unknown ids and cycles."""
        chain, seen = [], {rid}
        cur = self.get(rid)
        while cur and cur.parent and cur.parent not in seen:
            nxt = self.get(cur.parent)
            if nxt is None:
                break
            chain.append(nxt)
            seen.add(nxt.id)
            cur = nxt
        return chain

    def descendants(self, rid: str) -> List[Requirement]:
        out, stack = [], [rid]
        while stack:
            for c in self.children(stack.pop()):
                out.append(c)
                stack.append(c.id)
        return out

    def roots(self) -> List[Requirement]:
        return [r for r in self if r.parent is None]

    # -- persistence ----------------------------------------------------------
    def to_dict(self) -> dict:
        return {"name": self.name, "requirements": [r.to_dict() for r in self]}

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: dict) -> "RequirementSet":
        return cls(d.get("name", "Untitled"), [Requirement.from_dict(x) for x in d["requirements"]])

    @classmethod
    def load(cls, path: str | Path) -> "RequirementSet":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
