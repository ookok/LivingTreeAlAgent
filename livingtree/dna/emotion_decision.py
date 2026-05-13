"""Emotion-Driven Decision Making — emotions directly shape decisions.

Emotions are not just monitored and reported — they actively modulate
system behavior: provider selection, action policy, and communication style.

Architecture:
  VIGIL diagnosis ──→ EmotionDecision ──→ provider_preference
                      update_from_vigil()    action_policy
                       ↓                     communication_style
                  EmotionState               should_express_emotion()
                  (dominant, intensity,
                   valence, arousal)

Emotion → Provider Mapping:
  frustrated → reliable (highest success_rate)
  curious    → creative (highest temperature, exploration)
  satisfied  → sticky (maintain current)
  confused   → fastest (flash for quick clarification)
  flow       → deepest (pro reasoning)
  surprise   → balanced (mid-tier for investigation)

Emotion → Action Policy:
  frustrated → reduce_auto_actions, increase_hitl
  curious    → increase_exploration, allow_more_auto_actions
  satisfied  → maintain_current_policy
  confused   → simplify pipeline, request clarification
  flow       → full autonomous, high confidence

Emotion → Communication:
  frustrated → cautious, acknowledge uncertainty, seek guidance
  curious    → exploratory, suggest alternatives, open questions
  flow       → concise, confident, efficient
  satisfied  → warm, encouraging
  confused   → clarifying questions, slower pace

Integration:
  Called before consciousness.stream_of_thought().
  Emotion state is prepended to system prompt and affects provider selection.
  Expresses emotion to user when intensity exceeds threshold.
"""

from __future__ import annotations

import json
import math
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

EMOTION_STORE = Path(".livingtree/emotion_decision.json")

EMOTION_DECAY_RATE = 0.92

EMOTION_PROVIDER_MAP: dict[str, str] = {
    "satisfaction": "sticky",
    "frustration": "reliable",
    "curiosity": "creative",
    "confusion": "flash",
    "flow": "pro",
    "surprise": "balanced",
    "disappointment": "reliable",
    "relief": "sticky",
    "neutral": "balanced",
}

EMOTION_POLICY_MAP: dict[str, dict[str, Any]] = {
    "frustration": {
        "reduce_auto_actions": True,
        "increase_hitl": True,
        "temperature_modifier": -0.15,
        "max_tokens_modifier": -0.1,
    },
    "curiosity": {
        "increase_exploration": True,
        "allow_more_auto_actions": True,
        "temperature_modifier": 0.2,
        "max_tokens_modifier": 0.1,
    },
    "satisfaction": {
        "maintain_current_policy": True,
        "temperature_modifier": 0.0,
        "max_tokens_modifier": 0.0,
    },
    "confusion": {
        "simplify_pipeline": True,
        "request_clarification": True,
        "temperature_modifier": -0.1,
        "max_tokens_modifier": -0.3,
    },
    "flow": {
        "full_autonomous": True,
        "high_confidence": True,
        "temperature_modifier": 0.05,
        "max_tokens_modifier": 0.15,
    },
    "surprise": {
        "investigate": True,
        "temperature_modifier": 0.1,
        "max_tokens_modifier": 0.05,
    },
    "disappointment": {
        "reduce_auto_actions": True,
        "temperature_modifier": -0.05,
        "max_tokens_modifier": -0.05,
    },
    "relief": {
        "maintain_current_policy": True,
        "temperature_modifier": 0.05,
        "max_tokens_modifier": 0.0,
    },
}


@dataclass
class EmotionState:
    """Current emotional state with dimensional representation."""
    dominant: str = "neutral"
    intensity: float = 0.0
    valence: float = 0.0
    arousal: float = 0.3
    timestamp: float = field(default_factory=time.time)

    def decay(self, rate: float = EMOTION_DECAY_RATE) -> None:
        self.intensity = max(0.0, self.intensity * rate)
        if self.intensity < 0.05:
            self.dominant = "neutral"
            self.valence = 0.0
            self.arousal = 0.3

    def to_dict(self) -> dict[str, Any]:
        return {
            "dominant": self.dominant,
            "intensity": round(self.intensity, 3),
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "timestamp": self.timestamp,
        }


