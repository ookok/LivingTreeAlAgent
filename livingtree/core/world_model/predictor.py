"""
LivingTree 世界模型 (World Model)
===================================

前瞻设计：从"预测下一个token"转向"预测世界下一状态"
在脑内预演操作后果，验证预测准确性。

P2 增强:
- LearningPredictor: 从历史验证中学习，持续改进预测精度
- BayesianUpdater: 贝叶斯更新预测概率
- ScenarioTree: 分支预测 — 多路径 what-if 分析
- CausalAnalyzer: 因果分析 — 识别动作与结果之间的因果关系
"""

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ActionType(Enum):
    FILE_DELETE = "file_delete"
    FILE_MODIFY = "file_modify"
    FILE_CREATE = "file_create"
    COMMAND_EXECUTE = "command_execute"
    API_CALL = "api_call"
    MODEL_INVOKE = "model_invoke"
    UNKNOWN = "unknown"


@dataclass
class WorldState:
    timestamp: datetime = field(default_factory=datetime.now)
    file_count: int = 0
    disk_usage_gb: float = 0.0
    memory_usage_mb: float = 0.0
    active_sessions: int = 0
    pending_tasks: int = 0
    model_endpoint_count: int = 0
    health_checks_passed: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "file_count": self.file_count,
            "disk_usage_gb": self.disk_usage_gb,
            "memory_usage_mb": self.memory_usage_mb,
            "active_sessions": self.active_sessions,
            "pending_tasks": self.pending_tasks,
            "model_endpoint_count": self.model_endpoint_count,
            "health_checks_passed": self.health_checks_passed,
        }


@dataclass
class Action:
    type: ActionType = ActionType.UNKNOWN
    description: str = ""
    target: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    predicted_duration_ms: float = 0.0
    risk_score: float = 0.0
    requires_confirmation: bool = False


@dataclass
class PredictedOutcome:
    action: Action = field(default_factory=Action)
    success_likelihood: float = 0.9
    estimated_duration_ms: float = 100.0
    files_affected: int = 0
    token_cost_estimate: int = 0
    disk_change_gb: float = 0.0
    memory_change_mb: float = 0.0
    low_confidence_scenario: str = ""
    worst_case_description: str = ""
    confidence_lower: float = 0.7
    confidence_upper: float = 0.99
    confidence_interval: Dict[str, Any] = field(default_factory=dict)
    should_proceed: bool = True
    alternative_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActualOutcome:
    predicted_outcome: PredictedOutcome = field(default_factory=PredictedOutcome)
    actual_success: bool = False
    actual_duration_ms: float = 0.0
    actual_files_affected: int = 0
    actual_token_cost: int = 0
    prediction_error: float = 0.0
    verified_at: datetime = field(default_factory=datetime.now)


