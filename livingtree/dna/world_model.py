"""JEPA-style World Model — Predict consequences of actions before executing.

Answers "what would happen if Y?" instead of "what is X?". Maintains an internal
world representation and learns transition patterns from observed outcomes.

Architecture:
  WorldState → simulate(action) → SimulatedOutcome (prediction)
            → compare_alternatives → ranked SimulatedOutcome list
            → learn_from_outcome → updated transition_patterns

Integrated before the execute stage in LifeEngine to validate plans before
committing resources.

Inspired by: JEPA (Joint Embedding Predictive Architecture), LeCun 2022.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class WorldState:
    """Snapshot of the system's understanding of the world at a point in time."""

    description: str
    embedding: list[float] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.embedding:
            self.embedding = self._derive_embedding()

    def _derive_embedding(self) -> list[float]:
        """Derive a simple 128-dim embedding from description text.

        Uses character n-gram hashing — a lightweight alternative to full
        embedding models, sufficient for similarity comparison between states.
        """
        dim = 128
        seed = hash(self.description + "".join(self.entities + self.constraints))
        rng = random.Random(seed)
        vec = [0.0] * dim
        for ch in self.description:
            idx = ord(ch) % dim
            vec[idx] += 0.01
        for entity in self.entities:
            for ch in entity:
                vec[ord(ch) % dim] += 0.02
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def distance_to(self, other: WorldState) -> float:
        """Cosine distance between two world states."""
        if len(self.embedding) != len(other.embedding):
            return 1.0
        dot = sum(a * b for a, b in zip(self.embedding, other.embedding))
        return 1.0 - max(-1.0, min(1.0, dot))

    def summary(self) -> str:
        return (
            f"WorldState(entities={len(self.entities)}, "
            f"constraints={len(self.constraints)}, "
            f"desc={self.description[:60]}...)"
        )


@dataclass
class SimulatedOutcome:
    """The predicted result of taking an action from a given world state."""

    action: str
    predicted_state: WorldState
    confidence: float = 0.5
    side_effects: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    reasoning: str = ""
    timestamp: float = field(default_factory=time.time)

    def risk_level(self) -> str:
        if len(self.risks) >= 3 or self.confidence < 0.3:
            return "high"
        if len(self.risks) >= 1 or self.confidence < 0.6:
            return "medium"
        return "low"

    def summary(self) -> str:
        se = ", ".join(self.side_effects[:3]) or "none"
        rk = ", ".join(self.risks[:3]) or "none"
        return (
            f"SimulatedOutcome(action={self.action[:40]}, "
            f"confidence={self.confidence:.2f}, risk={self.risk_level()}, "
            f"side_effects=[{se}], risks=[{rk}])"
        )