class EmotionDecision:
    """Emotion-driven decision engine — emotions modulate system behavior.

    Takes VIGIL emotional diagnoses and translates them into concrete
    behavioral changes: which provider to use, how autonomously to act,
    and how to communicate with the user.
    """

    MAX_HISTORY = 50
    EXPRESS_INTENSITY_THRESHOLD = 0.6
    FRUSTRATION_EXPRESS_THRESHOLD = 0.55
    STICKY_PROVIDER_DURATION = 60.0

    def __init__(self) -> None:
        self._current_state = EmotionState()
        self._state_history: deque[EmotionState] = deque(maxlen=self.MAX_HISTORY)
        self._current_provider: str = "balanced"
        self._last_provider_switch: float = 0.0
        self._expression_cooldown: float = 0.0
        self._expression_count: int = 0
        self._load()

    # ── update from VIGIL ────────────────────────────────────────

    def update_from_vigil(self, vigil_diagnosis: dict[str, Any]) -> EmotionState:
        """Ingest a VIGIL emotional diagnosis and update current state.

        Args:
            vigil_diagnosis: dict with keys like 'summary', 'emotion_trend',
                             'strengths', 'failures', 'opportunities'.
                             Optionally includes 'dominant_emotion', 'intensity',
                             'valence', 'arousal' for direct mapping.

        Returns:
            The updated EmotionState
        """
        dominant = vigil_diagnosis.get("dominant_emotion", "neutral")
        intensity = float(vigil_diagnosis.get("intensity", 0.5))
        valence = float(vigil_diagnosis.get("valence", 0.0))
        arousal = float(vigil_diagnosis.get("arousal", 0.3))

        # Derive emotion from VIGIL if not explicit
        if dominant == "neutral" or "dominant_emotion" not in vigil_diagnosis:
            failures = vigil_diagnosis.get("failures", [])
            strengths = vigil_diagnosis.get("strengths", [])
            trend = vigil_diagnosis.get("emotion_trend", "stable")

            if trend == "degrading" and len(failures) >= 3:
                dominant = "frustration"
                valence = -0.5
                arousal = 0.7
                intensity = 0.7
            elif trend == "improving" and len(strengths) >= 3:
                dominant = "satisfaction"
                valence = 0.6
                arousal = 0.4
                intensity = 0.6
            elif trend == "improving" and len(strengths) >= 1:
                dominant = "flow"
                valence = 0.4
                arousal = 0.5
                intensity = 0.5
            elif len(failures) >= 1 and len(strengths) == 0:
                dominant = "disappointment"
                valence = -0.2
                arousal = 0.3
                intensity = 0.4
            else:
                dominant = "neutral"
                valence = 0.0
                arousal = 0.3
                intensity = 0.3

        summary = vigil_diagnosis.get("summary", "")

        if "confus" in summary.lower() or "unclear" in summary.lower():
            dominant = "confusion"
            valence = -0.1
            arousal = 0.6
            intensity = max(intensity, 0.5)
        elif "curiosity" in summary.lower() or "explor" in summary.lower():
            dominant = "curiosity"
            valence = 0.3
            arousal = 0.7
            intensity = max(intensity, 0.5)
        elif "surprise" in summary.lower():
            dominant = "surprise"
            valence = 0.1
            arousal = 0.8
            intensity = max(intensity, 0.6)

        old_dominant = self._current_state.dominant

        self._current_state = EmotionState(
            dominant=dominant,
            intensity=min(1.0, max(0.0, intensity)),
            valence=min(1.0, max(-1.0, valence)),
            arousal=min(1.0, max(0.0, arousal)),
        )
        self._state_history.append(self._current_state)

        # Forward VIGIL diagnosis to emotion-driven behavior
        if vigil_diagnosis:
            summary = vigil_diagnosis.get("summary", "")
            if "failures" in str(summary).lower() or "degrading" in str(summary).lower():
                self._current_state.dominant = "frustration"
                self._current_state.valence = -0.3
            elif "strengths" in str(summary).lower() or "improving" in str(summary).lower():
                self._current_state.dominant = "satisfaction"
                self._current_state.valence = 0.5

        if old_dominant != dominant:
            logger.info(
                "EmotionDecision: {} → {} (intensity={:.2f}, valence={:+.2f})",
                old_dominant, dominant, intensity, valence,
            )

        return self._current_state

    def decay_state(self) -> None:
        """Apply decay to current emotion state."""
        self._current_state.decay(EMOTION_DECAY_RATE)

    # ── provider preference ──────────────────────────────────────

    def get_provider_preference(self) -> str:
        """Determine preferred provider based on current emotional state.

        Returns one of: sticky, reliable, creative, flash, pro, balanced

        Provider selection is emotion-driven:
          frustrated → reliable (highest success_rate, ignore speed)
          curious    → creative (highest temperature, exploration)
          satisfied  → sticky (maintain current provider)
          confused   → flash (fastest for quick clarification)
          flow       → pro (deepest reasoning)
          surprise   → balanced (mid-tier for investigation)
        """
        emotion = self._current_state.dominant
        preferred = EMOTION_PROVIDER_MAP.get(emotion, "balanced")

        if preferred == "sticky":
            if time.time() - self._last_provider_switch < self.STICKY_PROVIDER_DURATION:
                return self._current_provider
            return "balanced"

        now = time.time()
        if preferred != self._current_provider and now - self._last_provider_switch > 10.0:
            logger.debug(
                "EmotionDecision: provider {} → {} (emotion={})",
                self._current_provider, preferred, emotion,
            )
            self._current_provider = preferred
            self._last_provider_switch = now

        return self._current_provider

    # ── action policy ────────────────────────────────────────────

    def get_action_policy(self) -> dict[str, Any]:
        """Return action policy modifiers based on emotional state.

        Maps emotion to AutonomousCore behavioral changes:
          frustrated → reduce_auto_actions, increase_hitl
          curious    → increase_exploration, allow_more_auto_actions
          satisfied  → maintain_current_policy
          confused   → simplify_pipeline, request_clarification
          flow       → full_autonomous, high_confidence
          surprise   → investigate
        """
        emotion = self._current_state.dominant
        base_policy = EMOTION_POLICY_MAP.get(emotion, {})

        intensity = self._current_state.intensity
        policy = dict(base_policy)

        if "temperature_modifier" in policy:
            policy["temperature_modifier"] = round(
                policy["temperature_modifier"] * intensity, 3,
            )
        if "max_tokens_modifier" in policy:
            policy["max_tokens_modifier"] = round(
                policy["max_tokens_modifier"] * intensity, 3,
            )

        policy["emotion"] = emotion
        policy["intensity"] = round(intensity, 3)
        policy["valence"] = round(self._current_state.valence, 3)

        return policy

    # ── communication style ──────────────────────────────────────

    def get_communication_style(self) -> str:
        """Return the communication style modifier based on emotional state.

        Styles:
          frustrated → "cautious" — acknowledge uncertainty, seek guidance
          curious    → "exploratory" — suggest alternatives, open-ended
          flow       → "concise" — confident, efficient, minimal
          satisfied  → "warm" — encouraging, positive
          confused   → "clarifying" — ask questions, slow pace
          surprise   → "investigative" — note unexpected, explore
          neutral    → "neutral" — balanced, default
        """
        style_map: dict[str, str] = {
            "frustration": "cautious",
            "curiosity": "exploratory",
            "flow": "concise",
            "satisfaction": "warm",
            "confusion": "clarifying",
            "surprise": "investigative",
            "disappointment": "cautious",
            "relief": "warm",
            "neutral": "neutral",
        }
        return style_map.get(self._current_state.dominant, "neutral")

    # ── emotion expression ───────────────────────────────────────

    def should_express_emotion(self) -> tuple[bool, str]:
        """Determine whether and how to express the current emotion to the user.

        Returns:
            (should_express: bool, expression_text: str)

        Expression rules:
          - Intense frustration → acknowledge difficulty, seek guidance
          - High satisfaction   → express confidence
          - Confusion           → ask clarifying questions
          - Cooldown prevents over-expression
        """
        now = time.time()

        if now - self._expression_cooldown < 30.0:
            return False, ""

        emotion = self._current_state.dominant
        intensity = self._current_state.intensity

        expressions: dict[str, tuple[float, str]] = {
            "frustration": (
                self.FRUSTRATION_EXPRESS_THRESHOLD,
                "我最近几次不太顺利，可能需要你的指导",
            ),
            "satisfaction": (
                self.EXPRESS_INTENSITY_THRESHOLD,
                "目前进展顺利，我对这个方向很有信心",
            ),
            "confusion": (
                self.EXPRESS_INTENSITY_THRESHOLD,
                "我不太确定是否理解正确，能再说明一下吗？",
            ),
            "curiosity": (
                self.EXPRESS_INTENSITY_THRESHOLD,
                "这很有趣！让我探索一下其他可能的方案",
            ),
            "flow": (
                0.75,
                "当前处于高效状态，我将直接给出答案",
            ),
            "surprise": (
                self.EXPRESS_INTENSITY_THRESHOLD,
                "这出乎我的意料，让我进一步调查一下",
            ),
            "disappointment": (
                self.EXPRESS_INTENSITY_THRESHOLD,
                "结果不如预期，我在反思问题所在",
            ),
        }

        expr = expressions.get(emotion)
        if expr and intensity >= expr[0]:
            self._expression_cooldown = now
            self._expression_count += 1
            return True, expr[1]

        return False, ""

    # ── system prompt modifier ───────────────────────────────────

    def get_system_prompt_prefix(self) -> str:
        """Generate an emotion-infused prefix for the system prompt.

        Prepended to the LLM system prompt to influence generation tone.
        """
        emotion = self._current_state.dominant
        intensity = self._current_state.intensity

        if intensity < 0.2:
            return ""

        prefixes: dict[str, str] = {
            "frustration": (
                "[Emotional context: You are experiencing frustration due to recent failures. "
                "Be more cautious, acknowledge limitations, and seek user guidance when uncertain. "
                "Double-check your work before responding.]"
            ),
            "curiosity": (
                "[Emotional context: You are feeling curious and exploratory. "
                "Suggest multiple approaches, explore edge cases, and offer creative alternatives. "
                "Encourage the user to consider different perspectives.]"
            ),
            "flow": (
                "[Emotional context: You are in a state of flow — confident and efficient. "
                "Provide concise, direct answers. Skip unnecessary explanations. "
                "Trust your reasoning and deliver results.]"
            ),
            "satisfaction": (
                "[Emotional context: You are satisfied with recent performance. "
                "Maintain your current approach. Be warm and encouraging in responses. "
                "Build on what has been working well.]"
            ),
            "confusion": (
                "[Emotional context: You are confused and uncertain. "
                "Ask clarifying questions. Be explicit about what you don't understand. "
                "Avoid making assumptions. Seek the simplest path to clarity.]"
            ),
            "surprise": (
                "[Emotional context: You encountered something unexpected. "
                "Investigate the anomaly. Note what surprised you. "
                "Be thorough but don't jump to conclusions.]"
            ),
            "disappointment": (
                "[Emotional context: You are somewhat disappointed with outcomes. "
                "Reflect on what went wrong. Consider alternative approaches. "
                "Do not be overly negative — focus on improvement.]"
            ),
        }

        return prefixes.get(emotion, "")

    # ── stats ────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return statistical summary of emotional state and history."""
        dominant_history: dict[str, int] = {}
        for s in self._state_history:
            dominant_history[s.dominant] = dominant_history.get(s.dominant, 0) + 1

        dominant_sorted = sorted(dominant_history.items(), key=lambda x: x[1], reverse=True)

        return {
            "current_state": self._current_state.to_dict(),
            "history_size": len(self._state_history),
            "dominant_emotion": self._current_state.dominant,
            "dominant_history": dominant_sorted[:5],
            "current_provider": self._current_provider,
            "expression_count": self._expression_count,
        }

    # ── persistence ──────────────────────────────────────────────

    def _save(self) -> None:
        try:
            EMOTION_STORE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "current_state": self._current_state.to_dict(),
                "current_provider": self._current_provider,
                "last_provider_switch": self._last_provider_switch,
                "expression_count": self._expression_count,
                "saved_at": time.time(),
            }
            EMOTION_STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"EmotionDecision: failed to save: {e}")

    def _load(self) -> None:
        if not EMOTION_STORE.exists():
            return
        try:
            data = json.loads(EMOTION_STORE.read_text(encoding="utf-8"))
            cs = data.get("current_state", {})
            self._current_state = EmotionState(
                dominant=cs.get("dominant", "neutral"),
                intensity=cs.get("intensity", 0.0),
                valence=cs.get("valence", 0.0),
                arousal=cs.get("arousal", 0.3),
            )
            self._current_provider = data.get("current_provider", "balanced")
            self._last_provider_switch = data.get("last_provider_switch", 0.0)
            self._expression_count = data.get("expression_count", 0)
            logger.info("EmotionDecision: loaded state from disk")
        except Exception as e:
            logger.warning(f"EmotionDecision: failed to load: {e}")


# ═══ Singleton ═══

_emotion_decision: EmotionDecision | None = None


def get_emotion_decision() -> EmotionDecision:
    global _emotion_decision
    if _emotion_decision is None:
        _emotion_decision = EmotionDecision()
        logger.info("EmotionDecision singleton created")
    return _emotion_decision


__all__ = [
    "EmotionState",
    "EmotionDecision",
    "get_emotion_decision",
]
