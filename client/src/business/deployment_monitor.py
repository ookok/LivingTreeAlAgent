"""
Deployment Monitor — Compatibility Stub
"""

class DeploymentMonitor:
    def __init__(self):
        self._statuses = {}

    def check(self, target: str) -> str:
        return "healthy"


__all__ = ["DeploymentMonitor"]
