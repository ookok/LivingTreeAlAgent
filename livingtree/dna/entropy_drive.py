"""Entropy Drive — entropy-driven deadlock breaking based on Global Workspace Theory.

GWA (Shang, arXiv:2604.08206, 2026): In multi-agent systems with passive
message passing and static memory pools, cognitive stagnation inevitably
emerges — repetitive, homogeneous responses that form reasoning deadlocks
during extended execution.

Solution: entropy-based intrinsic drive mathematically quantifies semantic
diversity, dynamically regulating generation temperature to autonomously
break reasoning deadlocks.

Integration:
    drive = get_entropy_drive()
    drive.observe(agent_output_text)                    # feed each output
    if drive.check_deadlock():                          # before inter-head round
        prompt = drive.inject_entropy_prompt()          # provocative prompt
        temp_boost = drive.get_temperature_boost()      # adjust LLM temperature
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Data Types ═══


@dataclass
class EntropyMetrics:
    """Snapshot of semantic diversity and deadlock state.

    Attributes:
        semantic_entropy: 0-1, higher = more diverse (1 - avg pairwise Jaccard)
        repetition_ratio: 0-1, how repetitive recent outputs are
        staleness: 0-1, how long since last novel output
        temperature_boost: current temperature adjustment applied
        deadlock_detected: whether deadlock conditions are met
    """
    semantic_entropy: float = 1.0
    repetition_ratio: float = 0.0
    staleness: float = 0.0
    temperature_boost: float = 0.0
    deadlock_detected: bool = False
    timestamp: float = field(default_factory=time.time)

    @property
    def is_healthy(self) -> bool:
        return not self.deadlock_detected and self.semantic_entropy >= 0.25

    @property
    def warning_level(self) -> str:
        if self.deadlock_detected:
            return "deadlock"
        if self.semantic_entropy < 0.25:
            return "warning"
        return "healthy"


# ═══ Entropy Drive ═══


class EntropyDrive:
    """Entropy-driven deadlock breaking via semantic diversity measurement.

    GWA (Shang, arXiv:2604.08206, 2026): When multi-agent heads communicate
    through passive message passing, they suffer cognitive stagnation —
    outputs become increasingly homogeneous, forming reasoning deadlocks.

    This module measures semantic entropy across recent outputs, detects
    deadlock conditions, and autonomously breaks them by injecting provocative
    prompts and boosting LLM temperature to increase output diversity.

    Called by SheshaOrchestrator before each inter-head collaboration round.
    """

    def __init__(
        self,
        window_size: int = 20,
        novelty_threshold: float = 0.3,
        max_temperature_boost: float = 0.5,
        decay_per_cycle: float = 0.05,
        deadlock_staleness_cycles: int = 10,
    ):
        self._window_size = window_size
        self._novelty_threshold = novelty_threshold
        self._max_temperature_boost = max_temperature_boost
        self._decay_per_cycle = decay_per_cycle
        self._deadlock_staleness_cycles = deadlock_staleness_cycles

        self._recent_outputs: deque[str] = deque(maxlen=window_size)
        self._current_temperature_boost: float = 0.0
        self._staleness_counter: int = 0
        self._deadlock_count: int = 0
        self._cycle_count: int = 0
        self._last_novel_cycle: int = -1
        self._last_metrics: EntropyMetrics | None = None

        # Internal: cached n-gram sets for each output to avoid recomputation
        self._ngram_cache: deque[set[str]] = deque(maxlen=window_size)

    # ── Observation ──

    def observe(self, output_text: str) -> None:
        """Record an agent output and compute novelty.

        Extracts bigrams from the output text and computes Jaccard overlap
        against the most recent output. If overlap exceeds 0.8, the output
        is considered repetitive and the staleness counter increments.
        """
        if not output_text or not output_text.strip():
            return

        text = output_text.strip()
        bigrams = self._extract_bigrams(text)

        self._recent_outputs.append(text)
        self._ngram_cache.append(bigrams)
        self._cycle_count += 1

        # Compare with previous output for rapid repetition detection
        if len(self._recent_outputs) >= 2:
            prev_bigrams = self._ngram_cache[-2]
            overlap = self._jaccard(bigrams, prev_bigrams)
            if overlap > 0.8:
                self._staleness_counter += 1
            else:
                self._staleness_counter = max(0, self._staleness_counter - 1)
                self._last_novel_cycle = self._cycle_count

    # ── Entropy Computation ──

    def compute_entropy(self) -> EntropyMetrics:
        """Compute full entropy metrics from recent outputs.

        Returns:
            EntropyMetrics with semantic_entropy, repetition_ratio,
            staleness, temperature_boost, and deadlock_detected flag.

        semantic_entropy = 1 - avg_pairwise_jaccard of all recent outputs.
        repetition_ratio = count of near-duplicate pairs / total pairs.
        staleness = 1.0 if last novel output > deadlock_staleness_cycles ago.
        """
        n = len(self._recent_outputs)
        if n < 2:
            self._last_metrics = EntropyMetrics(
                semantic_entropy=1.0,
                repetition_ratio=0.0,
                staleness=0.0,
                temperature_boost=self._current_temperature_boost,
                deadlock_detected=False,
            )
            return self._last_metrics

        # Compute pairwise Jaccard similarities
        total_pairs = 0
        sum_jaccard = 0.0
        near_duplicate_pairs = 0

        # Only compare recent_window to keep computation bounded
        recent_window = min(n, self._window_size)
        bigrams_list = list(self._ngram_cache)[-recent_window:]

        for i in range(recent_window):
            for j in range(i + 1, recent_window):
                sim = self._jaccard(bigrams_list[i], bigrams_list[j])
                sum_jaccard += sim
                total_pairs += 1
                if sim > 0.8:
                    near_duplicate_pairs += 1

        if total_pairs == 0:
            avg_jaccard = 0.0
        else:
            avg_jaccard = sum_jaccard / total_pairs

        semantic_entropy = max(0.0, min(1.0, 1.0 - avg_jaccard))
        repetition_ratio = near_duplicate_pairs / total_pairs if total_pairs > 0 else 0.0

        # Staleness: how many cycles since last novel output
        if self._last_novel_cycle < 0:
            staleness = 1.0
        else:
            cycles_since_novel = self._cycle_count - self._last_novel_cycle
            staleness = min(1.0, cycles_since_novel / self._deadlock_staleness_cycles)

        # Decay temperature boost if entropy is recovering
        if semantic_entropy > 0.35 and self._current_temperature_boost > 0.0:
            self._current_temperature_boost = max(
                0.0,
                self._current_temperature_boost - self._decay_per_cycle,
            )

        self._last_metrics = EntropyMetrics(
            semantic_entropy=round(semantic_entropy, 4),
            repetition_ratio=round(repetition_ratio, 4),
            staleness=round(staleness, 4),
            temperature_boost=round(self._current_temperature_boost, 4),
            deadlock_detected=self._detect_deadlock_conditions(
                semantic_entropy, repetition_ratio, staleness,
            ),
        )
        return self._last_metrics

    # ── Deadlock Detection ──

    def check_deadlock(self) -> bool:
        """Check if the system is in a reasoning deadlock.

        A deadlock is detected when:
          - semantic_entropy < 0.15 AND repetition_ratio > 0.7, OR
          - staleness > 0.8 (no novel output for 10+ cycles)

        Returns:
            True if deadlock conditions are met.
        """
        metrics = self.compute_entropy()
        return metrics.deadlock_detected

    def _detect_deadlock_conditions(
        self, semantic_entropy: float, repetition_ratio: float, staleness: float,
    ) -> bool:
        """Internal deadlock check from precomputed values.

        Two deadlock pathways:
        1. Entropy collapse: semantic_entropy < 0.15 AND repetition_ratio > 0.7
           → the system is producing nearly identical outputs repeatedly.
        2. Staleness deadlock: staleness > 0.8
           → no novel output has appeared for 10+ cycles.

        Returns:
            True if either deadlock condition is met.
        """
        entropy_collapse = semantic_entropy < 0.15 and repetition_ratio > 0.7
        staleness_deadlock = staleness > 0.8

        if entropy_collapse or staleness_deadlock:
            self._deadlock_count += 1
            return True
        return False

    # ── Temperature Regulation ──

    def get_temperature_boost(self) -> float:
        """Get the current temperature boost based on entropy state.

        Temperature regulation levels:
          - Normal (entropy >= 0.25): 0.0
          - Warning (entropy < 0.25): +0.15
          - Deadlock (entropy < 0.15): +0.3
          - Stale (staleness > 0.8): +0.2

        The boost is cumulative up to max_temperature_boost (0.5) and
        decays by decay_per_cycle (0.05) when entropy recovers above 0.35.

        Returns:
            Current temperature boost value [0.0, 0.5].
        """
        metrics = self.compute_entropy()

        if metrics.staleness > 0.8:
            self._current_temperature_boost = min(
                self._max_temperature_boost,
                self._current_temperature_boost + 0.2,
            )
            logger.debug(
                f"EntropyDrive: staleness={metrics.staleness:.2f}, "
                f"boost increased to {self._current_temperature_boost:.2f}",
            )
        elif metrics.semantic_entropy < 0.15:
            self._current_temperature_boost = min(
                self._max_temperature_boost,
                self._current_temperature_boost + 0.3,
            )
            logger.warning(
                f"EntropyDrive: DEADLOCK detected (entropy={metrics.semantic_entropy:.3f}), "
                f"boost={self._current_temperature_boost:.2f}",
            )
        elif metrics.semantic_entropy < 0.25:
            self._current_temperature_boost = min(
                self._max_temperature_boost,
                self._current_temperature_boost + 0.15,
            )
        # Decay is handled in compute_entropy() when entropy > 0.35

        return round(self._current_temperature_boost, 4)

    # ── Entropy Prompt Injection ──

    def inject_entropy_prompt(self) -> str | None:
        """Generate a provocative prompt to break reasoning deadlocks.

        When deadlock is detected, returns a prompt designed to force
        the agent to reconsider from a radically different perspective.
        Returns None when entropy is healthy (no deadlock).

        Returns:
            A Chinese entropy-injection prompt string, or None.
        """
        if not self.check_deadlock():
            return None

        prompts = [
            "你似乎陷入了思维定势。请从一个完全不同的角度重新思考这个问题。",
            "尝试一个你之前没有考虑过的方案。",
            "你的回答模式开始重复。请打破惯性思维，探索全新的思路。",
            "你之前的推理陷入了循环。请质疑你的基本假设，重新开始。",
            "跳出当前框架，从相反的方向思考这个问题可能是什么。",
        ]

        # Cycle through prompts based on deadlock count for variety
        idx = (self._deadlock_count - 1) % len(prompts)
        selected = prompts[idx]

        logger.info(
            f"EntropyDrive: injecting entropy prompt "
            f"(deadlock #{self._deadlock_count}): {selected[:40]}...",
        )
        return selected

    # ── Statistics ──

    def stats(self) -> dict[str, Any]:
        """Return current entropy drive statistics.

        Returns:
            dict with keys: entropy, repetition, staleness, boost,
            deadlock_count, cycle_count, window_size.
        """
        metrics = self.compute_entropy()
        return {
            "entropy": metrics.semantic_entropy,
            "repetition": metrics.repetition_ratio,
            "staleness": metrics.staleness,
            "boost": metrics.temperature_boost,
            "deadlock_count": self._deadlock_count,
            "cycle_count": self._cycle_count,
            "window_size": len(self._recent_outputs),
            "warning_level": metrics.warning_level,
        }

    # ── Reset ──

    def reset(self) -> None:
        """Clear all recent outputs and reset entropy state.

        Useful when starting a new conversation context or after
        a significant context shift that invalidates prior comparisons.
        """
        self._recent_outputs.clear()
        self._ngram_cache.clear()
        self._current_temperature_boost = 0.0
        self._staleness_counter = 0
        self._last_novel_cycle = -1
        self._last_metrics = None
        logger.debug("EntropyDrive: state reset")

    # ── Internal Helpers ──

    @staticmethod
    def _extract_bigrams(text: str) -> set[str]:
        """Extract character-level bigrams from text.

        Uses character bigrams to be language-agnostic (works for both
        Chinese characters and Latin/English words). The set representation
        enables efficient Jaccard similarity computation.

        Args:
            text: Input text string.

        Returns:
            Set of two-character substrings.
        """
        if len(text) < 2:
            return {text}
        return {text[i:i + 2] for i in range(len(text) - 1)}

    @staticmethod
    def _jaccard(set_a: set[str], set_b: set[str]) -> float:
        """Compute Jaccard similarity between two n-gram sets.

        Jaccard(A, B) = |A ∩ B| / |A ∪ B|
        Range: 0.0 (completely different) to 1.0 (identical).

        Args:
            set_a: First bigram set.
            set_b: Second bigram set.

        Returns:
            Jaccard similarity coefficient.
        """
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 1.0


# ═══ Singleton ═══

_entropy_drive: EntropyDrive | None = None


def get_entropy_drive() -> EntropyDrive:
    """Get or create the global EntropyDrive singleton instance.

    Called by SheshaOrchestrator before each inter-head collaboration round
    to check for deadlocks and inject entropy-breaking prompts and temperature
    boosts when needed.

    Returns:
        The singleton EntropyDrive instance.
    """
    global _entropy_drive
    if _entropy_drive is None:
        _entropy_drive = EntropyDrive()
    return _entropy_drive


__all__ = [
    "EntropyDrive",
    "EntropyMetrics",
    "get_entropy_drive",
]
