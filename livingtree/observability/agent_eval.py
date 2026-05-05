"""AgentEval — 4-layer evaluation framework for agent/tool performance.

    Based on Mission Control's eval architecture:
    1. Output eval: correctness scoring (LLM judges output quality)
    2. Trace eval: convergence/loop detection (did agent get stuck?)
    3. Component eval: per-tool reliability with latency percentiles
    4. Drift detection: behavior drift vs rolling baseline (10% threshold)

    Usage:
        ev = get_eval()
        ev.eval_output("summary", llm_output, expected_facts)
        ev.eval_trace("nvidia-reasoning", turn_count, repeating_patterns)
        ev.eval_component("gaussian_plume", success=True, latency_ms=342)
        drift = ev.check_drift("nvidia-reasoning")
"""
from __future__ import annotations

import json
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

EVAL_DIR = Path(".livingtree/evals")


class EvalLevel(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class OutputEval:
    agent: str
    task: str
    score: float = 0.0  # 0.0–1.0
    level: str = "pass"
    feedback: str = ""
    timestamp: float = 0.0


@dataclass
class TraceEval:
    agent: str
    turns: int = 0
    converged: bool = True
    loop_detected: bool = False
    avg_turn_depth: float = 0.0
    score: float = 0.0
    timestamp: float = 0.0


@dataclass
class ComponentMetric:
    tool: str
    success_rate: float = 1.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    total_calls: int = 0
    last_eval: float = 0.0


@dataclass
class DriftReport:
    agent: str
    baseline_score: float = 0.0
    current_score: float = 0.0
    drift_pct: float = 0.0
    threshold: float = 10.0
    alert: bool = False


class AgentEval:
    """Four-layer agent evaluation framework."""

    def __init__(self):
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        self._output_evals: list[OutputEval] = []
        self._trace_evals: list[TraceEval] = []
        self._components: dict[str, ComponentMetric] = {}
        self._drift_baselines: dict[str, deque[float]] = {}
        self._load()

    # ═══ Layer 1: Output Eval ═══

    async def eval_output(
        self,
        agent: str,
        task: str,
        output: str,
        expected: str = "",
        reference: str = "",
        hub=None,
    ) -> OutputEval:
        """LLM judges output quality against expected/reference.

        Args:
            agent: Agent/tool name
            task: What was asked
            output: What the agent produced
            expected: Known-correct answer (if available, gives higher confidence)
            reference: Context/facts to check against
        """
        ts = time.time()
        if not hub or not hub.world:
            score = self._heuristic_score(output, expected)
            ev = OutputEval(agent=agent, task=task, score=score,
                           level="pass" if score > 0.6 else "warn", timestamp=ts)
            self._output_evals.append(ev)
            self._maybe_save()
            return ev

        llm = hub.world.consciousness._llm
        ref_block = f"\nREFERENCE:\n{reference[:1000]}" if reference else ""
        exp_block = f"\nEXPECTED ANSWER:\n{expected[:500]}" if expected else ""

        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Evaluate this agent output quality. Score 0.0–1.0.\n\n"
                    f"TASK: {task}\n"
                    f"OUTPUT:\n{output[:2000]}{exp_block}{ref_block}\n\n"
                    f'Output JSON: {{"score": 0.85,"level":"pass|warn|fail","feedback":"brief reason"}}'
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.0, max_tokens=200, timeout=15,
            )
            if result and result.text:
                import re
                m = re.search(r'\{[\s\S]*\}', result.text)
                if m:
                    d = json.loads(m.group())
                    ev = OutputEval(
                        agent=agent, task=task,
                        score=float(d.get("score", 0.5)),
                        level=d.get("level", "pass"),
                        feedback=d.get("feedback", ""),
                        timestamp=ts,
                    )
                    self._output_evals.append(ev)
                    self._maybe_save()
                    return ev
        except Exception as e:
            logger.debug(f"Output eval: {e}")

        ev = OutputEval(agent=agent, task=task, score=0.5, level="warn",
                       timestamp=ts, feedback="LLM eval failed, default score")
        self._output_evals.append(ev)
        self._maybe_save()
        return ev

    def _heuristic_score(self, output: str, expected: str) -> float:
        """Fallback: simple overlap scoring."""
        if not output:
            return 0.0
        if expected:
            overlap = sum(1 for w in expected.split() if w in output)
            return min(overlap / max(len(expected.split()), 1), 1.0)
        # No expected: penalize very short outputs
        return min(len(output) / 500, 0.8)

    # ═══ Layer 2: Trace Eval ═══

    def eval_trace(
        self,
        agent: str,
        turns: int,
        repeated_patterns: bool = False,
        avg_turn_depth: float = 0.0,
    ) -> TraceEval:
        """Evaluate conversation trace for convergence/loop issues.

        Args:
            turns: Number of conversation turns
            repeated_patterns: Did agent repeat the same action?
            avg_turn_depth: Average reasoning depth per turn
        """
        ts = time.time()

        converged = not repeated_patterns and turns < 20
        loop_detected = repeated_patterns or turns > 30
        score = 1.0
        if loop_detected:
            score = 0.2
        elif turns > 15:
            score = 0.6
        elif turns > 10:
            score = 0.8
        if avg_turn_depth < 1.0:
            score *= 0.7  # shallow reasoning penalty

        ev = TraceEval(
            agent=agent, turns=turns, converged=converged,
            loop_detected=loop_detected, avg_turn_depth=avg_turn_depth,
            score=score, timestamp=ts,
        )
        self._trace_evals.append(ev)

        # Update drift baseline
        if agent not in self._drift_baselines:
            self._drift_baselines[agent] = deque(maxlen=100)
        self._drift_baselines[agent].append(score)

        self._maybe_save()
        return ev

    # ═══ Layer 3: Component Eval ═══

    def eval_component(
        self,
        tool: str,
        success: bool,
        latency_ms: float,
    ) -> ComponentMetric:
        """Record per-tool reliability and latency percentile.

        Called on every tool execution.
        """
        if tool not in self._components:
            self._components[tool] = ComponentMetric(tool=tool, last_eval=time.time())

        cm = self._components[tool]
        cm.total_calls += 1
        cm.last_eval = time.time()

        # Maintain latency samples for percentiles
        if not hasattr(cm, '_latencies'):
            cm._latencies = deque(maxlen=200)

        old_successes = int(cm.success_rate * (cm.total_calls - 1))
        cm.success_rate = (old_successes + (1 if success else 0)) / cm.total_calls

        if latency_ms > 0:
            cm._latencies.append(latency_ms)
            sorted_lat = sorted(cm._latencies)
            n = len(sorted_lat)
            if n >= 1:
                cm.p50_ms = sorted_lat[n // 2]
            if n >= 3:
                cm.p95_ms = sorted_lat[int(n * 0.95)]
                cm.p99_ms = sorted_lat[int(n * 0.99)]

        return cm

    # ═══ Layer 4: Drift Detection ═══

    def check_drift(
        self,
        agent: str,
        threshold: float = 10.0,
    ) -> DriftReport:
        """Detect behavior drift vs 4-week rolling baseline.

        Alert if current performance deviates >10% from baseline.
        """
        baseline = self._drift_baselines.get(agent, deque(maxlen=100))
        if len(baseline) < 10:
            return DriftReport(agent=agent, baseline_score=0, current_score=0,
                              drift_pct=0, threshold=threshold)

        baseline_scores = list(baseline)[:-5] if len(baseline) > 5 else list(baseline)
        current_scores = list(baseline)[-5:]

        baseline_avg = statistics.mean(baseline_scores)
        current_avg = statistics.mean(current_scores) if current_scores else baseline_avg

        drift_pct = abs(current_avg - baseline_avg) / max(baseline_avg, 0.01) * 100
        alert = drift_pct > threshold

        if alert:
            logger.warning(f"Drift alert: {agent} shifted {drift_pct:.1f}% ({baseline_avg:.2f}→{current_avg:.2f})")

        return DriftReport(
            agent=agent, baseline_score=baseline_avg, current_score=current_avg,
            drift_pct=drift_pct, threshold=threshold, alert=alert,
        )

    # ═══ Queries ═══

    def component_report(self, tool: str = "") -> ComponentMetric | None:
        return self._components.get(tool)

    def all_component_reports(self) -> dict[str, ComponentMetric]:
        return dict(self._components)

    def recent_output_evals(self, n: int = 10) -> list[OutputEval]:
        return self._output_evals[-n:]

    def recent_trace_evals(self, n: int = 10) -> list[TraceEval]:
        return self._trace_evals[-n:]

    def drift_status(self) -> dict[str, DriftReport]:
        return {
            agent: self.check_drift(agent)
            for agent in self._drift_baselines
        }

    def _heuristic_score(self, output: str, expected: str = "") -> float:
        """Fallback heuristic scoring when LLM unavailable."""
        if not output:
            return 0.0
        if expected:
            overlap = sum(1 for w in expected.split() if w in output)
            return min(overlap / max(len(expected.split()), 1), 1.0)
        return min(len(output) / 500, 0.8)

    def _save(self):
        data = {
            "output_evals": [
                {"agent": e.agent, "task": e.task, "score": e.score,
                 "level": e.level, "feedback": e.feedback, "timestamp": e.timestamp}
                for e in self._output_evals[-50:]
            ],
            "trace_evals": [
                {"agent": e.agent, "turns": e.turns, "score": e.score,
                 "loop_detected": e.loop_detected, "timestamp": e.timestamp}
                for e in self._trace_evals[-50:]
            ],
            "components": {
                k: {"tool": v.tool, "success_rate": v.success_rate,
                    "p50_ms": v.p50_ms, "p95_ms": v.p95_ms, "p99_ms": v.p99_ms,
                    "total_calls": v.total_calls}
                for k, v in self._components.items()
            },
        }
        (EVAL_DIR / "evals.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        fpath = EVAL_DIR / "evals.json"
        if not fpath.exists():
            return
        try:
            d = json.loads(fpath.read_text(encoding="utf-8"))
            for e in d.get("output_evals", []):
                self._output_evals.append(OutputEval(
                    agent=e.get("agent",""), task=e.get("task",""),
                    score=e.get("score",0), level=e.get("level","pass"),
                    feedback=e.get("feedback",""), timestamp=e.get("timestamp",0)))
            for e in d.get("trace_evals", []):
                self._trace_evals.append(TraceEval(
                    agent=e.get("agent",""), turns=e.get("turns",0),
                    score=e.get("score",0), loop_detected=e.get("loop_detected",False),
                    timestamp=e.get("timestamp",0)))
            for k, v in d.get("components", {}).items():
                self._components[k] = ComponentMetric(**{
                    f: v.get(f, 0) for f in ComponentMetric.__dataclass_fields__
                })
        except Exception:
            pass

    def _maybe_save(self):
        if len(self._output_evals) % 10 == 0:
            self._save()


def get_eval() -> AgentEval:
    global _ev
    if _ev is None:
        _ev = AgentEval()
    return _ev


_ev: AgentEval | None = None
