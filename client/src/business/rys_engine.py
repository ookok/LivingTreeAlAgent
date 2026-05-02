"""
RYS Engine — Compatibility Stub
"""


class RYSEngine:
    def __init__(self):
        pass

    def reason(self, context: str, query: str) -> str:
        return f"[RYS] {query}"

    def synthesize(self, facts: list) -> str:
        return "(synthesized)"


__all__ = ["RYSEngine"]
