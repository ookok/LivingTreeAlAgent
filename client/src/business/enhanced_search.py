"""
Enhanced Search — Compatibility Stub

Functionality migrated to livingtree.core.intent + model.router.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any


class SearchSource(Enum):
    WEB = "web"
    LOCAL = "local"
    KNOWLEDGE_BASE = "kb"
    CODE = "code"
    DOCS = "docs"


@dataclass
class SearchResult:
    title: str = ""
    url: str = ""
    snippet: str = ""
    source: SearchSource = SearchSource.WEB
    relevance: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class EnhancedSearch:
    def __init__(self):
        self._sources = []

    def search(self, query: str, sources: List[SearchSource] = None,
               limit: int = 10) -> List[SearchResult]:
        return [SearchResult(title=f"Result for: {query}", snippet="Placeholder result")]

    def add_source(self, source: SearchSource):
        if source not in self._sources:
            self._sources.append(source)


def get_enhanced_search():
    return EnhancedSearch()


__all__ = ["EnhancedSearch", "SearchSource", "SearchResult", "get_enhanced_search"]
