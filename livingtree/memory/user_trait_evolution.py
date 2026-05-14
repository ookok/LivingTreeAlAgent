"""UserTraitEvolutionTree — PersonaVLM PEM momentum-based user personality tracking.

PersonaVLM (Nie et al., CVPR 2026 Highlight): Momentum-based Personality Evolving
Mechanism (PEM) infers user's evolving latent traits from conversation behavior
and applies smooth momentum updates (β=0.85) to prevent noisy fluctuations.

Seven latent user traits tracked:
  engagement_depth        — how deeply the user engages with technical topics
  technical_sophistication — user's demonstrated technical knowledge level
  patience_tolerance      — tolerance for iterative correction/refinement
  feedback_directness     — how direct the user is in providing feedback
  topic_breadth           — diversity of topics the user covers
  interaction_regularity  — consistency of interaction patterns
  delegation_comfort      — willingness to delegate complex tasks

Momentum update formula (PEM):
  P_t = β·P_{t-1} + (1-β)·f(conversation_behavior)
  where β = 0.85, f() = trait inference from current conversation

Integration:
    ute = get_user_trait_evolution()
    ute.infer_from_conversation(messages, user_id)
    traits = ute.get_trait_vector(user_id)  # → dict[str, float]
    report = ute.get_growth_summary(user_id)
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

MOMENTUM_BETA = 0.85
MAX_SNAPSHOTS = 500

DEFAULT_TRAITS = {
    "engagement_depth": 0.50,
    "technical_sophistication": 0.50,
    "patience_tolerance": 0.70,
    "feedback_directness": 0.50,
    "topic_breadth": 0.40,
    "interaction_regularity": 0.50,
    "delegation_comfort": 0.50,
}

TRAIT_BEHAVIOR_SIGNALS = {
    "engagement_depth": {
        "increases": ["追问", "深入", "详细", "原理", "为什么", "how does", "explain", "deep"],
        "decreases": ["简单", "快速", "简短", "概述", "summary", "brief"],
    },
    "technical_sophistication": {
        "increases": ["框架", "架构", "优化", "部署", "Docker", "K8s", "API", "GPU"],
        "decreases": ["基础", "入门", "初级", "新手", "beginner"],
    },
    "patience_tolerance": {
        "increases": ["再试", "继续", "没事", "重来", "retry", "again"],
        "decreases": ["怎么又", "还是错", "不对", "还是不行", "wrong", "still"],
    },
    "feedback_directness": {
        "increases": ["不对", "错误", "不要", "改", "fix", "correct", "wrong"],
        "decreases": ["建议", "也许", "可能", "maybe", "perhaps", "suggest"],
    },
    "topic_breadth": {
        "increases": [],  # Inferred from domain diversity
        "decreases": [],
    },
    "interaction_regularity": {
        "increases": [],  # Inferred from time gaps
        "decreases": [],
    },
    "delegation_comfort": {
        "increases": ["帮我", "你来", "交给你", "你来处理", "handle", "delegate"],
        "decreases": ["我自己", "我来改", "我看看", "let me check", "I'll do"],
    },
}


@dataclass
class UserTraitSnapshot:
    user_id: str
    generation: int
    traits: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    conversation_stats: dict[str, Any] = field(default_factory=dict)

    def trait_vector(self) -> list[float]:
        return [self.traits[k] for k in sorted(self.traits)]


@dataclass
class TraitGrowthReport:
    first_gen: int
    last_gen: int
    span: int
    trait_deltas: dict[str, float] = field(default_factory=dict)
    trait_trends: dict[str, str] = field(default_factory=dict)
    emergent_traits: list[str] = field(default_factory=list)
    stable_traits: list[str] = field(default_factory=list)


class MomentumPersonalityUpdater:
    """Momentum-based smooth personality update (PEM, PersonaVLM).

    P_t = β·P_{t-1} + (1-β)·inferred_t
    Prevents noisy conversation-to-conversation fluctuations.
    """

    def __init__(self, beta: float = MOMENTUM_BETA):
        self.beta = beta

    def update(self, current: dict[str, float],
               inferred: dict[str, float]) -> dict[str, float]:
        updated = {}
        for trait, old_val in current.items():
            inferred_val = inferred.get(trait, old_val)
            new_val = self.beta * old_val + (1.0 - self.beta) * inferred_val
            new_val = max(0.05, min(0.95, new_val))
            updated[trait] = round(new_val, 4)
        return updated

    def should_evolve(self, old_traits: dict[str, float],
                      new_traits: dict[str, float], threshold: float = 0.10) -> list[str]:
        evolved = []
        for trait in old_traits:
            delta = abs(new_traits.get(trait, 0.5) - old_traits.get(trait, 0.5))
            if delta > threshold:
                evolved.append(trait)
        return evolved


class UserTraitEvolutionTree:
    """Tracks user personality trait evolution across conversations.

    Mirrors dna/trait_evolution_tree.py but for USER traits (not agent traits).
    Uses PEM momentum-based smoothing for stable evolution tracking.
    """

    _instance: UserTraitEvolutionTree | None = None

    @classmethod
    def instance(cls) -> UserTraitEvolutionTree:
        if cls._instance is None:
            cls._instance = UserTraitEvolutionTree()
        return cls._instance

    def __init__(self):
        self._users: dict[str, deque[UserTraitSnapshot]] = {}
        self._current_traits: dict[str, dict[str, float]] = {}
        self._updater = MomentumPersonalityUpdater()
        self._max_snapshots = MAX_SNAPSHOTS

    def infer_from_conversation(self, messages: list[str],
                                user_id: str = "default") -> dict[str, float]:
        inferred = dict(DEFAULT_TRAITS)
        combined = " ".join(messages).lower()

        for trait, signals in TRAIT_BEHAVIOR_SIGNALS.items():
            inc_count = sum(1 for s in signals["increases"] if s.lower() in combined)
            dec_count = sum(1 for s in signals["decreases"] if s.lower() in combined)
            if inc_count + dec_count == 0:
                continue
            delta = (inc_count - dec_count) / max(inc_count + dec_count, 1)
            inferred[trait] = max(0.05, min(0.95, inferred[trait] + delta * 0.08))

        inferred["topic_breadth"] = self._infer_topic_breadth(combined)
        inferred["interaction_regularity"] = self._infer_regularity(messages)

        self._store_snapshot(user_id, inferred)
        return inferred

    def get_trait_vector(self, user_id: str = "default") -> dict[str, float]:
        if user_id in self._current_traits:
            return dict(self._current_traits[user_id])
        return dict(DEFAULT_TRAITS)

    def get_growth_summary(self, user_id: str = "default") -> TraitGrowthReport:
        history = self._users.get(user_id, deque())
        if len(history) < 2:
            return TraitGrowthReport(first_gen=0, last_gen=0, span=0)

        first = history[0]
        last = history[-1]

        deltas = {}
        trends = {}
        for trait in DEFAULT_TRAITS:
            delta = last.traits.get(trait, 0.5) - first.traits.get(trait, 0.5)
            deltas[trait] = round(delta, 4)
            if delta > 0.05:
                trends[trait] = "rising"
            elif delta < -0.05:
                trends[trait] = "declining"
            else:
                trends[trait] = "stable"

        report = TraitGrowthReport(
            first_gen=first.generation,
            last_gen=last.generation,
            span=last.generation - first.generation,
            trait_deltas=deltas,
            trait_trends=trends,
            emergent_traits=[t for t, d in deltas.items() if d > 0.15],
            stable_traits=[t for t, d in deltas.items() if abs(d) < 0.03],
        )
        return report

    def get_trait_timeline(self, user_id: str, trait: str) -> list[float]:
        history = self._users.get(user_id, deque())
        return [s.traits.get(trait, 0.5) for s in history]

    def _store_snapshot(self, user_id: str, inferred: dict[str, float]):
        if user_id not in self._users:
            self._users[user_id] = deque(maxlen=self._max_snapshots)
            self._current_traits[user_id] = dict(DEFAULT_TRAITS)

        history = self._users[user_id]
        generation = len(history) + 1

        self._current_traits[user_id] = self._updater.update(
            self._current_traits[user_id], inferred)

        snapshot = UserTraitSnapshot(
            user_id=user_id,
            generation=generation,
            traits=dict(self._current_traits[user_id]),
            conversation_stats={"message_count": 1},
        )
        history.append(snapshot)

    @staticmethod
    def _infer_topic_breadth(combined: str) -> float:
        domains = []
        tech_kw = ["代码", "code", "API", "docker", "git", "部署"]
        data_kw = ["数据", "data", "分析", "analysis", "统计"]
        writing_kw = ["写", "文档", "报告", "document", "write"]
        design_kw = ["设计", "架构", "design", "architecture"]

        for kws in [tech_kw, data_kw, writing_kw, design_kw]:
            if any(kw.lower() in combined for kw in kws):
                domains.append(1)
        return min(0.95, len(domains) / 4.0 + 0.3)

    @staticmethod
    def _infer_regularity(messages: list[str]) -> float:
        if len(messages) < 3:
            return 0.5
        lengths = [len(m) for m in messages]
        avg_len = sum(lengths) / len(lengths)
        variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
        cv = math.sqrt(variance) / max(avg_len, 1)
        return min(0.95, 1.0 - cv * 0.5)


_ute: UserTraitEvolutionTree | None = None


def get_user_trait_evolution() -> UserTraitEvolutionTree:
    global _ute
    if _ute is None:
        _ute = UserTraitEvolutionTree()
    return _ute


__all__ = [
    "UserTraitEvolutionTree", "UserTraitSnapshot", "TraitGrowthReport",
    "MomentumPersonalityUpdater", "DEFAULT_TRAITS", "MOMENTUM_BETA",
    "get_user_trait_evolution",
]
