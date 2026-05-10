"""Telemetry & Observability — OpenTelemetry-style metric tracking.

Lightweight, zero-dependency instrumentation (no external OTel libraries).
Exposes Prometheus-compatible /metrics endpoint and structured trace logs.

Tracks:
  - module.entry/exit (trace_id, duration_ms)
  - llm.call (model, provider, latency, tokens, cost_yuan)
  - p2p.hop (peer, latency, byte_count)
  - safety.shield (input_blocked, output_flagged, hitl_escalated)
  - system.vitals (cpu, memory, disk)

Blood organ (🩸) mapping: metrics flow through the system like oxygen in blood.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class MetricPoint:
    name: str
    value: float
    labels: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    trace_id: str = ""


@dataclass
class TraceSpan:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_id: str = ""
    operation: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "ok"       # "ok", "error", "timeout"
    metadata: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000 if self.end_time else 0


class Telemetry:
    """Lightweight OTel-compatible metrics + tracing engine."""

    def __init__(self):
        self._metrics: defaultdict[str, list[MetricPoint]] = defaultdict(list)
        self._spans: deque[TraceSpan] = deque(maxlen=100)
        self._counters: defaultdict[str, int] = defaultdict(int)
        self._llm_calls: list[dict] = []
        self._start_time = time.time()

    # ═══ Module Instrumentation ═══

    @contextmanager
    def span(self, operation: str, parent_id: str = "", **meta):
        """Context manager for tracing a module entry/exit."""
        span = TraceSpan(
            parent_id=parent_id, operation=operation,
            start_time=time.time(), metadata=meta,
        )
        try:
            yield span
        except Exception as e:
            span.status = "error"
            span.metadata["error"] = str(e)[:200]
            raise
        finally:
            span.end_time = time.time()
            self._spans.append(span)
            self.record(operation.replace(".entry", "") + "_duration_ms",
                       span.duration_ms, {"status": span.status})

    def record(self, name: str, value: float, labels: dict = None, trace_id: str = ""):
        self._metrics[name].append(MetricPoint(
            name=name, value=value, labels=labels or {},
            trace_id=trace_id,
        ))

    # ═══ LLM Call Tracking ═══

    def record_llm(self, model: str, provider: str, latency_ms: float,
                   tokens_total: int = 0, tokens_prompt: int = 0,
                   cost_yuan: float = 0.0, success: bool = True):
        self.record("llm_call_total", 1, {"model": model, "provider": provider})
        self.record("llm_latency_ms", latency_ms, {"model": model})
        self.record("llm_tokens", tokens_total, {"model": model, "type": "total"})
        self.record("llm_tokens", tokens_prompt, {"model": model, "type": "prompt"})
        self.record("llm_cost_yuan", cost_yuan, {"model": model})
        if not success:
            self.record("llm_error_total", 1, {"model": model, "provider": provider})

        self._llm_calls.append({
            "model": model, "provider": provider,
            "latency_ms": round(latency_ms, 1),
            "tokens": tokens_total, "cost": round(cost_yuan, 4),
            "success": success, "ts": time.time(),
        })

    # ═══ P2P / Network ═══

    def record_p2p(self, peer: str, latency_ms: float, byte_count: int = 0,
                   success: bool = True):
        self.record("p2p_latency_ms", latency_ms, {"peer": peer})
        self.record("p2p_bytes", byte_count, {"peer": peer})
        if not success:
            self.record("p2p_error_total", 1, {"peer": peer})

    # ═══ Safety / Shield ═══

    def record_shield(self, layer: str, action: str):
        self.record("shield_total", 1, {"layer": layer, "action": action})

    # ═══ Metrics Endpoint (Prometheus format) ═══

    def prometheus_metrics(self) -> str:
        """Generate Prometheus-compatible text format."""
        lines = []

        for name, points in sorted(self._metrics.items()):
            recent = points[-50:]
            if not recent:
                continue

            values_by_labels: dict[str, list[float]] = {}
            for p in recent:
                key = ",".join(f'{k}="{v}"' for k, v in sorted(p.labels.items()))
                values_by_labels.setdefault(key, []).append(p.value)

            for lkey, vals in values_by_labels.items():
                safe_name = name.replace(".", "_").replace("-", "_")
                if lkey:
                    lines.append(f"# HELP {safe_name} LivingTree {name}")
                    lines.append(f"# TYPE {safe_name} gauge")
                    lines.append(f"{safe_name}{{{lkey}}} {sum(vals)/len(vals):.3f}")
                else:
                    lines.append(f"# HELP {safe_name} LivingTree {name}")
                    lines.append(f"# TYPE {safe_name} gauge")
                    lines.append(f"{safe_name} {sum(vals)/len(vals):.3f}")

        lines.append(f"# HELP lt_uptime_seconds LivingTree uptime")
        lines.append(f"# TYPE lt_uptime_seconds gauge")
        lines.append(f"lt_uptime_seconds {time.time() - self._start_time:.0f}")

        return "\n".join(lines) + "\n"

    # ═══ Stats ═══

    def stats(self) -> dict:
        llm_total = len(self._llm_calls)
        llm_cost = sum(c["cost"] for c in self._llm_calls)
        llm_avg_lat = sum(c["latency_ms"] for c in self._llm_calls[-10:]) / max(1, min(10, llm_total))

        return {
            "uptime_seconds": int(time.time() - self._start_time),
            "total_metrics": len(self._metrics),
            "metric_names": list(self._metrics.keys())[:20],
            "active_spans": sum(1 for s in self._spans if s.status != "ok"),
            "llm": {
                "total_calls": llm_total,
                "total_cost_yuan": round(llm_cost, 4),
                "avg_latency_ms": round(llm_avg_lat, 1),
            },
        }

    def render_html(self) -> str:
        st = self.stats()
        llm = st["llm"]

        recent_calls = ""
        for call in self._llm_calls[-5:]:
            status_icon = "✅" if call["success"] else "❌"
            recent_calls += (
                f'<div style="font-size:9px;padding:2px 8px;color:var(--dim)">'
                f'{status_icon} {call["model"]} · {call["latency_ms"]}ms · '
                f'{call["tokens"]}tok · ¥{call["cost"]}</div>'
            )

        metric_names = st["metric_names"][:12]

        return f'''<div class="card">
<h2>📊 遥测 <span style="font-size:10px;color:var(--dim)">— OpenTelemetry 兼容</span></h2>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0">
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="font-size:20px">⏱</div>
    <div style="font-size:16px;font-weight:700">{st["uptime_seconds"]//3600}h{(st["uptime_seconds"]%3600)//60}m</div>
    <div style="font-size:9px;color:var(--dim)">运行时间</div></div>
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="font-size:20px">🤖</div>
    <div style="font-size:16px;font-weight:700">{llm["total_calls"]}</div>
    <div style="font-size:9px;color:var(--dim)">LLM调用 · ¥{llm["total_cost_yuan"]}</div></div>
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="font-size:20px">⚡</div>
    <div style="font-size:16px;font-weight:700">{llm["avg_latency_ms"]:.0f}ms</div>
    <div style="font-size:9px;color:var(--dim)">平均延迟</div></div>
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="font-size:20px">📈</div>
    <div style="font-size:16px;font-weight:700">{st["total_metrics"]}</div>
    <div style="font-size:9px;color:var(--dim)">指标数 · {len(metric_names)}类</div></div>
</div>
<div style="font-size:9px;color:var(--dim);margin-top:4px">最近LLM调用:</div>
{recent_calls or '<div style="font-size:9px;color:var(--dim)">暂无</div>'}
<div style="margin-top:8px;font-size:9px;color:var(--dim)">
  指标类型: {", ".join(metric_names)} · /metrics (Prometheus)</div>
</div>'''


_instance: Optional[Telemetry] = None


def get_telemetry() -> Telemetry:
    global _instance
    if _instance is None:
        _instance = Telemetry()
    return _instance
