"""
LivingTree — Self-Evolution Engine (Full Migration)
=====================================================

Full migration from client/src/business/self_evolution.py

P2 增强:
- ABTestEngine: A/B 测试框架 — 安全对比新旧策略
- PatternLibrary: 已知成功/失败模式库
- SafetyGate: 安全门 — 高风险变更自动拦截
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple


class EvolutionStatus(Enum):
    STABLE = "stable"
    LEARNING = "learning"
    IMPROVING = "improving"
    STAGNANT = "stagnant"
    ADAPTING = "adapting"


class LearningType(Enum):
    SUPERVISED = "supervised"
    REINFORCEMENT = "reinforcement"
    UNSUPERVISED = "unsupervised"
    IMITATION = "imitation"


class MetricType(Enum):
    ACCURACY = "accuracy"
    LATENCY = "latency"
    MEMORY_USAGE = "memory_usage"
    COMPRESSION_RATIO = "compression_ratio"
    INTENT_RECOGNITION = "intent_recognition"
    SATISFACTION = "satisfaction"


@dataclass
class InteractionSample:
    sample_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query: str = ""
    context: str = ""
    response: str = ""
    success: bool = False
    latency_ms: float = 0.0
    tokens_used: int = 0
    feedback_score: float = 0.0
    intent_signature: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PerformanceMetric:
    metric_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metric_type: str = "accuracy"
    value: float = 0.0
    previous_value: float = 0.0
    delta: float = 0.0
    trend: str = "stable"
    window_size: int = 10
    min_value: float = 0.0
    max_value: float = 0.0
    avg_value: float = 0.0
    std_value: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class KnowledgePattern:
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_type: str = "intent"
    pattern_text: str = ""
    occurrence_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    last_seen: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EvolutionStrategy:
    strategy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    action: str = ""
    trigger_condition: str = ""
    success_count: int = 0
    total_applied: int = 0
    active: bool = True

    @property
    def success_rate(self) -> float:
        if self.total_applied == 0:
            return 0.0
        return self.success_count / self.total_applied


@dataclass
class ExecutionRecord:
    task_description: str = ""
    intent_type: str = ""
    complexity: float = 0.0
    success: bool = False
    duration_ms: float = 0.0
    tokens_used: int = 0
    errors: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReflectionReport:
    batch_size: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    avg_tokens: int = 0
    common_errors: List[str] = field(default_factory=list)
    patterns_found: List[str] = field(default_factory=list)
    suggested_improvements: List[str] = field(default_factory=list)
    overall_score: float = 0.0
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ImprovementProposal:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    category: str = ""
    expected_impact: float = 0.0
    risk_level: float = 0.0
    changes: Dict[str, Any] = field(default_factory=dict)
    status: str = "proposed"
    created_at: datetime = field(default_factory=datetime.now)
    adopted_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None


class PatternLibrary:
    """已知模式库 — 成功/失败模式存储，加速下次识别."""

    def __init__(self):
        self._success_patterns: List[Dict[str, Any]] = []
        self._failure_patterns: List[Dict[str, Any]] = []
        self._lock = Lock()

    def record_success(self, intent_type: str, complexity: float,
                       strategy: str = ""):
        with self._lock:
            self._success_patterns.append({
                "intent_type": intent_type, "complexity": complexity,
                "strategy": strategy, "timestamp": datetime.now().isoformat(),
            })
            if len(self._success_patterns) > 500:
                self._success_patterns = self._success_patterns[-500:]

    def record_failure(self, intent_type: str, complexity: float,
                       error: str = "", strategy: str = ""):
        with self._lock:
            self._failure_patterns.append({
                "intent_type": intent_type, "complexity": complexity,
                "error": error, "strategy": strategy,
                "timestamp": datetime.now().isoformat(),
            })
            if len(self._failure_patterns) > 500:
                self._failure_patterns = self._failure_patterns[-500:]

    def match_success(self, intent_type: str,
                      complexity: float) -> List[Dict[str, Any]]:
        matches = []
        for p in self._success_patterns[-100:]:
            if p["intent_type"] == intent_type:
                comp_diff = abs(p["complexity"] - complexity)
                matches.append((p, comp_diff))
        matches.sort(key=lambda x: x[1])
        return [m[0] for m in matches[:5]]

    def likely_to_fail(self, intent_type: str,
                       complexity: float) -> Optional[str]:
        recent = self._failure_patterns[-50:]
        matching = [p for p in recent if p["intent_type"] == intent_type]
        if len(matching) >= 3:
            error_types = [p.get("error", "") for p in matching]
            from collections import Counter
            return Counter(error_types).most_common(1)[0][0]
        return None


class SafetyGate:
    """安全门 — 高风险变更自动拦截."""

    def __init__(self, max_risk: float = 0.7,
                 min_confidence: float = 0.3):
        self.max_risk = max_risk
        self.min_confidence = min_confidence
        self._blocked_count: int = 0
        self._passed_count: int = 0

    def evaluate(self, proposal: ImprovementProposal) -> Tuple[bool, str]:
        if proposal.risk_level > self.max_risk:
            self._blocked_count += 1
            return False, f"风险等级 {proposal.risk_level:.2f} 超过阈值 {self.max_risk}"

        if proposal.expected_impact < self.min_confidence:
            self._blocked_count += 1
            return False, f"预期影响 {proposal.expected_impact:.2f} 低于最低置信度 {self.min_confidence}"

        self._passed_count += 1
        return True, "通过安全检查"

    @property
    def stats(self) -> Dict[str, int]:
        return {"blocked": self._blocked_count, "passed": self._passed_count}


class ABTestEngine:
    """A/B 测试引擎 — 安全对比新旧策略."""

    def __init__(self, min_sample_size: int = 30):
        self.min_sample_size = min_sample_size
        self._experiments: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def create_experiment(self, name: str, description: str = "") -> str:
        exp_id = str(uuid.uuid4())[:8]
        with self._lock:
            self._experiments[exp_id] = {
                "name": name, "description": description,
                "control": {"successes": 0, "total": 0, "latency_ms": []},
                "treatment": {"successes": 0, "total": 0, "latency_ms": []},
                "status": "running", "created_at": datetime.now(),
            }
        return exp_id

    def record(self, experiment_id: str, variant: str,
               success: bool, latency_ms: float = 0.0):
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp:
                return
            group = exp.get(variant)
            if group is None:
                return
            group["total"] += 1
            if success:
                group["successes"] += 1
            group["latency_ms"].append(latency_ms)

    def evaluate(self, experiment_id: str) -> Dict[str, Any]:
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp:
                return {"status": "not_found"}

            control = exp["control"]
            treatment = exp["treatment"]

            c_rate = (control["successes"] / control["total"]
                      if control["total"] > 0 else 0)
            t_rate = (treatment["successes"] / treatment["total"]
                      if treatment["total"] > 0 else 0)

            c_latency = (sum(control["latency_ms"]) / len(control["latency_ms"])
                         if control["latency_ms"] else 0)
            t_latency = (sum(treatment["latency_ms"]) / len(treatment["latency_ms"])
                         if treatment["latency_ms"] else 0)

            total_samples = control["total"] + treatment["total"]
            significant = total_samples >= self.min_sample_size
            winner = "none"
            if significant and abs(t_rate - c_rate) > 0.05:
                winner = "treatment" if t_rate > c_rate else "control"

            return {
                "experiment_id": experiment_id,
                "name": exp["name"],
                "control_rate": c_rate,
                "treatment_rate": t_rate,
                "control_latency_ms": c_latency,
                "treatment_latency_ms": t_latency,
                "control_samples": control["total"],
                "treatment_samples": treatment["total"],
                "significant": significant,
                "winner": winner,
                "improvement": t_rate - c_rate,
            }

    def list_experiments(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [{"id": k, "name": v["name"],
                     "status": v["status"],
                     "control_total": v["control"]["total"],
                     "treatment_total": v["treatment"]["total"],
                     }
                    for k, v in self._experiments.items()]


class SelfLearningEngine:
    def __init__(self, max_samples: int = 1000):
        self._samples: List[InteractionSample] = []
        self._patterns: List[KnowledgePattern] = []
        self._strategies: List[EvolutionStrategy] = []
        self._metrics: Dict[str, List[PerformanceMetric]] = defaultdict(list)
        self._max_samples = max_samples
        self._lock = Lock()

    def record_interaction(self, sample: InteractionSample):
        with self._lock:
            self._samples.append(sample)
            if len(self._samples) > self._max_samples:
                self._samples = self._samples[-self._max_samples:]

    def add_metric(self, metric: PerformanceMetric):
        with self._lock:
            self._metrics[metric.metric_type].append(metric)

    def discover_patterns(self) -> List[KnowledgePattern]:
        with self._lock:
            recent = self._samples[-100:]
            if len(recent) < 10:
                return []
            patterns = []
            intent_groups: Dict[str, List[InteractionSample]] = defaultdict(list)
            for s in recent:
                sig = s.intent_signature.get("type", "unknown")
                intent_groups[sig].append(s)
            for intent_type, samples in intent_groups.items():
                total = len(samples)
                successes = sum(1 for s in samples if s.success)
                if total >= 3:
                    patterns.append(KnowledgePattern(
                        pattern_type="intent",
                        pattern_text=f"intent:{intent_type}",
                        occurrence_count=total, success_count=successes,
                        failure_count=total - successes,
                        success_rate=successes / max(total, 1),
                    ))
            self._patterns = patterns
            return patterns

    def propose_improvement(self, metric_type: str) -> Optional[EvolutionStrategy]:
        metrics = self._metrics.get(metric_type, [])
        if len(metrics) < 5:
            return None
        recent = metrics[-10:]
        values = [m.value for m in recent]
        avg = sum(values) / len(values)
        prev_avg = sum(m.previous_value for m in recent[:5]) / 5
        if prev_avg > 0 and avg < prev_avg * 0.8:
            return EvolutionStrategy(
                name=f"improve_{metric_type}",
                description=f"Recent {metric_type} dropped to {avg:.2f}",
                action=f"optimize_{metric_type}",
                trigger_condition=f"{metric_type}_below_{avg:.2f}",
            )
        return None

    def apply_strategy(self, strategy: EvolutionStrategy) -> bool:
        with self._lock:
            strategy.total_applied += 1
            if strategy not in self._strategies:
                self._strategies.append(strategy)
            return True

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            recent = self._samples[-50:]
            return {
                "total_samples": len(self._samples),
                "recent_success_rate": (
                    sum(1 for s in recent if s.success) / max(len(recent), 1)),
                "patterns_discovered": len(self._patterns),
                "active_strategies": sum(1 for s in self._strategies if s.active),
                "metrics_tracked": list(self._metrics.keys()),
            }


class Reflector:
    def analyze_batch(self, records: List[ExecutionRecord]) -> ReflectionReport:
        if not records:
            return ReflectionReport(batch_size=0)

        successes = [r for r in records if r.success]
        success_rate = len(successes) / len(records)

        error_counts: Dict[str, int] = {}
        for r in records:
            if not r.success:
                for err in r.errors:
                    error_counts[err] = error_counts.get(err, 0) + 1

        common_errors = sorted(error_counts, key=error_counts.get, reverse=True)[:5]
        patterns = []
        if success_rate < 0.5:
            patterns.append("low_success_rate")
        if any("timeout" in str(e).lower() for e in common_errors):
            patterns.append("frequent_timeouts")
        if any("token" in str(e).lower() for e in common_errors):
            patterns.append("token_limit_issues")

        suggestions = []
        if success_rate < 0.7:
            suggestions.append("Enable deep reasoning mode for complex tasks")
            suggestions.append("Increase task decomposition granularity")
        if success_rate < 0.4:
            suggestions.append("Consider model tier upgrade")
            suggestions.append("Add explicit retry logic")

        complexity_scores = [r.complexity for r in records if r.complexity > 0]
        avg_complexity = sum(complexity_scores) / max(len(complexity_scores), 1)
        if avg_complexity > 0.6 and success_rate < 0.5:
            suggestions.append("High complexity tasks may need Thinking mode")

        return ReflectionReport(
            batch_size=len(records),
            success_rate=success_rate,
            avg_duration_ms=sum(r.duration_ms for r in records) / len(records),
            avg_tokens=int(sum(r.tokens_used for r in records) / len(records)),
            common_errors=common_errors,
            patterns_found=patterns,
            suggested_improvements=suggestions,
            overall_score=max(0.1, success_rate * 0.7 + min(1.0, 1000 / max(1, sum(r.duration_ms for r in records) / len(records))) * 0.3),
        )


class Optimizer:
    def __init__(self):
        self._pattern_library = PatternLibrary()
        self._safety_gate = SafetyGate()

    def propose_improvements(self, report: ReflectionReport) -> List[ImprovementProposal]:
        proposals = []
        if report.success_rate < 0.5:
            proposals.append(ImprovementProposal(
                description="Enable smart routing fallback strategy",
                category="routing", expected_impact=0.5, risk_level=0.1,
                changes={"enable_fallback": True, "complexity_threshold": 0.4}))
        if report.avg_tokens > 3000:
            proposals.append(ImprovementProposal(
                description="Enable context compression",
                category="strategy", expected_impact=0.4, risk_level=0.2,
                changes={"enable_compression": True, "max_context_tokens": 2048}))
        if report.avg_duration_ms > 5000:
            proposals.append(ImprovementProposal(
                description="Add caching layer for frequent queries",
                category="performance", expected_impact=0.6, risk_level=0.15,
                changes={"enable_cache": True, "cache_ttl_seconds": 3600}))
        return proposals

    def validate(self, proposal: ImprovementProposal) -> Tuple[bool, str]:
        return self._safety_gate.evaluate(proposal)


class Repairer:
    def auto_fix(self, error: str) -> Optional[str]:
        known = {
            "timeout": "retry",
            "connection": "retry_with_backoff",
            "token limit": "truncate_input",
            "out of memory": "reduce_batch",
            "rate limit": "wait_and_retry",
            "api key": "check_config",
            "model not found": "switch_to_fallback",
        }
        for pattern, fix in known.items():
            if pattern in error.lower():
                return fix
        return None


class EvolutionEngine:
    def __init__(self):
        self.reflector = Reflector()
        self.optimizer = Optimizer()
        self.repairer = Repairer()
        self.learner = SelfLearningEngine()
        self.ab_engine = ABTestEngine()
        self._history: List[ExecutionRecord] = []
        self._adopted: List[ImprovementProposal] = []
        self._lock = Lock()

    def record_execution(self, record: ExecutionRecord):
        with self._lock:
            self._history.append(record)
            if len(self._history) > 500:
                self._history = self._history[-500:]
            self.optimizer._pattern_library.record_success(
                record.intent_type, record.complexity) if record.success else \
                self.optimizer._pattern_library.record_failure(
                    record.intent_type, record.complexity,
                    ";".join(record.errors) if record.errors else "unknown")

    def reflect(self, batch_size: int = None) -> ReflectionReport:
        with self._lock:
            batch = self._history[-batch_size:] if batch_size else self._history[-50:]
        return self.reflector.analyze_batch(batch)

    def evolve(self) -> List[ImprovementProposal]:
        return self.optimizer.propose_improvements(self.reflect())

    def adopt(self, proposal: ImprovementProposal) -> Tuple[bool, str]:
        ok, reason = self.optimizer.validate(proposal)
        if not ok:
            return False, reason
        proposal.status = "adopted"
        proposal.adopted_at = datetime.now()
        with self._lock:
            self._adopted.append(proposal)
        return True, "adopted"

    def rollback(self, proposal_id: str) -> bool:
        with self._lock:
            for p in self._adopted:
                if p.id == proposal_id and p.status == "adopted":
                    p.status = "rolled_back"
                    p.rolled_back_at = datetime.now()
                    return True
        return False

    def should_evolve(self) -> bool:
        with self._lock:
            if len(self._history) < 10:
                return False
            recent = self._history[-10:]
            fail_rate = sum(1 for r in recent if not r.success) / len(recent)
            return fail_rate > 0.3

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            recent = self._history[-100:]
            return {
                "total_executions": len(self._history),
                "recent_success_rate": (
                    sum(1 for r in recent if r.success) / max(len(recent), 1)),
                "adopted_improvements": len(self._adopted),
                "rolled_back": sum(1 for p in self._adopted
                                   if p.status == "rolled_back"),
                "learner_stats": self.learner.get_stats(),
            }

    def diagnose(self) -> Dict[str, Any]:
        report = self.reflect()
        pattern_likely_fail = self.optimizer._pattern_library.likely_to_fail(
            "", 0.0)

        return {
            "recent_success_rate": report.success_rate,
            "common_errors": report.common_errors,
            "suggestions": report.suggested_improvements,
            "likely_failure": pattern_likely_fail,
            "safety_gate": self.optimizer._safety_gate.stats,
            "overall_score": report.overall_score,
        }


class AdaptiveCompressionStrategy:
    def __init__(self, default_max_tokens: int = 8000):
        self.default_max_tokens = default_max_tokens

    def compress(self, context: str, target_tokens: int = 4000) -> str:
        if len(context) <= target_tokens * 4:
            return context
        lines = context.split("\n")
        result, tokens = [], 0
        for line in reversed(lines):
            line_tokens = len(line) // 4
            if tokens + line_tokens > target_tokens and result:
                break
            result.insert(0, line)
            tokens += line_tokens
        return "\n".join(result)


class EvolutionController:
    def __init__(self, engine: Optional[EvolutionEngine] = None):
        self.engine = engine or EvolutionEngine()
        self.status = EvolutionStatus.STABLE
        self._cycle_count = 0

    def should_trigger(self) -> bool:
        self._cycle_count += 1
        if self._cycle_count % 10 == 0:
            return self.engine.should_evolve()
        return False

    def trigger_evolution(self) -> List[ImprovementProposal]:
        self.status = EvolutionStatus.LEARNING
        proposals = self.engine.evolve()
        if proposals:
            self.status = EvolutionStatus.IMPROVING
        else:
            self.status = EvolutionStatus.STABLE
        return proposals


__all__ = [
    "EvolutionEngine", "SelfLearningEngine",
    "Reflector", "Optimizer", "Repairer",
    "AdaptiveCompressionStrategy", "EvolutionController",
    "PatternLibrary", "SafetyGate", "ABTestEngine",
    "InteractionSample", "PerformanceMetric", "KnowledgePattern",
    "EvolutionStrategy", "ExecutionRecord",
    "ReflectionReport", "ImprovementProposal",
    "EvolutionStatus", "LearningType", "MetricType",
]
