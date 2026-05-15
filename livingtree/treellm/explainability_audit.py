"""ExplainabilityAudit — Decision traceability: "why did the system do that?"

Bridges existing rationale_generator, audit trail, and tracer into a unified
decision trace pipeline. Every routing/tool/aggregation decision is recorded
with its inputs, evaluation, alternatives, and rationale.

Frontend renders as an interactive decision tree.

Integration:
  audit = get_explainability_audit()
  trace = audit.start_trace(query)
  audit.record_decision(trace, "provider_election", {...})
  audit.record_decision(trace, "tool_call", {...})
  report = audit.generate_report(trace)  # → dict for frontend

Builds on: rationale_generator.Rationale, audit.py, tracer.py
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class DecisionNode:
    step: int
    type: str              # "provider_election" | "tool_call" | "vfs_op" | "aggregation" | "render"
    inputs: dict = field(default_factory=dict)
    chosen: str = ""       # What was chosen
    alternatives: list[dict] = field(default_factory=list)  # [{option, score, reason}]
    rationale: str = ""
    outcome: Any = None
    duration_ms: float = 0.0
    children: list["DecisionNode"] = field(default_factory=list)


@dataclass
class DecisionTrace:
    trace_id: str = ""
    query: str = ""
    start_time: float = field(default_factory=time.time)
    nodes: list[DecisionNode] = field(default_factory=list)
    total_duration_ms: float = 0.0
    final_provider: str = ""
    final_result_preview: str = ""


class ExplainabilityAudit:
    """Unified decision traceability pipeline."""

    _instance: Optional["ExplainabilityAudit"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "ExplainabilityAudit":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ExplainabilityAudit()
        return cls._instance

    def __init__(self):
        self._traces: list[DecisionTrace] = []
        self._max_traces = 100

    # ── Trace Lifecycle ────────────────────────────────────────────

    def start_trace(self, query: str) -> DecisionTrace:
        """Begin a new decision trace for a user query."""
        trace = DecisionTrace(
            trace_id=f"trace_{int(time.time()*1000)}_{len(self._traces)}",
            query=query[:500],
        )
        return trace

    def record_decision(self, trace: DecisionTrace, step_type: str,
                        chosen: str, alternatives: list[dict] = None,
                        rationale: str = "", inputs: dict = None,
                        outcome: Any = None,
                        duration_ms: float = 0.0) -> DecisionNode:
        """Record a single decision point in the trace."""
        node = DecisionNode(
            step=len(trace.nodes),
            type=step_type,
            inputs=inputs or {},
            chosen=chosen,
            alternatives=alternatives or [],
            rationale=rationale,
            outcome=outcome,
            duration_ms=duration_ms,
        )
        trace.nodes.append(node)
        return node

    def complete_trace(self, trace: DecisionTrace,
                       final_provider: str = "",
                       final_result: str = "") -> DecisionTrace:
        """Finalize a decision trace."""
        trace.final_provider = final_provider
        trace.final_result_preview = final_result[:200]
        trace.total_duration_ms = (time.time() - trace.start_time) * 1000
        self._traces.append(trace)
        if len(self._traces) > self._max_traces:
            self._traces = self._traces[-self._max_traces:]
        return trace

    # ── Report Generation ──────────────────────────────────────────

    def generate_report(self, trace: DecisionTrace) -> dict:
        """Generate a human-readable decision report."""
        steps = []
        for node in trace.nodes:
            step = {
                "step": node.step,
                "type": node.type,
                "chosen": node.chosen,
                "rationale": node.rationale[:200],
            }
            if node.alternatives:
                step["alternatives"] = [
                    {"option": a.get("name", a.get("provider", "?")),
                     "score": a.get("score", 0),
                     "reason": a.get("reason", "")[:100]}
                    for a in node.alternatives[:3]
                ]
            steps.append(step)

        return {
            "trace_id": trace.trace_id,
            "query": trace.query,
            "total_ms": round(trace.total_duration_ms, 0),
            "final_provider": trace.final_provider,
            "steps": steps,
            "step_count": len(steps),
        }

    def recent_traces(self, limit: int = 5) -> list[dict]:
        """Return recent decision traces for dashboard."""
        return [self.generate_report(t) for t in self._traces[-limit:]]

    def stats(self) -> dict:
        return {"traces": len(self._traces)}


_audit: Optional[ExplainabilityAudit] = None
_audit_lock = threading.Lock()


def get_explainability_audit() -> ExplainabilityAudit:
    global _audit
    if _audit is None:
        with _audit_lock:
            if _audit is None:
                _audit = ExplainabilityAudit()
    return _audit


__all__ = ["ExplainabilityAudit", "DecisionTrace", "DecisionNode", "get_explainability_audit"]
