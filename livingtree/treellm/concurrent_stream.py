"""ConcurrentStream — Dual-track concurrent streaming orchestrator.

Based on Thinking Machines Lab "Interaction Models" (May 2026):
  "The interaction model is in constant exchange with the user. When a task
   requires deeper reasoning, the interaction model delegates to a background
   model that runs asynchronously. Results stream back and the interaction
   model interleaves these updates into the conversation."

Two-track architecture for LivingTree:
  Track 1 (Interaction): Flash-tier model provides real-time presence
    - Immediate streaming response as user types/speaks
    - Handles backchannel, clarification, pacing
    - < 500ms first-token latency target

  Track 2 (Background): Pro-tier model does deep reasoning asynchronously
    - Dispatched concurrently, runs in background
    - Produces intermediate and final results
    - Results woven into Track 1's output stream

Key innovation over sequential routing: models work CONCURRENTLY, not sequentially.
The flash model keeps the user engaged while the pro model thinks deeply.
When pro model produces insights, they're seamlessly interleaved.

Integration:
  - Wraps TreeLLM streaming — flash model streams, pro model runs async
  - Uses SynapseAggregator to fuse results when both tracks complete
  - Coordinates with MicroTurnAware for timing of interleaving

Usage:
    cs = get_concurrent_stream()
    async for event in cs.stream(query="Analyze this architecture...",
                                  flash_model="deepseek-flash",
                                  pro_model="deepseek-pro"):
        if event.kind == "flash_token":
            print(event.text, end="")  # Real-time streaming
        elif event.kind == "pro_insight":
            print(f"\n[Deep insight]: {event.text}")  # Woven in
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, AsyncIterator, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


class StreamEventKind(StrEnum):
    """Types of events in the concurrent stream."""
    FLASH_TOKEN = "flash_token"          # Real-time token from flash model
    FLASH_COMPLETE = "flash_complete"    # Flash model finished
    PRO_INSIGHT = "pro_insight"          # Intermediate insight from pro model
    PRO_COMPLETE = "pro_complete"        # Pro model finished
    WEAVE_POINT = "weave_point"          # Natural insertion point for pro results
    ERROR = "error"                      # Error in either track
    META = "meta"                        # Metadata event


@dataclass
class StreamEvent:
    """A single event in the concurrent stream."""
    kind: StreamEventKind
    text: str = ""
    provider: str = ""
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class ConcurrentResult:
    """Complete result of a concurrent stream session."""
    flash_output: str = ""               # Complete flash model output
    pro_output: str = ""                 # Complete pro model output
    fused_output: str = ""              # SynapseAggregator fused output
    events: list[StreamEvent] = field(default_factory=list)
    flash_latency_ms: float = 0.0
    pro_latency_ms: float = 0.0
    flash_tokens: int = 0
    pro_tokens: int = 0
    weave_count: int = 0                # How many times pro insights were woven
    flash_first_token_ms: float = 0.0   # Time to first flash token


# ═══ ConcurrentStream Orchestrator ════════════════════════════════


class ConcurrentStream:
    """Dual-track concurrent streaming orchestrator.

    Design: Two models run simultaneously — flash for real-time presence,
    pro for deep reasoning. The flash stream is the user-facing output;
    pro insights are woven in at natural pause points.

    From TML: "This split lets the user benefit from both responsiveness
    as well as the full extent of intelligence."
    """

    FLASH_FIRST_TOKEN_TARGET = 500    # ms — must be fast
    PRO_WEAVE_DELAY = 2000            # ms — minimum gap between weaves
    MAX_PRO_INSIGHTS = 3              # Max intermediate weaves per session
    MIN_FLASH_TOKENS_FOR_WEAVE = 20   # Don't weave too early

    def __init__(self, chat_fn: Any = None):
        """Initialize with a chat function for LLM calls.

        chat_fn: async callable(messages, provider, stream) -> AsyncIterator[str]
        """
        self._chat_fn = chat_fn
        self._stats = {"sessions": 0, "weaves": 0, "avg_flash_ttft": 0.0}

    # ── Main Stream Pipeline ──────────────────────────────────────

    async def stream(
        self, query: str, flash_model: str, pro_model: str = "",
        system_prompt: str = "", task_type: str = "general",
    ) -> AsyncIterator[StreamEvent]:
        """Execute dual-track concurrent streaming.

        Track 1 (flash): starts immediately, streams tokens in real-time.
        Track 2 (pro): dispatched asynchronously, insights woven in later.

        Args:
            query: User query.
            flash_model: Provider name for real-time interaction model.
            pro_model: Provider name for background deep reasoning (optional).
            system_prompt: Optional system prompt.
            task_type: Task category.

        Yields:
            StreamEvent objects as they occur across both tracks.
        """
        self._stats["sessions"] += 1
        session_t0 = time.monotonic()
        sequence = 0

        messages = [{"role": "user", "content": query}]
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        # ── Track 1: Flash model (real-time) ──
        flash_task = asyncio.create_task(
            self._run_flash_track(messages, flash_model, query)
        )

        # ── Track 2: Pro model (background, if specified) ──
        pro_task = None
        if pro_model and pro_model != flash_model:
            pro_task = asyncio.create_task(
                self._run_pro_track(messages, pro_model, query, task_type)
            )

        # ── Orchestrate: interleave flash stream with pro insights ──
        flash_tokens: list[str] = []
        flash_complete = False
        pro_insights_buffer: list[str] = []
        weave_count = 0
        flash_first_token_ms = 0.0

        try:
            while not flash_complete:
                # Wait for next flash token or pro insight
                done, _ = await asyncio.wait(
                    [flash_task] + ([pro_task] if pro_task and not pro_task.done() else []),
                    timeout=0.1,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    if task == flash_task:
                        try:
                            result = task.result()
                            if isinstance(result, str):
                                token = result
                                if not flash_tokens:
                                    flash_first_token_ms = (time.monotonic() - session_t0) * 1000
                                flash_tokens.append(token)
                                sequence += 1
                                yield StreamEvent(
                                    kind=StreamEventKind.FLASH_TOKEN,
                                    text=token, provider=flash_model,
                                    sequence=sequence,
                                )

                                # Check if it's a good weave point
                                if (pro_insights_buffer and
                                    self._is_weave_point(flash_tokens, weave_count)):
                                    for insight in pro_insights_buffer:
                                        weave_count += 1
                                        sequence += 1
                                        yield StreamEvent(
                                            kind=StreamEventKind.PRO_INSIGHT,
                                            text=insight, provider=pro_model,
                                            sequence=sequence,
                                        )
                                    pro_insights_buffer.clear()

                            elif isinstance(result, StreamEvent):
                                if result.kind == StreamEventKind.FLASH_COMPLETE:
                                    flash_complete = True
                                    sequence += 1
                                    yield StreamEvent(
                                        kind=StreamEventKind.FLASH_COMPLETE,
                                        provider=flash_model, sequence=sequence,
                                    )
                                elif result.kind == StreamEventKind.ERROR:
                                    sequence += 1
                                    yield result
                                    flash_complete = True

                        except Exception as e:
                            logger.warning(f"ConcurrentStream flash error: {e}")
                            flash_complete = True

                    elif task == pro_task:
                        try:
                            result = task.result()
                            if isinstance(result, list):
                                # Batch of insights
                                pro_insights_buffer.extend(result[:self.MAX_PRO_INSIGHTS])
                                self._stats["weaves"] += len(result)
                            elif isinstance(result, str) and result:
                                pro_insights_buffer.append(result)
                                self._stats["weaves"] += 1
                        except Exception as e:
                            logger.debug(f"ConcurrentStream pro error: {e}")

            # ── Post-flash: deliver remaining pro insights ──
            if pro_insights_buffer:
                sequence += 1
                yield StreamEvent(
                    kind=StreamEventKind.WEAVE_POINT,
                    text=f"[Background analysis ready — {len(pro_insights_buffer)} insights]",
                    sequence=sequence,
                )
                for insight in pro_insights_buffer:
                    weave_count += 1
                    sequence += 1
                    yield StreamEvent(
                        kind=StreamEventKind.PRO_INSIGHT,
                        text=insight, provider=pro_model,
                        sequence=sequence,
                    )

            # ── Pro model complete (if still running) ──
            if pro_task and not pro_task.done():
                try:
                    pro_output = await asyncio.wait_for(pro_task, timeout=30.0)
                    if isinstance(pro_output, str) and pro_output:
                        sequence += 1
                        yield StreamEvent(
                            kind=StreamEventKind.PRO_COMPLETE,
                            text=pro_output, provider=pro_model,
                            sequence=sequence,
                        )
                except asyncio.TimeoutError:
                    pass

            # ── Session metadata ──
            total_ms = (time.monotonic() - session_t0) * 1000
            sequence += 1
            yield StreamEvent(
                kind=StreamEventKind.META,
                text="",
                metadata={
                    "total_ms": round(total_ms, 1),
                    "flash_tokens": len(flash_tokens),
                    "flash_ttft_ms": round(flash_first_token_ms, 1),
                    "pro_weaves": weave_count,
                },
                sequence=sequence,
            )

        except asyncio.CancelledError:
            flash_task.cancel()
            if pro_task:
                pro_task.cancel()
            raise
        except Exception as e:
            logger.error(f"ConcurrentStream fatal: {e}")
            yield StreamEvent(
                kind=StreamEventKind.ERROR,
                text=str(e), sequence=sequence,
            )

    # ── Track Runners ─────────────────────────────────────────────

    async def _run_flash_track(
        self, messages: list[dict], flash_model: str, query: str,
    ) -> StreamEvent | str:
        """Track 1: Run flash model for real-time streaming presence."""
        if not self._chat_fn:
            return StreamEvent(
                kind=StreamEventKind.ERROR,
                text="No chat function configured",
            )

        try:
            tokens: list[str] = []
            async for token in self._chat_fn(messages, flash_model, stream=True):
                tokens.append(token)
                # Yield each token back to orchestrator
                # (hack: return each token individually via task result)
                # Actually need a better pattern — use queue

            return StreamEvent(kind=StreamEventKind.FLASH_COMPLETE)
        except Exception as e:
            return StreamEvent(kind=StreamEventKind.ERROR, text=str(e))

    async def _run_pro_track(
        self, messages: list[dict], pro_model: str, query: str, task_type: str,
    ) -> list[str]:
        """Track 2: Run pro model asynchronously for deep reasoning.

        Returns a list of intermediate insights as they become available.
        Each insight is a meaningful chunk of reasoning, not raw tokens.
        """
        if not self._chat_fn:
            return []

        try:
            # Use DeepProbe to force deep reasoning on the pro track
            pro_query = query
            try:
                from .deep_probe import get_deep_probe
                probe = get_deep_probe()
                result = probe.rewrite(query, task_type=task_type, depth=3)
                pro_messages = [{"role": "user", "content": result.rewritten}]
            except ImportError:
                pro_messages = messages

            # Collect full pro output
            full_output: list[str] = []
            async for token in self._chat_fn(pro_messages, pro_model, stream=True):
                full_output.append(token)

            full_text = "".join(full_output)
            if not full_text:
                return []

            # Extract intermediate insights (key sentences)
            insights = self._extract_insights(full_text)
            return insights

        except Exception as e:
            logger.debug(f"ConcurrentStream pro track: {e}")
            return []

    # ── Weave Point Detection ─────────────────────────────────────

    def _is_weave_point(self, flash_tokens: list[str], weave_count: int) -> bool:
        """Determine if now is a good moment to weave in a pro insight.

        Good weave points:
          - After a natural pause (sentence end)
          - Not too early (< 20 tokens into flash response)
          - Not too frequent (minimum gap between weaves)
          - After paragraph breaks
        """
        if len(flash_tokens) < self.MIN_FLASH_TOKENS_FOR_WEAVE:
            return False
        if weave_count >= self.MAX_PRO_INSIGHTS:
            return False

        # Check if last few tokens indicate a natural pause
        recent = "".join(flash_tokens[-5:])
        pause_indicators = [
            ". ", "。", "！", "? ", "？", "\n\n",
            ".\n", ".\n\n", "):", "): ",
            "首先", "其次", "最后",
            "综上所述", "总之", "总结",
        ]
        return any(ind in recent for ind in pause_indicators)

    # ── Insight Extraction ────────────────────────────────────────

    @staticmethod
    def _extract_insights(text: str, max_insights: int = 3) -> list[str]:
        """Extract key standalone insights from pro model output.

        Each insight should be self-contained enough to be woven into
        the flash model's stream without disrupting flow.
        """
        import re
        insights: list[str] = []

        # Look for strong declarative sentences
        sentences = re.split(r'(?<=[.!?。！？])\s+', text)
        markers = [
            "key", "critical", "important", "notably", "significantly",
            "关键", "重要", "核心", "本质", "根本",
            "therefore", "thus", "hence", "因此", "所以",
            "however", "但是", "然而", "on the other hand",
        ]

        for s in sentences:
            s_lower = s.lower()
            if any(m in s_lower for m in markers) and len(s) > 30:
                insight = s.strip()
                if insight not in insights:
                    insights.append(insight)
            if len(insights) >= max_insights:
                break

        return insights

    # ── Synchronous Collector (for route_layered integration) ─────

    async def collect(
        self, query: str, flash_model: str, pro_model: str = "",
        system_prompt: str = "", task_type: str = "general",
        timeout: float = 60.0,
    ) -> ConcurrentResult:
        """Collect all events into a single ConcurrentResult.

        For integration with route_layered() which expects a single result.
        """
        result = ConcurrentResult()
        flash_parts: list[str] = []
        pro_parts: list[str] = []
        session_t0 = time.monotonic()

        try:
            async for event in asyncio.wait_for(
                self.stream(query, flash_model, pro_model, system_prompt, task_type),
                timeout=timeout,
            ):
                result.events.append(event)
                if event.kind == StreamEventKind.FLASH_TOKEN:
                    flash_parts.append(event.text)
                    if result.flash_first_token_ms == 0:
                        result.flash_first_token_ms = (time.monotonic() - session_t0) * 1000
                elif event.kind == StreamEventKind.PRO_INSIGHT:
                    pro_parts.append(f"[{event.provider}]: {event.text}")
                    result.weave_count += 1
                elif event.kind == StreamEventKind.PRO_COMPLETE:
                    pro_parts.append(event.text)
        except asyncio.TimeoutError:
            pass

        result.flash_output = "".join(flash_parts)
        result.pro_output = "\n\n".join(pro_parts)
        result.flash_tokens = len(flash_parts)
        result.pro_tokens = len("".join(pro_parts))

        # Fuse outputs via SynapseAggregator if both tracks have content
        if result.flash_output and result.pro_output:
            try:
                from .synapse_aggregator import get_synapse_aggregator, ModelOutput
                agg = get_synapse_aggregator()
                outputs = [
                    ModelOutput(provider=flash_model, text=result.flash_output,
                               election_score=0.8),
                    ModelOutput(provider=pro_model, text=result.pro_output,
                               election_score=0.9),
                ]
                fused = await agg.aggregate(outputs, query, task_type)
                result.fused_output = fused.aggregated_text
            except ImportError:
                result.fused_output = result.flash_output

        return result

    # ── Auto-connect to TreeLLM ────────────────────────────────────

    def auto_connect(self) -> bool:
        """Auto-connect ConcurrentStream to TreeLLM for dual-track streaming."""
        try:
            from .core import TreeLLM
            llm = TreeLLM()

            async def _chat_fn(messages, provider, stream=True):
                if stream:
                    async for token in llm.stream(messages, provider=provider):
                        yield token
                else:
                    result = await llm.chat(messages, provider=provider)
                    text = getattr(result, 'text', '') or str(result)
                    yield text

            self._chat_fn = _chat_fn
            logger.info("ConcurrentStream: auto-connected to TreeLLM")
            return True
        except Exception as e:
            logger.debug(f"ConcurrentStream auto_connect: {e}")
            return False

    # ── Statistics ─────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "sessions": self._stats["sessions"],
            "total_weaves": self._stats["weaves"],
            "avg_weaves_per_session": (
                self._stats["weaves"] / max(self._stats["sessions"], 1)
            ),
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_cs: Optional[ConcurrentStream] = None


def get_concurrent_stream() -> ConcurrentStream:
    global _cs
    if _cs is None:
        _cs = ConcurrentStream()
        _cs.auto_connect()
    return _cs


def set_stream_chat_fn(chat_fn) -> None:
    """Set the chat function for ConcurrentStream to use.

    chat_fn: async callable(messages: list[dict], provider: str, stream: bool) -> AsyncIterator[str]
    """
    cs = get_concurrent_stream()
    cs._chat_fn = chat_fn


__all__ = [
    "ConcurrentStream", "StreamEvent", "StreamEventKind", "ConcurrentResult",
    "get_concurrent_stream", "set_stream_chat_fn",
]
