"""
BudgetManager - 预算管理器

实现成本认知系统的第二层：预算管理
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import time
from datetime import datetime, timedelta


class BudgetType(Enum):
    TASK = "task"
    SESSION = "session"
    DAILY = "daily"
    PROJECT = "project"


class BudgetStatus(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    EXCEEDED = "exceeded"


@dataclass
class Budget:
    budget_id: str
    budget_type: BudgetType
    amount_usd: float
    spent_usd: float = 0.0
    remaining_usd: float = 0.0
    status: BudgetStatus = BudgetStatus.NORMAL
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    def __post_init__(self):
        self.remaining_usd = self.amount_usd

    def spend(self, amount: float) -> bool:
        if amount <= self.remaining_usd:
            self.spent_usd += amount
            self.remaining_usd -= amount
            self.updated_at = time.time()
            self._update_status()
            return True
        else:
            return False

    def _update_status(self):
        ratio = self.spent_usd / self.amount_usd
        if ratio >= 1.0:
            self.status = BudgetStatus.EXCEEDED
        elif ratio >= 0.8:
            self.status = BudgetStatus.WARNING
        else:
            self.status = BudgetStatus.NORMAL

    def reset(self):
        self.spent_usd = 0.0
        self.remaining_usd = self.amount_usd
        self.status = BudgetStatus.NORMAL
        self.updated_at = time.time()


@dataclass
class SessionBudget:
    session_id: str
    task_budget: Budget = None
    session_budget: Budget = None
    daily_budget: Budget = None

    def get_total_spent(self) -> float:
        total = 0.0
        if self.task_budget:
            total += self.task_budget.spent_usd
        if self.session_budget:
            total += self.session_budget.spent_usd
        return total

    def can_spend(self, amount: float) -> bool:
        if self.task_budget and not self.task_budget.spend(amount):
            return False
        if self.session_budget and not self.session_budget.spend(amount):
            return False
        if self.daily_budget and not self.daily_budget.spend(amount):
            return False
        return True


class BudgetManager:

    def __init__(self):
        self._logger = logger.bind(component="BudgetManager")
        self._budgets: Dict[str, Budget] = {}
        self._session_budgets: Dict[str, SessionBudget] = {}
        self._default_budgets = {
            BudgetType.TASK: {
                "simple": 0.01,
                "medium": 0.1,
                "complex": 1.0,
                "expert": 5.0
            },
            BudgetType.SESSION: 5.0,
            BudgetType.DAILY: 10.0,
        }
        self._init_daily_budget()
        self._logger.info("✅ BudgetManager 初始化完成")

    def _init_daily_budget(self):
        today = datetime.now().strftime("%Y-%m-%d")
        daily_budget_id = f"daily_{today}"
        if daily_budget_id not in self._budgets:
            budget = Budget(
                budget_id=daily_budget_id,
                budget_type=BudgetType.DAILY,
                amount_usd=self._default_budgets[BudgetType.DAILY]
            )
            self._budgets[daily_budget_id] = budget
            self._logger.debug(f"📅 初始化日预算: {daily_budget_id}")

    def create_session_budget(self, session_id: str) -> SessionBudget:
        today = datetime.now().strftime("%Y-%m-%d")
        daily_budget_id = f"daily_{today}"
        session_budget = SessionBudget(
            session_id=session_id,
            session_budget=Budget(
                budget_id=f"session_{session_id}",
                budget_type=BudgetType.SESSION,
                amount_usd=self._default_budgets[BudgetType.SESSION]
            ),
            daily_budget=self._budgets.get(daily_budget_id)
        )
        self._session_budgets[session_id] = session_budget
        self._logger.debug(f"🔄 创建会话预算: {session_id}")
        return session_budget

    def get_session_budget(self, session_id: str) -> Optional[SessionBudget]:
        return self._session_budgets.get(session_id)

    def allocate_task_budget(self, session_id: str, complexity: str = "medium") -> float:
        budget_amount = self._default_budgets[BudgetType.TASK].get(complexity, 0.1)
        task_budget = Budget(
            budget_id=f"task_{session_id}_{int(time.time())}",
            budget_type=BudgetType.TASK,
            amount_usd=budget_amount
        )
        session_budget = self._session_budgets.get(session_id)
        if session_budget:
            session_budget.task_budget = task_budget
            self._budgets[task_budget.budget_id] = task_budget
        self._logger.debug(f"💰 分配任务预算: {session_id} -> ${budget_amount}")
        return budget_amount

    def spend_budget(self, session_id: str, amount: float) -> bool:
        session_budget = self._session_budgets.get(session_id)
        if not session_budget:
            self._logger.warning(f"会话预算不存在: {session_id}")
            return False
        success = session_budget.can_spend(amount)
        if success:
            self._logger.debug(f"💸 消耗预算: {session_id} -> ${amount}")
        else:
            self._logger.warning(f"❌ 预算不足: {session_id}, 需要 ${amount}")
        return success

    def get_budget_status(self, session_id: str) -> Dict[str, Any]:
        session_budget = self._session_budgets.get(session_id)
        if not session_budget:
            return {"error": "会话预算不存在"}
        return {
            "session_id": session_id,
            "task": {
                "spent": session_budget.task_budget.spent_usd if session_budget.task_budget else 0.0,
                "remaining": session_budget.task_budget.remaining_usd if session_budget.task_budget else 0.0,
                "total": session_budget.task_budget.amount_usd if session_budget.task_budget else 0.0,
                "status": session_budget.task_budget.status.value if session_budget.task_budget else "none"
            },
            "session": {
                "spent": session_budget.session_budget.spent_usd if session_budget.session_budget else 0.0,
                "remaining": session_budget.session_budget.remaining_usd if session_budget.session_budget else 0.0,
                "total": session_budget.session_budget.amount_usd if session_budget.session_budget else 0.0,
                "status": session_budget.session_budget.status.value if session_budget.session_budget else "none"
            },
            "daily": {
                "spent": session_budget.daily_budget.spent_usd if session_budget.daily_budget else 0.0,
                "remaining": session_budget.daily_budget.remaining_usd if session_budget.daily_budget else 0.0,
                "total": session_budget.daily_budget.amount_usd if session_budget.daily_budget else 0.0,
                "status": session_budget.daily_budget.status.value if session_budget.daily_budget else "none"
            }
        }

    def check_budget_available(self, session_id: str, required_amount: float) -> bool:
        session_budget = self._session_budgets.get(session_id)
        if not session_budget:
            return False
        total_remaining = 0.0
        if session_budget.task_budget:
            total_remaining += session_budget.task_budget.remaining_usd
        if session_budget.session_budget:
            total_remaining += session_budget.session_budget.remaining_usd
        return total_remaining >= required_amount

    def update_budget(self, budget_id: str, new_amount: float):
        if budget_id in self._budgets:
            budget = self._budgets[budget_id]
            budget.amount_usd = new_amount
            budget.remaining_usd = new_amount - budget.spent_usd
            budget.updated_at = time.time()
            self._logger.info(f"🔧 更新预算: {budget_id} -> ${new_amount}")

    def reset_session_budget(self, session_id: str):
        session_budget = self._session_budgets.get(session_id)
        if session_budget:
            if session_budget.task_budget:
                session_budget.task_budget.reset()
            if session_budget.session_budget:
                session_budget.session_budget.reset()
            self._logger.info(f"🔄 重置会话预算: {session_id}")

    def cleanup_expired_budgets(self):
        today = datetime.now().strftime("%Y-%m-%d")
        expired_budgets = []
        for budget_id, budget in self._budgets.items():
            if budget.budget_type == BudgetType.DAILY and budget_id != f"daily_{today}":
                expired_budgets.append(budget_id)
        for budget_id in expired_budgets:
            del self._budgets[budget_id]
        if expired_budgets:
            self._logger.info(f"🗑️ 清理过期预算: {len(expired_budgets)} 个")


budget_manager = BudgetManager()


def get_budget_manager() -> BudgetManager:
    return budget_manager
