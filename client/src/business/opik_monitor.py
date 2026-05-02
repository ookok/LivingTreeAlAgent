"""
Opik Monitor — Compatibility Stub
"""


class OpikMonitor:
    def __init__(self, project: str = "livingtree"):
        self.project = project

    def track(self, name: str, metadata: dict = None):
        pass

    def log(self, level: str, message: str):
        pass


__all__ = ["OpikMonitor"]
