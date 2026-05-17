"""DEPRECATED — re-exports from livingtree.treellm.router.

This file is kept for backward compatibility. All routing logic has been
consolidated into router.py.  Import from router.py directly in new code.
"""
from .router import BudgetStrategy as BudgetRouter
from .router import get_router as _get_router


def get_budget_router():
    return _get_router("budget")._strategies["budget"]


__all__ = ["BudgetRouter", "get_budget_router"]
