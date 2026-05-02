"""
Distributed Tracer — Compatibility Stub

Functionality migrated to livingtree.core.observability.tracer.
"""

from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class Span:
    trace_id: str = ""
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Trace:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    spans: list = field(default_factory=list)


class DistributedTracer:
    def __init__(self):
        self._traces = []

    def start_trace(self, name: str = "") -> Trace:
        t = Trace()
        self._traces.append(t)
        return t

    def start_span(self, trace: Trace, name: str) -> Span:
        span = Span(trace_id=trace.trace_id, name=name)
        trace.spans.append(span)
        return span


def get_tracer():
    return DistributedTracer()


__all__ = ["DistributedTracer", "get_tracer", "Trace", "Span"]
