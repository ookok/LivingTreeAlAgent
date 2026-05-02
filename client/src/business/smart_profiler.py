"""
Smart Profiler — Compatibility Stub

Functionality migrated to livingtree.core.observability.metrics (MetricsCollector).
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ProfileResult:
    name: str = ""
    duration_ms: float = 0.0
    memory_mb: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class OptimizationSuggestion:
    def __init__(self, description: str = "", impact: str = "medium"):
        self.description = description
        self.impact = impact


class SmartProfiler:
    def __init__(self):
        self._results: List[ProfileResult] = []

    def profile(self, func, *args, **kwargs):
        import time
        start = time.time()
        result = func(*args, **kwargs)
        duration = (time.time() - start) * 1000
        self._results.append(ProfileResult(name=func.__name__, duration_ms=duration))
        return result


def get_profiler():
    return SmartProfiler()


__all__ = ["SmartProfiler", "get_profiler", "ProfileResult", "OptimizationSuggestion"]
