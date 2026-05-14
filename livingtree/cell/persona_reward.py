"""PersonaRewardModel — PersonaVLM GRPO reward shaping for personalized generation.

PersonaVLM (CVPR 2026): Two-stage training with custom GRPO reward model
(Qwen3-30B as judge) scoring persona alignment. This module provides:
  1. persona_preservation_reward() — penalize responses contradicting known facts
  2. persona_reference_reward() — reward responses referencing user preferences
  3. trait_alignment_reward() — reward style matching inferred user traits
  4. PersonaRewardModel — unified reward model with weighted composite scoring

GRPO integration: plug into swift_trainer.py GRPO reward pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class PersonaRewardScores:
    preservation: float = 0.0
    reference: float = 0.0
    trait_alignment: float = 0.0
    composite: float = 0.0

    def weighted_score(self, weights: dict[str, float] = None) -> float:
        w = weights or {"preservation": 0.40, "reference": 0.30, "trait_alignment": 0.30}
        return (
            self.preservation * w.get("preservation", 0.40)
            + self.reference * w.get("reference", 0.30)
            + self.trait_alignment * w.get("trait_alignment", 0.30)
        )


class PersonaRewardModel:
    """GRPO-compatible reward model for persona alignment.

    Three reward axes:
      1. Preservation: response must NOT contradict known persona facts
      2. Reference: response SHOULD reference relevant user preferences when appropriate
      3. Trait Alignment: response style SHOULD match inferred user traits
    """

    def __init__(self):
        self._known_facts: dict[str, list[str]] = {}
        self._trait_profile: dict[str, float] = {}

    def register_facts(self, user_id: str, facts: list[str]) -> None:
        self._known_facts[user_id] = [f.lower() for f in facts]

    def register_traits(self, traits: dict[str, float]) -> None:
        self._trait_profile.update(traits)

    def score(self, response: str, user_id: str = "default",
              query: str = "", weights: dict[str, float] = None) -> PersonaRewardScores:
        scores = PersonaRewardScores()
        response_lower = response.lower()

        scores.preservation = self._score_preservation(response_lower, user_id)
        scores.reference = self._score_reference(response_lower, user_id, query)
        scores.trait_alignment = self._score_trait_alignment(response_lower)
        scores.composite = scores.weighted_score(weights)

        return scores

    def _score_preservation(self, response_lower: str, user_id: str) -> float:
        facts = self._known_facts.get(user_id, [])
        if not facts:
            return 1.0

        contradictions = 0
        for fact in facts:
            fact_terms = fact.split()
            if len(fact_terms) < 3:
                continue
            negations = ["not", "no", "don't", "doesn't", "不", "没", "非", "无"]
            for neg in negations:
                if neg in response_lower and any(t in response_lower for t in fact_terms):
                    contradictions += 1
                    break

        penalty = contradictions * 0.25
        return max(0.0, 1.0 - penalty)

    def _score_reference(self, response_lower: str, user_id: str,
                         query: str) -> float:
        facts = self._known_facts.get(user_id, [])
        if not facts:
            return 0.5

        referenced = 0
        for fact in facts:
            fact_terms = [t for t in fact.split() if len(t) > 2]
            if sum(1 for t in fact_terms if t in response_lower) >= len(fact_terms) * 0.4:
                referenced += 1

        ref_ratio = min(1.0, referenced / max(len(facts) * 0.3, 1))
        return round(0.3 + ref_ratio * 0.7, 4)

    def _score_trait_alignment(self, response_lower: str) -> float:
        traits = self._trait_profile
        if not traits:
            return 0.5

        score = 0.5
        directness = traits.get("feedback_directness", 0.5)

        response_len = len(response_lower.split())
        if directness > 0.6:
            if 30 <= response_len <= 150:
                score += 0.15
            elif response_len > 300:
                score -= 0.10
        else:
            if response_len > 200:
                score += 0.10

        sophistication = traits.get("technical_sophistication", 0.5)
        technical_terms = ["architecture", "pipeline", "optimize", "framework",
                           "deploy", "Docker", "API", "GPU", "架构", "流水线"]
        tech_count = sum(1 for t in technical_terms if t.lower() in response_lower)
        if sophistication > 0.6 and tech_count >= 2:
            score += 0.10
        elif sophistication < 0.4 and tech_count >= 3:
            score -= 0.05

        return round(max(0.0, min(1.0, score)), 4)


_persona_reward: PersonaRewardModel | None = None


def get_persona_reward_model() -> PersonaRewardModel:
    global _persona_reward
    if _persona_reward is None:
        _persona_reward = PersonaRewardModel()
    return _persona_reward


def persona_preservation_reward(response: str, known_facts: list[str],
                                response_lower: str = "") -> float:
    if response_lower:
        rl = response_lower
    else:
        rl = response.lower()
    if not known_facts:
        return 1.0

    contradictions = 0
    for fact in known_facts:
        fact_terms = fact.split()
        if len(fact_terms) < 3:
            continue
        negations = ["not", "no", "don't", "doesn't", "不", "没", "非", "无"]
        for neg in negations:
            if neg in rl and any(t in rl for t in fact_terms):
                contradictions += 1
                break

    return max(0.0, 1.0 - contradictions * 0.25)


def persona_reference_reward(response: str, user_facts: list[str]) -> float:
    rl = response.lower()
    if not user_facts:
        return 0.5

    referenced = 0
    for fact in user_facts:
        fact_terms = [t for t in fact.split() if len(t) > 2]
        if fact_terms and sum(1 for t in fact_terms if t in rl) >= len(fact_terms) * 0.4:
            referenced += 1

    return round(0.3 + min(1.0, referenced / max(len(user_facts) * 0.3, 1)) * 0.7, 4)


__all__ = [
    "PersonaRewardModel", "PersonaRewardScores",
    "persona_preservation_reward", "persona_reference_reward",
    "get_persona_reward_model",
]
