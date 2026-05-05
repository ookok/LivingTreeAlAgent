"""UnifiedSearch — multi-engine web search with automatic fallback.

Priority: SparkSearch (iFlytek ONE Search, free) → DDGSearch (DuckDuckGo, free).
Each engine gets retry + proxy via the resilience layer.

Usage:
    from .unified_search import search
    results = await search("Python async best practices", limit=5)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from loguru import logger

from ..network.resilience import with_resilience


@dataclass
class UnifiedResult:
    title: str
    url: str
    summary: str = ""
    source: str = ""

    def format_display(self) -> str:
        src = f"[dim]({self.source})[/dim]"
        lines = [f"[bold]{self.title}[/bold] {src}"]
        lines.append(f"  [dim]{self.url}[/dim]")
        if self.summary:
            lines.append(f"  {self.summary[:150]}")
        return "\n".join(lines)


class UnifiedSearch:
    """Multi-engine search dispatcher with automatic failover."""

    def __init__(self, spark_search=None, ddg_search=None):
        self._spark = spark_search
        self._ddg = ddg_search
        self._initialized = False

    def _ensure_engines(self):
        if self._initialized:
            return
        if self._spark is None:
            try:
                from .spark_search import create_spark_search
                self._spark = create_spark_search()
            except Exception:
                self._spark = False  # mark as unavailable
        if self._ddg is None:
            try:
                from .ddg_search import DDGSearch
                self._ddg = DDGSearch()
            except Exception:
                self._ddg = False
        self._initialized = True

    @with_resilience(max_retries=2)
    async def query(self, q: str, limit: int = 10) -> list[UnifiedResult]:
        """Search across engines with automatic fallback."""
        self._ensure_engines()

        # Engine 1: SparkSearch
        if self._spark and self._spark is not False:
            try:
                from .spark_search import SearchResult
                raw = await self._spark.query(q, limit=limit)
                if raw:
                    results = []
                    for r in raw:
                        if isinstance(r, SearchResult):
                            results.append(UnifiedResult(
                                title=r.title, url=r.url,
                                summary=r.summary, source="spark",
                            ))
                        elif hasattr(r, 'title'):
                            results.append(UnifiedResult(
                                title=r.title, url=r.url,
                                summary=getattr(r, 'summary', ''), source="spark",
                            ))
                    if results:
                        logger.info(f"SparkSearch: {len(results)} results for '{q[:50]}'")
                        return results
            except Exception as e:
                logger.debug(f"SparkSearch failed: {e}")

        # Engine 2: DDGSearch (fallback)
        if self._ddg and self._ddg is not False:
            try:
                from .ddg_search import DDGResult
                raw = await self._ddg.query(q, limit=limit)
                if raw:
                    results = []
                    for r in raw:
                        if isinstance(r, DDGResult):
                            results.append(UnifiedResult(
                                title=r.title, url=r.url,
                                summary=r.summary, source="ddg",
                            ))
                        elif hasattr(r, 'title'):
                            results.append(UnifiedResult(
                                title=r.title, url=r.url,
                                summary=getattr(r, 'summary', ''), source="ddg",
                            ))
                    if results:
                        logger.info(f"DDGSearch: {len(results)} results for '{q[:50]}'")
                        return results
            except Exception as e:
                logger.debug(f"DDGSearch failed: {e}")

        return []

    def format_results(self, results: list[UnifiedResult], max_results: int = 10) -> str:
        if not results:
            return "[dim]No results found[/dim]"

        sources = set(r.source for r in results)
        source_str = "+".join(sorted(sources))
        lines = [f"[bold]Search Results ({len(results)}) [{source_str}]:[/bold]"]

        for r in results[:max_results]:
            lines.append(f"  [bold #58a6ff]{r.title[:80]}[/bold #58a6ff]")
            lines.append(f"    [dim]{r.url}[/dim]")
            if r.summary:
                lines.append(f"    {r.summary[:150]}")
            lines.append("")

        return "\n".join(lines)


# ═══ Global singleton ═══

_unified_search: UnifiedSearch | None = None


def get_unified_search() -> UnifiedSearch:
    global _unified_search
    if _unified_search is None:
        _unified_search = UnifiedSearch()
    return _unified_search


async def search(query: str, limit: int = 10) -> list[UnifiedResult]:
    return await get_unified_search().query(query, limit=limit)
