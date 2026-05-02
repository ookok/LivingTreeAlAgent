"""
Search Tool — Compatibility Stub
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SearchToolResult:
    title: str = ""
    url: str = ""
    snippet: str = ""


class SearchTool:
    def __init__(self):
        self._engines = []

    def search(self, query: str, limit: int = 10) -> List[SearchToolResult]:
        return [SearchToolResult(title=f"Search: {query}", snippet="(stub)")]


__all__ = ["SearchTool", "SearchToolResult"]
