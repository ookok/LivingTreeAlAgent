"""DEPRECATED — re-exports from livingtree.treellm.router.

This file is kept for backward compatibility. All routing logic has been
consolidated into router.py.  Import from router.py directly in new code.
"""
from .router import FitnessStrategy as FitnessRouter
from .router import get_router as _get_router


def get_fitness_router():
    return _get_router("fitness")._strategies["fitness"]


__all__ = ["FitnessRouter", "get_fitness_router"]
