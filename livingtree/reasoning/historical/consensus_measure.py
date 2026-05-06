"""Historical Logic — Consensus Measure (民心向背律).

历史逻辑第三规律：以实际效果检验成败。

核心机制：
  1. A/B 双轨评估: 新旧方案并行运行，统计指标对比
  2. 用户反馈聚合: 隐式(行为) + 显式(评分) 信号融合
  3. 统计显著性: 基于样本量的置信区间
  4. 决策阈值: 显著性达标 → 自动切换更优方案

应用场景：
  - discard vs compact 策略效果对比
  - 层次分块 vs 普通分块的检索精度对比
  - 多模型性价比 A/B 测试
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class DecisionOutcome(str, Enum):
    A_WINS = "A_wins"        # 方案A胜出
    B_WINS = "B_wins"        # 方案B胜出
    TIE = "tie"              # 无显著差异
    INSUFFICIENT_DATA = "insufficient"  # 数据不足


@dataclass
class TrialResult:
    """单次试验结果。"""
    variant: str              # "A" or "B"
    metric_name: str
    value: float
    user_id: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


@dataclass
class ABComparison:
    """A/B 比较结果。"""
    metric_name: str
    a_mean: float
    b_mean: float
    a_std: float
    b_std: float
    a_count: int
    b_count: int
    improvement: float          # B相对A的改进百分比 (可为负)
    p_value: float              # 统计显著性
    outcome: DecisionOutcome
    confidence_interval: tuple[float, float]  # 95% CI
    recommendation: str = ""


class ConsensusMeasure:
    """民心向背律 — A/B 评估 + 用户反馈聚合。

    通过实际运行效果（而非理论推导）判定策略优劣，
    是历史逻辑"实践检验真理"的工程实现。

    Usage:
        cm = ConsensusMeasure()
        cm.start_experiment("chunking_method", "flat", "hierarchical")
        cm.record("chunking_method", "A", "retrieval_precision", 0.72)
        cm.record("chunking_method", "B", "retrieval_precision", 0.85)
        result = cm.evaluate("chunking_method")
        if result.outcome == DecisionOutcome.B_WINS:
            cm.adopt("chunking_method")  # 切换到B方案
    """

    def __init__(self, name: str = "default", significance_level: float = 0.05):
        self.name = name
        self.significance_level = significance_level
        self._experiments: dict[str, dict[str, Any]] = {}
        self._results: dict[str, list[TrialResult]] = defaultdict(list)
        self._adopted: dict[str, str] = {}
        self._lock = threading.Lock()
        self._min_sample_size = 30

    def start_experiment(
        self, name: str, variant_a: str, variant_b: str, description: str = "",
    ) -> None:
        """启动一个A/B实验。"""
        with self._lock:
            self._experiments[name] = {
                "variant_a": variant_a,
                "variant_b": variant_b,
                "description": description,
                "started_at": time.time(),
                "status": "running",
            }
            logger.info("Consensus[%s]: experiment '%s' started: %s vs %s",
                       self.name, name, variant_a, variant_b)

    def record(
        self, experiment: str, variant: str, metric: str, value: float,
        user_id: str = "", **metadata,
    ) -> None:
        """记录一次试验观测。"""
        with self._lock:
            result = TrialResult(
                variant=variant,
                metric_name=metric,
                value=value,
                user_id=user_id,
                metadata=metadata,
            )
            self._results[experiment].append(result)

    def evaluate(self, experiment: str, metric: str = None,
                 min_samples: int = None) -> ABComparison:
        """评估A/B实验结果。

        使用 Welch's t-test 判断统计显著性。
        """
        min_n = min_samples or self._min_sample_size

        with self._lock:
            trials = self._results.get(experiment, [])

            if metric:
                trials = [t for t in trials if t.metric_name == metric]
            elif trials:
                metric = trials[0].metric_name

            a_trials = [t for t in trials if t.variant == "A"]
            b_trials = [t for t in trials if t.variant == "B"]

            if len(a_trials) < min_n or len(b_trials) < min_n:
                return ABComparison(
                    metric_name=metric or "",
                    a_mean=0.0, b_mean=0.0, a_std=0.0, b_std=0.0,
                    a_count=len(a_trials), b_count=len(b_trials),
                    improvement=0.0, p_value=1.0,
                    outcome=DecisionOutcome.INSUFFICIENT_DATA,
                    confidence_interval=(0.0, 0.0),
                    recommendation=f"Need {min_n} samples per variant",
                )

            a_vals = [t.value for t in a_trials]
            b_vals = [t.value for t in b_trials]

            a_mean = sum(a_vals) / len(a_vals)
            b_mean = sum(b_vals) / len(b_vals)

            a_std = self._std(a_vals)
            b_std = self._std(b_vals)

            improvement = (b_mean - a_mean) / max(abs(a_mean), 0.001)

            p_value = self._welch_ttest(a_vals, b_vals)

            outcome = DecisionOutcome.TIE
            recommendation = ""
            if p_value < self.significance_level:
                if improvement > 0:
                    outcome = DecisionOutcome.B_WINS
                    recommendation = f"B wins: +{improvement:.1%} (p={p_value:.4f})"
                elif improvement < 0:
                    outcome = DecisionOutcome.A_WINS
                    recommendation = f"A wins: {improvement:.1%} (p={p_value:.4f})"
                else:
                    outcome = DecisionOutcome.TIE
                    recommendation = "No practical difference"
            else:
                recommendation = f"Not significant (p={p_value:.4f}, n={len(a_trials)}+{len(b_trials)})"

            ci = self._confidence_interval(a_vals, b_vals)

            logger.info(
                "Consensus[%s]: '%s' %s | A=%.3f±%.3f(n=%d) B=%.3f±%.3f(n=%d) p=%.4f",
                self.name, experiment, outcome.value,
                a_mean, a_std, len(a_vals), b_mean, b_std, len(b_vals), p_value,
            )

            return ABComparison(
                metric_name=metric or "",
                a_mean=a_mean, b_mean=b_mean,
                a_std=a_std, b_std=b_std,
                a_count=len(a_vals), b_count=len(b_vals),
                improvement=improvement, p_value=p_value,
                outcome=outcome,
                confidence_interval=ci,
                recommendation=recommendation,
            )

    def adopt(self, experiment: str) -> str:
        """采纳实验中的更优方案（民心向背：实践决定选择）。"""
        result = self.evaluate(experiment)
        with self._lock:
            if result.outcome == DecisionOutcome.B_WINS:
                self._adopted[experiment] = "B"
                if experiment in self._experiments:
                    self._experiments[experiment]["status"] = "completed"
                    self._experiments[experiment]["adopted"] = "B"
                logger.info("Consensus[%s]: adopting B for '%s'", self.name, experiment)
                return "B"
            elif result.outcome == DecisionOutcome.A_WINS:
                self._adopted[experiment] = "A"
                if experiment in self._experiments:
                    self._experiments[experiment]["status"] = "completed"
                    self._experiments[experiment]["adopted"] = "A"
                logger.info("Consensus[%s]: adopting A for '%s'", self.name, experiment)
                return "A"
            return "tie"

    def get_adopted(self, experiment: str) -> Optional[str]:
        return self._adopted.get(experiment)

    def get_sample_size(self, experiment: str) -> tuple[int, int]:
        trials = self._results.get(experiment, [])
        return (
            sum(1 for t in trials if t.variant == "A"),
            sum(1 for t in trials if t.variant == "B"),
        )

    def all_experiments(self) -> dict[str, dict]:
        result = {}
        for name, exp in self._experiments.items():
            a_n, b_n = self.get_sample_size(name)
            ev = self.evaluate(name)
            result[name] = {
                    **exp,
                    "a_samples": a_n,
                    "b_samples": b_n,
                    "outcome": ev.outcome.value,
                    "improvement": ev.improvement,
                "recommendation": ev.recommendation,
            }
        return result

    @staticmethod
    def _std(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)

    @staticmethod
    def _welch_ttest(a: list[float], b: list[float]) -> float:
        """Welch's t-test (不假设等方差)。"""
        n_a, n_b = len(a), len(b)
        if n_a < 2 or n_b < 2:
            return 1.0

        mean_a = sum(a) / n_a
        mean_b = sum(b) / n_b

        var_a = sum((x - mean_a) ** 2 for x in a) / (n_a - 1)
        var_b = sum((x - mean_b) ** 2 for x in b) / (n_b - 1)

        se = math.sqrt(var_a / n_a + var_b / n_b)
        if se == 0:
            return 0.0 if abs(mean_a - mean_b) < 1e-9 else 1e-10

        t = abs(mean_a - mean_b) / se

        df_num = (var_a / n_a + var_b / n_b) ** 2
        df_den = ((var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1))
        df = df_num / max(df_den, 1e-10)

        # Student's t CDF approximation
        x = df / (df + t * t)
        p = 1 - x

        return min(1.0, max(0.0, p * 2))  # two-tailed

    @staticmethod
    def _confidence_interval(a: list[float], b: list[float]) -> tuple[float, float]:
        """95% CI for the difference of means."""
        n_a, n_b = len(a), len(b)
        if n_a < 2 or n_b < 2:
            return (-float('inf'), float('inf'))

        mean_a = sum(a) / n_a
        mean_b = sum(b) / n_b
        diff = mean_b - mean_a

        var_a = sum((x - mean_a) ** 2 for x in a) / (n_a - 1)
        var_b = sum((x - mean_b) ** 2 for x in b) / (n_b - 1)
        se = math.sqrt(var_a / n_a + var_b / n_b)

        z = 1.96  # 95% CI
        margin = z * se
        return (diff - margin, diff + margin)

    def get_stats(self) -> dict:
        with self._lock:
            running = sum(1 for e in self._experiments.values() if e["status"] == "running")
            completed = sum(1 for e in self._experiments.values() if e["status"] == "completed")
            return {
                "name": self.name,
                "experiments": len(self._experiments),
                "running": running,
                "completed": completed,
                "total_trials": sum(len(v) for v in self._results.values()),
                "adopted": dict(self._adopted),
            }
