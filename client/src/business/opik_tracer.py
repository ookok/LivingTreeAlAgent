"""
Opik Tracer — Compatibility Stub
"""


class OpikTracer:
    def __init__(self, project: str = "livingtree"):
        self.project = project

    def start_trace(self, name: str) -> str:
        return "trace-0"

    def end_trace(self, trace_id: str):
        pass


__all__ = ["OpikTracer"]
