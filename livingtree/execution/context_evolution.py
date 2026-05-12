"""Context Density Maximizer + Adaptive Topology Router + Cognitive Evolution.

Combines insights from three papers (all implemented as mixins/integrations):
  - GenericAgent (2604.17091): context information density maximization
  - AdaptOrch (2602.16873): task DAG → topology routing O(|V|+|E|)
  - AutoAgent (2603.09716): cognitive evolution + elastic memory

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


@dataclass
class ContextSlice:
    """A managed slice of the context window."""
    content: str
    tokens: int
    importance: float        # 0 (disposable) to 1 (critical)
    age: int = 0              # Turns since creation
    strategy: DensityStrategy = DensityStrategy.COMPRESS


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
        """Add a context slice, auto-managing token budget."""
        tokens = len(content) // 3
        sl = ContextSlice(content=content, tokens=tokens, importance=importance)
        self._slices.append(sl)
        self._total_tokens += tokens
        self._enforce_budget()

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
