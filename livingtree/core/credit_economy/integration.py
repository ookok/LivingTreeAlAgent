"""
CreditEconomyManager - 积分经济模型集成模块
"""

from typing import Dict, List, Optional, Any, Callable
from threading import RLock
import time

from .credit_registry import CreditRegistry, PluginCreditProfile, UserCreditProfile, TaskType
from .task_estimator import TaskEstimator, TaskSpec, EstimationResult
from .scheduler import Scheduler, SchedulingDecision, SchedulingStrategy
from .learning import CreditLearning
from .dag_orchestrator import DAGOrchestrator, WorkflowSpec, ExecutionPlan
from .transaction_ledger import TransactionLedger, Transaction, TransactionType


class CreditEconomyManager:

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
        self.scheduler = Scheduler.get_instance()
        self.learning = CreditLearning.get_instance()
        self.dag_orchestrator = DAGOrchestrator.get_instance()
        self.ledger = TransactionLedger.get_instance()
        self._current_user_id: str = "default"
        self._observers: Dict[str, List[Callable]] = {}
        self.registry.register_preset_plugins()

    @classmethod
    def get_instance(cls) -> 'CreditEconomyManager':
        return cls()

    def set_current_user(self, user_id: str) -> None:
        self._current_user_id = user_id
        user = self.registry.get_user(user_id)
        if user:
            self.scheduler.set_user(user)

    def get_current_user(self) -> UserCreditProfile:
        return self.registry.get_user(self._current_user_id)

    def create_user(
        self,
        user_id: str,
        initial_credits: float = 10000.0,
        time_value_per_hour: float = 200.0,
        quality_preference: int = 80
    ) -> UserCreditProfile:
        user = UserCreditProfile(
            user_id=user_id,
            total_credits=initial_credits,
            time_value_per_hour=time_value_per_hour,
            quality_preference=quality_preference,
        )
        self.registry.register_user(user)
        self.ledger.get_or_create_account(user_id, initial_balance=initial_credits)
        return user

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
        decision.status = "executing"
        decision.execution_start_time = time.time()
        result = {
            "task_id": decision.task_id,
            "plugin_id": decision.selected_plugin_id,
            "status": "completed",
            "output": f"模拟输出 from {decision.selected_plugin_name}",
        }
        decision.status = "completed"
        decision.execution_end_time = time.time()
        self.ledger.deduct(
            user_id=self._current_user_id,
            amount=decision.estimation.total_credits,
            task_id=decision.task_id,
            plugin_id=decision.selected_plugin_id,
            description=f"任务执行: {decision.task_id}",
        )
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

    def create_and_execute_workflow(
        self,
        workflow: WorkflowSpec,
        input_data: Dict[str, Any]
    ) -> ExecutionPlan:
        plan = self.dag_orchestrator.plan(workflow, input_data, self._current_user_id)
        if not plan.is_feasible:
            return plan
        for node_plan in plan.node_plans:
            self.ledger.deduct(
                user_id=self._current_user_id,
                amount=node_plan.estimated_credits,
                task_id=node_plan.node_id,
                plugin_id=node_plan.plugin_id,
                workflow_id=workflow.workflow_id,
                description=f"工作流节点: {node_plan.node_id}",
            )
        return plan

    def get_user_balance(self) -> float:
        return self.ledger.get_balance(self._current_user_id)

    def recharge_credits(self, amount: float, source: str = "manual") -> Transaction:
        tx = self.ledger.recharge(self._current_user_id, amount, source)
        self.registry.update_user_credits(self._current_user_id, amount)
        return tx

    def reward_credits(self, amount: float, reason: str) -> Transaction:
        tx = self.ledger.reward(self._current_user_id, amount, reason)
        self.registry.update_user_credits(self._current_user_id, amount)
        return tx

    def get_dashboard(self) -> Dict[str, Any]:
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

    def get_video_translation_workflow(self, input_length: int = 0) -> WorkflowSpec:
        return self.dag_orchestrator.create_video_translation_workflow(input_length)

    def get_document_analysis_workflow(self, depth: str = "normal") -> WorkflowSpec:
        return self.dag_orchestrator.create_document_analysis_workflow(depth)

    def add_observer(self, event_type: str, callback: Callable) -> None:
        if event_type not in self._observers:
            self._observers[event_type] = []
        self._observers[event_type].append(callback)

    def _notify_observers(self, event_type: str, data: Any) -> None:
        for callback in self._observers.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                print(f"CreditEconomyManager observer error: {e}")


def get_credit_economy_manager() -> CreditEconomyManager:
    return CreditEconomyManager.get_instance()