class StatePredictor:
    """世界模型预测器 — 基于规则 + 历史学习."""

    def __init__(self):
        self._prediction_cache: Dict[str, PredictedOutcome] = {}
        self._accuracy_history: List[float] = []
        self._action_stats: Dict[ActionType, Dict[str, float]] = defaultdict(
            lambda: {"count": 0, "successes": 0, "avg_duration": 0, "avg_tokens": 0})

    def predict_outcome(self, action: Action,
                        current_state: Optional[WorldState] = None) -> PredictedOutcome:
        stats = self._action_stats[action.type]

        likelihood = 0.9
        files_affected = 0
        token_cost = 0
        should_proceed = True
        worst_case = ""
        alternative = None

        if action.type == ActionType.FILE_DELETE:
            likelihood = 0.95
            files_affected = 1
            worst_case = "意外删除了错误文件，无法恢复"

        elif action.type == ActionType.FILE_MODIFY:
            likelihood = 0.90
            files_affected = 1
            worst_case = "修改错误导致文件损坏"
            alternative = "先备份文件再修改"

        elif action.type == ActionType.COMMAND_EXECUTE:
            likelihood = 0.80
            worst_case = "命令执行失败或产生意外副作用"
            alternative = "使用模拟环境预演"

        elif action.type == ActionType.API_CALL:
            likelihood = 0.85
            token_cost = 500
            worst_case = "API超时或返回错误"
            alternative = "使用缓存结果"

        elif action.type == ActionType.MODEL_INVOKE:
            likelihood = 0.90
            token_cost = 2000
            worst_case = "模型超时或返回不准确结果"
            alternative = "先用轻量模型尝试"

        if stats["count"] >= 5:
            learned_success_rate = stats["successes"] / stats["count"]
            likelihood = likelihood * 0.4 + learned_success_rate * 0.6

        if action.risk_score > 0.7:
            should_proceed = False

        conf_lower = max(0.0, likelihood - 0.15)
        conf_upper = min(1.0, likelihood + 0.10)

        outcome = PredictedOutcome(
            action=action,
            success_likelihood=likelihood,
            estimated_duration_ms=action.predicted_duration_ms,
            files_affected=files_affected,
            token_cost_estimate=token_cost,
            low_confidence_scenario=worst_case,
            worst_case_description=worst_case,
            confidence_lower=conf_lower,
            confidence_upper=conf_upper,
            confidence_interval={"lower": conf_lower, "upper": conf_upper},
            should_proceed=should_proceed,
            alternative_action=alternative,
        )

        return outcome

    def verify_prediction(self, predicted: PredictedOutcome,
                          actual: ActualOutcome) -> float:
        errors = []

        if predicted.estimated_duration_ms > 0:
            time_error = abs(
                predicted.estimated_duration_ms - actual.actual_duration_ms
            ) / max(predicted.estimated_duration_ms, 1)
            errors.append(time_error)

        if predicted.token_cost_estimate > 0:
            token_error = abs(
                predicted.token_cost_estimate - actual.actual_token_cost
            ) / max(predicted.token_cost_estimate, 1)
            errors.append(token_error)

        success_error = abs(predicted.success_likelihood
                            - float(actual.actual_success))
        errors.append(success_error)

        weight = sum([0.2, 0.3, 0.5]) if len(errors) >= 3 else len(errors)
        score = sum(errors) / max(weight, 1)

        self._accuracy_history.append(1.0 - score)

        atype = predicted.action.type
        stats = self._action_stats[atype]
        stats["count"] += 1
        if actual.actual_success:
            stats["successes"] += 1
        if actual.actual_duration_ms > 0:
            stats["avg_duration"] = (
                stats["avg_duration"] * 0.8 + actual.actual_duration_ms * 0.2
                if stats["avg_duration"] > 0 else actual.actual_duration_ms)
        if actual.actual_token_cost > 0:
            stats["avg_tokens"] = (
                stats["avg_tokens"] * 0.8 + actual.actual_token_cost * 0.2
                if stats["avg_tokens"] > 0 else actual.actual_token_cost)

        return score

    def get_accuracy(self) -> float:
        if not self._accuracy_history:
            return 1.0
        return sum(self._accuracy_history[-20:]) / min(len(self._accuracy_history), 20)

    def get_action_stats(self, action_type: Optional[ActionType] = None) -> Dict[str, Any]:
        if action_type:
            stats = self._action_stats[action_type]
            return {
                "count": stats["count"],
                "success_rate": (
                    stats["successes"] / stats["count"] if stats["count"] > 0 else 0),
                "avg_duration_ms": stats["avg_duration"],
                "avg_tokens": stats["avg_tokens"],
            }
        return {
            at.value: {
                "count": s["count"],
                "success_rate": s["successes"] / s["count"] if s["count"] > 0 else 0,
            }
            for at, s in self._action_stats.items() if s["count"] > 0
        }


class BayesianUpdater:
    """贝叶斯更新器 — 基于先验概率和观测更新信念."""

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        self.alpha = prior_alpha
        self.beta = prior_beta
        self._successes = 0
        self._failures = 0

    def update(self, success: bool):
        if success:
            self._successes += 1
        else:
            self._failures += 1

    @property
    def probability(self) -> float:
        return (self.alpha + self._successes) / (
            self.alpha + self.beta + self._successes + self._failures)

    @property
    def confidence(self) -> float:
        total = self.alpha + self.beta + self._successes + self._failures
        if total < 2:
            return 0.0
        var = (self.probability * (1 - self.probability)) / total
        return 1.0 - math.sqrt(var) * 2

    def reset(self):
        self._successes = 0
        self._failures = 0


