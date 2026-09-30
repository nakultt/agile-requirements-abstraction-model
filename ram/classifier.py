"""Lexicon-based abstraction-level classifier.

A deliberately transparent baseline: every cue has a weight, the level with the highest
cumulative weight wins, and the margin over the runner-up is reported as confidence.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

from .model import Level

_LEX_PATH = Path(__file__).with_name("lexicon.json")
_KEYS = {"product": Level.PRODUCT, "feature": Level.FEATURE,
         "function": Level.FUNCTION, "component": Level.COMPONENT}


@dataclass
class Classification:
    level: Level
    scores: Dict[Level, float]
    confidence: float          # 0..1, softmax share of the winning level
    cues: List[str]            # matched cue strings, for explainability


@lru_cache(maxsize=1)
def _lexicon() -> Dict[Level, List[Tuple[re.Pattern, float]]]:
    raw = json.loads(_LEX_PATH.read_text(encoding="utf-8"))
    return {lvl: [(re.compile(p, re.I), w) for p, w in raw[k]] for k, lvl in _KEYS.items()}


def classify(text: str) -> Classification:
    scores = {lvl: 0.0 for lvl in Level}
    cues: List[str] = []
    for lvl, rules in _lexicon().items():
        for pat, weight in rules:
            for m in pat.finditer(text):
                scores[lvl] += weight
                cues.append(f"{lvl.label}:{m.group(0).lower()}")
    if not any(scores.values()):                       # no cue at all -> weak prior for Function
        scores[Level.FUNCTION] = 0.1
    ranked = sorted(scores.items(), key=lambda kv: (kv[1], int(kv[0])), reverse=True)
    best = ranked[0]                                   # ties resolve to the more concrete level
    total = sum(math.exp(v) for v in scores.values())
    conf = math.exp(best[1]) / total if total else 0.0
    return Classification(best[0], scores, round(conf, 3), cues)
