"""Inverse Reinforcement Learning — infer user preferences from behavior.

Rather than requiring manual specification of reward functions, IRL observes
user signals (accept, reject, correct, praise, ignore) and infers their
underlying preferences. This allows the system to align with user intent
without explicit preference engineering.

Preference signals are extracted from:
  - accepted: user confirms a suggestion → preference confirmed
  - rejected: user rejects a suggestion → inverse preference learned
  - corrected: user provides specific correction → preference extracted from correction text
  - praised: user expresses satisfaction → related preference reweighted
  - ignored: user skips something → weak negative signal

Integration:
  Called after each user interaction to update preference model.
  Used by LifeEngine for action ranking: `rank_actions()` orders options
  by inferred user preference rather than hardcoded heuristics.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

PREFERENCE_STORE = Path(".livingtree/inverse_reward_prefs.json")

CORRECTION_EXTRACT_PATTERNS: list[tuple[str, str]] = [
    (r"(简单|简洁|简明|简化|simpler?|simple|concise)", "prefers simplicity over complexity"),
    (r"(详细|详尽|细节|具体|detailed?|detail|thorough)", "prefers detail over brevity"),
    (r"(快|速度|快速|迅速|faster?|fast|quick|speed)", "prefers speed over depth"),
    (r"(准确|精确|质量|高质量|accurate|quality|precise|正确)", "prefers accuracy over speed"),
    (r"(代码|实现|示例|example|code|implement)", "prefers concrete code examples"),
    (r"(解释|说明|解释一下|explain|为什么|原因)", "prefers explanation over direct answer"),
    (r"(中文|Chinese|用中文|说中文)", "prefers Chinese language output"),
    (r"(英文|English|用英文|说英文)", "prefers English language output"),
    (r"(友好|温柔|礼貌|友善|gentle|polite|friendly)", "prefers friendly tone"),
    (r"(直接|干脆|直接说|brief|straight|direct)", "prefers direct communication"),
    (r"(安全|保守|safe|conservative|cautious)", "prefers safety over risk"),
    (r"(大胆|冒险|尝试|bold|creative|创新)", "prefers creativity over safety"),
    (r"(可视化|图表|graph|chart|visual|diagram)", "prefers visual representations"),
    (r"(文本|文字|text|read|阅读)", "prefers text output over visuals"),
    (r"(安静|少说|静默|silent|quiet|minimal)", "prefers minimal verbosity"),
    (r"(多模态|multimodal|声音|audio|视频|video)", "prefers multimodal responses"),
    (r"(记忆|记得|记住|remember|memory|history)", "prefers memory-aware responses"),
    (r"(隐私|保密|private|secret|privacy)", "prefers privacy-conscious behavior"),
]

SIGNAL_WEIGHTS: dict[str, float] = {
    "accepted": 0.10,
    "rejected": 0.15,
    "corrected": 0.20,
    "praised": 0.08,
    "ignored": 0.03,
}


@dataclass
class PreferenceSignal:
    """A single inferred user preference signal from one interaction."""
    signal_type: str
    context: str
    inferred_preference: str
    confidence: float
    timestamp: float = field(default_factory=time.time)


class InverseRewardModel:
    """Learns user preferences from behavioral signals via inverse RL.

    Rather than asking users to specify preferences, this model observes
    behavior (accepts, rejects, corrections, praise, silence) and infers
    the latent reward function those behaviors imply.
    """

    MAX_HISTORY = 200
    MIN_CONFIDENCE_DELTA = 0.01
    PATTERN_COOLDOWN = 0.05
    TOP_K_FOR_SUGGESTION = 5
    RECENCY_DECAY = 0.90
    MIN_PREFERENCE_WEIGHT = 0.0
    MAX_PREFERENCE_WEIGHT = 1.0

    def __init__(self) -> None:
        self._preferences: dict[str, float] = {}
        self._observation_history: deque[PreferenceSignal] = deque(maxlen=self.MAX_HISTORY)
        self._signal_counts: dict[str, int] = defaultdict(int)
        self._correction_patterns: dict[str, list[float]] = defaultdict(list)
        self._load()

    # ── observation ──────────────────────────────────────────────

    def observe(self, signal_type: str, context: str, correction_text: str = "") -> PreferenceSignal:
        """Record a user behavior signal and infer the corresponding preference.

        Args:
            signal_type: one of "accepted", "rejected", "corrected", "praised", "ignored"
            context: description of what was happening
            correction_text: user's correction message (required for "corrected")

        Returns:
            The inferred PreferenceSignal
        """
        self._signal_counts[signal_type] += 1

        if signal_type == "accepted":
            signal = self._handle_accepted(context)
        elif signal_type == "rejected":
            signal = self._handle_rejected(context)
        elif signal_type == "corrected":
            signal = self._handle_corrected(context, correction_text)
        elif signal_type == "praised":
            signal = self._handle_praised(context)
        elif signal_type == "ignored":
            signal = self._handle_ignored(context)
        else:
            signal = PreferenceSignal(
                signal_type=signal_type,
                context=context,
                inferred_preference="unknown signal type",
                confidence=0.05,
            )

        self._observation_history.append(signal)
        self._apply_decay()
        self._save()
        logger.debug(
            "IRL observe: type={} pref={} conf={:.2f}",
            signal_type, signal.inferred_preference, signal.confidence,
        )
        return signal

    def _handle_accepted(self, context: str) -> PreferenceSignal:
        pref_key = self._context_to_preference_key(context)
        if pref_key:
            current = self._preferences.get(pref_key, 0.5)
            new_weight = min(self.MAX_PREFERENCE_WEIGHT, current + SIGNAL_WEIGHTS["accepted"])
            self._preferences[pref_key] = new_weight
            return PreferenceSignal(
                signal_type="accepted",
                context=context,
                inferred_preference=pref_key,
                confidence=new_weight,
            )
        return PreferenceSignal(
            signal_type="accepted",
            context=context,
            inferred_preference="preference confirmed",
            confidence=0.3,
        )

    def _handle_rejected(self, context: str) -> PreferenceSignal:
        pref_key = self._context_to_preference_key(context)
        inverse_key = self._invert_preference(pref_key) if pref_key else ""
        if inverse_key:
            current = self._preferences.get(inverse_key, 0.5)
            new_weight = min(self.MAX_PREFERENCE_WEIGHT, current + SIGNAL_WEIGHTS["rejected"])
            self._preferences[inverse_key] = new_weight
            return PreferenceSignal(
                signal_type="rejected",
                context=context,
                inferred_preference=inverse_key,
                confidence=new_weight,
            )
        return PreferenceSignal(
            signal_type="rejected",
            context=context,
            inferred_preference="preference opposed",
            confidence=0.4,
        )

    def _handle_corrected(self, context: str, correction_text: str) -> PreferenceSignal:
        inferred = self._extract_preference_from_correction(correction_text)
        if inferred:
            self._correction_patterns[inferred].append(time.time())
            recent_count = sum(
                1 for t in self._correction_patterns[inferred]
                if time.time() - t < 3600
            )
            base_conf = 0.3
            if recent_count >= 3:
                base_conf = 0.75
            elif recent_count >= 2:
                base_conf = 0.55

            current = self._preferences.get(inferred, 0.5)
            new_weight = min(
                self.MAX_PREFERENCE_WEIGHT,
                current + SIGNAL_WEIGHTS["corrected"],
            )
            self._preferences[inferred] = new_weight

            return PreferenceSignal(
                signal_type="corrected",
                context=context,
                inferred_preference=inferred,
                confidence=max(base_conf, new_weight),
            )
        return PreferenceSignal(
            signal_type="corrected",
            context=context,
            inferred_preference="specific preference extracted",
            confidence=0.15,
        )

    def _handle_praised(self, context: str) -> PreferenceSignal:
        pref_key = self._context_to_preference_key(context)
        if pref_key:
            current = self._preferences.get(pref_key, 0.5)
            new_weight = min(self.MAX_PREFERENCE_WEIGHT, current + SIGNAL_WEIGHTS["praised"])
            self._preferences[pref_key] = new_weight
            return PreferenceSignal(
                signal_type="praised",
                context=context,
                inferred_preference=pref_key,
                confidence=new_weight,
            )
        return PreferenceSignal(
            signal_type="praised",
            context=context,
            inferred_preference="satisfaction expressed",
            confidence=0.25,
        )

    def _handle_ignored(self, context: str) -> PreferenceSignal:
        pref_key = self._context_to_preference_key(context)
        if pref_key:
            current = self._preferences.get(pref_key, 0.5)
            new_weight = max(self.MIN_PREFERENCE_WEIGHT, current - SIGNAL_WEIGHTS["ignored"])
            self._preferences[pref_key] = new_weight
            return PreferenceSignal(
                signal_type="ignored",
                context=context,
                inferred_preference=pref_key,
                confidence=new_weight,
            )
        return PreferenceSignal(
            signal_type="ignored",
            context=context,
            inferred_preference="disinterest detected",
            confidence=0.1,
        )

    # ── reward computation ───────────────────────────────────────

    def get_reward(self, action_description: str, context: str = "") -> float:
        """Compute reward for an action based on inferred user preferences.

        Args:
            action_description: human-readable description of the action
            context: optional additional context

        Returns:
            float reward score (higher = more aligned with user preferences)
        """
        combined = f"{action_description} {context}".lower()
        total_weight = 0.0
        match_count = 0

        for pref_key, weight in self._preferences.items():
            if self._preference_matches(pref_key, combined):
                total_weight += weight
                match_count += 1

        if match_count == 0:
            return 0.5  # neutral baseline

        return total_weight / match_count

    def rank_actions(self, actions: list[str], context: str = "") -> list[tuple[str, float]]:
        """Rank actions by inferred user preference (highest first).

        Args:
            actions: list of human-readable action descriptions
            context: optional additional context

        Returns:
            sorted list of (action_description, reward_score) tuples
        """
        scored = [(a, self.get_reward(a, context)) for a in actions]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ── profile ──────────────────────────────────────────────────

    def get_preference_profile(self) -> dict[str, Any]:
        """Return a summary of all learned user preferences."""
        sorted_prefs = sorted(
            self._preferences.items(), key=lambda x: x[1], reverse=True,
        )
        top = [(k, round(v, 3)) for k, v in sorted_prefs[:10]]
        pref_dict = {k: v for k, v in top}
        return {
            "preferences": top,
            "prefers_speed": pref_dict.get("speed", pref_dict.get("latency", 0)),
            "prefers_simplicity": pref_dict.get("simplicity", pref_dict.get("cost", 0)),
            "total_preferences_learned": len(self._preferences),
            "total_observations": len(self._observation_history),
            "signal_distribution": dict(self._signal_counts),
            "latest_corrections": [
                {
                    "preference": s.inferred_preference,
                    "confidence": round(s.confidence, 3),
                    "timestamp": s.timestamp,
                }
                for s in list(self._observation_history)[-5:]
                if s.signal_type == "corrected"
            ],
        }

    def stats(self) -> dict[str, Any]:
        """Return statistical summary of the inverse reward model."""
        if not self._preferences:
            confidence_dist = {"none": 0}
        else:
            weights = list(self._preferences.values())
            confidence_dist = {
                "min": round(min(weights), 3),
                "max": round(max(weights), 3),
                "mean": round(sum(weights) / len(weights), 3),
                "high_confidence_count": sum(1 for w in weights if w > 0.7),
                "low_confidence_count": sum(1 for w in weights if w < 0.3),
            }

        return {
            "preferences_learned": len(self._preferences),
            "observations": len(self._observation_history),
            "signal_counts": dict(self._signal_counts),
            "confidence_distribution": confidence_dist,
            "correction_patterns_with_3plus": sum(
                1 for ts in self._correction_patterns.values()
                if sum(1 for t in ts if time.time() - t < 3600) >= 3
            ),
        }

    # ── internal helpers ─────────────────────────────────────────

    def _context_to_preference_key(self, context: str) -> str:
        ctx_lower = context.lower()
        for pattern, preference in CORRECTION_EXTRACT_PATTERNS:
            if re.search(pattern, ctx_lower):
                return preference
        return ""

    def _invert_preference(self, pref_key: str) -> str:
        inversions = {
            "prefers simplicity over complexity": "prefers detail over brevity",
            "prefers detail over brevity": "prefers simplicity over complexity",
            "prefers speed over depth": "prefers accuracy over speed",
            "prefers accuracy over speed": "prefers speed over depth",
            "prefers concrete code examples": "prefers explanation over direct answer",
            "prefers explanation over direct answer": "prefers concrete code examples",
            "prefers Chinese language output": "prefers English language output",
            "prefers English language output": "prefers Chinese language output",
            "prefers friendly tone": "prefers direct communication",
            "prefers direct communication": "prefers friendly tone",
            "prefers safety over risk": "prefers creativity over safety",
            "prefers creativity over safety": "prefers safety over risk",
            "prefers visual representations": "prefers text output over visuals",
            "prefers text output over visuals": "prefers visual representations",
            "prefers minimal verbosity": "prefers detail over brevity",
        }
        return inversions.get(pref_key, f"opposes: {pref_key}")

    def _extract_preference_from_correction(self, text: str) -> str:
        text_lower = text.lower()
        for pattern, preference in CORRECTION_EXTRACT_PATTERNS:
            if re.search(pattern, text_lower):
                return preference
        return ""

    def _preference_matches(self, pref_key: str, action_text: str) -> bool:
        keywords_map = {
            "prefers simplicity over complexity": ["simple", "简洁", "简短", "简明", "minimal", "basic"],
            "prefers detail over brevity": ["detail", "详细", "详尽", "具体", "thorough", "comprehensive"],
            "prefers speed over depth": ["fast", "quick", "快速", "迅速", "speed", "flash", "fastest"],
            "prefers accuracy over speed": ["accurate", "精确", "准确", "quality", "careful", "verify"],
            "prefers concrete code examples": ["code", "example", "代码", "示例", "implement", "snippet"],
            "prefers explanation over direct answer": ["explain", "解释", "说明", "why", "原因", "reason"],
            "prefers Chinese language output": [],
            "prefers English language output": [],
            "prefers friendly tone": ["friendly", "友善", "礼貌", "gentle", "warm"],
            "prefers direct communication": ["direct", "straight", "直接", "brief", "blunt"],
            "prefers safety over risk": ["safe", "conservative", "保守", "secure", "verify", "check"],
            "prefers creativity over safety": ["creative", "创新", "bold", "探索", "experiment", "novel"],
            "prefers visual representations": ["visual", "chart", "图像", "图表", "可视化", "diagram"],
            "prefers text output over visuals": ["text", "文本", "read", "阅读", "文字"],
            "prefers minimal verbosity": ["silent", "quiet", "安静", "少说", "minimal", "brief"],
            "prefers multimodal responses": ["audio", "video", "声音", "图像", "multimodal", "多模态"],
            "prefers memory-aware responses": ["remember", "memory", "记住", "历史", "history", "之前"],
            "prefers privacy-conscious behavior": ["private", "隐私", "保密", "secret", "safe"],
        }
        keywords = keywords_map.get(pref_key, [pref_key.lower()])
        return any(kw in action_text for kw in keywords) if keywords else False

    def _apply_decay(self) -> None:
        """Apply recency-weighted decay to all preference weights."""
        if len(self._observation_history) < 10:
            return
        for key in list(self._preferences):
            self._preferences[key] = max(
                self.MIN_PREFERENCE_WEIGHT,
                self._preferences[key] * self.RECENCY_DECAY,
            )
            if self._preferences[key] <= self.MIN_PREFERENCE_WEIGHT + 0.01:
                del self._preferences[key]

    # ── persistence ──────────────────────────────────────────────

    def _save(self) -> None:
        try:
            PREFERENCE_STORE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "preferences": self._preferences,
                "signal_counts": dict(self._signal_counts),
                "correction_patterns": {
                    k: [t for t in v if time.time() - t < 3600]
                    for k, v in self._correction_patterns.items()
                },
                "saved_at": time.time(),
            }
            PREFERENCE_STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"IRL: failed to save preferences: {e}")

    def _load(self) -> None:
        if not PREFERENCE_STORE.exists():
            return
        try:
            data = json.loads(PREFERENCE_STORE.read_text(encoding="utf-8"))
            self._preferences = data.get("preferences", {})
            self._signal_counts = defaultdict(int, data.get("signal_counts", {}))
            raw_patterns = data.get("correction_patterns", {})
            now = time.time()
            self._correction_patterns = {
                k: [t for t in v if now - t < 3600]
                for k, v in raw_patterns.items()
            }
            logger.info(f"IRL: loaded {len(self._preferences)} preferences from disk")
        except Exception as e:
            logger.warning(f"IRL: failed to load preferences: {e}")


# ═══ Singleton ═══

_inverse_reward: InverseRewardModel | None = None


def get_inverse_reward() -> InverseRewardModel:
    global _inverse_reward
    if _inverse_reward is None:
        _inverse_reward = InverseRewardModel()
        logger.info("InverseRewardModel singleton created")
    return _inverse_reward


__all__ = [
    "PreferenceSignal",
    "InverseRewardModel",
    "get_inverse_reward",
]
