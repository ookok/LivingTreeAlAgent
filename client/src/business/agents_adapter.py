"""
Agents Adapter — Compatibility Stub
"""

class AgentsAdapter:
    def __init__(self):
        self._adapters = {}

    def register(self, name: str, adapter):
        self._adapters[name] = adapter

    def get(self, name: str):
        return self._adapters.get(name)


__all__ = ["AgentsAdapter"]
