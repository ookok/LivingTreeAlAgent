"""Distributed request tracing with span management and layered evidence distillation."""
from __future__ import annotations

import re
import time
import uuid
from contextlib import asynccontextmanager
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterator, Optional

from loguru import logger
from pydantic import BaseModel, Field

from .logger import LogContext


# ── Distilled Evidence (Agentic Harness: layered trajectory distillation) ──

class EvidenceLayer:
    """Layer name constants for distilled evidence."""
    RAW = "raw"
    STRUCTURED = "structured"
    INSIGHT = "insight"
    ACTION = "action"


@dataclass
class DistilledEvidence:
    """One piece of distilled evidence from trace spans.

    AHE paper concept: raw trace spans → structured evidence corpus → actionable insights.
    Four layers:
      - raw: verbatim span content
      - structured: key facts extracted (errors, latencies, tool calls)
      - insight: patterns and anomalies detected
      - action: concrete recommendations
    """
    layer: str
    summary: str
    evidence_type: str  # e.g. "error", "latency_anomaly", "tool_call", "cost_spike"
    source_span_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)


class TraceSpan(BaseModel):
    """A single trace span representing a unit of work."""
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    parent_span_id: Optional[str] = None
    name: str
    service: str = "livingtree"
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    status: str = "ok"
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)

    def finish(self, status: str = "ok") -> None:
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status

    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })


