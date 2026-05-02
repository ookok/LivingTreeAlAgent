"""
Marketplace — Compatibility Stub
"""

class Marketplace:
    def __init__(self):
        self._items = []

    def list_items(self, category: str = "") -> list:
        return self._items

    def search(self, query: str) -> list:
        return []


__all__ = ["Marketplace"]