class WorldModel:
    """JEPA-style predictive world model.

    Maintains state history and transition patterns to predict outcomes of
    proposed actions. Supports LLM-backed simulation (when consciousness is
    available) and heuristic fallback for fast local inference.

    Usage:
        model = get_world_model()
        state = model.observe_state("Editing config.py", entities=["config"], constraints=["read-only"])
        outcome = await model.simulate("modify port setting", state, consciousness)
    """

    MAX_STATE_HISTORY = 50
    MAX_OUTCOME_HISTORY = 100
    SIMILARITY_THRESHOLD = 0.3
    DEFAULT_EMBEDDING_DIM = 128

    def __init__(self, consciousness: Any = None):
        self._consciousness = consciousness
        self._state_history: deque[WorldState] = deque(maxlen=self.MAX_STATE_HISTORY)
        self._outcome_history: deque[SimulatedOutcome] = deque(maxlen=self.MAX_OUTCOME_HISTORY)
        self._transition_patterns: dict[str, list[dict]] = {}
        self._simulation_count: int = 0
        self._total_confidence: float = 0.0
        self._accuracy_samples: list[float] = []

    def observe_state(
        self,
        description: str,
        entities: list[str] | None = None,
        constraints: list[str] | None = None,
    ) -> WorldState:
        """Record a new world state observation.

        Returns the recorded WorldState. If a very similar state already exists
        in recent history, returns the existing one instead to avoid duplicates.
        """
        state = WorldState(
            description=description,
            entities=entities or [],
            constraints=constraints or [],
        )

        for recent in reversed(self._state_history):
            if recent.distance_to(state) < self.SIMILARITY_THRESHOLD:
                logger.debug(
                    f"WorldModel: merging similar state (dist={recent.distance_to(state):.3f})"
                )
                if description not in recent.entities:
                    recent.entities = list(set(recent.entities + state.entities))
                if constraints:
                    recent.constraints = list(set(recent.constraints + state.constraints))
                return recent

        self._state_history.append(state)
        logger.debug(f"WorldModel: observed new state [{len(self._state_history)} total]")
        return state

    async def simulate(
        self,
        action: str,
        current_state: WorldState,
        consciousness: Any = None,
    ) -> SimulatedOutcome:
        """Simulate the outcome of taking an action from the current state.

        Uses LLM reasoning when consciousness is available, otherwise falls
        back to heuristic pattern-matching against known transition patterns.

        Args:
            action: The proposed action (e.g., "modify config.py", "delete temp files")
            current_state: The current world state to simulate from
            consciousness: Optional consciousness instance for LLM-backed simulation

        Returns:
            SimulatedOutcome with predicted state, confidence, risks, and reasoning
        """
        llm = consciousness or self._consciousness

        if llm:
            outcome = await self._llm_simulate(action, current_state, llm)
        else:
            outcome = self._heuristic_simulate(action, current_state)

        self._outcome_history.append(outcome)
        self._simulation_count += 1
        self._total_confidence += outcome.confidence

        logger.info(
            f"WorldModel: simulated '{action[:50]}' → "
            f"confidence={outcome.confidence:.2f}, risk={outcome.risk_level()}"
        )
        return outcome

    async def _llm_simulate(
        self,
        action: str,
        state: WorldState,
        consciousness: Any,
    ) -> SimulatedOutcome:
        """Use LLM reasoning to simulate action outcomes."""
        constraints_text = "\n".join(f"  - {c}" for c in state.constraints) or "  (none)"
        entities_text = ", ".join(state.entities) or "(none)"

        prompt = (
            f"You are a world model predicting consequences of actions.\n\n"
            f"Current world state:\n"
            f"  Description: {state.description}\n"
            f"  Key entities: {entities_text}\n"
            f"  Constraints:\n{constraints_text}\n\n"
            f"Proposed action: {action}\n\n"
            f"Predict the likely outcomes of this action. Consider:\n"
            f"  1. Direct effects — what immediately changes?\n"
            f"  2. Side effects — what might indirectly happen?\n"
            f"  3. Risks — what could go wrong?\n"
            f"  4. Constraint violations — would this break any constraints?\n\n"
            f"Respond with a JSON object:\n"
            f'{{"predicted_description": "description of resulting state",'
            f'"confidence": 0.0-1.0,'
            f'"side_effects": ["effect1", "effect2"],'
            f'"risks": ["risk1", "risk2"],'
            f'"reasoning": "step-by-step reasoning chain"}}'
        )

        try:
            raw = await consciousness.query(prompt, max_tokens=600, temperature=0.3)
            result = self._parse_simulation_json(raw, action, state)
        except Exception as e:
            logger.warning(f"WorldModel LLM simulation failed: {e}, falling back to heuristic")
            result = self._heuristic_simulate(action, state)

        return result

    def _parse_simulation_json(
        self,
        raw: str,
        action: str,
        state: WorldState,
    ) -> SimulatedOutcome:
        """Parse LLM JSON response into a SimulatedOutcome."""
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                data = json.loads(raw[start:end + 1])
            else:
                raise json.JSONDecodeError("No JSON object found", raw, 0)
        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"WorldModel JSON parse error: {e}")
            return self._heuristic_simulate(action, state)

        predicted_desc = data.get("predicted_description", f"After {action}")
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        side_effects = data.get("side_effects", [])
        risks = data.get("risks", [])
        reasoning = data.get("reasoning", "")

        predicted_state = WorldState(
            description=predicted_desc,
            entities=list(state.entities),
            constraints=list(state.constraints),
        )

        return SimulatedOutcome(
            action=action,
            predicted_state=predicted_state,
            confidence=confidence,
            side_effects=side_effects if isinstance(side_effects, list) else [],
            risks=risks if isinstance(risks, list) else [],
            reasoning=reasoning if isinstance(reasoning, str) else "",
        )

    def _heuristic_simulate(
        self,
        action: str,
        state: WorldState,
    ) -> SimulatedOutcome:
        """Fast heuristic simulation using learned transition patterns.

        Matches the action against known patterns and nearby states to estimate
        likely outcomes without an LLM call.
        """
        action_lower = action.lower()
        side_effects: list[str] = []
        risks: list[str] = []
        confidence = 0.5
        reasoning = "Heuristic simulation based on transition patterns."

        patterns = self._find_matching_patterns(action)
        if patterns:
            all_se = []
            all_rk = []
            all_conf = []
            for p in patterns:
                all_se.extend(p.get("side_effects", []))
                all_rk.extend(p.get("risks", []))
                all_conf.append(p.get("confidence", 0.5))
            side_effects = list(dict.fromkeys(all_se))[:5]
            risks = list(dict.fromkeys(all_rk))[:5]
            confidence = sum(all_conf) / len(all_conf) if all_conf else 0.5
            reasoning = f"Matched {len(patterns)} similar transition pattern(s)."

        constraint_violations = self._check_constraint_violations(action, state)
        risks.extend(constraint_violations)
        if constraint_violations:
            confidence = max(0.1, confidence - 0.15 * len(constraint_violations))

        predicted_state = WorldState(
            description=f"After '{action}': {state.description}",
            entities=list(state.entities),
            constraints=list(state.constraints),
        )

        return SimulatedOutcome(
            action=action,
            predicted_state=predicted_state,
            confidence=round(confidence, 4),
            side_effects=side_effects,
            risks=risks,
            reasoning=reasoning,
        )

    def _find_matching_patterns(self, action: str) -> list[dict]:
        """Find transition patterns similar to the given action."""
        results: list[dict] = []
        action_lower = action.lower()
        for key, patterns in self._transition_patterns.items():
            key_lower = key.lower()
            if key_lower in action_lower or action_lower in key_lower:
                results.extend(patterns)
            words = set(action_lower.split())
            key_words = set(key_lower.split())
            if len(words & key_words) >= 2:
                results.extend(patterns)
        return results

    def _check_constraint_violations(
        self,
        action: str,
        state: WorldState,
    ) -> list[str]:
        """Heuristically check if action might violate known constraints."""
        violations: list[str] = []
        action_lower = action.lower()

        danger_pairs = [
            (["delete", "remove", "rm"], "May delete critical data"),
            (["modify", "change", "edit", "write"], "May alter important state"),
            (["install", "download", "fetch"], "May introduce external dependencies"),
            (["restart", "reboot", "shutdown"], "May cause service interruption"),
            (["disable", "turn off", "stop"], "May disable protection mechanism"),
        ]

        for keywords, risk_msg in danger_pairs:
            if any(kw in action_lower for kw in keywords):
                for constraint in state.constraints:
                    if any(kw in constraint.lower() for kw in ["read-only", "immutable", "protected", "safety"]):
                        violations.append(f"{risk_msg} (violates: {constraint})")

        return violations

    async def compare_alternatives(
        self,
        actions: list[str],
        state: WorldState,
        consciousness: Any = None,
    ) -> list[SimulatedOutcome]:
        """Simulate multiple alternative actions and rank by predicted outcome.

        Returns outcomes sorted by confidence (descending), with highest
        confidence first. Use this for action selection.

        Args:
            actions: List of action descriptions to compare
            state: Current world state
            consciousness: Optional consciousness for LLM-backed simulation

        Returns:
            Ranked list of SimulatedOutcome objects (best first)
        """
        if not actions:
            return []

        if len(actions) == 1:
            outcome = await self.simulate(actions[0], state, consciousness)
            return [outcome]

        outcomes: list[SimulatedOutcome] = []
        for action in actions:
            outcome = await self.simulate(action, state, consciousness)
            outcomes.append(outcome)

        outcomes.sort(
            key=lambda o: (
                -len(o.risks) * 0.3 + o.confidence * 1.0
            ),
            reverse=True,
        )

        logger.info(
            f"WorldModel: compared {len(actions)} alternatives, "
            f"best='{outcomes[0].action[:40]}' (conf={outcomes[0].confidence:.2f})"
        )
        return outcomes

    def learn_from_outcome(
        self,
        action: str,
        predicted: SimulatedOutcome,
        actual: WorldState,
    ) -> float:
        """Compare a prediction against reality and update transition patterns.

        Records the transition pattern and computes prediction accuracy.
        The accuracy score is used to adjust future confidence estimates.

        Args:
            action: The action that was taken
            predicted: The predicted outcome before execution
            actual: The actual observed state after execution

        Returns:
            Prediction accuracy score (0.0 to 1.0)
        """
        similarity = 1.0 - predicted.predicted_state.distance_to(actual)

        side_effect_hit = 0
        if predicted.side_effects:
            actual_desc_lower = actual.description.lower()
            for se in predicted.side_effects:
                if se.lower()[:30] in actual_desc_lower:
                    side_effect_hit += 1
            side_precision = side_effect_hit / len(predicted.side_effects)
        else:
            side_precision = 0.5

        risk_hit = 0
        if predicted.risks:
            for risk in predicted.risks:
                if risk.lower()[:20] in actual.description.lower():
                    risk_hit += 1
            risk_accuracy = risk_hit / len(predicted.risks)
        else:
            risk_accuracy = 0.5

        accuracy = 0.4 * similarity + 0.3 * side_precision + 0.3 * risk_accuracy

        self._accuracy_samples.append(accuracy)
        if len(self._accuracy_samples) > 100:
            self._accuracy_samples = self._accuracy_samples[-100:]

        pattern_entry = {
            "predicted_description": predicted.predicted_state.description,
            "actual_description": actual.description,
            "confidence": predicted.confidence,
            "accuracy": accuracy,
            "side_effects": predicted.side_effects,
            "risks": predicted.risks,
            "timestamp": time.time(),
        }

        action_key = action.lower().strip()
        if action_key not in self._transition_patterns:
            self._transition_patterns[action_key] = []
        self._transition_patterns[action_key].append(pattern_entry)
        if len(self._transition_patterns[action_key]) > 20:
            self._transition_patterns[action_key] = self._transition_patterns[action_key][-20:]

        logger.info(
            f"WorldModel: learned from '{action[:40]}' — "
            f"accuracy={accuracy:.3f}, similarity={similarity:.3f}"
        )
        return round(accuracy, 4)

    def get_mental_model(self) -> str:
        """Compressed natural-language description of current world understanding.

        Summarizes recent states, known transition patterns, and prediction
        accuracy trend.
        """
        lines: list[str] = []

        lines.append("=== Mental Model ===")

        recent_states = list(self._state_history)[-5:]
        if recent_states:
            lines.append(f"\nRecent states ({len(self._state_history)} total):")
            for s in reversed(recent_states):
                lines.append(f"  - {s.description[:80]} [{len(s.entities)} entities, {len(s.constraints)} constraints]")

        known_entities = set()
        for s in self._state_history:
            known_entities.update(s.entities)
        if known_entities:
            lines.append(f"\nKnown entities: {', '.join(sorted(known_entities)[:15])}")
            if len(known_entities) > 15:
                lines.append(f"  ... and {len(known_entities) - 15} more")

        known_constraints = set()
        for s in self._state_history:
            known_constraints.update(s.constraints)
        if known_constraints:
            lines.append(f"\nActive constraints: {', '.join(sorted(known_constraints)[:10])}")

        if self._transition_patterns:
            lines.append(f"\nLearned transition patterns: {len(self._transition_patterns)}")
            top_patterns = sorted(
                self._transition_patterns.items(),
                key=lambda kv: sum(e.get("accuracy", 0) for e in kv[1]) / max(len(kv[1]), 1),
                reverse=True,
            )[:5]
            for key, entries in top_patterns:
                avg_acc = sum(e.get("accuracy", 0) for e in entries) / len(entries)
                lines.append(f"  - '{key[:50]}': avg accuracy={avg_acc:.2f}, samples={len(entries)}")

        if self._accuracy_samples:
            recent_acc = self._accuracy_samples[-10:]
            avg_acc = sum(recent_acc) / len(recent_acc)
            trend = "improving" if len(recent_acc) >= 2 and recent_acc[-1] > recent_acc[0] else "stable"
            lines.append(f"\nPrediction accuracy: {avg_acc:.3f} ({trend}, last {len(recent_acc)} samples)")

        if not self._state_history:
            lines.append("\nNo states observed yet. The world model is empty.")

        return "\n".join(lines)

    def stats(self) -> dict:
        """Return diagnostic statistics about the world model."""
        avg_confidence = (
            self._total_confidence / self._simulation_count
            if self._simulation_count > 0
            else 0.0
        )
        avg_accuracy = (
            sum(self._accuracy_samples) / len(self._accuracy_samples)
            if self._accuracy_samples
            else 0.0
        )
        return {
            "states_observed": len(self._state_history),
            "simulations_run": self._simulation_count,
            "prediction_accuracy": round(avg_accuracy, 4),
            "average_confidence": round(avg_confidence, 4),
            "transition_patterns": len(self._transition_patterns),
            "total_learned_entries": sum(
                len(v) for v in self._transition_patterns.values()
            ),
            "accuracy_samples": len(self._accuracy_samples),
            "known_entities": len(
                set(e for s in self._state_history for e in s.entities)
            ),
            "known_constraints": len(
                set(c for s in self._state_history for c in s.constraints)
            ),
        }

    async def validate_plan(
        self,
        plan_steps: list[str],
        state: WorldState,
        consciousness: Any = None,
        min_confidence: float = 0.4,
    ) -> tuple[bool, list[SimulatedOutcome], str]:
        """Validate a multi-step plan by simulating each step.

        Returns (is_safe, all_outcomes, summary). A plan is safe when:
          - No step has risk_level "high"
          - All steps have confidence >= min_confidence
          - No constraint violations are flagged

        Args:
            plan_steps: Ordered list of action descriptions in the plan
            state: Starting world state
            consciousness: Optional consciousness for LLM simulation
            min_confidence: Minimum acceptable confidence per step

        Returns:
            Tuple of (is_safe, list of outcomes, human-readable summary)
        """
        all_outcomes: list[SimulatedOutcome] = []
        current_state = state
        blocked = False
        reasons: list[str] = []

        for i, step in enumerate(plan_steps):
            outcome = await self.simulate(step, current_state, consciousness)
            all_outcomes.append(outcome)

            if outcome.risk_level() == "high":
                blocked = True
                reasons.append(f"Step {i + 1} ('{step[:40]}') has HIGH risk: {outcome.risks[:3]}")
            elif outcome.confidence < min_confidence:
                blocked = True
                reasons.append(
                    f"Step {i + 1} ('{step[:40]}') confidence too low: "
                    f"{outcome.confidence:.2f} < {min_confidence}"
                )

            current_state = outcome.predicted_state

        is_safe = not blocked
        if is_safe:
            summary = f"Plan validated: {len(plan_steps)} steps, all safe."
        else:
            summary = (
                f"Plan REJECTED: {len(reasons)} issue(s) found.\n"
                + "\n".join(f"  - {r}" for r in reasons)
            )

        logger.info(f"WorldModel plan validation: {'PASS' if is_safe else 'FAIL'} — {summary[:120]}")
        return is_safe, all_outcomes, summary


_world_model: Optional[WorldModel] = None


def get_world_model(consciousness: Any = None) -> WorldModel:
    """Get or create the singleton WorldModel instance.

    Args:
        consciousness: Optional consciousness to use for LLM-backed
                       simulation. Only used on first call (ignored on
                       subsequent calls).

    Returns:
        The singleton WorldModel instance.
    """
    global _world_model
    if _world_model is None:
        _world_model = WorldModel(consciousness=consciousness)
        logger.info("WorldModel singleton initialized")
    elif consciousness is not None and _world_model._consciousness is None:
        _world_model._consciousness = consciousness
    return _world_model
