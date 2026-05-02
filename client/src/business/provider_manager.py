"""
Provider Manager — Compatibility Stub

Functionality migrated to livingtree.adapters.providers.
"""


class ProviderManager:
    def __init__(self):
        self._providers = {}

    def register(self, name: str, provider):
        self._providers[name] = provider

    def get(self, name: str):
        return self._providers.get(name)


__all__ = ["ProviderManager"]
