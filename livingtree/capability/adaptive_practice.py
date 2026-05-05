"""AdaptivePractice — detect weak areas, self-study during idle time.

    Like a student who knows which chapters they're bad at and deliberately
    practices those during study hall.

    1. Quality tracking: per-template modification rate from user edits
    2. Weakness detection: identify templates/skills with low AgentEval scores
    3. Idle self-study: search for better samples, refine templates, test
    4. Progress tracking: did practice improve the quality score?

    Usage:
        ap = get_adaptive_practice()
        ap.record_modification("环评报告", "sec4.2.1", modified_chars=200)
        weaknesses = ap.detect_weaknesses()  # → [{template, section, score, trend}]
        await ap.practice_weakest(hub)       # self-study during idle
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

PRACTICE_FILE = Path(".livingtree/adaptive_practice.json")
MODIFICATION_LOG = Path(".livingtree/template_modifications.json")


@dataclass
class SkillScore:
    template: str
    section: str = ""
    quality_score: float = 1.0          # 0-1 from AgentEval
    user_mod_rate: float = 0.0          # % of generated content user modified
    total_generations: int = 0
    total_modifications: int = 0
    practice_count: int = 0
    last_practiced: float = 0.0
    score_history: list[float] = field(default_factory=list)
    trend: str = "stable"               # improving, declining, stable


class AdaptivePractice:
    """Self-aware weakness detection and idle self-study."""

    def __init__(self):
        PRACTICE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._scores: dict[str, SkillScore] = {}
        self._mod_log: list[dict] = []
        self._load()

    def record_modification(self, template: str, section: str, modified_chars: int = 0, total_chars: int = 0):
        """Record a user modification to generated content."""
        key = f"{template}|{section}"
        entry = {
            "template": template, "section": section,
            "modified_chars": modified_chars, "total_chars": total_chars,
            "timestamp": time.time(),
        }
        self._mod_log.append(entry)
        if len(self._mod_log) > 500:
            self._mod_log = self._mod_log[-500:]

        if key not in self._scores:
            self._scores[key] = SkillScore(template=template, section=section)

        s = self._scores[key]
        s.total_modifications += 1 if modified_chars > 0 else 0
        s.total_generations += 1
        s.user_mod_rate = s.total_modifications / max(s.total_generations, 1)
        s.score_history.append(1.0 - s.user_mod_rate)
        if len(s.score_history) > 20:
            s.score_history = s.score_history[-20:]

        # Detect trend
        if len(s.score_history) >= 5:
            recent = s.score_history[-5:]
            older = s.score_history[-10:-5] if len(s.score_history) >= 10 else s.score_history[:5]
            avg_recent = sum(recent) / len(recent)
            avg_older = sum(older) / len(older)
            if avg_recent > avg_older + 0.1:
                s.trend = "improving"
            elif avg_recent < avg_older - 0.1:
                s.trend = "declining"
            else:
                s.trend = "stable"

        s.quality_score = 1.0 - s.user_mod_rate
        self._maybe_save()

    def detect_weaknesses(self, top_n: int = 5) -> list[SkillScore]:
        """Find the weakest templates/sections. Ranked worst first."""
        if not self._scores:
            return []

        # Only consider sections with enough data
        scored = [
            s for s in self._scores.values()
            if s.total_generations >= 3
        ]

        # Sort by worst quality (lowest score), then by declining trend
        scored.sort(key=lambda s: (s.quality_score, 0 if s.trend == "declining" else 1))
        return scored[:top_n]

    async def practice_weakest(self, hub) -> SkillScore | None:
        """Self-study the weakest area during idle time.

        Steps:
        1. Identify weakest section
        2. Search for better reference documents via DeepSearch
        3. If found, load into DocStructureLearner for refinement
        4. Generate improved template version
        5. Auto-evaluate with AgentEval
        """
        weaknesses = self.detect_weaknesses(1)
        if not weaknesses:
            return None

        target = weaknesses[0]
        if target.practice_count >= 5:
            # Don't keep practicing if not improving
            if target.trend != "improving":
                return None

        logger.info(f"AdaptivePractice: studying {target.template}/{target.section} (score={target.quality_score:.2f})")

        if hub and hub.world:
            try:
                from ..network.external_access import get_external_access
                ext = get_external_access()
                query = f"{target.template} {target.section} 范文 模板"
                results = await ext.deep_search(query, hub=hub, max_results=5)

                if results:
                    target.practice_count += 1
                    target.last_practiced = time.time()
                    self._save()
                    logger.info(f"Practice: found {len(results)} references for {target.section}")
                    return target
            except Exception as e:
                logger.debug(f"Practice search: {e}")

        return target

    def report(self) -> dict[str, Any]:
        weaknesses = self.detect_weaknesses(5)
        strengths = sorted(
            [s for s in self._scores.values() if s.total_generations >= 3],
            key=lambda s: -s.quality_score,
        )[:5]

        return {
            "total_tracked": len(self._scores),
            "weakest": [
                {"template": w.template, "section": w.section,
                 "score": round(w.quality_score, 2), "trend": w.trend,
                 "mod_rate": round(w.user_mod_rate * 100, 1)}
                for w in weaknesses
            ],
            "strongest": [
                {"template": s.template, "section": s.section,
                 "score": round(s.quality_score, 2)}
                for s in strengths
            ],
        }

    def _save(self):
        data = {}
        for key, s in self._scores.items():
            data[key] = {
                "template": s.template, "section": s.section,
                "quality_score": s.quality_score, "user_mod_rate": s.user_mod_rate,
                "total_generations": s.total_generations,
                "total_modifications": s.total_modifications,
                "practice_count": s.practice_count,
                "last_practiced": s.last_practiced,
                "score_history": s.score_history, "trend": s.trend,
            }
        PRACTICE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if not PRACTICE_FILE.exists():
            return
        try:
            data = json.loads(PRACTICE_FILE.read_text(encoding="utf-8"))
            for key, d in data.items():
                self._scores[key] = SkillScore(
                    template=d.get("template", ""), section=d.get("section", ""),
                    quality_score=d.get("quality_score", 1.0),
                    user_mod_rate=d.get("user_mod_rate", 0.0),
                    total_generations=d.get("total_generations", 0),
                    total_modifications=d.get("total_modifications", 0),
                    practice_count=d.get("practice_count", 0),
                    last_practiced=d.get("last_practiced", 0),
                    score_history=d.get("score_history", []),
                    trend=d.get("trend", "stable"),
                )
        except Exception:
            pass

    def _maybe_save(self):
        if len(self._scores) % 10 == 0:
            self._save()


_ap: AdaptivePractice | None = None


def get_adaptive_practice() -> AdaptivePractice:
    global _ap
    if _ap is None:
        _ap = AdaptivePractice()
    return _ap
