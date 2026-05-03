"""Distributed request tracing with span management."""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterator, Optional

from loguru import logger
from pydantic import BaseModel, Field

from .logger import LogContext


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


_default_tracer = RequestTracer()
