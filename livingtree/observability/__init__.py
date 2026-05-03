"""Observability layer — Structured logging, distributed tracing, and metrics.

Exports: get_logger, RequestTracer, MetricsCollector, setup_observability
"""

from .logger import get_logger, LogContext, setup_logging
from .tracer import RequestTracer, TraceSpan, trace_span
from .metrics import MetricsCollector, MetricGauge, MetricCounter, MetricHistogram
from .setup import setup_observability, get_observability

__all__ = [
    "get_logger",
    "LogContext",
    "setup_logging",
    "RequestTracer",
    "TraceSpan",
    "trace_span",
    "MetricsCollector",
    "MetricGauge",
    "MetricCounter",
    "MetricHistogram",
    "setup_observability",
    "get_observability",
]