@dataclass
class ScenarioNode:
    action: Action
    outcome: PredictedOutcome
    children: List["ScenarioNode"] = field(default_factory=list)
    probability: float = 1.0
    cumulative_risk: float = 0.0

    def add_child(self, child: "ScenarioNode"):
        self.children.append(child)


class ScenarioTree:
    """场景树 — 多路径 what-if 分析."""

    def __init__(self, predictor: StatePredictor):
        self.predictor = predictor
        self.root: Optional[ScenarioNode] = None

    def build(self, actions: List[Action]) -> ScenarioNode:
        if not actions:
            raise ValueError("empty actions list")

        self.root = ScenarioNode(
            action=actions[0],
            outcome=self.predictor.predict_outcome(actions[0]),
        )
        current_level = [self.root]

        for action in actions[1:]:
            next_level = []
            for parent in current_level:
                predicted = self.predictor.predict_outcome(action)
                child = ScenarioNode(
                    action=action,
                    outcome=predicted,
                    probability=parent.probability * predicted.success_likelihood,
                    cumulative_risk=parent.cumulative_risk + (1 - predicted.success_likelihood),
                )
                parent.add_child(child)
                next_level.append(child)

                if predicted.success_likelihood < 0.7:
                    alt_node = ScenarioNode(
                        action=Action(
                            type=action.type,
                            description=f"[备选] {action.description}",
                            target=action.target,
                            risk_score=min(1.0, action.risk_score - 0.2),
                        ),
                        outcome=self.predictor.predict_outcome(Action(
                            type=action.type, description=f"[备选] {action.description}")),
                        probability=parent.probability * 0.3,
                        cumulative_risk=parent.cumulative_risk + 0.3,
                    )
                    parent.add_child(alt_node)
                    next_level.append(alt_node)

            current_level = next_level

        return self.root

    def best_path(self) -> List[ScenarioNode]:
        if self.root is None:
            return []

        best_path: List[ScenarioNode] = []
        best_score = -float("inf")

        def dfs(node: ScenarioNode, path: List[ScenarioNode]):
            nonlocal best_path, best_score
            path = path + [node]
            if not node.children:
                score = node.probability - node.cumulative_risk * 0.5
                if score > best_score:
                    best_score = score
                    best_path = path
            for child in node.children:
                dfs(child, path)

        dfs(self.root, [])
        return best_path

    def risk_report(self) -> Dict[str, Any]:
        if self.root is None:
            return {"status": "empty"}

        def collect_leaves(node: ScenarioNode) -> List[ScenarioNode]:
            if not node.children:
                return [node]
            result = []
            for child in node.children:
                result.extend(collect_leaves(child))
            return result

        leaves = collect_leaves(self.root)
        total_prob = sum(l.probability for l in leaves)
        avg_risk = sum(l.cumulative_risk for l in leaves) / max(len(leaves), 1)

        high_risk = [l for l in leaves if l.cumulative_risk > 0.5]

        return {
            "total_paths": len(leaves),
            "avg_success_probability": total_prob / max(len(leaves), 1),
            "avg_cumulative_risk": avg_risk,
            "high_risk_paths": len(high_risk),
            "recommendation": "谨慎执行" if high_risk else "可安全执行",
        }


