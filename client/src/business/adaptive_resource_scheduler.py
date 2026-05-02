"""
Adaptive Resource Scheduler — Compatibility Stub
"""


class LoadMonitor:
    def __init__(self):
        self._cpu_pct = 0.0
        self._memory_pct = 0.0

    @property
    def cpu_usage(self):
        return self._cpu_pct

    @property
    def memory_usage(self):
        return self._memory_pct


class AdaptiveResourceScheduler:
    def __init__(self):
        self._monitor = LoadMonitor()

    @property
    def monitor(self):
        return self._monitor


def get_resource_scheduler():
    return AdaptiveResourceScheduler()


__all__ = ["AdaptiveResourceScheduler", "get_resource_scheduler", "LoadMonitor"]
