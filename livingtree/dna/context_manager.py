"""ContextManager — unified context strategy coordinator.

Auto-selects the best context mode by task complexity:
  - Low complexity (< 0.3): simple text context (cheap, O(1))
  - Medium complexity (0.3–0.6): ContextWiki structured pages (on-demand)
  - High complexity (> 0.6): VectorContext compressed embedding (dense)

Coordinates FoldAgent, ContextWiki, and VectorContext into a single
decision point so downstream callers don't need to know which strategy is active.

Integration:
    cm = get_context_manager()
    context_text = await cm.build_context(ctx, complexity=0.55, max_chars=500)
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger


class ContextManager:
    """Unified context strategy — auto-selects best mode by task complexity.

    Lazy-loads ContextWiki and VectorPipeline singletons so that:
      - Simple tasks pay zero overhead for wiki/vector subsystems
      - Complex tasks get the full power of structured or dense context

    Usage:
        cm = get_context_manager()
        text = await cm.build_context(ctx, task_complexity=ctx.metadata.get("complexity", 0.5), max_chars=500)
    """

    def __init__(self) -> None:
        self._wiki = None       # lazy — ContextWiki singleton
        self._vector = None     # lazy — VectorPipeline singleton
        self._bridge = None     # lazy — VectorBridge singleton
        self._vctx = None       # lazy — VectorContext instance
        self._call_count: int = 0
        self._mode_counts: dict[str, int] = {"simple": 0, "wiki": 0, "vector": 0}

    # ── Build context ──────────────────────────────────────────────

    async def build_context(
        self, ctx: Any, task_complexity: float, max_chars: int = 500
    ) -> str:
        """Select and build the best context representation for the current task.

        Args:
            ctx: LifeContext instance (has .intent, .metadata, etc.)
            task_complexity: 0.0–1.0 complexity score.
            max_chars: Target maximum character count for output.

        Returns:
            A text string representing the current context, ready for LLM prompt injection.
        """
        self._call_count += 1
        if task_complexity < 0.3:
            self._mode_counts["simple"] += 1
            return self._simple_context(ctx)
        elif task_complexity < 0.6:
            self._mode_counts["wiki"] += 1
            return self._wiki_context(ctx, max_chars)
        else:
            self._mode_counts["vector"] += 1
            return self._vector_context(ctx, max_chars)

    # ── Mode implementations ───────────────────────────────────────

    def _simple_context(self, ctx: Any) -> str:
        """Bare-minimum context: just the user intent, truncated to 300 chars."""
        raw = ""
        if hasattr(ctx, "intent") and ctx.intent:
            raw = str(ctx.intent)
        elif hasattr(ctx, "user_input") and ctx.user_input:
            raw = str(ctx.user_input)
        return raw[:300]

    def _wiki_context(self, ctx: Any, max_chars: int) -> str:
        """Structured wiki pages: on-demand retrieval of relevant topic pages.

        Uses ContextWiki's build_context() which searches for the most relevant
        wiki pages and assembles them into a prompt-ready block.
        """
        try:
            from ..knowledge.context_wiki import get_context_wiki
            wiki = get_context_wiki()
            return wiki.build_context(max_chars=max_chars)
        except Exception as e:
            logger.debug(f"ContextManager wiki fallback: {e}")
            return self._simple_context(ctx)

    def _vector_context(self, ctx: Any, max_chars: int) -> str:
        """Dense embedding: compress the shared 768-dim vector into a text summary.

        Uses VectorPipeline.compress_to_text() which extracts the dominant
        semantic dimensions, stage weight proportions, and trending direction
        from the accumulated VectorContext.
        """
        try:
            from .vector_context import get_vector_pipeline, get_vector_bridge
            pipeline = get_vector_pipeline()
            if self._vctx is None:
                bridge = get_vector_bridge()
                ui = getattr(ctx, "user_input", "") or getattr(ctx, "intent", "") or ""
                self._vctx = bridge.text_to_vector(ui)
            return pipeline.compress_to_text(self._vctx, max_chars)
        except Exception as e:
            logger.debug(f"ContextManager vector fallback: {e}")
            return self._wiki_context(ctx, max_chars)

    # ── Update vector (called by LifeEngine after each stage) ──────

    def update_vector(self, stage_name: str, stage_text: str) -> float:
        """Update the internal VectorContext with a stage's output.

        Returns the magnitude of the delta (how much information was added).
        """
        try:
            from .vector_context import get_vector_bridge, get_stage_vectorizer
            bridge = get_vector_bridge()
            vectorizer = get_stage_vectorizer()
            if self._vctx is None:
                self._vctx = bridge.text_to_vector(stage_text)
                return 1.0
            delta = vectorizer.vectorize_stage_output(
                stage_name, stage_text, self._vctx.vector
            )
            return self._vctx.update(stage_name, delta)
        except Exception as e:
            logger.debug(f"ContextManager update_vector: {e}")
            return 0.0

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return usage statistics for monitoring."""
        base = {
            "call_count": self._call_count,
            "mode_distribution": dict(self._mode_counts),
        }
        if self._vctx is not None:
            base["vector_stages"] = len(self._vctx.updates)
            base["vector_magnitude"] = getattr(self._vctx, "magnitude", lambda: sum(abs(v) for v in self._vctx.vector))() if hasattr(self._vctx, "vector") else 0.0
        return base

    def set_active_vctx(self, vctx) -> None:
        """Bind an existing VectorContext (from LifeEngine._vctx)."""
        self._vctx = vctx


# ═══ Singleton ═══

_manager: ContextManager | None = None


def get_context_manager() -> ContextManager:
    """Get or create the global ContextManager singleton."""
    global _manager
    if _manager is None:
        _manager = ContextManager()
        logger.info("ContextManager singleton initialized")
    return _manager


__all__ = [
    "ContextManager",
    "get_context_manager",
]
