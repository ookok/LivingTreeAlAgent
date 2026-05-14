"""Context Density Maximizer + Adaptive Topology Router + Cognitive Evolution.

Combines insights from three papers (all implemented as mixins/integrations):
  - GenericAgent (2604.17091): context information density maximization
  - AdaptOrch (2602.16873): task DAG → topology routing O(|V|+|E|)
  - AutoAgent (2603.09716): cognitive evolution + elastic memory

v2.5 Opus 4.7: dynamic_reassess() re-scores all slices against current query.
soft_evict() compresses instead of deleting low-value slices. attention_decay
models mid-section information decay for long conversations.

Integrated into livingtree execution and DNA layers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# Part 1: Context Density Maximizer (GenericAgent)
# ═══════════════════════════════════════════════════════

class DensityStrategy(str, Enum):
    TRUNCATE = "truncate"     # Cut oldest messages
    COMPRESS = "compress"     # Summarize old content
    EVICT = "evict"           # Remove low-value entries
    ANCHOR = "anchor"         # Keep critical info visible
    SOFT_EVICT = "soft_evict"  # Opus 4.7: compress instead of delete


@dataclass
class ContextSlice:
    """A managed slice of the context window.

    v2.5 Opus 4.7: attention_decay models mid-section information decay.
    Higher decay → slice has been "in the middle" too long and needs boost.

    v2.6 ALiBi Slopes: alibi_slope determines decay rate per slice by information
    entropy. High-entropy slices (speculative, conversational) get steep slope
    (1/2) = rapid decay. Low-entropy slices (decisions, facts) get flat slope
    (1/256) = persistent preservation. Mirrors ALiBi's per-head slope spectrum.
    """
    content: str
    tokens: int
    importance: float        # 0 (disposable) to 1 (critical)
    age: int = 0              # Turns since creation
    strategy: DensityStrategy = DensityStrategy.COMPRESS
    attention_decay: float = 0.0  # Opus 4.7: cumulative mid-section decay
    alibi_slope: float = 0.5      # v2.6: geometric decay rate (higher = decays faster)


class ContextDensityMaximizer:
    """Maximize decision-relevant information per context token.

    GenericAgent's 4 mechanisms:
      1. Minimal atomic tool set — reduce persistent overhead
      2. Hierarchical memory — show summary by default, expand on demand
      3. Self-evolution — compress trajectories into reusable SOPs
      4. Context truncation — layered eviction when budget exceeded
    """

    def __init__(self, max_tokens: int = 8192):
        self.max_tokens = max_tokens
        self._slices: list[ContextSlice] = []
        self._total_tokens = 0
        self._density_score = 0.0

    def add_slice(self, content: str, importance: float = 0.5) -> None:
        """Add a context slice, auto-managing token budget.

        v2.6 ALiBi: slices with high information entropy (speculative,
        conversational) get steep alibi_slope → rapid decay. Low-entropy
        slices (decisions, facts, definitions) get flat slope → persistent.
        """
        tokens = len(content) // 3
        alibi_slope = self._compute_entropy_slope(content)
        sl = ContextSlice(
            content=content, tokens=tokens, importance=importance,
            alibi_slope=alibi_slope,
        )
        self._slices.append(sl)
        self._total_tokens += tokens
        self._enforce_budget()

    @staticmethod
    def _compute_entropy_slope(content: str) -> float:
        """Compute ALiBi slope from content information entropy.

        High entropy (more unique words, question marks, hedges) → steep slope (rapid decay).
        Low entropy (few unique words, declarative, structured) → flat slope (persistent).
        Maps slopes to geometric spectrum: {1/2, 1/4, 1/8, 1/16, 1/32, 1/64, 1/128, 1/256}.
        """
        if not content.strip():
            return 0.25
        words = content.lower().split()
        if len(words) < 3:
            return 0.0625
        unique_ratio = len(set(words)) / len(words)
        hedge_count = sum(1 for w in words if w in {"maybe", "perhaps", "possibly", "might", "could", "大概", "可能"})
        question_count = content.count("?") + content.count("？")
        entropy = unique_ratio * 0.5 + min(hedge_count * 0.15, 0.3) + min(question_count * 0.1, 0.2)
        slope_index = max(0, min(7, int(entropy * 8)))
        return 1.0 / (2.0 ** (slope_index + 1))

    def _enforce_budget(self) -> None:
        """Apply layered eviction when over budget."""
        while self._total_tokens > self.max_tokens and self._slices:
            # Evict: remove oldest low-importance slice first
            candidates = [
                (i, s) for i, s in enumerate(self._slices)
                if s.importance < 0.3 and s.age > 2
            ]
            if candidates:
                idx, _ = candidates[0]
            else:
                # Fallback: evict oldest
                idx = 0

            removed = self._slices.pop(idx)
            self._total_tokens -= removed.tokens

        # Age all slices
        for s in self._slices:
            s.age += 1

    @property
    def density(self) -> float:
        """Information density: weighted importance / total tokens."""
        if not self._slices or self._total_tokens == 0:
            return 0.0
        weighted = sum(s.importance * s.tokens for s in self._slices)
        return weighted / self._total_tokens

    # ── Opus 4.7: Dynamic Reassessment + Soft Evict ──

    def dynamic_reassess(self, query: str) -> None:
        """Re-score all slices against the current query each turn.

        Opus 4.7: Instead of fixed importance set at insertion time,
        re-evaluate relevance dynamically. Old low-importance slices
        that match the current query get restored importance.
        """
        if not query:
            return
        q_words = set(query.lower().split())
        for s in self._slices:
            s.lower = s.content.lower()
            overlap = sum(1 for w in q_words if w in s.lower)
            base_score = overlap / max(len(q_words), 1)
            decay_compensated = min(1.0, base_score + s.attention_decay * 0.3)
            s.importance = max(s.importance, decay_compensated)
            s.attention_decay += 0.05

    def soft_evict(self, target_importance: float = 0.15) -> int:
        """Compress (instead of delete) low-importance slices.

        Opus 4.7: soft eviction preserves info that might become relevant
        later, unlike binary delete. Compressed slices retain 25% token budget
        and switch to DensityStrategy.SOFT_EVICT.
        Returns number of slices soft-evicted.
        """
        count = 0
        for s in self._slices:
            if s.importance < target_importance and s.strategy != DensityStrategy.SOFT_EVICT:
                s.content = s.content[:max(50, s.tokens // 4)]
                s.tokens = len(s.content) // 3
                s.strategy = DensityStrategy.SOFT_EVICT
                count += 1
                self._total_tokens -= s.tokens
        return count

    def decay(self, mid_section_range: tuple[int, int] = (5, 15),
              decay_rate: float = 0.08) -> None:
        """Apply mid-section attention decay with per-slice ALiBi slopes.

        v2.6 ALiBi: each slice decays at its own geometric rate. High-entropy
        slices with steep alibi_slope (1/2) decay 32x faster than low-entropy
        slices with flat alibi_slope (1/256). This mirrors ALiBi's per-head
        slope distribution mapped to per-slice information entropy.
        """
        start, end = mid_section_range
        for i, s in enumerate(self._slices):
            if start <= i < end:
                s.attention_decay += decay_rate * s.alibi_slope * 16.0


# ═══════════════════════════════════════════════════════
# Part 2: Adaptive Topology Router (AdaptOrch)
# ═══════════════════════════════════════════════════════

class TopologyType(str, Enum):
    PARALLEL = "parallel"        # All subtasks run simultaneously
    SEQUENTIAL = "sequential"    # One after another
    HIERARCHICAL = "hierarchical"  # Tree structure with delegation
    HYBRID = "hybrid"            # Mixed: parallel groups executed sequentially


class TopologyRouter:
    """Route task DAGs to optimal orchestration topology in O(|V|+|E|).

    AdaptOrch's key insight: topology selection dominates model selection
    when LLM capabilities converge.
    """

    def route(self, subtask_count: int, parallelism_width: int,
              critical_path_depth: int, coupling: float = 0.5) -> TopologyType:
        """Select optimal topology based on task DAG structure.

        Args:
            subtask_count: Total number of subtasks (|V|).
            parallelism_width: Max tasks that can run in parallel.
            critical_path_depth: Longest dependency chain.
            coupling: Inter-subtask coupling strength (0=independent, 1=highly coupled).

        Returns:
            Optimal TopologyType.
        """
        # Heuristic from AdaptOrch's empirical findings:
        if parallelism_width >= subtask_count * 0.7 and coupling < 0.3:
            return TopologyType.PARALLEL
        elif critical_path_depth >= subtask_count * 0.8:
            return TopologyType.SEQUENTIAL
        elif coupling > 0.6 or critical_path_depth > 3:
            return TopologyType.HIERARCHICAL
        else:
            return TopologyType.HYBRID


# ═══════════════════════════════════════════════════════
# Part 3: Cognitive Evolution (AutoAgent)
# ═══════════════════════════════════════════════════════

@dataclass
class CognitiveState:
    """Evolving cognitive state — what the agent knows about itself."""
    tools: dict[str, float] = field(default_factory=dict)     # tool → confidence
    capabilities: dict[str, float] = field(default_factory=dict)  # capability → mastery
    peers: dict[str, float] = field(default_factory=dict)      # peer agent → reliability
    task_patterns: dict[str, float] = field(default_factory=dict)  # pattern → success_rate
    last_updated: float = field(default_factory=time.time)


class CognitiveEvolution:
    """Self-improving cognitive model — AutoAgent's closed-loop evolution.

    Tracks: which tools work, which capabilities are strong,
    which peers are reliable, which task patterns succeed.
    Updates after each execution cycle based on outcomes.
    """

    def __init__(self):
        self._state = CognitiveState()

    def update_tool(self, tool_name: str, success: bool) -> None:
        if tool_name not in self._state.tools:
            self._state.tools[tool_name] = 0.5
        alpha = 0.2  # Learning rate
        target = 1.0 if success else 0.0
        self._state.tools[tool_name] += alpha * (target - self._state.tools[tool_name])

    def update_peer(self, peer_name: str, success: bool) -> None:
        if peer_name not in self._state.peers:
            self._state.peers[peer_name] = 0.5
        alpha = 0.15
        target = 1.0 if success else 0.0
        self._state.peers[peer_name] += alpha * (target - self._state.peers[peer_name])

    def update_pattern(self, pattern: str, success: bool) -> None:
        if pattern not in self._state.task_patterns:
            self._state.task_patterns[pattern] = 0.5
        alpha = 0.1
        target = 1.0 if success else 0.0
        self._state.task_patterns[pattern] += alpha * (target - self._state.task_patterns[pattern])

    def best_tool(self) -> Optional[str]:
        if not self._state.tools:
            return None
        return max(self._state.tools, key=self._state.tools.get)

    def tool_confidence(self, name: str) -> float:
        return self._state.tools.get(name, 0.5)

    def peer_reliability(self, name: str) -> float:
        return self._state.peers.get(name, 0.5)

    def evolve_from_outcome(self, task_type: str, tools_used: list[str],
                             peers_involved: list[str], success: bool) -> None:
        """Full evolution step after an execution cycle."""
        for t in tools_used:
            self.update_tool(t, success)
        for p in peers_involved:
            self.update_peer(p, success)
        self.update_pattern(task_type, success)
        self._state.last_updated = time.time()

        if self._state.task_patterns:
            top_patterns = sorted(
                self._state.task_patterns.items(), key=lambda x: -x[1]
            )[:3]
            logger.debug(f"CognitiveEvolution: top patterns={top_patterns}")

    @property
    def summary(self) -> dict:
        return {
            "tools": dict(sorted(self._state.tools.items(), key=lambda x: -x[1])[:5]),
            "peers": dict(sorted(self._state.peers.items(), key=lambda x: -x[1])[:5]),
            "patterns": dict(sorted(self._state.task_patterns.items(), key=lambda x: -x[1])[:5]),
            "last_updated": self._state.last_updated,
        }


# ── Singletons ──

_density_max: Optional[ContextDensityMaximizer] = None
_topology: Optional[TopologyRouter] = None
_cognitive: Optional[CognitiveEvolution] = None


def get_density_maximizer(max_tokens: int = 8192) -> ContextDensityMaximizer:
    global _density_max
    if _density_max is None:
        _density_max = ContextDensityMaximizer(max_tokens)
    return _density_max


def get_topology_router() -> TopologyRouter:
    global _topology
    if _topology is None:
        _topology = TopologyRouter()
    return _topology


def get_cognitive_evolution() -> CognitiveEvolution:
    global _cognitive
    if _cognitive is None:
        _cognitive = CognitiveEvolution()
    return _cognitive
