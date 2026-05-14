"""ContinuousBenchmark — Scheduled performance tracking with historical trends and regression alerts.

Builds on canary_tester and observability/metrics to provide:
  - Scheduled benchmark runs (hourly/daily/on-commit)
  - Historical time-series of benchmark scores
  - Regression detection with auto-rollback recommendation
  - Trend visualization data

Integration:
  bench = get_continuous_benchmark()
  result = await bench.run()    # → BenchmarkResult
  trend = bench.trend(days=7)   # → historical trend data
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

BENCHMARK_FILE = Path(".livingtree/benchmark_history.jsonl")


@dataclass
class BenchmarkResult:
    run_id: str = ""
    timestamp: float = field(default_factory=time.time)
    version: str = ""
    total_queries: int = 0
    passed: int = 0
    regressions: int = 0
    avg_latency_ms: float = 0.0
    avg_depth: float = 0.0
    avg_quality: float = 0.0
    avg_cost_yuan: float = 0.0
    pass_rate: float = 0.0
    score: float = 0.0         # Composite 0-100
    degraded: bool = False
    recommendations: list[str] = field(default_factory=list)


class ContinuousBenchmark:
    """Scheduled performance benchmarking with historical tracking."""

    _instance: Optional["ContinuousBenchmark"] = None

    @classmethod
    def instance(cls) -> "ContinuousBenchmark":
        if cls._instance is None:
            cls._instance = ContinuousBenchmark()
        return cls._instance

    def __init__(self):
        self._history: list[BenchmarkResult] = []
        self._runs = 0
        self._load()

    async def run(self, llm: Any = None) -> BenchmarkResult:
        """Run a full benchmark cycle and compare against historical baseline."""
        self._runs += 1
        result = BenchmarkResult(run_id=f"bench_{int(time.time())}_{self._runs}")

        try:
            from .canary_tester import get_canary_tester
            tester = get_canary_tester()
            if llm is None:
                from .core import TreeLLM
                llm = TreeLLM()
            canary_report = await tester.run(llm)

            result.total_queries = canary_report.total
            result.passed = canary_report.passed
            result.regressions = canary_report.regressions
            result.avg_latency_ms = canary_report.avg_latency_ms
            result.pass_rate = canary_report.pass_rate

            # Composite score: pass_rate × 0.5 + (1-regression_rate) × 0.3 + latency_factor × 0.2
            regression_penalty = 1.0 - min(result.regressions / max(result.total_queries, 1), 1.0)
            latency_factor = max(0, 1.0 - (result.avg_latency_ms - 500) / 2000)
            result.score = int(
                (result.pass_rate * 50 + regression_penalty * 30 + latency_factor * 20)
            )
            result.score = max(0, min(100, result.score))

            # Historical comparison
            if self._history:
                last = self._history[-1]
                if result.score < last.score - 10:
                    result.degraded = True
                    result.recommendations = [
                        f"Score degraded from {last.score} to {result.score}",
                        f"Pass rate: {last.pass_rate:.0%} → {result.pass_rate:.0%}",
                        f"Latency: {last.avg_latency_ms:.0f}ms → {result.avg_latency_ms:.0f}ms",
                        "Consider reverting recent changes and re-running benchmark.",
                    ]

        except Exception as e:
            logger.debug(f"ContinuousBenchmark: {e}")

        self._history.append(result)
        self._save(result)
        return result

    def trend(self, days: int = 7) -> dict:
        """Return historical trend data for the last N days."""
        now = time.time()
        cutoff = now - days * 86400
        recent = [r for r in self._history if r.timestamp > cutoff]

        if not recent:
            return {"days": days, "data_points": 0}

        return {
            "days": days,
            "data_points": len(recent),
            "scores": [r.score for r in recent],
            "pass_rates": [round(r.pass_rate, 3) for r in recent],
            "latencies": [round(r.avg_latency_ms, 0) for r in recent],
            "current_score": recent[-1].score,
            "score_trend": "improving" if len(recent) >= 2 and recent[-1].score > recent[0].score else "declining" if len(recent) >= 2 and recent[-1].score < recent[0].score else "stable",
            "degraded_runs": sum(1 for r in recent if r.degraded),
        }

    def latest(self) -> Optional[BenchmarkResult]:
        return self._history[-1] if self._history else None

    def _save(self, result: BenchmarkResult):
        try:
            BENCHMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(BENCHMARK_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "run_id": result.run_id, "timestamp": result.timestamp,
                    "score": result.score, "pass_rate": round(result.pass_rate, 3),
                    "latency_ms": round(result.avg_latency_ms, 0),
                    "regressions": result.regressions, "degraded": result.degraded,
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _load(self):
        try:
            if BENCHMARK_FILE.exists():
                for line in BENCHMARK_FILE.read_text(encoding="utf-8").strip().split("\n"):
                    d = json.loads(line)
                    self._history.append(BenchmarkResult(
                        run_id=d.get("run_id", ""), timestamp=d.get("timestamp", 0),
                        score=d.get("score", 0), pass_rate=d.get("pass_rate", 0),
                        avg_latency_ms=d.get("latency_ms", 0),
                        regressions=d.get("regressions", 0),
                        degraded=d.get("degraded", False),
                    ))
        except Exception:
            pass

    def stats(self) -> dict:
        return {"runs": len(self._history), "trend": self.trend(7)}


_bench: Optional[ContinuousBenchmark] = None


def get_continuous_benchmark() -> ContinuousBenchmark:
    global _bench
    if _bench is None:
        _bench = ContinuousBenchmark()
    return _bench


__all__ = ["ContinuousBenchmark", "BenchmarkResult", "get_continuous_benchmark"]