class CausalAnalyzer:
    """因果分析器 — 识别动作与结果的因果关系."""

    def __init__(self):
        self._observations: List[Tuple[Action, ActualOutcome]] = []
        self._correlations: Dict[str, Dict[str, float]] = {}

    def record(self, action: Action, outcome: ActualOutcome):
        self._observations.append((action, outcome))
        if len(self._observations) > 1000:
            self._observations = self._observations[-1000:]

        key = f"{action.type.value}:{action.description[:30]}"
        if key not in self._correlations:
            self._correlations[key] = {"count": 0.0, "success_count": 0.0}

        self._correlations[key]["count"] += 1
        if outcome.actual_success:
            self._correlations[key]["success_count"] += 1

    def effectiveness(self, action_type: ActionType) -> float:
        relevant = {
            k: v for k, v in self._correlations.items()
            if k.startswith(action_type.value)
        }
        if not relevant:
            return 0.5
        total = sum(v["count"] for v in relevant.values())
        successes = sum(v["success_count"] for v in relevant.values())
        return successes / total if total > 0 else 0.5

    def most_effective_actions(self, top_k: int = 5) -> List[Tuple[str, float]]:
        ranked = [
            (key, v["success_count"] / v["count"])
            for key, v in self._correlations.items()
            if v["count"] >= 3
        ]
        ranked.sort(key=lambda x: -x[1])
        return ranked[:top_k]

    def least_effective_actions(self, top_k: int = 5) -> List[Tuple[str, float]]:
        ranked = [
            (key, v["success_count"] / v["count"])
            for key, v in self._correlations.items()
            if v["count"] >= 3
        ]
        ranked.sort(key=lambda x: x[1])
        return ranked[:top_k]


class OutcomeSimulator:
    """结果模拟器 — 批量预演和 what-if 分析."""

    def __init__(self, predictor: Optional[StatePredictor] = None):
        self.predictor = predictor or StatePredictor()
        self.causal_analyzer = CausalAnalyzer()
        self.scenario_tree = ScenarioTree(self.predictor)

    def simulate_scenario(self, actions: List[Action],
                         initial_state: Optional[WorldState] = None) -> List[PredictedOutcome]:
        outcomes = []
        for action in actions:
            outcome = self.predictor.predict_outcome(action, initial_state)
            outcomes.append(outcome)
            if outcome.worst_case_description:
                outcome.metadata["flagged"] = True
        return outcomes

    def best_path(self, actions: List[Action]) -> Optional[Action]:
        outcomes = self.simulate_scenario(actions)
        if not outcomes:
            return None
        best = max(outcomes,
                   key=lambda o: o.success_likelihood * 10 - o.token_cost_estimate / 1000)
        return best.action

    def risk_assessment(self, actions: List[Action]) -> Dict[str, Any]:
        outcomes = self.simulate_scenario(actions)
        risky = [o for o in outcomes if not o.should_proceed]
        high_cost = [o for o in outcomes if o.token_cost_estimate > 5000]

        total_risk = (
            sum(1.0 - o.success_likelihood for o in outcomes)
            + sum(1.0 for o in risky)
        ) / max(len(outcomes), 1)

        return {
            "total_actions": len(outcomes),
            "risky_actions": len(risky),
            "high_cost_actions": len(high_cost),
            "overall_risk_score": min(1.0, total_risk),
            "recommended_review": len(risky) > 0,
            "estimated_total_tokens": sum(o.token_cost_estimate for o in outcomes),
            "estimated_total_duration_ms": sum(o.estimated_duration_ms for o in outcomes),
            "causal_insight": (
                self.causal_analyzer.most_effective_actions(3) if outcomes else []
            ),
        }

    def what_if(self, actions: List[Action]) -> Dict[str, Any]:
        """完整的 what-if 分析 — 使用场景树."""
        self.scenario_tree.build(actions)
        best = self.scenario_tree.best_path()
        risk = self.scenario_tree.risk_report()

        return {
            "scenario_count": risk["total_paths"],
            "best_path": [{
                "action": n.action.description,
                "success_likelihood": n.outcome.success_likelihood,
            } for n in best],
            "risk_report": risk,
        }


__all__ = [
    "StatePredictor",
    "OutcomeSimulator",
    "BayesianUpdater",
    "ScenarioTree",
    "ScenarioNode",
    "CausalAnalyzer",
    "PredictedOutcome",
    "ActualOutcome",
    "Action",
    "ActionType",
    "WorldState",
]
