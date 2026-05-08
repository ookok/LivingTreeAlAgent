"""Scinet DSSA Router — Dual-Space Sparse Attention for efficient routing.

Based on SpikingBrain2.0 (Pan et al., 2026):
  "SpikingBrain2.0: Brain-Inspired Foundation Models for Efficient
   Long-Context and Cross-Platform Inference"

Core innovation: DSSA (Dual-Space Sparse Attention) — inter-layer hybrid of
  - MoBA (Mixture of Block Attention): sparse softmax, routes queries to top-k blocks
  - SSE (Sparse State Expansion): sparse linear attention with gated state

Architecture (adapted for Scinet routing):
  Input: [proxy_blocks | persona_blocks | protocol_blocks | strategy_blocks]
     │
     ├──► MoBA Layer (sparse softmax attention)
     │      • Split into blocks of size B
     │      • Route queries to top-k relevant blocks
     │      • Softmax attention only within selected blocks
     │      • Complexity: O(N·k·B) instead of O(N²)
     │
     ├──► SSE Layer (sparse linear attention)
     │      • State expansion via gated DeltaNet
     │      • Linear complexity O(N·d²) regardless of sequence length
     │      • Sparsity control via gate mechanism
     │
     └──► Inter-layer alternation
            • Odd layers: MoBA (high precision, moderate sparsity)
            • Even layers: SSE (high efficiency, linear complexity)
            • Combined: DSSA

Integration with Laser Router:
  Laser (latent superposition) ←→ DSSA (sparse attention)
  Users can choose: Laser for 95% token reduction, DSSA for memory efficiency

Usage:
    dssa = DSSARouter(num_blocks=16, block_size=4, top_k=3)
    await dssa.initialize()
    decision = await dssa.route(domain, category, proxy_pool)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
from loguru import logger

DSSA_CACHE = Path(".livingtree/dssa_state.json")

# Default dimensions
D_MODEL = 64       # Hidden dimension
NUM_BLOCKS = 16    # Number of routing blocks
BLOCK_SIZE = 4     # Features per block (total features = 64)
TOP_K = 3          # Top-k blocks for MoBA
SSE_EXPAND = 4     # SSE state expansion factor
NUM_DSSA_LAYERS = 4  # Alternating MoBA/SSE layers


@dataclass
class BlockInfo:
    """Metadata for a single routing block."""
    block_id: int
    block_type: str  # proxy, persona, protocol, strategy
    features: np.ndarray  # [BLOCK_SIZE]
    importance: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0


@dataclass
class DSSADecision:
    """Routing decision from DSSA sparse attention."""
    proxy_id: str = ""
    persona_id: str = ""
    protocol: str = "h2"
    padding: str = "standard"
    strategy: str = "NEGOTIATE"
    confidence: float = 0.5
    # MoBA metrics
    moba_blocks_selected: int = 0
    moba_sparsity: float = 0.0  # Fraction of attention skipped
    # SSE metrics
    sse_effective_rank: int = 0
    sse_sparsity: float = 0.0
    # Combined
    total_compute_saved: float = 0.0  # Fraction vs full attention


class BlockRouter:
    """MoBA-style block-routing attention.

    Splits the input sequence into blocks of fixed size, then routes each
    query to only the top-k most relevant blocks. This achieves O(N·k·B)
    complexity instead of O(N²) for full attention.

    From SpikingBrain2.0: "MoBA achieves 5-10x speedup over full attention
    at sequence lengths > 8K while maintaining >95% of the quality."
    """

    def __init__(self, num_blocks: int = NUM_BLOCKS,
                 block_size: int = BLOCK_SIZE, top_k: int = TOP_K):
        self.num_blocks = num_blocks
        self.block_size = block_size
        self.top_k = top_k
        self.total_dim = num_blocks * block_size

        # Learnable block embeddings (query/key projections for routing)
        rng = np.random.RandomState(42)
        self.W_q = rng.randn(block_size, block_size) * 0.1  # Block query projection
        self.W_k = rng.randn(block_size, block_size) * 0.1  # Block key projection
        self.W_v = rng.randn(block_size, block_size) * 0.1  # Block value projection
        self.W_o = rng.randn(block_size, block_size) * 0.1  # Output projection

        # Block metadata
        self._blocks: list[BlockInfo] = []
        self._initialize_blocks()

    def _initialize_blocks(self):
        """Initialize block metadata with routing categories."""
        categories = (
            ["proxy"] * 4 + ["persona"] * 4 +
            ["protocol"] * 4 + ["strategy"] * 4
        )
        for i in range(self.num_blocks):
            self._blocks.append(BlockInfo(
                block_id=i,
                block_type=categories[min(i, len(categories) - 1)],
                features=np.zeros(self.block_size),
            ))

    def set_block_features(self, block_idx: int, features: np.ndarray):
        """Update features for a specific block."""
        if 0 <= block_idx < self.num_blocks:
            self._blocks[block_idx].features = features.copy()

    def forward(self, query: np.ndarray) -> tuple[np.ndarray, list[int], float]:
        """MoBA forward pass: route query to top-k blocks, attend sparsely.

        Args:
            query: [BLOCK_SIZE] query vector

        Returns:
            output: [BLOCK_SIZE] attended output
            selected_blocks: list of block indices selected
            sparsity: fraction of attention computation saved
        """
        # Step 1: Compute query-key similarity with all blocks
        q_proj = np.dot(query, self.W_q)
        scores = np.zeros(self.num_blocks)
        for i in range(self.num_blocks):
            k_proj = np.dot(self._blocks[i].features, self.W_k)
            scores[i] = np.dot(q_proj, k_proj)

        # Step 2: Route to top-k blocks (key MoBA innovation)
        top_indices = np.argsort(scores)[::-1][:self.top_k]
        top_scores = scores[top_indices]

        # Step 3: Sparse softmax attention within selected blocks
        top_scores = top_scores / math.sqrt(self.block_size)  # Scale
        score_max = top_scores.max()
        exp_scores = np.exp(top_scores - score_max)
        attn_weights = exp_scores / exp_scores.sum()

        # Step 4: Weighted value combination
        output = np.zeros(self.block_size)
        for idx, weight in zip(top_indices, attn_weights):
            v_proj = np.dot(self._blocks[idx].features, self.W_v)
            output += weight * v_proj
            self._blocks[idx].access_count += 1
            self._blocks[idx].last_accessed = time.time()
            self._blocks[idx].importance = max(
                self._blocks[idx].importance, float(weight),
            )

        # Output projection
        output = np.dot(output, self.W_o)

        # Sparsity metric
        sparsity = 1.0 - (self.top_k / self.num_blocks)

        return output, list(top_indices), sparsity


class SparseLinearAttention:
    """SSE-style sparse linear attention with gated state expansion.

    From SpikingBrain2.0: "SSE is a sparse state expansion mechanism on top
    of Gated DeltaNet, enabling improved long-context retrieval with
    controllable computation and parameter overhead."

    Key properties:
    - Linear complexity O(N·d²) regardless of sequence length
    - Gated state update: S_t = gate * S_{t-1} + (1-gate) * new_state
    - Sparse expansion: only activate top dimensions based on input energy
    """

    def __init__(self, dim: int = BLOCK_SIZE, expand: int = SSE_EXPAND):
        self.dim = dim
        self.expand = expand
        self.effective_dim = dim * expand

        rng = np.random.RandomState(43)
        # State expansion matrices
        self.W_expand = rng.randn(dim, self.effective_dim) * 0.05
        self.W_contract = rng.randn(self.effective_dim, dim) * 0.05

        # Gating mechanism (controls state update rate)
        self.W_gate = rng.randn(dim) * 0.1  # [dim] for scalar gate output
        self.b_gate = 0.0

        # Delta update (learned change to state)
        self.W_delta = rng.randn(dim, self.effective_dim) * 0.05

        # Recurrent state
        self._state: Optional[np.ndarray] = None  # [effective_dim]
        self._state_dim_usage: np.ndarray = np.ones(self.effective_dim)  # Track dimension usage

    def reset_state(self):
        self._state = np.zeros(self.effective_dim)

    def forward(self, x: np.ndarray) -> tuple[np.ndarray, float, int]:
        """SSE forward pass with sparse state expansion.

        Args:
            x: [dim] input vector

        Returns:
            output: [dim] output
            sparsity: fraction of state dimensions not activated
            effective_rank: number of active state dimensions
        """
        if self._state is None:
            self.reset_state()

        # Step 1: State expansion
        expanded = np.dot(x, self.W_expand)

        # Step 2: Gate computation (sigmoid)
        gate_input = np.dot(x, self.W_gate) + self.b_gate
        gate = 1.0 / (1.0 + np.exp(-gate_input))  # Sigmoid

        # Step 3: Delta state
        delta = np.dot(x, self.W_delta)

        # Step 4: Sparse activation — only update high-energy dimensions
        energy = np.abs(expanded)
        energy_threshold = np.percentile(energy, 100 - (100 // self.expand))
        active_mask = energy >= energy_threshold
        n_active = int(np.sum(active_mask))
        n_active = max(n_active, 1)  # Ensure at least 1 dimension active

        # Update only active dimensions (sparse update)
        gate_val = float(gate) if hasattr(gate, 'item') else gate
        new_state = self._state.copy()
        new_state[active_mask] = (
            gate_val * self._state[active_mask] +
            (1 - gate_val) * expanded[active_mask] +
            0.1 * delta[active_mask]
        )
        self._state = new_state

        # Track dimension usage
        self._state_dim_usage[active_mask] = (
            self._state_dim_usage[active_mask] * 0.95 + 0.05
        )

        # Step 5: Contract back to output dimension
        output = np.dot(self._state, self.W_contract)

        # Sparsity metrics
        total_dims = self.effective_dim
        sparsity = 1.0 - (n_active / total_dims)

        return output, sparsity, n_active


class DSSALayer:
    """A single DSSA layer — alternates MoBA and SSE.

    From SpikingBrain2.0: "DSSA interleaves MoBA and SSE layers,
    achieving an improved performance-efficiency trade-off."

    Odd layers (MoBA): high-precision sparse softmax attention
    Even layers (SSE): efficient sparse linear attention with state
    """

    def __init__(self, layer_idx: int):
        self.layer_idx = layer_idx
        is_moba = (layer_idx % 2 == 0)  # Alternating: 0=MoBA, 1=SSE, 2=MoBA, ...

        if is_moba:
            self._moba = BlockRouter()
            self._sse = None
        else:
            self._moba = None
            self._sse = SparseLinearAttention()

        self._layer_norm_weight = np.ones(BLOCK_SIZE)
        self._layer_norm_bias = np.zeros(BLOCK_SIZE)

    def forward(self, query: np.ndarray, block_features: list[np.ndarray] = None,
                ) -> tuple[np.ndarray, dict]:
        """Forward pass through MoBA or SSE layer.

        Returns (output, metrics) where metrics contains layer-type-specific stats.
        """
        metrics = {"layer_type": "moba" if self._moba else "sse", "layer_idx": self.layer_idx}

        if self._moba:
            # MoBA: sparse block attention
            if block_features:
                for i, feat in enumerate(block_features[:self._moba.num_blocks]):
                    self._moba.set_block_features(i, feat)

            output, selected_blocks, sparsity = self._moba.forward(query)
            metrics["selected_blocks"] = selected_blocks
            metrics["sparsity"] = sparsity
            metrics["blocks_used"] = len(selected_blocks)

        else:
            # SSE: sparse linear attention
            if block_features and len(block_features) > 0:
                # Aggregate block features for SSE input
                aggregated = np.mean(block_features[:4], axis=0)
            else:
                aggregated = query

            output, sparsity, effective_rank = self._sse.forward(aggregated)
            metrics["sparsity"] = sparsity
            metrics["effective_rank"] = effective_rank

        # Layer norm + residual
        mean = output.mean()
        std = output.std() + 1e-6
        output_norm = self._layer_norm_weight * (output - mean) / std + self._layer_norm_bias
        output = query + output_norm  # Residual connection

        return output, metrics


class DSSARouter:
    """DSSA-based sparse attention router for Scinet.

    Uses Dual-Space Sparse Attention (interleaved MoBA + SSE layers) to
    efficiently route requests through proxy/persona/protocol space.

    Compared to Laser (latent superposition):
      - Laser: 8 latent steps, 95% token reduction
      - DSSA: 4 sparse attention layers, memory-efficient, long-context capable

    Architecture:
      Input Query [BLOCK_SIZE]
          ↓
      ┌─ DSSA Layer 0 (MoBA) ─┐
      │  Route to top-3 proxy  │
      │  blocks, sparse attn   │
      └──────────┬─────────────┘
                 ↓
      ┌─ DSSA Layer 1 (SSE) ───┐
      │  Linear attention with  │
      │  gated state expansion  │
      └──────────┬──────────────┘
                 ↓
      ┌─ DSSA Layer 2 (MoBA) ─┐
      │  Route to top-3 persona │
      │  + protocol blocks       │
      └──────────┬─────────────┘
                 ↓
      ┌─ DSSA Layer 3 (SSE) ───┐
      │  Final state contraction │
      │  → decode decision       │
      └──────────┬──────────────┘
                 ↓
           DSSADecision

    Usage:
        dssa = DSSARouter()
        await dssa.initialize()
        decision = await dssa.route("github.com", "DEDICATED")
    """

    def __init__(self, num_layers: int = NUM_DSSA_LAYERS):
        self.num_layers = num_layers
        self._layers: list[DSSALayer] = []
        self._block_features: list[np.ndarray] = []

        # Decision decoder (final layer → decision)
        rng = np.random.RandomState(44)
        self.W_decode = rng.randn(BLOCK_SIZE, 5) * 0.1  # [proxy, persona, protocol, strategy, padding]

        # Domain hash for deterministic initialization
        self._domain_cache: dict[str, np.ndarray] = {}
        self._decision_cache: dict[str, DSSADecision] = {}

        self._stats = {
            "total_routes": 0,
            "avg_moba_sparsity": 0.0,
            "avg_sse_sparsity": 0.0,
            "avg_compute_saved": 0.0,
        }

    async def initialize(self):
        for i in range(self.num_layers):
            self._layers.append(DSSALayer(i))
        self._init_block_features()
        logger.info(
            "DSSARouter: %d layers (%d MoBA + %d SSE), %d blocks",
            self.num_layers,
            sum(1 for l in self._layers if l._moba),
            sum(1 for l in self._layers if l._sse),
            NUM_BLOCKS,
        )

    def _init_block_features(self):
        """Initialize block features from routing categories.

        Each block represents a routing concept:
        - Blocks 0-3:  proxy candidates (quality, latency, protocol, country)
        - Blocks 4-7:  persona candidates (browser, platform, TLS, headers)
        - Blocks 8-11: protocol candidates (h3, h2, http/1.1, h2+ws)
        - Blocks 12-15: strategy candidates (OBFUSCATE, NEGOTIATE, DIRECT, padding)
        """
        rng = np.random.RandomState(100)
        self._block_features = []

        for i in range(NUM_BLOCKS):
            feat = rng.randn(BLOCK_SIZE) * 0.1
            # Add category-specific bias
            category = i // 4
            feat[category % BLOCK_SIZE] += 0.5
            # Normalize
            norm = np.linalg.norm(feat)
            if norm > 0:
                feat = feat / norm
            self._block_features.append(feat)

    def _build_query(self, domain: str, category: str) -> np.ndarray:
        """Build query vector from domain + category."""
        if domain in self._domain_cache:
            return self._domain_cache[domain]

        query = np.zeros(BLOCK_SIZE)
        domain_hash = hashlib.sha256(domain.encode()).digest()
        for i in range(min(BLOCK_SIZE, len(domain_hash))):
            query[i] = domain_hash[i] / 255.0

        cat_map = {"DEDICATED": 0.3, "SEARCH": 0.6, "CDN": 0.5, "VIDEO": 0.9, "GENERAL": 0.4}
        query[1] = cat_map.get(category, 0.4)

        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm
        self._domain_cache[domain] = query
        return query

    async def route(
        self, domain: str, category: str = "GENERAL",
    ) -> DSSADecision:
        """Execute full DSSA routing pipeline.

        Pipeline: build_query → MoBA layer → SSE layer → ... → decode
        """
        # Cache check
        cache_key = f"{domain}:{category}"
        if cache_key in self._decision_cache:
            return self._decision_cache[cache_key]

        query = self._build_query(domain, category)
        total_sparsity = 0.0
        moba_blocks = 0
        sse_rank = 0

        # Forward through all DSSA layers
        hidden = query.copy()
        all_metrics = []
        for layer in self._layers:
            hidden, metrics = layer.forward(hidden, self._block_features)
            all_metrics.append(metrics)
            total_sparsity += metrics.get("sparsity", 0)

            if metrics["layer_type"] == "moba":
                moba_blocks += metrics.get("blocks_used", 0)
            else:
                sse_rank += metrics.get("effective_rank", 0)

        # Decode decision
        logits = np.dot(hidden, self.W_decode)
        probs = 1.0 / (1.0 + np.exp(-logits))  # Sigmoid per dimension

        # Decode from probabilities
        proxy_idx = int(np.clip(probs[0] * 4, 0, 3))
        persona_idx = int(np.clip(probs[1] * 8, 0, 7))
        protocol_idx = int(np.clip(probs[2] * 5, 0, 4))
        strategy_idx = int(np.clip(probs[3] * 3, 0, 2))
        padding_idx = int(np.clip(probs[4] * 3, 0, 2))

        proxy_map = {0: "direct", 1: "proxy_pool", 2: "ip_pool", 3: "optimal_ip"}
        persona_map = {
            0: "chrome130_win", 1: "chrome124_mac", 2: "firefox130_win",
            3: "safari17_mac", 4: "edge130_win", 5: "brave_win",
            6: "chrome_mobile_android", 7: "opera_win",
        }
        protocol_map = {0: "h3", 1: "h2", 2: "http/1.1", 3: "h2+ws", 4: "grpc"}
        strategy_map = {0: "OBFUSCATE", 1: "NEGOTIATE", 2: "DIRECT"}
        padding_map = {0: "standard", 1: "aggressive", 2: "minimal"}

        avg_sparsity = total_sparsity / self.num_layers
        compute_saved = avg_sparsity  # Fraction of compute saved vs full attention

        decision = DSSADecision(
            proxy_id=proxy_map.get(proxy_idx, "direct"),
            persona_id=persona_map.get(persona_idx, "chrome130_win"),
            protocol=protocol_map.get(protocol_idx, "h2"),
            padding=padding_map.get(padding_idx, "standard"),
            strategy=strategy_map.get(strategy_idx, "NEGOTIATE"),
            confidence=float(np.mean(probs)),
            moba_blocks_selected=moba_blocks,
            moba_sparsity=float(np.mean([
                m.get("sparsity", 0) for m in all_metrics if m["layer_type"] == "moba"
            ] or [0])),
            sse_effective_rank=sse_rank,
            sse_sparsity=float(np.mean([
                m.get("sparsity", 0) for m in all_metrics if m["layer_type"] == "sse"
            ] or [0])),
            total_compute_saved=compute_saved,
        )

        self._decision_cache[cache_key] = decision

        # Update stats
        n = self._stats["total_routes"]
        self._stats["avg_moba_sparsity"] = (
            self._stats["avg_moba_sparsity"] * n + decision.moba_sparsity
        ) / (n + 1)
        self._stats["avg_sse_sparsity"] = (
            self._stats["avg_sse_sparsity"] * n + decision.sse_sparsity
        ) / (n + 1)
        self._stats["avg_compute_saved"] = (
            self._stats["avg_compute_saved"] * n + compute_saved
        ) / (n + 1)
        self._stats["total_routes"] += 1

        return decision

    def get_attention_heatmap(self) -> dict[str, list[float]]:
        """Get attention importance for all blocks (interpretability)."""
        moba = self._layers[0]._moba if self._layers and self._layers[0]._moba else None
        if moba is None:
            return {}

        return {
            "block_importance": [b.importance for b in moba._blocks],
            "block_access_count": [b.access_count for b in moba._blocks],
            "block_types": [b.block_type for b in moba._blocks],
        }

    def get_stats(self) -> dict:
        heatmap = self.get_attention_heatmap()
        return {
            **self._stats,
            "cache_size": len(self._decision_cache),
            "num_layers": self.num_layers,
            "num_blocks": NUM_BLOCKS,
            "top_blocks_by_importance": sorted(
                zip(heatmap.get("block_types", []), heatmap.get("block_importance", [])),
                key=lambda x: x[1], reverse=True,
            )[:5] if heatmap else [],
        }


_dssa_router: Optional[DSSARouter] = None


def get_dssa_router() -> DSSARouter:
    global _dssa_router
    if _dssa_router is None:
        _dssa_router = DSSARouter()
    return _dssa_router
