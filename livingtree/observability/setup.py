"""One-shot observability setup from config."""
from __future__ import annotations

from typing import Optional

from ..config import LTAIConfig, get_config as _get_cfg
from .logger import setup_logging
from .tracer import RequestTracer
from .metrics import MetricsCollector


class ObservabilityHandle:
    """Bundle of observability components."""
    def __init__(self, tracer: RequestTracer, metrics: MetricsCollector):
        self.tracer = tracer
        self.metrics = metrics


_handle: Optional[ObservabilityHandle] = None


def setup_observability(config: Optional[LTAIConfig] = None) -> ObservabilityHandle:
    """Bootstrap logging, tracing, and metrics from config.

    Called once at startup by the integration layer.
    """
    global _handle
    cfg = config or _get_cfg()

    setup_logging(
        level=cfg.observability.log_level,
        log_file=cfg.observability.log_file or None,
        rotation=cfg.observability.log_rotation,
        retention=cfg.observability.log_retention,
    )

    tracer = RequestTracer(
        sample_rate=cfg.observability.trace_sample_rate,
        enabled=cfg.observability.tracing_enabled,
    )

    metrics = MetricsCollector()

    _handle = ObservabilityHandle(tracer=tracer, metrics=metrics)
    return _handle


def get_observability() -> ObservabilityHandle:
    """Get the global observability handle."""
    global _handle
    if _handle is None:
        _handle = setup_observability()
    return _handle
