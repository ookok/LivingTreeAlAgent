"""DEPRECATED — re-exports from livingtree.treellm.router.

This file is kept for backward compatibility. All routing logic has been
consolidated into router.py.  Import from router.py directly in new code.
"""
from .router import ThompsonStrategy as ThompsonRouter
from .router import get_router as _get_router


def get_bandit_router():
    return _get_router("thompson")._strategies["thompson"]


__all__ = ["ThompsonRouter", "get_bandit_router"]
