"""
LivingTree 链路追踪 (Request Tracer)
==================================

追踪一个用户请求从进入到完成的全链路。
支持 span 嵌套、自动计时、Opik 兼容导出。
"""

import time
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock


@dataclass
class Span:
    name: str
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_id: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    status: str = "running"
    input_summary: str = ""
    output_summary: str = ""
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000


@dataclass
class TraceContext:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    request_id: str = ""
    start_time: float = field(default_factory=time.time)
    spans: List[Span] = field(default_factory=list)
    status: str = "running"
    total_tokens: int = 0


class RequestTracer:
    def __init__(self):
        self._active_traces: Dict[str, TraceContext] = {}
        self._lock = Lock()

    def start_trace(self, request_id: str = "") -> TraceContext:
        ctx = TraceContext(request_id=request_id or str(uuid.uuid4())[:8])
        with self._lock:
            self._active_traces[ctx.trace_id] = ctx
        return ctx

    def start_span(self, ctx: TraceContext, name: str, parent_span: Optional[Span] = None) -> Span:
        span = Span(
            name=name,
            parent_id=parent_span.span_id if parent_span else ""
        )
        ctx.spans.append(span)
        return span

    def end_span(self, span: Span, success: bool = True, error: str = "",
                 output_summary: str = ""):
        span.end_time = time.time()
        span.status = "success" if success else "error"
        span.error = error
        span.output_summary = output_summary

    def end_trace(self, ctx: TraceContext, success: bool = True, error: str = ""):
        ctx.status = "success" if success else "error"
        with self._lock:
            ctx_key = ctx.trace_id
        self._collect_metrics(ctx, error)

    def _collect_metrics(self, ctx: TraceContext, error: str):
        total_duration = sum(s.duration_ms for s in ctx.spans)
        failed_spans = sum(1 for s in ctx.spans if s.status == "error")

    def get_active_trace_count(self) -> int:
        with self._lock:
            return len(self._active_traces)


# ── 全局追踪器 ─────────────────────────────────────────────────────

_default_tracer: Optional[RequestTracer] = None


def get_tracer() -> RequestTracer:
    global _default_tracer
    if _default_tracer is None:
        _default_tracer = RequestTracer()
    return _default_tracer


__all__ = ["RequestTracer", "TraceContext", "Span", "get_tracer"]
