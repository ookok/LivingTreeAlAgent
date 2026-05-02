"""
CostManager — Compatibility Stub
=================================

功能已迁移至 livingtree.core.model.router 的 CostBudget。
此模块提供兼容接口。
"""

from business.global_model_router import CostBudget, get_global_router


class CostManager:
    def __init__(self):
        self._budget = CostBudget()

    def get_monthly_limit(self) -> float:
        return self._budget.monthly_limit

    def get_daily_limit(self) -> float:
        return self._budget.daily_limit

    def get_current_month_spent(self) -> float:
        self._budget.reset_if_needed()
        return self._budget.current_month_spent

    def get_current_day_spent(self) -> float:
        self._budget.reset_if_needed()
        return self._budget.current_day_spent

    def can_afford(self, cost: float) -> bool:
        self._budget.reset_if_needed()
        return self._budget.can_afford(cost)

    def record_cost(self, cost: float):
        self._budget.reset_if_needed()
        self._budget.record_spend(cost)


_global_cost_manager: CostManager = None


def get_cost_manager() -> CostManager:
    global _global_cost_manager
    if _global_cost_manager is None:
        _global_cost_manager = CostManager()
    return _global_cost_manager
