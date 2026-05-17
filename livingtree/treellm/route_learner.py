"""DEPRECATED — re-exports from livingtree.treellm.router.

This file is kept for backward compatibility. All routing logic has been
consolidated into router.py.  Import from router.py directly in new code.
"""
from .router import (
    RouteLearner, LearnedProfile, RoutingWeight, get_route_learner,
)

__all__ = ["RouteLearner", "LearnedProfile", "RoutingWeight", "get_route_learner"]
