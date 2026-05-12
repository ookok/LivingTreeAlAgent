"""Surprise-Gated Memory Routing — dopamine-gated memory evolution.

Based on D-MEM (Song & Xin, arXiv:2603.14597, 2026):
  RPE (Reward Prediction Error) gates memory evolution —
    routine inputs bypass (O(1) fast buffer cache),
    surprising inputs trigger full O(N) memory restructuring.

This replaces timer-based "every 10 cycles" with surprise-based
"when RPE exceeds threshold" gating for 80%+ token reduction.

Architecture:
  Input → CriticRouter (RPE) →
    ├─ Low RPE (routine)  → O(1) fast_buffer → bypass evolution
    └─ High RPE (surprise) → dopamine signal → O(N) evolution pipeline

Integration:
  Called by MemPO before each optimize() call to decide whether
  a full memory restructuring cycle is warranted.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class SurpriseSignal:
    """Result of CriticRouter evaluating an input.

    Encodes the complete RPE-based gating decision: whether an input
    is sufficiently surprising to warrant memory restructuring.
    """

    surprise_score: float = 0.0
    utility_score: float = 0.0
    rpe: float = 0.0
    should_evolve: bool = False
    reason: str = ""
    timestamp: float = field(default_factory=time.time)
    content_hash: str = ""


class CriticRouter:
    """RPE-based gating router — evaluates input surprise and utility.

    Computes Reward Prediction Error as:
      RPE = surprise_score * 0.6 + utility_score * 0.4

    Surprise measures deviation from expected patterns (n-gram overlap).
    Utility measures potential future value (new entities, contradictions, numbers).

    Low RPE → fast_path  (O(1) bypass)
    High RPE → evolve_path (O(N) full memory restructuring)
    """

    NGRAM_N = 3
    NUM_PATTERN = re.compile(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?%?\b")
    ENTITY_PATTERN = re.compile(
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
        r"|\bhttps?://[^\s]+"
        r"|\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
    )

    def __init__(self, surprise_threshold: float = 0.4):
        self._expected_patterns: dict[str, float] = {}
        self._surprise_threshold = surprise_threshold
        self._lock = threading.RLock()
        self._total_evaluations = 0
        self._recent_signals: deque[SurpriseSignal] = deque(maxlen=50)

    def evaluate(self, content: str, context: dict[str, Any] | None = None) -> SurpriseSignal:
        content_str = content if isinstance(content, str) else str(content)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:12]

        surprise_score = self._compute_surprise(content_str)
        utility_score = self._compute_utility(content_str, context or {})
        rpe = surprise_score * 0.6 + utility_score * 0.4
        should_evolve = rpe > self._surprise_threshold

        reason_parts = []
        if surprise_score > 0.5:
            reason_parts.append(f"high surprise ({surprise_score:.2f})")
        if utility_score > 0.5:
            reason_parts.append(f"high utility ({utility_score:.2f})")
        if not reason_parts:
            reason_parts.append("routine input")
        reason = "; ".join(reason_parts)

        signal = SurpriseSignal(
            surprise_score=round(surprise_score, 4),
            utility_score=round(utility_score, 4),
            rpe=round(rpe, 4),
            should_evolve=should_evolve,
            reason=reason,
            content_hash=content_hash,
            timestamp=time.time(),
        )

        with self._lock:
            self._total_evaluations += 1
            self._recent_signals.append(signal)

        if should_evolve:
            logger.debug(
                "CriticRouter: RPE={:.3f} > threshold={:.2f} → evolve ({})",
                rpe, self._surprise_threshold, reason,
            )

        return signal

    def _compute_surprise(self, content: str) -> float:
        """Compute surprise as 1 - max n-gram overlap with expected patterns."""
        ngrams = self._extract_ngrams(content.lower(), self.NGRAM_N)

        if not ngrams or not self._expected_patterns:
            with self._lock:
                if len(self._expected_patterns) < 20:
                    self._absorb_patterns(ngrams)
            return 0.7 if not self._expected_patterns else 0.35

        max_overlap = 0.0
        matched = 0
        for ng in ngrams:
            if ng in self._expected_patterns:
                matched += 1
                score = self._expected_patterns[ng]
                if score > max_overlap:
                    max_overlap = score

        overlap_ratio = matched / max(len(ngrams), 1)
        surprise = max(0.0, min(1.0, 1.0 - overlap_ratio))

        no_match_boost = 0.0
        if matched == 0 and len(self._expected_patterns) > 30:
            no_match_boost = 0.3
            surprise = max(surprise, 0.65)

        return min(1.0, surprise + no_match_boost)

    def _compute_utility(self, content: str, context: dict[str, Any]) -> float:
        """Compute utility: novel entities, numbers, contradictions, specificity.

        Returns a 0-1 score of how useful this input is for future tasks.
        """
        utility = 0.0

        entities = self.ENTITY_PATTERN.findall(content)
        if entities:
            novel_entities = 0
            known = context.get("known_entities", set())
            for e in entities:
                if e.lower() not in known:
                    novel_entities += 1
            entity_utility = min(1.0, novel_entities / max(len(entities), 1))
            utility = max(utility, entity_utility * 0.5)

        numbers = self.NUM_PATTERN.findall(content)
        if len(numbers) >= 3:
            utility = max(utility, min(0.7, len(numbers) * 0.05))

        known_facts = context.get("known_facts", [])
        if known_facts:
            content_lower = content.lower()
            contradictions = 0
            for fact in known_facts:
                if isinstance(fact, str) and fact.lower() in content_lower:
                    negation_words = re.findall(
                        r"\b(not|no|never|wrong|incorrect|false|disagree|but actually|however|cannot|won't)\b",
                        content_lower.split(fact.lower())[1] if fact.lower() in content_lower else "",
                    )
                    if negation_words:
                        contradictions += 1
            if contradictions > 0:
                utility = max(utility, min(0.8, 0.3 + contradictions * 0.15))

        if len(content) > 500:
            utility = max(utility, 0.15)

        words = content.split()
        if len(words) > 50:
            unique_ratio = len(set(w.lower() for w in words)) / len(words)
            if unique_ratio > 0.8:
                utility = max(utility, unique_ratio * 0.3)

        return min(1.0, utility)

    def update_expectations(self, content: str, success: bool = True) -> None:
        """Update expected patterns after processing.

        Successful patterns become more expected (surprise decreases).
        Failed patterns are partially de-weighted.
        """
        content_str = content if isinstance(content, str) else str(content)
        ngrams = self._extract_ngrams(content_str.lower(), self.NGRAM_N)

        with self._lock:
            for ng in ngrams:
                current = self._expected_patterns.get(ng, 0.0)
                if success:
                    update = 0.08
                    self._expected_patterns[ng] = min(1.0, current + update)
                else:
                    update = 0.03
                    self._expected_patterns[ng] = max(0.01, current - update)

            recent_keys = list(self._expected_patterns.keys())
            if len(recent_keys) > 5000:
                oldest = sorted(
                    recent_keys, key=lambda k: self._expected_patterns[k],
                )[:1000]
                for k in oldest:
                    if self._expected_patterns[k] < 0.1:
                        del self._expected_patterns[k]

    def get_routing_decision(self, content: str) -> str:
        """Return routing label without building full SurpriseSignal.

        Returns:
            "fast_path" — routine input, use O(1) buffer cache
            "evolve_path" — surprising input, trigger O(N) evolution
        """
        content_str = content if isinstance(content, str) else str(content)
        surprise = self._compute_surprise(content_str)
        utility = self._compute_utility(content_str, {})
        rpe = surprise * 0.6 + utility * 0.4

        if rpe > self._surprise_threshold:
            return "evolve_path"
        return "fast_path"

    def set_threshold(self, threshold: float) -> None:
        with self._lock:
            self._surprise_threshold = max(0.05, min(0.95, threshold))

    @property
    def threshold(self) -> float:
        return self._surprise_threshold

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            total = max(self._total_evaluations, 1)
            evolves = sum(1 for s in self._recent_signals if s.should_evolve)
            bypasses = total - evolves
            recent_surprise_avg = (
                sum(s.rpe for s in self._recent_signals) / max(len(self._recent_signals), 1)
            )
            return {
                "total_evaluations": self._total_evaluations,
                "evolves": evolves,
                "bypasses": bypasses,
                "bypass_ratio": round(bypasses / total, 4),
                "recent_surprise_avg": round(recent_surprise_avg, 4),
                "threshold": self._surprise_threshold,
                "known_patterns": len(self._expected_patterns),
            }

    def _extract_ngrams(self, text: str, n: int) -> list[str]:
        words = text.split()
        if len(words) < n:
            return words[:]
        return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]

    def _absorb_patterns(self, ngrams: list[str]) -> None:
        for ng in ngrams:
            if ng not in self._expected_patterns:
                self._expected_patterns[ng] = 0.1


class SurpriseGatedMemory:
    """Dopamine-gated memory pipeline — surprise-based evolution trigger.

    Replaces periodical optimization with RPE-gated:
      - Routine inputs → O(1) fast_buffer cache, bypass evolution entirely
      - Surprising inputs → dopamine signal → full MemPO evolution pipeline

    Expected token savings: 80%+ by skipping unnecessary optimizations.

    Usage:
        gate = get_surprise_gate()
        result = await gate.process(content, memory_system=mempo)
        if result["routed"] == "evolve":
            # Memory restructuring was triggered
            ...
    """

    def __init__(self, surprise_threshold: float = 0.4):
        self._fast_buffer: dict[str, Any] = {}
        self._critic = CriticRouter(surprise_threshold=surprise_threshold)
        self._evolution_count = 0
        self._bypass_count = 0
        self._total_processed = 0
        self._lock = threading.RLock()
        self._recent_results: deque[dict[str, Any]] = deque(maxlen=100)
        self._surprise_history: deque[SurpriseSignal] = deque(maxlen=100)
        self._start_time = time.time()

    async def process(
        self,
        content: str,
        memory_system: Any = None,
        consciousness: Any = None,
    ) -> dict[str, Any]:
        """Evaluate and route input through surprise-gated memory pipeline.

        Args:
            content: The input text/memory to evaluate.
            memory_system: MemPO optimizer or similar memory system with .optimize()
            consciousness: Optional consciousness object for context enrichment.

        Returns:
            dict with routing decision, signal details, and evolution stats.
        """
        t0 = time.time()

        context: dict[str, Any] = {}
        if consciousness is not None:
            try:
                if hasattr(consciousness, "get_context"):
                    context = consciousness.get_context() or {}
                elif hasattr(consciousness, "known_entities"):
                    context["known_entities"] = consciousness.known_entities
            except Exception:
                pass

        signal = self._critic.evaluate(content, context)

        with self._lock:
            self._surprise_history.append(signal)

        if not signal.should_evolve:
            content_hash = hashlib.sha256(
                (content if isinstance(content, str) else str(content)).encode()
            ).hexdigest()[:16]
            with self._lock:
                self._fast_buffer[content_hash] = {
                    "content": content if isinstance(content, str) else str(content),
                    "signal": signal,
                    "cached_at": time.time(),
                }
                self._bypass_count += 1
                self._total_processed += 1

                if len(self._fast_buffer) > 500:
                    oldest_keys = sorted(
                        self._fast_buffer.keys(),
                        key=lambda k: self._fast_buffer[k]["cached_at"],
                    )[:200]
                    for k in oldest_keys:
                        del self._fast_buffer[k]

            elapsed = (time.time() - t0) * 1000
            return {
                "routed": "fast_path",
                "signal": signal,
                "action": "bypass",
                "bypass_count": self._bypass_count,
                "evolution_count": self._evolution_count,
                "elapsed_ms": round(elapsed, 2),
                "buffer_size": len(self._fast_buffer),
            }

        evolution_result = {}
        if memory_system is not None:
            try:
                if hasattr(memory_system, "optimize"):
                    evolution_result = memory_system.optimize()
                elif hasattr(memory_system, "evolve"):
                    if hasattr(memory_system.evolve, "__code__"):
                        import asyncio
                        if asyncio.iscoroutinefunction(memory_system.evolve):
                            evolution_result = await memory_system.evolve(content, signal)
                        else:
                            evolution_result = memory_system.evolve(content, signal)
                    else:
                        evolution_result = memory_system.evolve(content, signal)
            except Exception as exc:
                logger.warning("SurpriseGatedMemory: evolution failed — {}", exc)
                evolution_result = {"error": str(exc)}

        with self._lock:
            self._evolution_count += 1
            self._total_processed += 1

        elapsed = (time.time() - t0) * 1000

        logger.info(
            "SurpriseGatedMemory: EVOLVE (RPE={:.3f}) — \"{}\" ({}ms)",
            signal.rpe, signal.reason[:80], round(elapsed),
        )

        result = {
            "routed": "evolve_path",
            "signal": signal,
            "action": "evolve",
            "evolution_count": self._evolution_count,
            "bypass_count": self._bypass_count,
            "evolution_result": evolution_result,
            "buffer_size": len(self._fast_buffer),
            "elapsed_ms": round(elapsed, 2),
        }

        with self._lock:
            self._recent_results.append(result)

        return result

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            total = max(self._total_processed, 1)
            bypass_ratio = self._bypass_count / total
            evolution_ratio = self._evolution_count / total
            recent_surprise = sum(
                s.rpe for s in self._surprise_history
            ) / max(len(self._surprise_history), 1)
            uptime = max(time.time() - self._start_time, 1)
            return {
                "bypass_count": self._bypass_count,
                "evolution_count": self._evolution_count,
                "total_processed": self._total_processed,
                "bypass_ratio": round(bypass_ratio, 4),
                "evolution_ratio": round(evolution_ratio, 4),
                "avg_surprise": round(recent_surprise, 4),
                "fast_buffer_size": len(self._fast_buffer),
                "threshold": self._critic.threshold,
                "uptime_s": round(uptime, 1),
                "token_savings_estimate": f"{round(bypass_ratio * 100, 1)}%",
                "critic": self._critic.get_stats(),
            }

    def set_fast_threshold(self, threshold: float) -> None:
        """Adjust surprise threshold. Lower = more evolutions triggered.

        Default 0.4. Reducing to 0.2 makes the system evolve more frequently;
        raising to 0.6 makes it more conservative.
        """
        self._critic.set_threshold(threshold)
        logger.info("SurpriseGatedMemory: threshold set to {}", threshold)

    def get_recent_surprises(self, limit: int = 5) -> list[dict[str, Any]]:
        """Return the most surprising recent inputs."""
        with self._lock:
            sorted_signals = sorted(
                self._surprise_history,
                key=lambda s: s.rpe,
                reverse=True,
            )[:limit]
        return [
            {
                "surprise_score": s.surprise_score,
                "utility_score": s.utility_score,
                "rpe": s.rpe,
                "should_evolve": s.should_evolve,
                "reason": s.reason,
                "content_hash": s.content_hash,
                "timestamp": s.timestamp,
            }
            for s in sorted_signals
        ]

    def get_routing_decision(self, content: str) -> str:
        """Quick routing decision without full processing.

        Returns "fast_path" or "evolve_path".
        """
        return self._critic.get_routing_decision(content)

    def reset_stats(self) -> None:
        """Reset counters (useful for benchmarking)."""
        with self._lock:
            self._evolution_count = 0
            self._bypass_count = 0
            self._total_processed = 0
            self._start_time = time.time()
            self._recent_results.clear()
            self._surprise_history.clear()

    def warm_buffer(self, contents: list[str]) -> None:
        """Pre-populate the fast buffer and expected patterns with known content.

        Useful during initialization to avoid treating startup data as surprising.
        """
        for c in contents:
            c_str = c if isinstance(c, str) else str(c)
            self._critic.update_expectations(c_str, success=True)
            content_hash = hashlib.sha256(c_str.encode()).hexdigest()[:16]
            self._fast_buffer[content_hash] = {
                "content": c_str,
                "signal": None,
                "cached_at": time.time(),
            }
        logger.info(
            "SurpriseGatedMemory: warmed buffer with {} items ({} patterns)",
            len(contents), len(self._critic._expected_patterns),
        )


# ═══ Singleton ═══

_surprise_gate: SurpriseGatedMemory | None = None


def get_surprise_gate(surprise_threshold: float = 0.4) -> SurpriseGatedMemory:
    """Get or create the global SurpriseGatedMemory singleton.

    Args:
        surprise_threshold: RPE threshold for triggering evolution (0-1).
            Only used on first creation; subsequent calls ignore this parameter.

    Returns:
        The global SurpriseGatedMemory instance.
    """
    global _surprise_gate
    if _surprise_gate is None:
        _surprise_gate = SurpriseGatedMemory(surprise_threshold=surprise_threshold)
        logger.info(
            "SurpriseGatedMemory singleton created (threshold={})",
            surprise_threshold,
        )
    return _surprise_gate


__all__ = [
    "SurpriseSignal",
    "CriticRouter",
    "SurpriseGatedMemory",
    "get_surprise_gate",
]
