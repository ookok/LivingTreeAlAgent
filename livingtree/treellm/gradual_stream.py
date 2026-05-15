"""GradualStream — Three-phase progressive disclosure streaming.

Phase 1 (<500ms): One-sentence summary + direction hint
Phase 2 (1-3s):   Core conclusions (2-3 key findings, ~150 tokens)
Phase 3 (remainder): Full detailed answer via pro model

Users get immediate value (summary at 500ms) instead of waiting for complete output.

Integration:
    gs = get_gradual_stream()
    async for event in gs.stream(query, flash_model, pro_model, llm):
        yield format_sse(event)
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, AsyncIterator, Optional

from loguru import logger


class GradualPhase(StrEnum):
    SUMMARY = "summary"
    CORE = "core"
    DETAIL = "detail"
    DONE = "done"
    ERROR = "error"


@dataclass
class GradualEvent:
    phase: GradualPhase
    text: str
    timestamp: float = 0.0
    metadata: dict = None

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if self.metadata is None:
            self.metadata = {}


class GradualStream:
    """Three-phase progressive disclosure streaming."""

    _instance: Optional["GradualStream"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "GradualStream":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = GradualStream()
        return cls._instance

    def __init__(self):
        self._sessions = 0
        self.PHASE2_TOKEN_CAP = 150
        self.SUMMARY_TARGET_MS = 500

    async def stream(
        self, query: str, flash_model: str, pro_model: str = "",
        llm: Any = None, chat_fn: Any = None,
    ) -> AsyncIterator[GradualEvent]:
        """Execute three-phase progressive streaming.

        Args:
            query: User query.
            flash_model: Fast model for summary + core phases.
            pro_model: Deep model for detail phase (optional).
            llm: TreeLLM instance for chat/stream methods.
            chat_fn: Alternative chat function.
        """
        self._sessions += 1
        t0 = time.monotonic()
        chat = chat_fn or (lambda m, p, **kw: llm.chat(m, provider=p, **kw))
        stream_fn = chat_fn or (lambda m, p: llm.stream(m, provider=p))

        # ── Phase 1: Instant summary (<500ms target) ──
        yield GradualEvent(phase=GradualPhase.SUMMARY, text="", metadata={"status": "analyzing"})
        try:
            summary_result = await chat(
                [{"role": "user", "content": f"用一句话概括回答:{query[:300]}"}],
                flash_model, max_tokens=60, temperature=0.3,
            )
            summary_text = getattr(summary_result, 'text', '') or str(summary_result)
            if summary_text:
                elapsed = (time.monotonic() - t0) * 1000
                yield GradualEvent(
                    phase=GradualPhase.SUMMARY,
                    text=summary_text.strip() + "\n\n",
                    metadata={"elapsed_ms": round(elapsed, 0)},
                )
        except Exception as e:
            logger.debug(f"GradualStream phase1: {e}")

        # ── Phase 2: Core conclusions (~150 tokens) ──
        yield GradualEvent(phase=GradualPhase.CORE, text="", metadata={"status": "conclusions"})
        core_tokens = 0
        try:
            async for token in stream_fn(
                [{"role": "user", "content": query}], flash_model,
            ):
                if not token:
                    continue
                core_tokens += 1
                yield GradualEvent(phase=GradualPhase.CORE, text=token)
                if core_tokens >= self.PHASE2_TOKEN_CAP:
                    yield GradualEvent(
                        phase=GradualPhase.CORE,
                        text="\n\n---\n",
                        metadata={"truncated": True},
                    )
                    break
        except Exception as e:
            logger.debug(f"GradualStream phase2: {e}")

        # ── Phase 3: Full detail via pro model ──
        pro_model_name = pro_model if pro_model and pro_model != flash_model else flash_model
        yield GradualEvent(phase=GradualPhase.DETAIL, text="", metadata={"status": "detail"})
        try:
            async for token in stream_fn(
                [{"role": "user", "content": query}], pro_model_name,
            ):
                if token:
                    yield GradualEvent(phase=GradualPhase.DETAIL, text=token)
        except Exception as e:
            logger.debug(f"GradualStream phase3: {e}")

        total_ms = (time.monotonic() - t0) * 1000
        yield GradualEvent(
            phase=GradualPhase.DONE, text="",
            metadata={"total_ms": round(total_ms, 0), "core_tokens": core_tokens},
        )

    def stats(self) -> dict:
        return {"sessions": self._sessions}


_gradual: Optional[GradualStream] = None
_gradual_lock = threading.Lock()


def get_gradual_stream() -> GradualStream:
    global _gradual
    if _gradual is None:
        with _gradual_lock:
            if _gradual is None:
                _gradual = GradualStream()
    return _gradual


__all__ = ["GradualStream", "GradualEvent", "GradualPhase", "get_gradual_stream"]
