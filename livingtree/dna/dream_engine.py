"""Dream Engine — adversarial memory recombination during low-load periods.

Inspired by hippocampal replay + GAN-style remixing.
During idle cycles, the system randomly recombines stored memories
and tests whether new hypergraph connections are logically coherent.

Three-stage dream cycle:
  REPLAY  — randomly activate mature synapses and associated hyperedges
  REMIX   — attempt to form new hyperedges between unrelated memories
  VERIFY  — use PrecedenceModel to check if new connections make sense
  WAKE    — valid connections are promoted; invalid ones are discarded

This mimics the biological function of sleep:
  - Memory consolidation (hippocampal replay)
  - Creative recombination (default mode network)
  - Synaptic pruning (eliminating weak connections)
"""

from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class DreamConnection:
    """A candidate connection discovered during dreaming."""
    entity_a: str
    entity_b: str
    proposed_relation: str           # "might_be_related_to"
    coherence_score: float           # How logically sound this connection is
    accepted: bool = False           # Promoted after wake verification
    source_memories: list[str] = field(default_factory=list)


@dataclass
class DreamReport:
    """Result of one dream cycle."""
    cycle_id: int
    memories_replayed: int
    connections_attempted: int
    connections_accepted: int
    creative_insights: list[str]
    pruned_connections: int
    duration_ms: float


class DreamEngine:
    """Adversarial memory recombination during low-load periods.

    Triggered by the homeostatic daemon when:
      - System is idle (no user tasks for > 5 min)
      - Silent synapse ratio > 0.25 (room to grow)
      - Active > mature synapses (need consolidation)
    """

    MAX_CONNECTIONS_PER_DREAM = 20

    def __init__(self, modules: dict[str, Any] | None = None):
        self._modules = modules or {}
        self._history: deque[DreamReport] = deque(maxlen=50)
        self._dream_count = 0

    def should_dream(self) -> bool:
        """Check if conditions are right for dreaming."""
        sp = self._modules.get("synaptic_plasticity")
        if not sp:
            return False
        sr = sp.silent_ratio()
        return sr > 0.2  # Enough room for new connections

    async def dream(self) -> DreamReport | None:
        """Execute one dream cycle: replay → remix → verify → wake."""
        t0 = time.time()
        self._dream_count += 1
        sp = self._modules.get("synaptic_plasticity")
        hg = self._modules.get("hypergraph_store")
        pm = self._modules.get("precedence_model")

        if not hg or len(hg._entities) < 5:
            return None

        # ═══ REPLAY: sample mature synapses ═══
        mature_sids = [
            sid for sid, m in sp._synapses.items()
            if m.state.value == "mature" and m.weight > 0.5
        ] if sp else []
        entities = list(hg._entities.keys())

        if len(entities) < 3:
            return None

        # ═══ REMIX: try to form new connections ═══
        new_connections: list[DreamConnection] = []
        attempts = min(self.MAX_CONNECTIONS_PER_DREAM, len(entities) * 2)

        for _ in range(attempts):
            a, b = random.sample(entities, 2)
            if a == b:
                continue
            # Check if connection already exists
            existing = hg.get_precedence_chain(a, direction="both", max_depth=1)
            if existing:
                continue
            # Check coherence via PrecedenceModel
            coherence = self._assess_coherence(a, b, hg, pm)
            if coherence > 0.3:
                new_connections.append(DreamConnection(
                    entity_a=a, entity_b=b,
                    proposed_relation="dreamed_connection",
                    coherence_score=coherence,
                    source_memories=[sid for sid in mature_sids[:3] if a in sid or b in sid],
                ))

        # ═══ VERIFY: check coherence ═══
        accepted = 0
        insights = []
        for conn in new_connections:
            if conn.coherence_score > 0.5:
                try:
                    label_a = hg._entities.get(conn.entity_a)
                    label_b = hg._entities.get(conn.entity_b)
                    la = label_a.label if label_a else conn.entity_a
                    lb = label_b.label if label_b else conn.entity_b
                    from .hypergraph_store import Hyperedge
                    hg.add_hyperedge(Hyperedge(
                        entities=[conn.entity_a, conn.entity_b],
                        relation="dreamed_connection",
                        weight=conn.coherence_score * 0.3,  # Start weak
                        properties={"dream_cycle": self._dream_count},
                    ))
                    conn.accepted = True
                    accepted += 1
                    insights.append(f"梦见 {la[:20]} 可能与 {lb[:20]} 有关 (置信度 {conn.coherence_score:.2f})")
                except Exception:
                    pass

        # ═══ WAKE: prune very weak connections ═══
        pruned = 0
        if sp:
            pruned = sp.decay_all()

        report = DreamReport(
            cycle_id=self._dream_count,
            memories_replayed=len(mature_sids),
            connections_attempted=attempts,
            connections_accepted=accepted,
            creative_insights=insights[:5],
            pruned_connections=pruned,
            duration_ms=(time.time() - t0) * 1000,
        )
        self._history.append(report)

        if accepted > 0:
            logger.info(f"🌙 梦境#{self._dream_count}: {accepted} 个新连接, {pruned} 个修剪")
        return report

    @staticmethod
    def _assess_coherence(a: str, b: str, hg, pm) -> float:
        """How logically coherent is a connection between a and b?"""
        if not pm:
            return 0.3  # Neutral without model

        # Get entity labels as "type" proxies
        label_a = hg._entities.get(a).label if a in hg._entities else a
        label_b = hg._entities.get(b).label if b in hg._entities else b

        # Check transition probability between their "types"
        prob = pm.transition_prob(label_a[:20], label_b[:20])

        # Semantic distance bonus: closer = more likely related
        try:
            from .gravity_model import KnowledgeGravity
            gm = KnowledgeGravity(hg)
            dist = gm._semantic_distance(label_a, label_b)
            semantic_bonus = 1.0 - dist
        except Exception:
            semantic_bonus = 0.5

        return max(0.0, min(1.0, prob * 0.6 + semantic_bonus * 0.4))

    def stats(self) -> dict:
        return {
            "dreams_completed": self._dream_count,
            "total_connections_accepted": sum(
                r.connections_accepted for r in self._history),
            "total_connections_pruned": sum(
                r.pruned_connections for r in self._history),
        }


# ═══ Singleton ═══

_dreamer: DreamEngine | None = None


def get_dream_engine(modules=None) -> DreamEngine:
    global _dreamer
    if _dreamer is None:
        _dreamer = DreamEngine(modules)
    return _dreamer


__all__ = ["DreamEngine", "DreamReport", "DreamConnection", "get_dream_engine"]
