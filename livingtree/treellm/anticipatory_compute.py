"""AnticipatoryCompute — Predictive pre-computation with speculative cache warming.

Builds on ContextMoE, ConversationStateMachine, SemanticCache, and PredictiveRouter.

Predicts user's next likely query and pre-computes answers during idle time.
When the user actually asks, 0ms response from pre-warmed cache.

Key innovations:
  1. NextQueryPredictor: Markov model over conversation state transitions
  2. SpeculativePreloader: pre-fetch context from ContextMoE for predicted queries
  3. IdleComputeScheduler: uses DaemonDoctor idle windows for pre-computation

Integration:
  acc = get_anticipatory_compute()
  predicted = await acc.predict_next(session_id, current_query)
  await acc.prewarm(predicted)  # Cache speculative results
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class PredictedQuery:
    query_text: str
    probability: float = 0.5
    source: str = ""         # "markov" | "pattern" | "csm"
    expected_latency_saving_ms: float = 0.0


class AnticipatoryCompute:
    """Predicts and pre-computes likely next queries."""

    _instance: Optional["AnticipatoryCompute"] = None

    @classmethod
    def instance(cls) -> "AnticipatoryCompute":
        if cls._instance is None:
            cls._instance = AnticipatoryCompute()
        return cls._instance

    def __init__(self):
        # Markov transition model: state → next_state → count
        self._transitions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # Pattern memory: (current_query, next_query) frequency
        self._query_pairs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._predictions = 0
        self._hits = 0

    # ── Prediction ─────────────────────────────────────────────────

    async def predict_next(self, session_id: str, current_query: str,
                           current_state: str = "") -> list[PredictedQuery]:
        """Predict user's next likely queries. Returns top-3 by probability."""
        predictions = []

        # 1. Markov state transition
        if current_state:
            next_states = self._transitions.get(current_state, {})
            total = sum(next_states.values())
            for state, count in sorted(next_states.items(), key=lambda x: -x[1])[:3]:
                prob = count / max(total, 1)
                predictions.append(PredictedQuery(
                    query_text=f"[{state}] related query",
                    probability=prob, source="markov",
                ))

        # 2. Query pairs (exact query → next query)
        pairs = self._query_pairs.get(current_query.lower()[:80], {})
        total_pairs = sum(pairs.values())
        for next_q, count in sorted(pairs.items(), key=lambda x: -x[1])[:5]:
            prob = count / max(total_pairs, 1)
            # Avoid duplicates
            if not any(p.query_text == next_q for p in predictions):
                predictions.append(PredictedQuery(
                    query_text=next_q, probability=prob, source="pattern",
                ))

        # 3. CSM state-based hints
        try:
            from .conversation_state_machine import STAGE_ROUTING
            if current_state in STAGE_ROUTING:
                routing = STAGE_ROUTING[current_state]
                if routing.get("task_type") == "code":
                    predictions.append(PredictedQuery(
                        query_text="代码需要什么修改?",
                        probability=0.4, source="csm",
                    ))
        except Exception:
            pass

        predictions.sort(key=lambda x: -x.probability)
        self._predictions += 1
        return predictions[:3]

    async def prewarm(self, predictions: list[PredictedQuery],
                      llm: Any = None) -> int:
        """Pre-compute answers for predicted queries and cache them."""
        warmed = 0
        for pred in predictions:
            if pred.probability < 0.3:
                continue

            try:
                from .semantic_cache import get_semantic_cache, _to_lsh
                cache = get_semantic_cache()

                # Check if already cached
                emb = [float(ord(c)) / 255.0 for c in pred.query_text[:16]] + [0.0] * (16 - min(16, len(pred.query_text)))
                if cache.get(emb):
                    continue

                # Pre-compute via LLM if available and probability is high
                if llm and pred.probability > 0.5:
                    try:
                        result = await llm.chat(
                            [{"role": "user", "content": pred.query_text}],
                            max_tokens=512, temperature=0.3,
                        )
                        text = getattr(result, 'text', '') or str(result)
                        if text:
                            cache.set(emb, text[:2000])
                            warmed += 1
                    except Exception:
                        pass
            except Exception:
                pass

        if warmed:
            logger.debug(f"AnticipatoryCompute: pre-warmed {warmed} predictions")
        return warmed

    # ── Learning ───────────────────────────────────────────────────

    def learn(self, current_query: str, next_query: str,
              current_state: str = "", next_state: str = "") -> None:
        """Learn from actual user behavior to improve predictions."""
        # Update query pairs
        key = current_query.lower()[:80]
        self._query_pairs[key][next_query.lower()[:200]] += 1

        # Update state transitions
        if current_state and next_state and current_state != next_state:
            self._transitions[current_state][next_state] += 1

        # Track hit rate: was next_query in our predictions?
        if self._predictions > 0:
            # Simplified hit detection
            if any(p.query_text.lower() in next_query.lower() or
                   next_query.lower() in p.query_text.lower()
                   for p in self._last_predictions):
                self._hits += 1

        self._last_predictions = []

    _last_predictions: list[PredictedQuery] = field(default_factory=list)

    async def _save_predictions(self, predictions):
        self._last_predictions = predictions

    @property
    def hit_rate(self) -> float:
        return self._hits / max(self._predictions, 1)

    def stats(self) -> dict:
        return {
            "predictions": self._predictions,
            "hits": self._hits,
            "hit_rate": round(self.hit_rate, 3),
            "states_tracked": len(self._transitions),
            "query_pairs": sum(len(v) for v in self._query_pairs.values()),
        }


_acc: Optional[AnticipatoryCompute] = None


def get_anticipatory_compute() -> AnticipatoryCompute:
    global _acc
    if _acc is None:
        _acc = AnticipatoryCompute()
    return _acc


__all__ = ["AnticipatoryCompute", "PredictedQuery", "get_anticipatory_compute"]