class RequestTracer:
    """Manages distributed tracing across async and sync boundaries."""

    def __init__(self, sample_rate: float = 0.1, enabled: bool = True):
        self.sample_rate = sample_rate
        self.enabled = enabled
        self._active_spans: dict[str, list[TraceSpan]] = {}
        self._completed_spans: list[TraceSpan] = []
        self._max_completed = 10000
        self._generations: list[GenerationSpan] = []

    def should_sample(self) -> bool:
        import random
        return random.random() < self.sample_rate

    def start_span(self, name: str, parent: Optional[TraceSpan] = None,
                   attributes: Optional[dict] = None) -> TraceSpan:
        span = TraceSpan(
            name=name,
            parent_span_id=parent.span_id if parent else None,
            trace_id=parent.trace_id if parent and parent.trace_id else uuid.uuid4().hex[:16],
            attributes=attributes or {},
        )
        if not span.trace_id:
            span.trace_id = uuid.uuid4().hex[:16]
        LogContext.set_trace(span.trace_id)
        self._active_spans.setdefault(span.trace_id, []).append(span)
        logger.debug(f"Span started: {name} (trace={span.trace_id[:8]})")
        return span

    def end_span(self, span: TraceSpan, status: str = "ok") -> None:
        span.finish(status)
        self._completed_spans.append(span)
        if len(self._completed_spans) > self._max_completed:
            self._completed_spans = self._completed_spans[-self._max_completed:]
        if span.trace_id in self._active_spans:
            self._active_spans[span.trace_id] = [
                s for s in self._active_spans[span.trace_id] if s.span_id != span.span_id
            ]
        logger.debug(f"Span ended: {span.name} ({span.duration_ms:.1f}ms)")

    @contextmanager
    def span(self, name: str, attributes: Optional[dict] = None) -> Iterator[TraceSpan]:
        if not self.enabled or not self.should_sample():
            yield TraceSpan(name=name)
            return
        s = self.start_span(name, attributes=attributes)
        try:
            yield s
        except Exception as e:
            s.add_event("exception", {"error": str(e)})
            self.end_span(s, "error")
            raise
        else:
            self.end_span(s, "ok")

    @asynccontextmanager
    async def async_span(self, name: str, attributes: Optional[dict] = None) -> AsyncIterator[TraceSpan]:
        if not self.enabled or not self.should_sample():
            yield TraceSpan(name=name)
            return
        s = self.start_span(name, attributes=attributes)
        try:
            yield s
        except Exception as e:
            s.add_event("exception", {"error": str(e)})
            self.end_span(s, "error")
            raise
        else:
            self.end_span(s, "ok")

    def start_generation(self, name: str, model: str = "", provider: str = "",
                         prompt_tokens: int = 0, completion_tokens: int = 0,
                         parent: Optional[TraceSpan] = None,
                         model_parameters: Optional[dict] = None) -> GenerationSpan:
        gen = GenerationSpan(
            name=name, model=model, provider=provider,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            parent_span_id=parent.span_id if parent else None,
            model_parameters=model_parameters or {},
        )
        gen.cost_yuan = calculate_cost(model, prompt_tokens, completion_tokens)
        logger.debug(f"Generation started: {name} (model={model}, tokens={prompt_tokens}+{completion_tokens})")
        return gen

    def end_generation(self, gen: GenerationSpan, output_text: str = "",
                       completion_tokens: Optional[int] = None, status: str = "ok") -> None:
        gen.output_text = output_text[:500]
        if completion_tokens is not None:
            gen.completion_tokens = completion_tokens
        gen.total_tokens = gen.prompt_tokens + gen.completion_tokens
        gen.finish(status)
        if not gen.cost_yuan:
            gen.cost_yuan = calculate_cost(gen.model, gen.prompt_tokens, gen.completion_tokens)
        self._generations.append(gen)
        logger.debug(f"Generation ended: {gen.name} ({gen.duration_ms:.0f}ms, {gen.total_tokens}t, ¥{gen.cost_yuan:.4f})")

    @contextmanager
    def generation(self, name: str, model: str = "", provider: str = "",
                   prompt_tokens: int = 0, **kwargs) -> Iterator[GenerationSpan]:
        if not self.enabled:
            yield GenerationSpan(name=name)
            return
        g = self.start_generation(name, model=model, provider=provider,
                                   prompt_tokens=prompt_tokens, **kwargs)
        try:
            yield g
        except Exception as e:
            self.end_generation(g, output_text=str(e)[:500], status="error")
            raise
        else:
            self.end_generation(g, output_text=g.output_text, status="ok")

    @asynccontextmanager
    async def async_generation(self, name: str, model: str = "", provider: str = "",
                               prompt_tokens: int = 0, **kwargs) -> AsyncIterator[GenerationSpan]:
        if not self.enabled:
            yield GenerationSpan(name=name)
            return
        g = self.start_generation(name, model=model, provider=provider,
                                   prompt_tokens=prompt_tokens, **kwargs)
        try:
            yield g
        except Exception as e:
            self.end_generation(g, output_text=str(e)[:500], status="error")
            raise
        else:
            self.end_generation(g, output_text=g.output_text, status="ok")

    def get_cost_summary(self) -> dict[str, Any]:
        if not self._generations:
            return {"total_cost_yuan": 0.0, "total_tokens": 0, "total_generations": 0, "by_model": {}, "by_provider": {}}
        total_cost = sum(g.cost_yuan for g in self._generations)
        total_tokens = sum(g.total_tokens for g in self._generations)
        by_model: dict[str, dict] = {}
        by_provider: dict[str, dict] = {}
        for g in self._generations:
            if g.model:
                m = by_model.setdefault(g.model, {"cost": 0.0, "tokens": 0, "calls": 0})
                m["cost"] += g.cost_yuan; m["tokens"] += g.total_tokens; m["calls"] += 1
            if g.provider:
                p = by_provider.setdefault(g.provider, {"cost": 0.0, "tokens": 0, "calls": 0})
                p["cost"] += g.cost_yuan; p["tokens"] += g.total_tokens; p["calls"] += 1
        return {
            "total_cost_yuan": round(total_cost, 6),
            "total_tokens": total_tokens,
            "total_generations": len(self._generations),
            "avg_cost_per_call": round(total_cost / len(self._generations), 6),
            "by_model": {k: {kk: round(vv, 6) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in by_model.items()},
            "by_provider": {k: {kk: round(vv, 6) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in by_provider.items()},
        }

    def distill_evidence(self, window: int = 500) -> list[DistilledEvidence]:
        """Distill raw trace spans into layered evidence corpus.

        Agentic Harness-style trajectory distillation:
        - Layer 1 (raw): verbatim span summaries
        - Layer 2 (structured): key facts (errors, latencies, generations)
        - Layer 3 (insight): patterns & anomalies detected
        - Layer 4 (action): concrete recommendations

        Returns a list of DistilledEvidence objects across all 4 layers,
        ordered by importance (insights and actions first).
        """
        spans = self._completed_spans[-window:]
        gens = self._generations[-window:]
        if not spans and not gens:
            return []

        evidence: list[DistilledEvidence] = []
        error_spans = [s for s in spans if s.status == "error"]
        slow_spans = [s for s in spans if s.duration_ms > 5000]
        ok_spans = [s for s in spans if s.status == "ok"]

        # ── Layer 1: RAW ──
        evidence.append(DistilledEvidence(
            layer=EvidenceLayer.RAW,
            summary=f"Traced {len(spans)} spans ({len(ok_spans)} OK, {len(error_spans)} errors, {len(slow_spans)} slow) "
                    f"and {len(gens)} LLM generations over last window={window}",
            evidence_type="trace_summary",
            source_span_ids=[s.span_id for s in spans[:10]],
            confidence=1.0,
        ))

        if gens:
            total_cost = sum(g.cost_yuan for g in gens)
            total_tokens = sum(g.total_tokens for g in gens)
            evidence.append(DistilledEvidence(
                layer=EvidenceLayer.RAW,
                summary=f"LLM generations: {len(gens)} calls, {total_tokens} tokens, ¥{total_cost:.4f} total cost",
                evidence_type="generation_summary",
                source_span_ids=[g.span_id for g in gens[:5]],
                confidence=1.0,
            ))

        # ── Layer 2: STRUCTURED ──
        for s in error_spans:
            error_msg = ""
            for ev in s.events:
                if ev.get("name") == "exception":
                    error_msg = ev.get("attributes", {}).get("error", "")
            evidence.append(DistilledEvidence(
                layer=EvidenceLayer.STRUCTURED,
                summary=f"Error in span '{s.name}': {error_msg[:200]}" if error_msg else f"Error in span '{s.name}'",
                evidence_type="error",
                source_span_ids=[s.span_id],
                confidence=0.95,
                details={"error": error_msg, "duration_ms": s.duration_ms},
            ))

        for s in slow_spans:
            evidence.append(DistilledEvidence(
                layer=EvidenceLayer.STRUCTURED,
                summary=f"Slow span '{s.name}': {s.duration_ms:.0f}ms (threshold: 5000ms)",
                evidence_type="latency_anomaly",
                source_span_ids=[s.span_id],
                confidence=0.8,
                details={"duration_ms": s.duration_ms, "threshold_ms": 5000},
            ))

        for g in gens[-20:]:
            if g.cost_yuan > 0.01:
                evidence.append(DistilledEvidence(
                    layer=EvidenceLayer.STRUCTURED,
                    summary=f"Costly generation: {g.name} ({g.model}), {g.total_tokens}t, ¥{g.cost_yuan:.4f}",
                    evidence_type="cost_spike",
                    source_span_ids=[g.span_id],
                    confidence=0.85,
                    details={"model": g.model, "tokens": g.total_tokens, "cost_yuan": g.cost_yuan},
                ))

        # ── Layer 3: INSIGHT ──
        total_spans = len(spans)
        if total_spans > 0:
            error_rate = len(error_spans) / total_spans
            if error_rate > 0.1:
                evidence.append(DistilledEvidence(
                    layer=EvidenceLayer.INSIGHT,
                    summary=f"High error rate detected: {error_rate:.1%} ({len(error_spans)}/{total_spans} spans)",
                    evidence_type="error_pattern",
                    source_span_ids=[s.span_id for s in error_spans[:5]],
                    confidence=0.7,
                    details={"error_rate": error_rate, "error_count": len(error_spans)},
                ))

        if len(slow_spans) > 3:
            avg_slow = sum(s.duration_ms for s in slow_spans) / len(slow_spans)
            evidence.append(DistilledEvidence(
                layer=EvidenceLayer.INSIGHT,
                summary=f"Recurring latency issue: {len(slow_spans)} spans exceed 5s (avg {avg_slow:.0f}ms)",
                evidence_type="latency_pattern",
                source_span_ids=[s.span_id for s in slow_spans[:5]],
                confidence=0.6,
                details={"slow_count": len(slow_spans), "avg_slow_ms": avg_slow},
            ))

        gen_errors = [g for g in gens if g.status == "error"]
        if gen_errors and len(gens) > 0:
            gen_error_rate = len(gen_errors) / len(gens)
            if gen_error_rate > 0.05:
                evidence.append(DistilledEvidence(
                    layer=EvidenceLayer.INSIGHT,
                    summary=f"Generation failure pattern: {gen_error_rate:.1%} generations error ({len(gen_errors)}/{len(gens)})",
                    evidence_type="generation_failure",
                    source_span_ids=[g.span_id for g in gen_errors[:5]],
                    confidence=0.75,
                    details={"gen_error_rate": gen_error_rate},
                ))

        # ── Layer 4: ACTION ──
        if error_spans:
            top_errors: dict[str, int] = {}
            for s in error_spans:
                top_errors[s.name] = top_errors.get(s.name, 0) + 1
            worst = max(top_errors, key=top_errors.get)
            evidence.append(DistilledEvidence(
                layer=EvidenceLayer.ACTION,
                summary=f"Investigate '{worst}' ({top_errors[worst]} errors) — add retry or circuit breaker",
                evidence_type="recommendation",
                source_span_ids=[],
                confidence=0.5,
                details={"most_frequent_error": worst, "error_count": top_errors[worst]},
            ))

        if slow_spans:
            slow_names = list({s.name for s in slow_spans})
            evidence.append(DistilledEvidence(
                layer=EvidenceLayer.ACTION,
                summary=f"Consider adding caching or async for slow operations: {', '.join(slow_names[:3])}",
                evidence_type="recommendation",
                source_span_ids=[],
                confidence=0.4,
                details={"slow_operations": slow_names},
            ))

        return evidence

    def get_statistics(self) -> dict[str, Any]:
        spans = self._completed_spans[-1000:]
        if not spans:
            return {"total_spans": 0, "avg_duration_ms": 0, "error_rate": 0}
        avg_duration = sum(s.duration_ms for s in spans) / len(spans)
        errors = sum(1 for s in spans if s.status == "error")
        return {
            "total_spans": len(spans),
            "active_spans": sum(len(v) for v in self._active_spans.values()),
            "avg_duration_ms": round(avg_duration, 2),
            "error_rate": round(errors / len(spans), 4),
        }


def trace_span(name: str, tracer: Optional[RequestTracer] = None):
    """Decorator to wrap a function in a trace span."""
    def decorator(func):
        import functools
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            t = tracer or _default_tracer
            with t.span(name):
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            t = tracer or _default_tracer
            with t.span(name):
                return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


class GenerationSpan(BaseModel):
    """A single LLM generation span (Langfuse-style Generation)."""
    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    parent_span_id: Optional[str] = None
    name: str
    model: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_yuan: float = 0.0
    input_text: str = ""
    output_text: str = ""
    model_parameters: dict[str, Any] = Field(default_factory=dict)
    usage_metadata: dict[str, Any] = Field(default_factory=dict)
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    status: str = "ok"

    def finish(self, status: str = "ok") -> None:
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status
        self.total_tokens = self.prompt_tokens + self.completion_tokens


_MODEL_COSTS: dict[str, dict[str, float]] = {
    "deepseek-ai": {"input": 0.0, "output": 0.0},  # ModelScope free
    "qwen3": {"input": 0.0, "output": 0.0},  # ModelScope free
    "qwen/": {"input": 0.0, "output": 0.0},  # ModelScope free
    "modelscope": {"input": 0.0, "output": 0.0},  # free tier
    "baichuan": {"input": 0.0, "output": 0.0},  # Bailing free tier
    "bailing": {"input": 0.0, "output": 0.0},  # Bailing free tier
    "stepfun": {"input": 0.0, "output": 0.0},  # StepFun free tier
    "step-": {"input": 0.0, "output": 0.0},  # StepFun model prefix
    "internlm": {"input": 0.0, "output": 0.0},  # InternLM free tier
    "deepseek": {"input": 0.1, "output": 0.5},
    "qwen-turbo": {"input": 0.3, "output": 0.6},
    "qwen-max": {"input": 4.0, "output": 12.0},
    "gpt-4o-mini": {"input": 1.0, "output": 3.0},
    "gpt-4o": {"input": 18.0, "output": 54.0},
    "claude-sonnet": {"input": 11.0, "output": 35.0},
    "glm-4-flash": {"input": 0.1, "output": 0.4},
    "longcat": {"input": 0.0, "output": 0.0},  # free
    "fallback": {"input": 1.0, "output": 2.0},
}

def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost in yuan for a generation."""
    key = model.lower()
    for k, v in _MODEL_COSTS.items():
        if k in key:
            pricing = v
            break
    else:
        pricing = _MODEL_COSTS["fallback"]
    return (prompt_tokens / 1_000_000) * pricing["input"] + (completion_tokens / 1_000_000) * pricing["output"]
