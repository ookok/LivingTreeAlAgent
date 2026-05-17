"""DEPRECATED — re-exports from livingtree.treellm.router.

This file is kept for backward compatibility. All routing logic has been
consolidated into router.py.  Import from router.py directly in new code.
"""
from .router import PredictiveStrategy as PredictiveRouter
from .router import get_router as _get_router


def get_predictive_router():
    return _get_router("predictive")._strategies["predictive"]


__all__ = ["PredictiveRouter", "get_predictive_router"]
