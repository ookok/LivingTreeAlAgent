"""Direct Preference Optimization for Agents — learn from binary preferences.

Based on DPO (NeurIPS 2023): RLHF is unnecessary for alignment.
Convert preference learning into binary cross-entropy — simple, stable, direct.

Applied to LivingTree without model training:
- Every user accept/reject/edit is a preference pair (chosen vs rejected)
- Build implicit reward signal from interaction patterns
- Use preferences to rank skills, route models, optimize responses
- No RL, no reward model, no PPO — just counting and ranking

Preference sources already available:
- HITL approve/reject
- User edits to AI responses
- Tool success/failure
- Skill hit/miss
- Model election outcomes
"""

from __future__ import annotations

import json as _json
import math
import time as _time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger


PREF_DIR = Path(".livingtree/preferences")
PREF_DIR.mkdir(parents=True, exist_ok=True)
PREF_LOG = PREF_DIR / "preferences.jsonl"


@dataclass
class PreferencePair:
    """A single binary preference: chosen > rejected."""
    pair_id: str
    context: str           # What task/query was this for
    chosen: str            # The preferred response/action
    rejected: str          # The rejected response/action  
    source: str = ""       # "hitl", "edit", "tool_result", "model_election"
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)


class PreferenceTracker:
    """Collects binary preference pairs from all interaction channels."""

    def __init__(self):
        self._pairs: list[PreferencePair] = []
        self._scores: dict[str, float] = defaultdict(lambda: 0.5)  # entity → score
        self._counts: dict[str, int] = defaultdict(int)

    def record(self, context: str, chosen: str, rejected: str,
               source: str = "user", metadata: dict | None = None) -> str:
        """Record a binary preference: the user preferred 'chosen' over 'rejected'."""
        import hashlib
        pid = hashlib.md5(f"{context}{chosen}{_time.time()}".encode()).hexdigest()[:12]
        pair = PreferencePair(
            pair_id=pid, context=context, chosen=chosen,
            rejected=rejected, source=source,
            timestamp=_time.time(), metadata=metadata or {},
        )
        self._pairs.append(pair)

        # Update entity scores using DPO-inspired binary preference
        # chosen entity gets +1, rejected gets -1 (simple Bradley-Terry approximation)
        self._scores[chosen] = min(1.0, self._scores.get(chosen, 0.5) + 0.1)
        self._scores[rejected] = max(0.0, self._scores.get(rejected, 0.5) - 0.1)
        self._counts[chosen] += 1
        self._counts[rejected] += 1

        # Persist
        with open(PREF_LOG, "a", encoding="utf-8") as f:
            f.write(_json.dumps(pair.__dict__, ensure_ascii=False) + "\n")

        return pid

    def record_implicit(self, context: str, response: str, was_accepted: bool):
        """Record implicit preference: user accepted/used the response or not."""
        if was_accepted:
            self._scores[response[:50]] = min(1.0, self._scores.get(response[:50], 0.5) + 0.05)
        else:
            self._scores[response[:50]] = max(0.0, self._scores.get(response[:50], 0.5) - 0.05)

    def get_score(self, entity: str) -> float:
        """Get learned preference score for an entity (model/skill/tool/pattern)."""
        return self._scores.get(entity, 0.5)

    def rank_entities(self, entities: list[str]) -> list[tuple[str, float]]:
        """Rank entities by learned preference. Higher = more preferred.

        This is the DPO-equivalent: no RL needed, just sort by score.
        """
        ranked = [(e, self.get_score(e)) for e in entities]
        ranked.sort(key=lambda x: -x[1])
        return ranked

    def best_entity(self, entities: list[str]) -> Optional[str]:
        """Get the most preferred entity from a list."""
        ranked = self.rank_entities(entities)
        return ranked[0][0] if ranked else None

    def preference_strength(self, entity_a: str, entity_b: str) -> float:
        """How much more is entity_a preferred over entity_b? 0-1 scale."""
        score_a = self.get_score(entity_a)
        score_b = self.get_score(entity_b)
        if score_a <= score_b:
            return 0.0
        # DPO-style: probability that a is preferred over b
        return 1.0 / (1.0 + math.exp(-(score_a - score_b) * 5))

    def stats(self) -> dict:
        total = len(self._pairs)
        return {
            "total_pairs": total,
            "total_entities": len(self._scores),
            "sources": self._source_breakdown(),
            "top_preferred": sorted(
                [(e, round(s, 3)) for e, s in self._scores.items() if s > 0.55],
                key=lambda x: -x[1],
            )[:10],
            "most_rejected": sorted(
                [(e, round(s, 3)) for e, s in self._scores.items() if s < 0.45],
                key=lambda x: x[1],
            )[:5],
        }

    def _source_breakdown(self) -> dict:
        sources = {}
        for p in self._pairs:
            sources[p.source] = sources.get(p.source, 0) + 1
        return sources


