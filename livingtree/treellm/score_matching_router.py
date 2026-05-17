"""DEPRECATED — re-exports from livingtree.treellm.router.

This file is kept for backward compatibility. All routing logic has been
consolidated into router.py.  Import from router.py directly in new code.
"""
from .router import ScoreMatchStrategy as ScoreMatchingRouter
from .router import get_router as _get_router


def get_score_matching_router():
    return _get_router("score_match")._strategies["score_match"]


__all__ = ["ScoreMatchingRouter", "get_score_matching_router"]
