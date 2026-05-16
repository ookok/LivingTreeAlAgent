"""OpenTelemetry standardization for the existing observability layer.

Integrates with OpenTelemetry SDK for distributed tracing while maintaining
backward compatibility with the existing RequestTracer and MetricsCollector.

When opentelemetry packages are not installed, all methods gracefully no-op
while still recording timing data to MetricsCollector histograms.

Usage:
    otel = get_otel()
    otel.setup(OtelConfig(service_name="livingtree", console_export=True))

    with OtelSpan("my_operation", {"key": "value"}) as span:
        span.set_attribute("extra", "info")
        span.add_event("milestone")

    otel.trace_llm_call("openrouter", "deepseek-chat", messages, response)
    otel.shutdown()
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

# ── Optional OpenTelemetry imports ──────────────────────────────────────────

from opentelemetry import trace as _otel_trace
from opentelemetry.sdk.trace import TracerProvider as _SdkProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)


# ── Configuration ───────────────────────────────────────────────────────────

@dataclass
class OtelConfig:
    """OpenTelemetry SDK configuration."""
    service_name: str = "livingtree"
    otlp_endpoint: str | None = None
    console_export: bool = True
    trace_sampling_rate: float = 1.0
    enabled: bool = True


# ── OtelSpan context manager ────────────────────────────────────────────────

class OtelSpan:
    """Context manager wrapping an OpenTelemetry span.

    When OTel SDK is unavailable, works as a lightweight timing wrapper
    that records duration to MetricsCollector.
    """

    def __init__(self, name: str, attributes: dict[str, Any] | None = None):
        self.name = name
        self._attributes: dict[str, Any] = attributes or {}
        self._span: Any = None
        self._start_time: float = 0.0
        self._otel_ok = _otel_trace is not None

    def set_attribute(self, key: str, value: Any) -> None:
        self._attributes[key] = value
        if self._span is not None and self._otel_ok:
            self._span.set_attribute(key, value)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        if self._span is not None and self._otel_ok:
            self._span.add_event(name, attributes=attributes)

    def record_exception(self, exc: BaseException) -> None:
        if self._span is not None and self._otel_ok:
            self._span.record_exception(exc)

    def context(self) -> Any:
        """Return the span context for cross-service propagation."""
        if self._span is not None and self._otel_ok:
            return self._span.get_span_context()
        return None

    def __enter__(self) -> OtelSpan:
        self._start_time = time.time()
        if self._otel_ok and _otel_trace is not None:
            tracer = _otel_trace.get_tracer(__name__)
            self._span = tracer.start_span(
                self.name, attributes=self._attributes, kind=SpanKind.INTERNAL,
            )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        duration_ms = (time.time() - self._start_time) * 1000
        if self._span is not None and self._otel_ok:
            if exc_val is not None:
                self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))
                self._span.record_exception(exc_val)
            self._span.set_attribute("duration_ms", duration_ms)
            self._span.end()
        _record_duration("span", self.name, duration_ms)
        return False


# ── OtelIntegration ─────────────────────────────────────────────────────────

class OtelIntegration:
    """OpenTelemetry integration manager.

    Bridges OTel SDK with the existing MetricsCollector — all span durations
    are recorded as histograms on the collector for unified dashboards.
    """

    def __init__(self) -> None:
        self._config: OtelConfig | None = None
        self._provider: Any = None
        self._collector: Any = None
        self._lock = threading.Lock()
        self._setup_done = False

    def setup(
        self,
        config: OtelConfig | None = None,
        collector: Any = None,
    ) -> None:
        """Initialize the OpenTelemetry SDK.

        Args:
            config: OTel configuration. Defaults to OtelConfig().
            collector: Existing MetricsCollector instance for auto-wiring.
                       If None, attempts to resolve from get_observability().
        """
        with self._lock:
            self._config = config or OtelConfig()
            self._resolve_collector(collector)

            if not self._config.enabled or not _otel_trace is not None:
                logger.info("OpenTelemetry integration not enabled or SDK unavailable")
                self._setup_done = True
                return

            _register_histograms(self._collector)

            self._provider = _SdkProvider()
            processors: list[Any] = []

            if self._config.console_export and ConsoleSpanExporter is not None:
                processors.append(BatchSpanProcessor(ConsoleSpanExporter()))

            if self._config.otlp_endpoint and OTLPSpanExporter is not None and OTLPSpanExporter is not None:
                processors.append(
                    BatchSpanProcessor(
                        OTLPSpanExporter(endpoint=self._config.otlp_endpoint, insecure=True)
                    )
                )

            for processor in processors:
                self._provider.add_span_processor(processor)

            _otel_trace.set_tracer_provider(self._provider)
            self._setup_done = True

            logger.info(
                f"OpenTelemetry initialized: service={self._config.service_name}, "
                f"exporters={len(processors)}, sampling={self._config.trace_sampling_rate}"
            )

    def _resolve_collector(self, collector: Any) -> None:
        if collector is not None:
            self._collector = collector
            return
        try:
            from .setup import get_observability
            handle = get_observability()
            self._collector = handle.metrics if handle else None
        except Exception:
            self._collector = None

    def get_tracer(self, name: str) -> Any:
        """Return a named tracer instance.

        Args:
            name: Logical name for the tracer (e.g. "livingtree.tasks",
                  "livingtree.knowledge"). Falls back to __name__ for OTel SDK.
        """
        if not self._setup_done or not _otel_trace is not None or _otel_trace is None:
            return None
        return _otel_trace.get_tracer(name or "livingtree")

    # ── High-level trace helpers ────────────────────────────────────────

    def trace_llm_call(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]] | None = None,
        response: dict[str, Any] | None = None,
    ) -> None:
        """Record an LLM API call as a span with token counts and latency.

        Creates a standalone span recording the full LLM request/response
        lifecycle. Intended to replace manual time.time() latency tracking
        in routes.py and providers.py.

        Args:
            provider: AI provider name (e.g. "openrouter", "deepseek").
            model: Model identifier (e.g. "deepseek-chat", "gpt-4o").
            messages: The prompt messages sent to the model.
            response: Dict with 'model', 'usage' (prompt_tokens/completion_tokens),
                      'latency_ms', 'content', and any provider-specific fields.
        """
        self._check_setup()
        attrs = {
            "llm.provider": provider,
            "llm.model": model,
        }
        if messages is not None:
            attrs["llm.message_count"] = len(messages)
        response = response or {}
        usage = response.get("usage", {}) if isinstance(response, dict) else {}
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        latency_ms = response.get("latency_ms", 0)
        attrs.update({
            "llm.prompt_tokens": prompt_tokens,
            "llm.completion_tokens": completion_tokens,
            "llm.total_tokens": prompt_tokens + completion_tokens,
            "llm.latency_ms": latency_ms,
        })
        _record_duration("llm_call", f"{provider}/{model}", latency_ms)

        if self._otel_ready():
            tracer = _otel_trace.get_tracer("livingtree.llm")
            with tracer.start_as_current_span(
                "llm.call", kind=SpanKind.CLIENT, attributes=attrs,
            ) as span:
                if latency_ms:
                    span.set_attribute("duration_ms", latency_ms)

    def trace_organ_activity(
        self,
        organ_name: str,
        action: str,
        duration_ms: float = 0.0,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Record an organ pipeline step as a span.

        Each of the 12 biological organs reports pipeline activity through
        this method, replacing raw time.time() tracking.

        Args:
            organ_name: Name of the organ (e.g. "cortex", "hippocampus").
            action: The action performed (e.g. "reason", "remember").
            duration_ms: Measured duration of the action in milliseconds.
            attributes: Additional key-value metadata for the span.
        """
        self._check_setup()
        attrs = dict(attributes or {})
        attrs.update({
            "organ.name": organ_name,
            "organ.action": action,
            "organ.duration_ms": duration_ms,
        })
        _record_duration("organ", f"{organ_name}.{action}", duration_ms)
        if self._otel_ready():
            tracer = _otel_trace.get_tracer("livingtree.organ")
            with tracer.start_as_current_span(
                "organ.activity", kind=SpanKind.INTERNAL, attributes=attrs,
            ):
                pass

    def trace_knowledge_query(
        self,
        query: str,
        results_count: int = 0,
        latency_ms: float = 0.0,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Trace a RAG / knowledge base query.

        Args:
            query: The search / retrieval query string (truncated to 500 chars).
            results_count: Number of documents or results returned.
            latency_ms: Query latency in milliseconds.
            attributes: Extra metadata (source, index, etc.).
        """
        self._check_setup()
        attrs = dict(attributes or {})
        attrs.update({
            "knowledge.query": query[:500],
            "knowledge.results_count": results_count,
            "knowledge.latency_ms": latency_ms,
        })
        _record_duration("knowledge_query", "rag_query", latency_ms)
        if self._otel_ready():
            tracer = _otel_trace.get_tracer("livingtree.knowledge")
            with tracer.start_as_current_span(
                "knowledge.query", kind=SpanKind.INTERNAL, attributes=attrs,
            ):
                pass

    def trace_http_request(
        self,
        method: str,
        url: str,
        status_code: int = 0,
        latency_ms: float = 0.0,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Trace an outgoing HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Request URL (truncated to 500 chars).
            status_code: Response HTTP status code.
            latency_ms: Request latency in milliseconds.
            attributes: Extra metadata (headers, content-length, etc.).
        """
        self._check_setup()
        attrs = dict(attributes or {})
        attrs.update({
            "http.method": method,
            "http.url": url[:500],
            "http.status_code": status_code,
            "http.latency_ms": latency_ms,
        })
        _record_duration("http_request", f"{method}.{_sanitize_url(url)}", latency_ms)
        if self._otel_ready():
            tracer = _otel_trace.get_tracer("livingtree.http")
            with tracer.start_as_current_span(
                "http.request", kind=SpanKind.CLIENT, attributes=attrs,
            ) as span:
                if status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {status_code}"))
                if latency_ms:
                    span.set_attribute("duration_ms", latency_ms)

    def get_current_span(self) -> Any:
        """Return the currently active OpenTelemetry span, or None."""
        if not self._otel_ready():
            return None
        span = _otel_trace.get_current_span()
        if span is None:
            return None
        span_ctx = span.get_span_context()
        if span_ctx is None or not span_ctx.is_valid:
            return None
        return span

    def shutdown(self) -> None:
        """Gracefully shut down the tracer provider."""
        if self._provider is not None and _otel_trace is not None:
            self._provider.shutdown()
            logger.info("OpenTelemetry tracer provider shut down")

    # ── Internals ───────────────────────────────────────────────────────

    def _check_setup(self) -> None:
        if not self._setup_done:
            logger.debug("OtelIntegration not set up — call otel.setup() first")

    def _otel_ready(self) -> bool:
        return (
            self._setup_done
            and self._config is not None
            and self._config.enabled
            and _otel_trace is not None
            and _otel_trace is not None
        )


# ── Singleton ───────────────────────────────────────────────────────────────

_integration: OtelIntegration | None = None
_integration_lock = threading.Lock()


def get_otel() -> OtelIntegration:
    """Return the singleton OtelIntegration instance."""
    global _integration
    if _integration is None:
        with _integration_lock:
            if _integration is None:
                _integration = OtelIntegration()
    return _integration


# ── Internal helpers ────────────────────────────────────────────────────────

def _record_duration(category: str, name: str, duration_ms: float) -> None:
    """Record a span duration to the auto-wired MetricsCollector histogram."""
    if duration_ms <= 0:
        return
    try:
        collector = _get_collector()
        if collector is None:
            return
        key = f"livingtree_otel_{category}_duration_ms"
        hist = getattr(collector, key.replace(".", "_"), None)
        if hist is None:
            return
        hist.observe(duration_ms)
    except Exception:
        pass


def _register_histograms(collector: Any) -> None:
    """Register OTel-specific histograms on the MetricsCollector if available."""
    if collector is None:
        return
    categories = ["span", "llm_call", "organ", "knowledge_query", "http_request"]
    for cat in categories:
        key = f"livingtree_otel_{cat}_duration_ms"
        if not hasattr(collector, key.replace(".", "_")):
            try:
                collector.register_histogram(
                    key, f"OTel {cat} duration in milliseconds",
                )
            except Exception:
                pass


def _get_collector() -> Any:
    integration = _integration
    if integration is None or integration._collector is None:
        return None
    return integration._collector


def _sanitize_url(url: str) -> str:
    """Extract a sanitized short name from a URL for metric labels."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.hostname or url[:50]
    except Exception:
        return url[:50]
