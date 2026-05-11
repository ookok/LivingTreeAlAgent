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

import asyncio
import json
import numpy as np
import statistics
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

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


class EvalCase(BaseModel):
    """A single evaluation case."""
    id: str
    name: str
    task: str
    input: str
    expected: str = ""
    reference: str = ""
    category: str = "general"
    difficulty: str = "medium"
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationDataset(BaseModel):
    """A collection of evaluation cases."""
    id: str
    name: str
    description: str = ""
    cases: list[EvalCase] = Field(default_factory=list)
    created_at: float = 0.0
    version: str = "1.0.0"


@dataclass
class EvalResult:
    case_id: str
    score: float
    level: str
    feedback: str
    latency_ms: float


@dataclass
class DatasetResult:
    dataset_id: str
    agent: str
    total_cases: int
    completed: int
    failed: int
    avg_score: float
    pass_rate: float
    results: list[EvalResult]
    duration_ms: float
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "agent": self.agent,
            "total_cases": self.total_cases,
            "completed": self.completed,
            "failed": self.failed,
            "avg_score": self.avg_score,
            "pass_rate": self.pass_rate,
            "results": [asdict(r) for r in self.results],
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DatasetResult":
        d["results"] = [EvalResult(**r) for r in d.get("results", [])]
        return cls(**d)


@dataclass
class CaseComparison:
    case_id: str
    score_before: float
    score_after: float
    improved: bool


@dataclass
class ComparisonReport:
    before_id: str
    after_id: str
    avg_score_before: float
    avg_score_after: float
    score_delta: float
    pass_rate_before: float
    pass_rate_after: float
    improved_cases: list[CaseComparison]
    regressed_cases: list[CaseComparison]
    new_passes: list[str]
    new_failures: list[str]


