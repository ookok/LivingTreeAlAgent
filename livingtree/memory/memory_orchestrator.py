"""MemoryOrchestrator — unified memory processing pipeline.

Coordinates five memory subsystems into a single orchestrated pipeline:
  1. SurpriseGate (CriticRouter RPE) — decides whether to trigger memory evolution
  2. MemPO (Memory Policy Optimizer) — credit assignment + retention optimization
  3. EmotionalMemory — stores content with emotional context weighting
  4. FadeMem — memory decay (integrated via EmotionalMemory.decay_all)
  5. StructMem — struct_mem binding (delegated to LifeEngine hook)

The orchestrator replaces ad-hoc memory calls scattered across LifeEngine
with a single `process_memory()` call that runs the full pipeline.

Core flow (D-MEM inspired, Song & Xin 2026):
    Input → CriticRouter(RPE) →
      ├─ Low RPE → fast buffer (skip evolution)
      └─ High RPE → dopamine signal → MemPO evolution + Emotional store

Integration:
    mo = get_memory_orchestrator()
    result = await mo.process_memory(content, task_id, success_rate, ctx)
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger


class MemoryOrchestrator:
    """Unified memory orchestrator — surprise-gated memory evolution pipeline.

    Exists to centralize memory orchestration so callers (LifeEngine, interactive
    loops, batch processors) don't need to individually chain surprise gating →
    MemPO → emotional → struct mem. The orchestrator owns the routing decision
    and delegates to each subsystem.

    Usage:
        mo = get_memory_orchestrator()
        await mo.process_memory(content="task summary", task_id="sess_123",
                                success_rate=0.85, ctx=life_ctx)
    """

    def __init__(self) -> None:
        self._mempo = None       # lazy — MemPOOptimizer singleton
        self._surprise = None    # lazy — SurpriseGatedMemory singleton
        self._emotional = None   # lazy — EmotionalMemoryStore singleton
        self._total_processed: int = 0
        self._total_evolved: int = 0
        self._last_process_time: float = 0.0

    # ── Process memory ─────────────────────────────────────────────

    async def process_memory(
        self,
        content: str,
        task_id: str,
        success_rate: float,
        ctx: Any = None,
    ) -> dict:
        """Run the full memory processing pipeline.

        Args:
            content: The memory content to store.
            task_id: Unique identifier for this task/cycle.
            success_rate: 0.0–1.0 success rate for credit assignment.
            ctx: Optional LifeContext for additional metadata.

        Returns:
            {"processed": True, "evolved": bool, "emotional_stored": bool}
        """
        self._total_processed += 1
        self._last_process_time = time.time()
        result: dict = {"processed": True, "evolved": False, "emotional_stored": False}

        # 1. ── Surprise gate decides routing ──
        evolved = False
        try:
            from ..dna.surprise_gating import get_surprise_gate
            sg = get_surprise_gate()
            context = {"task_id": task_id}
            if ctx is not None and hasattr(ctx, "metadata"):
                context["complexity"] = ctx.metadata.get("complexity", 0.5)
            signal = sg._critic.evaluate(content, context)
            evolved = signal.should_evolve
        except Exception as e:
            logger.debug(f"MemoryOrchestrator surprise gate skipped: {e}")

        # 2. ── If surprising, trigger MemPO memory evolution ──
        if evolved:
            try:
                from .memory_policy import get_mempo_optimizer
                mempo = get_mempo_optimizer()
                mempo.add_memory(content, source="cycle", session=task_id)
                mempo.log_access(f"mem_{mempo._next_id - 1}", task_id)
                if success_rate >= 0.5:
                    mempo.on_task_complete(
                        task_id,
                        success=min(success_rate, 1.0),
                        task_output=content,
                    )
                else:
                    mempo.on_task_fail(task_id)
                mempo.optimize()
                self._total_evolved += 1
                result["evolved"] = True
            except Exception as e:
                logger.debug(f"MemoryOrchestrator MemPO skipped: {e}")

        # 3. ── Store emotional context ──
        try:
            from .emotional_memory import get_emotional_memory
            em = get_emotional_memory()
            em.store(content, {"source": "cycle", "task_id": task_id})
            result["emotional_stored"] = True
        except Exception as e:
            logger.debug(f"MemoryOrchestrator emotional store skipped: {e}")

        return result

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return orchestrator statistics for monitoring."""
        base = {
            "orchestrator": "active",
            "total_processed": self._total_processed,
            "total_evolved": self._total_evolved,
            "evolution_rate": (
                self._total_evolved / max(self._total_processed, 1)
            ),
        }
        try:
            from .memory_policy import get_mempo_optimizer
            mempo = get_mempo_optimizer()
            base["mempo"] = mempo.get_stats()
        except Exception:
            pass
        return base

    # ── PersonaVLM force-retrieve ───────────────────────────────────

    def force_retrieve_context(self, user_id: str = "", query: str = "") -> str:
        """PersonaVLM: bypass SurpriseGate and retrieve all user memory types.

        Used when RetrievalUrgency exceeds threshold (context shift, high
        complexity, topic novelty). Forces retrieval of: Core Identity,
        Episodic, Semantic, and Procedural memories from PersonaMemory
        and EmotionalMemory subsystems.

        Args:
            user_id: User identifier ("" for current session user)
            query: Current query to filter relevant memories

        Returns:
            Context string with all relevant user memories, prioritized
        """
        parts: list[str] = []
        priority_order = ["core_identity", "semantic", "episodic", "procedural"]

        try:
            from .persona_memory import get_persona_memory
            pm = get_persona_memory()
            for mem_type in priority_order:
                facts = pm._storage.get(mem_type, [])
                if not facts:
                    continue
                if query:
                    scored = [(self._score_persona_fact(f, query), f) for f in facts]
                    scored.sort(key=lambda x: x[0], reverse=True)
                    relevant = [f for s, f in scored[:5] if s > 0.1]
                else:
                    relevant = facts[:3]
                if relevant:
                    label = mem_type.replace("_", " ").title()
                    parts.append(f"[{label}]")
                    for f in relevant:
                        text = f.get("fact", "")
                        if isinstance(f, str):
                            text = str(f)
                        parts.append(f"- {text[:300]}")
                    parts.append("")
        except Exception as e:
            logger.debug(f"force_retrieve_context persona skip: {e}")

        try:
            from .emotional_memory import get_emotional_memory
            em = get_emotional_memory()
            episodes = em.get_all_flashbulbs()
            if episodes:
                parts.append("[Episodic Flashbulbs]")
                for ep in episodes[:5]:
                    parts.append(f"- {str(ep)[:200]}")
                parts.append("")
        except Exception as e:
            logger.debug(f"force_retrieve_context emotion skip: {e}")

        return "\n".join(parts) if parts else ""

    def _score_persona_fact(self, fact, query: str) -> float:
        if isinstance(fact, dict):
            text = str(fact.get("fact", str(fact))).lower()
        else:
            text = str(fact).lower()
        ql = query.lower()
        words = [w for w in ql.split() if len(w) > 1] or [ql]
        hits = sum(1 for w in words if w in text)
        return hits / max(len(words), 1)


# ═══ Singleton ═══

_orchestrator: MemoryOrchestrator | None = None


def get_memory_orchestrator() -> MemoryOrchestrator:
    """Get or create the global MemoryOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MemoryOrchestrator()
        logger.info("MemoryOrchestrator singleton initialized")
    return _orchestrator


__all__ = [
    "MemoryOrchestrator",
    "get_memory_orchestrator",
]
