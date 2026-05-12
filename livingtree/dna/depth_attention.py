"""Depth Attention (AttnRes) — learned content-dependent layer weighting.

Inspired by Kimi Team's "Attention Residuals" (arXiv:2603.15031, 2026).
Instead of all layers/stages having equal fixed-weight connections, each layer
uses learned, content-dependent softmax attention over preceding outputs.

CONCEPT:
  BEFORE (fixed equal weights):         AFTER (depth attention):
  Stage1 ──1.0──┐                       Stage1 ──0.1──┐
  Stage2 ──1.0──┼── Output              Stage2 ──0.3──┼── softmax ── Output
  Stage3 ──1.0──┘                       Stage3 ──0.6──┘
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


@dataclass
class AttentionStats:
    temperature: float
    biases: list[float]
    current_weights: list[float]
    entropy: float


class DepthAttention:
    """Learned softmax attention over preceding layers."""

    def __init__(
        self,
        num_layers: int,
        temperature: float = 1.0,
        learned_bias: list[float] | None = None,
    ) -> None:
        self.num_layers = num_layers
        self.temperature = max(temperature, 0.01)
        self._current_weights: list[float] = [1.0 / num_layers] * num_layers
        if learned_bias is not None:
            if len(learned_bias) != num_layers:
                raise ValueError(
                    f"learned_bias length {len(learned_bias)} != num_layers {num_layers}"
                )
            self.learned_bias = list(learned_bias)
        else:
            self.learned_bias = [0.0] * num_layers

    def compute_weights(self, values: list[float]) -> list[float]:
        if len(values) != self.num_layers:
            raise ValueError(
                f"values length {len(values)} != num_layers {self.num_layers}"
            )
        logits = [
            v / self.temperature + b
            for v, b in zip(values, self.learned_bias)
        ]
        max_logit = max(logits)
        exps = [math.exp(z - max_logit) for z in logits]
        total = sum(exps)
        if total == 0:
            self._current_weights = [1.0 / self.num_layers] * self.num_layers
        else:
            self._current_weights = [e / total for e in exps]
        logger.debug(
            f"DepthAttention: weights={[round(w, 3) for w in self._current_weights]}"
        )
        return list(self._current_weights)

    def weighted_aggregate(self, values: list[float], content: list[str]) -> str:
        weights = self.compute_weights(values)
        parts: list[str] = []
        for w, c in zip(weights, content):
            if c:
                parts.append(c)
                if len(parts) > 1:
                    parts[-1] = c  # keep last; prepend weight multiplier
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0]
        scored = sorted(zip(weights, parts), key=lambda x: x[0], reverse=True)
        return "\n".join(
            f"[weight={w:.2f}] {p}" for w, p in scored if w > 0.01
        )

    def select_top_k(self, values: list[float], k: int = 3) -> list[int]:
        weights = self.compute_weights(values)
        indexed = list(enumerate(weights))
        indexed.sort(key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in indexed[:k]]

    def update_bias(self, feedback: list[tuple[int, float]]) -> None:
        for layer_idx, reward in feedback:
            if 0 <= layer_idx < self.num_layers:
                self.learned_bias[layer_idx] = (
                    0.9 * self.learned_bias[layer_idx] + 0.1 * reward
                )
        logger.debug(f"DepthAttention: updated biases={[round(b, 3) for b in self.learned_bias]}")

    def entropy(self) -> float:
        w = self._current_weights
        ent = 0.0
        for wi in w:
            if wi > 0:
                ent -= wi * math.log(wi)
        return ent

    def stats(self) -> AttentionStats:
        return AttentionStats(
            temperature=self.temperature,
            biases=list(self.learned_bias),
            current_weights=list(self._current_weights),
            entropy=self.entropy(),
        )


class BlockDepthAttention:
    """Attends over blocks of layers instead of individual layers.

    Groups layers into blocks, reducing memory while preserving most gains.
    """

    def __init__(
        self,
        num_layers: int,
        block_size: int = 3,
        temperature: float = 1.0,
        learned_bias: list[float] | None = None,
    ) -> None:
        if block_size < 1:
            raise ValueError(f"block_size must be >= 1, got {block_size}")
        self.block_size = block_size
        num_blocks = max(1, (num_layers + block_size - 1) // block_size)
        self.num_blocks = num_blocks
        self.temperature = max(temperature, 0.01)
        self._current_weights: list[float] = [1.0 / num_blocks] * num_blocks
        if learned_bias is not None:
            if len(learned_bias) != num_blocks:
                raise ValueError(
                    f"learned_bias length {len(learned_bias)} != num_blocks {num_blocks}"
                )
            self.learned_bias = list(learned_bias)
        else:
            self.learned_bias = [0.0] * num_blocks

    def _block_averages(self, block_values: list[list[float]]) -> list[float]:
        if len(block_values) != self.num_blocks:
            raise ValueError(
                f"block_values length {len(block_values)} != num_blocks {self.num_blocks}"
            )
        return [sum(blk) / max(len(blk), 1) for blk in block_values]

    def compute_block_weights(self, block_values: list[list[float]]) -> list[float]:
        averages = self._block_averages(block_values)
        logits = [
            avg / self.temperature + b
            for avg, b in zip(averages, self.learned_bias)
        ]
        max_logit = max(logits)
        exps = [math.exp(z - max_logit) for z in logits]
        total = sum(exps)
        if total == 0:
            self._current_weights = [1.0 / self.num_blocks] * self.num_blocks
        else:
            self._current_weights = [e / total for e in exps]
        return list(self._current_weights)

    def select_top_k(self, block_values: list[list[float]], k: int = 3) -> list[int]:
        weights = self.compute_block_weights(block_values)
        indexed = list(enumerate(weights))
        indexed.sort(key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in indexed[:k]]

    def update_bias(self, feedback: list[tuple[int, float]]) -> None:
        for block_idx, reward in feedback:
            if 0 <= block_idx < self.num_blocks:
                self.learned_bias[block_idx] = (
                    0.9 * self.learned_bias[block_idx] + 0.1 * reward
                )

    def entropy(self) -> float:
        ent = 0.0
        for wi in self._current_weights:
            if wi > 0:
                ent -= wi * math.log(wi)
        return ent

    def stats(self) -> AttentionStats:
        return AttentionStats(
            temperature=self.temperature,
            biases=list(self.learned_bias),
            current_weights=list(self._current_weights),
            entropy=self.entropy(),
        )


class StageAttention:
    """Convenience wrapper mapping stage names to attention weights.

    Designed for LifeEngine pipeline stages:
    perceive → cognize → ontogrow → plan → simulate → execute → reflect → evolve
    """

    DEFAULT_STAGES: list[str] = [
        "perceive", "cognize", "ontogrow", "plan",
        "simulate", "execute", "reflect", "evolve",
    ]

    def __init__(
        self,
        stage_names: list[str] | None = None,
        temperature: float = 1.0,
        learned_bias: list[float] | None = None,
    ) -> None:
        self.stage_names = list(stage_names or self.DEFAULT_STAGES)
        n = len(self.stage_names)
        self._attention = DepthAttention(
            num_layers=n,
            temperature=temperature,
            learned_bias=learned_bias,
        )

    def attend_to_stages(
        self, stage_signals: dict[str, float]
    ) -> dict[str, float]:
        values = [stage_signals.get(name, 0.0) for name in self.stage_names]
        weights = self._attention.compute_weights(values)
        return dict(zip(self.stage_names, weights))

    def get_top_stages(
        self, stage_signals: dict[str, float], k: int = 3
    ) -> list[str]:
        values = [stage_signals.get(name, 0.0) for name in self.stage_names]
        indices = self._attention.select_top_k(values, k=k)
        return [self.stage_names[i] for i in indices]

    def update_from_outcome(
        self,
        stage_signals: dict[str, float],
        successful_stages: list[str],
    ) -> None:
        feedback: list[tuple[int, float]] = []
        for i, name in enumerate(self.stage_names):
            reward = 1.0 if name in successful_stages else 0.0
            feedback.append((i, reward))
        self._attention.update_bias(feedback)

    def entropy(self) -> float:
        return self._attention.entropy()

    def stats(self) -> AttentionStats:
        return self._attention.stats()


# ═══════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════

_attention: DepthAttention | None = None


def get_depth_attention(num_layers: int = 8) -> DepthAttention:
    """Get or create the singleton DepthAttention."""
    global _attention
    if _attention is None:
        _attention = DepthAttention(num_layers=num_layers)
        logger.info(f"DepthAttention singleton created (num_layers={num_layers})")
    return _attention


__all__ = [
    "AttentionStats",
    "BlockDepthAttention",
    "DepthAttention",
    "StageAttention",
    "get_depth_attention",
]