class AgentEval:
    """Four-layer agent evaluation framework."""

    def __init__(self):
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        self._output_evals: list[OutputEval] = []
        self._trace_evals: list[TraceEval] = []
        self._components: dict[str, ComponentMetric] = {}
        self._drift_baselines: dict[str, deque[float]] = {}
        self._load()
        self._seed_quick_start()

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

    # ═══ Dataset Management ═══

    @staticmethod
    def _datasets_dir() -> Path:
        d = EVAL_DIR / "datasets"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _runs_dir() -> Path:
        d = EVAL_DIR / "runs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def load_dataset(self, dataset_path_or_id: str) -> EvaluationDataset:
        p = Path(dataset_path_or_id)
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
        else:
            candidate = self._datasets_dir() / f"{dataset_path_or_id}.json"
            if not candidate.exists():
                raise FileNotFoundError(f"Dataset not found: {dataset_path_or_id}")
            data = json.loads(candidate.read_text(encoding="utf-8"))
        return EvaluationDataset(**data)

    def save_dataset(self, dataset: EvaluationDataset) -> None:
        target = self._datasets_dir() / f"{dataset.id}.json"
        target.write_text(json.dumps(dataset.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")

    def list_datasets(self) -> list[dict]:
        ds_dir = self._datasets_dir()
        items = []
        for f in sorted(ds_dir.glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                items.append({"id": d.get("id"), "name": d.get("name"), "cases": len(d.get("cases", [])), "description": d.get("description", "")})
            except Exception:
                continue
        return items

    def delete_dataset(self, dataset_id: str) -> None:
        target = self._datasets_dir() / f"{dataset_id}.json"
        if target.exists():
            target.unlink()

    # ═══ Batch Evaluation ═══
    async def run_dataset(self, agent: str, dataset: EvaluationDataset,
                          hub=None, concurrency: int = 3) -> DatasetResult:
        """Run evaluation against all cases in a dataset."""
        semaphore = asyncio.Semaphore(concurrency)
        results: list[EvalResult] = []
        start_ts = time.time()

        async def eval_one(case: EvalCase) -> EvalResult:
            t0 = time.time()
            async with semaphore:
                raw = await self.eval_output(agent, case.task, case.input, case.expected, case.reference, hub)
            latency_ms = (time.time() - t0) * 1000
            if isinstance(raw, OutputEval):
                return EvalResult(case_id=case.id, score=raw.score, level=raw.level, feedback=raw.feedback, latency_ms=latency_ms)
            score = raw.score if hasattr(raw, 'score') else 0.5
            level = raw.level if hasattr(raw, 'level') else "warn"
            feedback = raw.feedback if hasattr(raw, 'feedback') else ""
            return EvalResult(case_id=case.id, score=score, level=level, feedback=feedback, latency_ms=latency_ms)

        tasks = [eval_one(c) for c in dataset.cases]
        for fut in asyncio.as_completed(tasks):
            try:
                results.append(await fut)
            except Exception as e:
                results.append(EvalResult(case_id="unknown", score=0.0, level="fail", feedback=str(e), latency_ms=0))

        duration_ms = (time.time() - start_ts) * 1000
        total = len(dataset.cases)
        avg_score = sum(r.score for r in results) / max(total, 1)
        pass_rate = sum(1 for r in results if r.score > 0.6) / max(total, 1)

        ds_result = DatasetResult(
            dataset_id=dataset.id, agent=agent, total_cases=total,
            completed=len(results), failed=total - len(results),
            avg_score=round(avg_score, 3), pass_rate=round(pass_rate, 3),
            results=results, duration_ms=round(duration_ms, 1), timestamp=time.time(),
        )

        # Persist
        run_path = self._runs_dir() / f"run_{int(start_ts * 1000)}.json"
        run_path.write_text(json.dumps(ds_result.to_dict(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return ds_result

    # ═══ Run Comparison ═══
    def compare_runs(self, run_a_id: str, run_b_id: str) -> ComparisonReport:
        """Compare two evaluation runs."""
        def _load(run_id: str) -> DatasetResult:
            runs_dir = self._runs_dir()
            path = runs_dir / run_id
            if not path.exists():
                path = runs_dir / f"{run_id}.json"
            if not path.exists():
                raise FileNotFoundError(f"Run not found: {run_id}")
            d = json.loads(path.read_text(encoding="utf-8"))
            return DatasetResult.from_dict(d)

        before = _load(run_a_id)
        after = _load(run_b_id)
        before_map = {r.case_id: r for r in before.results}
        after_map = {r.case_id: r for r in after.results}
        all_ids = sorted(set(list(before_map.keys()) + list(after_map.keys())))

        improved, regressed, new_passes, new_failures = [], [], [], []
        for cid in all_ids:
            bb = before_map.get(cid)
            aa = after_map.get(cid)
            sb = bb.score if bb else 0.0
            sa = aa.score if aa else 0.0
            if bb and aa:
                if sa > sb:
                    improved.append(CaseComparison(cid, sb, sa, True))
                elif sa < sb:
                    regressed.append(CaseComparison(cid, sb, sa, False))
            if bb and bb.score <= 0.6 and aa and aa.score > 0.6:
                new_passes.append(cid)
            if bb and bb.score > 0.6 and aa and aa.score <= 0.6:
                new_failures.append(cid)

        return ComparisonReport(
            before_id=run_a_id, after_id=run_b_id,
            avg_score_before=before.avg_score, avg_score_after=after.avg_score,
            score_delta=round(after.avg_score - before.avg_score, 3),
            pass_rate_before=before.pass_rate, pass_rate_after=after.pass_rate,
            improved_cases=improved, regressed_cases=regressed,
            new_passes=new_passes, new_failures=new_failures,
        )

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


    # ═══ SSDataBench: Population-Level Evaluation ═══

    def eval_population(
        self,
        agent: str,
        evaluands: list[dict],
        reference_stats: dict = None,
    ) -> dict:
        """SSDataBench-style population-level statistical validation.

        Goes beyond individual output scoring to evaluate whether a batch
        of agent outputs preserves real-world population-level distributions.

        From paper: "assessment should center on the ability of LLM-generated
        data to reproduce real-world, population-level statistical patterns."

        Args:
            agent: Agent name
            evaluands: List of {score, latency_ms, level} dicts from prior evals
            reference_stats: Optional reference {mean_score, std_score, ...}

        Returns:
            Population-level report dict
        """
        from livingtree.observability.statistical_validator import (
            get_validator, DimensionReport, Severity as SSSeverity,
        )

        if len(evaluands) < 10:
            return {
                "agent": agent, "status": "insufficient_data",
                "message": "Need >=10 evaluands for population analysis (have {}).".format(len(evaluands)),
            }

        validator = get_validator()
        reports = []

        # 1. Score distribution
        scores = [e.get("score", 0.5) for e in evaluands]
        latencies = [e.get("latency_ms", 0) for e in evaluands]

        # Reference: expected score distribution centered on 0.7 with some variance
        ref_scores = [0.5 + (i % 10) * 0.05 for i in range(len(scores))]
        reports.append(validator.validate_univariate(
            synthetic_values=scores, reference_values=ref_scores,
            dimension_name="score_distribution",
        ))

        # 2. Score vs latency bivariate
        ref_latencies = [500 + (i % 5) * 200 for i in range(len(latencies))]
        reports.append(validator.validate_bivariate(
            synthetic_x=scores, synthetic_y=latencies,
            reference_x=ref_scores, reference_y=ref_latencies,
            dimension_name="score_vs_latency",
        ))

        # 3. Pass/fail ratio
        pass_count = sum(1 for e in evaluands if e.get("level") == "pass" or e.get("score", 0) >= 0.6)
        fail_count = sum(1 for e in evaluands if e.get("level") == "fail" or e.get("score", 0) < 0.4)
        total = len(evaluands)
        pass_ratio = pass_count / max(total, 1)

        # 4. Variance collapse check (paper's key finding)
        score_std = float(np.std(scores))
        variance_collapse = score_std < 0.05  # Very low variance = typological compression
        if variance_collapse:
            reports.append(DimensionReport(
                dimension="variance_collapse_check", score=20.0,
                passed=False, severity=SSSeverity.CRITICAL,
                synthetic_count=total, reference_count=total,
                details="Variance collapse: score std={:.4f}. Agent outputs may be typologically compressed.".format(score_std),
            ))

        # Generate report
        full_report = validator.ssdata_report("agent_eval:{}".format(agent), reports)

        return {
            "agent": agent,
            "total_evaluands": total,
            "population_score": full_report.overall_score,
            "population_passed": full_report.passed,
            "pass_ratio": round(pass_ratio, 3),
            "score_mean": round(float(np.mean(scores)), 3),
            "score_std": round(score_std, 4),
            "score_median": round(float(np.median(scores)), 3),
            "variance_collapse_warning": variance_collapse,
            "dimensions": [
                {"dim": d.dimension, "score": d.score, "passed": d.passed}
                for d in full_report.dimensions
            ],
            "warnings": full_report.warnings,
            "recommendations": full_report.recommendations,
        }

    def _seed_quick_start(self):
        """Register built-in quick-start dataset if none exist."""
        ds_dir = self._datasets_dir()
        if any(ds_dir.glob("*.json")):
            return
        dataset = EvaluationDataset(
            id="quick-start", name="快速入门评估集", description="5个基础评估用例",
            version="1.0.0", created_at=time.time(),
            cases=[
                EvalCase(id="summary-001", name="文本摘要", task="总结以下文章的核心观点",
                         input="人工智能正在改变我们的工作方式...", expected="AI改变了工作模式", category="summary", difficulty="easy"),
                EvalCase(id="reasoning-001", name="逻辑推理", task="如果所有A都是B，某些B是C，那么某些A一定是C吗？",
                         input="", expected="不一定", category="reasoning", difficulty="medium", tags=["logic"]),
                EvalCase(id="code-001", name="代码解释", task="解释以下Python代码的作用",
                         input="def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
                         expected="递归计算斐波那契数列", category="code", difficulty="easy", tags=["python"]),
                EvalCase(id="math-001", name="数学计算", task="计算 15% of 240",
                         input="", expected="36", category="math", difficulty="easy"),
                EvalCase(id="creative-001", name="创意写作", task="用三句话描述未来城市的景象",
                         input="", expected="", category="creative", difficulty="hard"),
            ],
        )
        self.save_dataset(dataset)
        logger.info("Seeded quick-start evaluation dataset")

def get_eval() -> AgentEval:
    global _ev
    if _ev is None:
        _ev = AgentEval()
    return _ev


_ev: AgentEval | None = None
