"""
调度决策引擎 (Scheduler)
=========================

为每个任务找到最经济的执行方案的综合决策系统。

核心策略：
1. 预算优先：严格遵守用户预算约束
2. 质量优先：确保满足最低质量要求
3. 速度优先：最小化用户等待时间
4. 成本优先：最小化积分消耗
5. 均衡模式：综合考虑多维度因素

不是简单地"选最便宜插件"，而是综合考虑：
- 直接积分消耗
- 时间积分成本（用户时间价值）
- 质量要求
- 用户偏好
- 实时负载
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
from threading import RLock
import time

from .credit_registry import CreditRegistry, UserCreditProfile, PluginCreditProfile
from .task_estimator import TaskEstimator, TaskSpec, EstimationResult


class SchedulingStrategy(Enum):
    """调度策略"""
    BUDGET_FIRST = "budget_first"         # 预算优先
    QUALITY_FIRST = "quality_first"       # 质量优先
    SPEED_FIRST = "speed_first"           # 速度优先
    COST_FIRST = "cost_first"             # 成本优先
    BALANCED = "balanced"                 # 均衡模式


@dataclass
class SchedulingDecision:
    """
    调度决策结果

    包含选中的插件、备选方案、以及决策理由。
    """
    task_id: str
    strategy: SchedulingStrategy

    # 主要决策
    selected_plugin_id: str
    selected_plugin_name: str
    estimation: EstimationResult

    # 备选方案
    alternatives: List[EstimationResult] = field(default_factory=list)

    # 决策信息
    decision_time_ms: float = 0.0         # 决策耗时
    reasoning: str = ""                   # 决策理由
    warning: str = ""                     # 警告信息
    timestamp: float = field(default_factory=time.time)

    # 执行状态
    status: str = "pending"               # pending/ executing/ completed/ failed
    execution_start_time: Optional[float] = None
    execution_end_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "strategy": self.strategy.value,
            "selected_plugin_id": self.selected_plugin_id,
            "selected_plugin_name": self.selected_plugin_name,
            "estimation": self.estimation.to_dict(),
            "alternatives": [a.to_dict() for a in self.alternatives],
            "decision_time_ms": self.decision_time_ms,
            "reasoning": self.reasoning,
            "warning": self.warning,
            "timestamp": self.timestamp,
            "status": self.status,
        }


@dataclass
class SchedulingConstraint:
    """调度约束"""
    min_quality: int = 60                 # 最低质量
    max_credits: float = 1000.0          # 最大积分消耗
    max_wait_time: float = 60.0           # 最大等待时间（秒）
    allowed_plugins: List[str] = field(default_factory=list)  # 允许的插件
    blocked_plugins: List[str] = field(default_factory=list)  # 禁用的插件
    force_plugin: Optional[str] = None     # 强制使用某插件


class Scheduler:
    """
    调度决策引擎

    核心职责：
    1. 根据策略选择最优插件
    2. 处理复杂约束
    3. 提供备选方案
    4. 记录决策历史
    """

    _instance = None
    _lock = RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.registry = CreditRegistry.get_instance()
        self.estimator = TaskEstimator(self.registry)

        # 用户配置
        self._current_user: Optional[UserCreditProfile] = None

        # 策略配置
        self._default_strategy = SchedulingStrategy.BALANCED

        # 决策历史
        self._history: List[SchedulingDecision] = []

        # 观察者回调
        self._observers: Dict[str, List[Callable]] = {}

        # 负载状态（模拟）
        self._plugin_loads: Dict[str, float] = {}  # plugin_id -> current_load (0-1)

    @classmethod
    def get_instance(cls) -> 'Scheduler':
        return cls()

    def set_user(self, user: UserCreditProfile) -> None:
        """设置当前用户"""
        self._current_user = user

    def set_strategy(self, strategy: SchedulingStrategy) -> None:
        """设置默认策略"""
        self._default_strategy = strategy

    # ==================== 核心调度 ====================

    def schedule(
        self,
        task: TaskSpec,
        strategy: Optional[SchedulingStrategy] = None,
        constraint: Optional[SchedulingConstraint] = None
    ) -> SchedulingDecision:
        """
        调度任务

        Args:
            task: 任务规格
            strategy: 调度策略（可选，使用默认策略）
            constraint: 额外约束（可选）

        Returns:
            调度决策
        """
        start_time = time.time()
        strategy = strategy or self._default_strategy

        # 应用用户配置约束
        if self._current_user and constraint is None:
            constraint = SchedulingConstraint(
                min_quality=max(constraint.min_quality if constraint else 0, self._current_user.quality_preference),
                max_credits=self._current_user.budget_per_task,
                max_wait_time=self._current_user.max_wait_time_sec,
                blocked_plugins=self._current_user.blocked_plugins,
            )

        # 决策
        decision = self._make_decision(task, strategy, constraint)
        decision.decision_time_ms = (time.time() - start_time) * 1000

        # 记录历史
        self._history.append(decision)
        if len(self._history) > 1000:
            self._history = self._history[-1000:]

        return decision

    def _make_decision(
        self,
        task: TaskSpec,
        strategy: SchedulingStrategy,
        constraint: Optional[SchedulingConstraint]
    ) -> SchedulingDecision:
        """执行决策逻辑"""

        # 获取候选插件
        candidates = self._get_candidates(task, constraint)

        if not candidates:
            return self._create_no_plugin_decision(task, strategy, "没有找到符合条件的插件")

        # 估算所有候选
        estimations = []
        for plugin in candidates:
            est = self.estimator.estimate(task, plugin, self._current_user)
            if est.is_feasible:
                # 应用负载因素（繁忙插件成本略高）
                est = self._apply_load_factor(est, plugin)
                estimations.append(est)

        if not estimations:
            return self._create_no_plugin_decision(task, strategy, "所有候选插件都不可行")

        # 根据策略排序
        sorted_estimations = self._sort_by_strategy(estimations, strategy)

        # 选择最佳
        best = sorted_estimations[0]
        alternatives = sorted_estimations[1:6]  # 前5个备选

        # 构建决策
        decision = SchedulingDecision(
            task_id=task.task_id,
            strategy=strategy,
            selected_plugin_id=best.plugin_id,
            selected_plugin_name=best.plugin_name,
            estimation=best,
            alternatives=alternatives,
            reasoning=self._generate_reasoning(best, strategy),
            warning=self._generate_warning(best, alternatives, task),
        )

        return decision

    def _get_candidates(
        self,
        task: TaskSpec,
        constraint: Optional[SchedulingConstraint]
    ) -> List[PluginCreditProfile]:
        """获取候选插件列表"""
        # 基础查询
        candidates = self.registry.list_plugins(
            task_type=task.task_type,
            enabled_only=True,
            min_quality=task.min_quality if not constraint else constraint.min_quality
        )

        # 应用约束过滤
        if constraint:
            # 插件白名单
            if constraint.allowed_plugins:
                candidates = [c for c in candidates if c.plugin_id in constraint.allowed_plugins]

            # 插件黑名单
            if constraint.blocked_plugins:
                candidates = [c for c in candidates if c.plugin_id not in constraint.blocked_plugins]

            # 强制使用某插件
            if constraint.force_plugin:
                forced = self.registry.get_plugin(constraint.force_plugin)
                if forced:
                    return [forced]

        # 用户偏好
        if self._current_user and self._current_user.preferred_plugins:
            # 将偏好插件排在前面
            def sort_key(c: PluginCreditProfile) -> Tuple[int, float]:
                pref_order = self._current_user.preferred_plugins.index(c.plugin_id) \
                    if c.plugin_id in self._current_user.preferred_plugins else 999
                return (pref_order, c.capability.quality_score)
            candidates.sort(key=sort_key)

        return candidates

    def _apply_load_factor(
        self,
        estimation: EstimationResult,
        plugin: PluginCreditProfile
    ) -> EstimationResult:
        """应用负载因素（繁忙时成本略高）"""
        load = self._plugin_loads.get(plugin.plugin_id, 0.0)
        if load > 0.7:
            # 高负载，增加5-15%成本
            factor = 1.0 + (load - 0.7) * 0.5
            estimation.direct_credits *= factor
            estimation.total_credits *= factor
        return estimation

    def _sort_by_strategy(
        self,
        estimations: List[EstimationResult],
        strategy: SchedulingStrategy
    ) -> List[EstimationResult]:
        """根据策略排序"""

        if strategy == SchedulingStrategy.COST_FIRST:
            # 成本优先：按总积分升序
            return sorted(estimations, key=lambda x: x.total_credits)

        elif strategy == SchedulingStrategy.SPEED_FIRST:
            # 速度优先：按时长升序
            return sorted(estimations, key=lambda x: x.estimated_time_sec)

        elif strategy == SchedulingStrategy.QUALITY_FIRST:
            # 质量优先：按质量降序
            return sorted(estimations, key=lambda x: -x.quality_score)

        elif strategy == SchedulingStrategy.BUDGET_FIRST:
            # 预算优先：在预算内选质量最高的
            budget = self._current_user.budget_per_task if self._current_user else float('inf')
            under_budget = [e for e in estimations if e.total_credits <= budget]
            if under_budget:
                return sorted(under_budget, key=lambda x: -x.quality_score)
            # 超出预算，选最便宜的
            return sorted(estimations, key=lambda x: x.total_credits)

        else:  # BALANCED
            # 均衡模式：综合评分 = 0.4*质量 + 0.3*速度 + 0.3*成本
            # 归一化
            max_credits = max(e.total_credits for e in estimations) or 1
            max_time = max(e.estimated_time_sec for e in estimations) or 1

            for e in estimations:
                quality_score_norm = e.quality_score / 100
                time_score_norm = 1 - (e.estimated_time_sec / max_time)
                cost_score_norm = 1 - (e.total_credits / max_credits)
                e._balance_score = 0.4 * quality_score_norm + 0.3 * time_score_norm + 0.3 * cost_score_norm

            return sorted(estimations, key=lambda x: -x._balance_score)

    def _generate_reasoning(
        self,
        best: EstimationResult,
        strategy: SchedulingStrategy
    ) -> str:
        """生成决策理由"""
        strategy_names = {
            SchedulingStrategy.COST_FIRST: "成本优先",
            SchedulingStrategy.SPEED_FIRST: "速度优先",
            SchedulingStrategy.QUALITY_FIRST: "质量优先",
            SchedulingStrategy.BUDGET_FIRST: "预算优先",
            SchedulingStrategy.BALANCED: "均衡模式",
        }

        reason = f"使用【{best.plugin_name}】执行任务。"
        reason += f"预估耗时{best.estimated_time_sec:.1f}秒，"
        reason += f"质量评分{best.quality_score}分，"
        reason += f"总积分消耗{best.total_credits:.1f}。"

        if best.time_credits > 0:
            reason += f"（其中时间成本{best.time_credits:.1f}积分）"

        return reason

    def _generate_warning(
        self,
        best: EstimationResult,
        alternatives: List[EstimationResult],
        task: TaskSpec
    ) -> str:
        """生成警告信息"""
        warnings = []

        # 质量警告
        if best.quality_score < task.min_quality + 10:
            warnings.append(f"质量分数{best.quality_score}接近最低要求{task.min_quality}")

        # 成本警告
        if self._current_user:
            budget_ratio = best.total_credits / self._current_user.budget_per_task
            if budget_ratio > 0.8:
                warnings.append(f"消耗{best.total_credits:.0f}积分，占预算{budget_ratio*100:.0f}%")

        # 时间警告
        if best.estimated_time_sec > task.max_wait_time * 0.8:
            warnings.append(f"预估时间{best.estimated_time_sec:.1f}秒，接近最大等待时间")

        # 有更好选择？
        if len(alternatives) >= 2:
            quality_diff = alternatives[0].quality_score - best.quality_score
            if quality_diff > 10 and best.total_credits > alternatives[0].total_credits * 1.5:
                warnings.append(f"存在更高质量方案（{alternatives[0].plugin_name}），积分差异{(best.total_credits - alternatives[0].total_credits):.0f}")

        return "; ".join(warnings) if warnings else ""

    def _create_no_plugin_decision(
        self,
        task: TaskSpec,
        strategy: SchedulingStrategy,
        reason: str
    ) -> SchedulingDecision:
        """创建无插件可用的决策"""
        return SchedulingDecision(
            task_id=task.task_id,
            strategy=strategy,
            selected_plugin_id="",
            selected_plugin_name="无",
            estimation=EstimationResult(plugin_id="", plugin_name="无", task_id=task.task_id),
            reasoning=reason,
            status="failed"
        )

    # ==================== 负载管理 ====================

    def report_plugin_load(self, plugin_id: str, load: float) -> None:
        """
        上报插件负载（0-1）

        由插件在执行过程中调用。
        """
        self._plugin_loads[plugin_id] = max(0, min(1, load))

    def get_plugin_load(self, plugin_id: str) -> float:
        """获取插件当前负载"""
        return self._plugin_loads.get(plugin_id, 0.0)

    # ==================== 观察者 ====================

    def add_observer(self, event_type: str, callback: Callable) -> None:
        """添加观察者"""
        if event_type not in self._observers:
            self._observers[event_type] = []
        self._observers[event_type].append(callback)

    def _notify_observers(self, event_type: str, data: Any) -> None:
        """通知观察者"""
        for callback in self._observers.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Scheduler observer error: {e}")

    # ==================== 历史 ====================

    def get_history(
        self,
        task_id: Optional[str] = None,
        limit: int = 10
    ) -> List[SchedulingDecision]:
        """获取决策历史"""
        history = self._history
        if task_id:
            history = [h for h in history if h.task_id == task_id]
        return history[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """获取调度统计"""
        if not self._history:
            return {}

        total = len(self._history)
        plugins_used = {}
        total_credits = 0
        total_time_ms = 0

        for decision in self._history:
            if decision.selected_plugin_id:
                plugins_used[decision.selected_plugin_id] = \
                    plugins_used.get(decision.selected_plugin_id, 0) + 1
            total_credits += decision.estimation.total_credits
            total_time_ms += decision.decision_time_ms

        return {
            "total_decisions": total,
            "plugins_usage": plugins_used,
            "avg_credits": total_credits / total if total else 0,
            "avg_decision_time_ms": total_time_ms / total if total else 0,
        }


def get_scheduler() -> Scheduler:
    """获取调度器单例"""
    return Scheduler.get_instance()