class PreferenceRouter:
    """Uses learned preferences to route decisions without RL."""

    def __init__(self, tracker: PreferenceTracker):
        self._tracker = tracker

    def route_model(self, candidates: list[str]) -> str:
        """Select the most preferred model for this task type."""
        ranked = self._tracker.rank_entities(candidates)
        return ranked[0][0] if ranked else candidates[0] if candidates else ""

    def route_skill(self, task_context: str, available_skills: list[str]) -> str:
        """Select the most preferred skill based on learned preferences."""
        ranked = self._tracker.rank_entities(available_skills)
        best = ranked[0][0] if ranked else ""
        strength = self._tracker.preference_strength(best, ranked[1][0]) if len(ranked) > 1 else 1.0
        logger.debug(f"Preference route: {best} (strength: {strength:.1%})")
        return best

    def should_retry(self, entity: str, fallback: str) -> bool:
        """Should we retry with a different entity based on preference strength?"""
        strength = self._tracker.preference_strength(fallback, entity)
        return strength > 0.6  # Fallback is significantly preferred

    def stats(self) -> dict:
        return self._tracker.stats()


# ═══ Integration with existing systems ═══

class DPOHooks:
    """Hooks to collect preferences from existing interaction channels."""

    def __init__(self, tracker: PreferenceTracker = None):
        self._tracker = tracker or get_preferences()

    def on_hitl_decision(self, request_id: str, approved: bool, context: str = ""):
        """HITL approve/reject → preference pair."""
        if approved:
            self._tracker.record_implicit(context, f"hitl_{request_id}", True)
        else:
            self._tracker.record_implicit(context, f"hitl_{request_id}", False)

    def on_user_edit(self, original: str, edited: str, context: str = ""):
        """User edited AI response → chosen=edited, rejected=original."""
        if original != edited and len(edited) > 10:
            self._tracker.record(context, edited[:100], original[:100], source="edit")

    def on_model_election(self, chosen_model: str, rejected_models: list[str],
                           task: str = ""):
        """Model was chosen over others → implicit preference."""
        for rejected in rejected_models:
            self._tracker.record(task, chosen_model, rejected, source="model_election")

    def on_tool_result(self, tool_name: str, success: bool, context: str = ""):
        """Tool succeeded/failed → implicit preference."""
        self._tracker.record_implicit(context, f"tool_{tool_name}", success)


_preferences_instance: Optional[PreferenceTracker] = None
_router_instance: Optional[PreferenceRouter] = None
_hooks_instance: Optional[DPOHooks] = None


def get_preferences() -> PreferenceTracker:
    global _preferences_instance
    if _preferences_instance is None:
        _preferences_instance = PreferenceTracker()
    return _preferences_instance


def get_pref_router() -> PreferenceRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = PreferenceRouter(get_preferences())
    return _router_instance


def get_dpo_hooks() -> DPOHooks:
    global _hooks_instance
    if _hooks_instance is None:
        _hooks_instance = DPOHooks()
    return _hooks_instance
