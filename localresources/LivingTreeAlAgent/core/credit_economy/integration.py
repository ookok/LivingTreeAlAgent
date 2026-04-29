"""
积分经济模型集成模块
=====================

将积分经济模型与现有 Hermes Desktop 系统集成：
1. 与 PluginManager 集成
2. 与 EventBus 集成
3. 提供 UI 接口
"""

from typing import Dict, List, Optional, Any, Callable
from threading import RLock

from .credit_registry import CreditRegistry, PluginCreditProfile, UserCreditProfile, TaskType
from .task_estimator import TaskEstimator, TaskSpec, EstimationResult
from .scheduler import Scheduler, Scheduler as SchedClass, SchedulingDecision, SchedulingStrategy
from .learning import CreditLearning
from .dag_orchestrator import DAGOrchestrator, WorkflowSpec, ExecutionPlan
from .transaction_ledger import TransactionLedger, Transaction, TransactionType


class CreditEconomyManager:
    """
    积分经济模型管理器

    统一管理所有积分相关功能，提供简化的接口。
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

        # 核心组件
        self.registry = CreditRegistry.get_instance()
        self.estimator = TaskEstimator(self.registry)
        self.scheduler = Scheduler.get_instance()
        self.learning = CreditLearning.get_instance()
        self.dag_orchestrator = DAGOrchestrator.get_instance()
        self.ledger = TransactionLedger.get_instance()

        # 当前用户
        self._current_user_id: str = "default"

        # 观察者
        self._observers: Dict[str, List[Callable]] = {}

        # 初始化预置插件
        self.registry.register_preset_plugins()

    @classmethod
    def get_instance(cls) -> 'CreditEconomyManager':
        return cls()

    # ==================== 用户管理 ====================

    def set_current_user(self, user_id: str) -> None:
        """设置当前用户"""
        self._current_user_id = user_id
        user = self.registry.get_user(user_id)
        if user:
            self.scheduler.set_user(user)

    def get_current_user(self) -> UserCreditProfile:
        """获取当前用户"""
        return self.registry.get_user(self._current_user_id)

    def create_user(
        self,
        user_id: str,
        initial_credits: float = 10000.0,
        time_value_per_hour: float = 200.0,
        quality_preference: int = 80
    ) -> UserCreditProfile:
        """创建用户"""
        user = UserCreditProfile(
            user_id=user_id,
            total_credits=initial_credits,
            time_value_per_hour=time_value_per_hour,
            quality_preference=quality_preference,
        )
        self.registry.register_user(user)
        self.ledger.get_or_create_account(user_id, initial_balance=initial_credits)
        return user

    # ==================== 核心调度 ====================

    def schedule_task(
        self,
        task_type: TaskType,
        input_length: int,
        input_data: Any = None,
        task_id: Optional[str] = None,
        strategy: SchedulingStrategy = SchedulingStrategy.BALANCED,
        min_quality: int = 60,
        budget: Optional[float] = None
    ) -> SchedulingDecision:
        """
        调度任务的简便方法

        Args:
            task_type: 任务类型
            input_length: 输入长度
            input_data: 输入数据
            task_id: 任务ID
            strategy: 调度策略
            min_quality: 最低质量
            budget: 任务预算

        Returns:
            调度决策
        """
        user = self.get_current_user()

        task = TaskSpec(
            task_id=task_id or f"task_{int(time.time()*1000)}",
            task_type=task_type,
            input_length=input_length,
            input_data=input_data,
            min_quality=min_quality,
            budget=budget or user.budget_per_task,
        )

        decision = self.scheduler.schedule(task, strategy)

        return decision

    def execute_scheduled_task(
        self,
        decision: SchedulingDecision,
        input_data: Any = None
    ) -> Dict[str, Any]:
        """
        执行调度的任务

        Args:
            decision: 调度决策
            input_data: 输入数据

        Returns:
            执行结果
        """
        # 更新状态
        decision.status = "executing"
        decision.execution_start_time = time.time()

        # 模拟执行（实际会调用对应插件）
        # 这里只是演示，实际使用时会被插件执行逻辑替代
        result = {
            "task_id": decision.task_id,
            "plugin_id": decision.selected_plugin_id,
            "status": "completed",
            "output": f"模拟输出 from {decision.selected_plugin_name}",
        }

        # 更新决策状态
        decision.status = "completed"
        decision.execution_end_time = time.time()

        # 记录积分消耗
        self.ledger.deduct(
            user_id=self._current_user_id,
            amount=decision.estimation.total_credits,
            task_id=decision.task_id,
            plugin_id=decision.selected_plugin_id,
            description=f"任务执行: {decision.task_id}",
        )

        # 记录学习数据
        self.learning.record(
            plugin_id=decision.selected_plugin_id,
            task_id=decision.task_id,
            task_type="",
            predicted_time=decision.estimation.estimated_time_sec,
            actual_time=decision.execution_end_time - decision.execution_start_time,
            predicted_credits=decision.estimation.total_credits,
            actual_credits=decision.estimation.total_credits,
            predicted_quality=decision.estimation.quality_score,
            actual_quality=decision.estimation.quality_score,
        )

        return result

    # ==================== 工作流 ====================

    def create_and_execute_workflow(
        self,
        workflow: WorkflowSpec,
        input_data: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        创建并执行工作流

        Args:
            workflow: 工作流规格
            input_data: 输入数据

        Returns:
            执行计划
        """
        # 生成执行计划
        plan = self.dag_orchestrator.plan(workflow, input_data, self._current_user_id)

        if not plan.is_feasible:
            return plan

        # 模拟执行工作流
        for node_plan in plan.node_plans:
            # 记录积分消耗
            self.ledger.deduct(
                user_id=self._current_user_id,
                amount=node_plan.estimated_credits,
                task_id=node_plan.node_id,
                plugin_id=node_plan.plugin_id,
                workflow_id=workflow.workflow_id,
                description=f"工作流节点: {node_plan.node_id}",
            )

        return plan

    # ==================== 积分管理 ====================

    def get_user_balance(self) -> float:
        """获取当前用户余额"""
        return self.ledger.get_balance(self._current_user_id)

    def recharge_credits(self, amount: float, source: str = "manual") -> Transaction:
        """充值积分"""
        tx = self.ledger.recharge(self._current_user_id, amount, source)
        # 更新用户余额
        self.registry.update_user_credits(self._current_user_id, amount)
        return tx

    def reward_credits(self, amount: float, reason: str) -> Transaction:
        """奖励积分"""
        tx = self.ledger.reward(self._current_user_id, amount, reason)
        self.registry.update_user_credits(self._current_user_id, amount)
        return tx

    # ==================== 统计与分析 ====================

    def get_dashboard(self) -> Dict[str, Any]:
        """获取仪表盘数据"""
        user = self.get_current_user()
        balance = self.get_user_balance()
        summary = self.ledger.get_user_summary(self._current_user_id)
        sched_stats = self.scheduler.get_statistics()
        metrics = self.learning.get_all_metrics()

        return {
            "user": {
                "user_id": self._current_user_id,
                "balance": balance,
                "time_value_per_hour": user.time_value_per_hour,
                "quality_preference": user.quality_preference,
            },
            "ledger": summary,
            "scheduler": sched_stats,
            "learning": {
                pid: {
                    "sample_count": m.sample_count,
                    "avg_satisfaction": m.avg_satisfaction,
                    "prediction_accuracy": m.prediction_accuracy,
                    "suggestions": self.learning.suggest_optimization(pid),
                }
                for pid, m in metrics.items()
            },
            "available_plugins": [
                p.to_dict() for p in self.registry.list_plugins(enabled_only=True)
            ],
        }

    # ==================== 预置工作流 ====================

    def get_video_translation_workflow(self, input_length: int = 0) -> WorkflowSpec:
        """获取视频翻译工作流"""
        return self.dag_orchestrator.create_video_translation_workflow(input_length)

    def get_document_analysis_workflow(self, depth: str = "normal") -> WorkflowSpec:
        """获取文档分析工作流"""
        return self.dag_orchestrator.create_document_analysis_workflow(depth)

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
                print(f"CreditEconomyManager observer error: {e}")


# 辅助函数
import time


def get_credit_economy_manager() -> CreditEconomyManager:
    """获取积分经济模型管理器单例"""
    return CreditEconomyManager.get_instance()
