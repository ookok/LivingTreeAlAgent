"""DDGSearch — DuckDuckGo web search (no API key needed, free forever).

Used as automatic fallback when SparkSearch is unavailable or fails.
Integrated with resilience layer for proxy/mirror/retry support.

Usage:
    search = DDGSearch()
    results = await search.query("Python async best practices", limit=5)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class DDGResult:
    title: str
    url: str
    summary: str = ""

    def format_display(self) -> str:
        lines = [f"[bold]{self.title}[/bold]"]
        lines.append(f"  [dim]{self.url}[/dim]")
        if self.summary:
            lines.append(f"  {self.summary[:120]}")
        return "\n".join(lines)


class DDGSearch:
    """DuckDuckGo search — runs in thread executor (sync SDK)."""

    def __init__(self, timeout: float = 15.0):
        self._timeout = timeout

    async def query(self, query: str, limit: int = 10,
                    region: str = "wt-wt") -> list[DDGResult]:
        if not query.strip():
            return []

        try:
            # DDGS is sync, run in thread to not block event loop
            return await asyncio.to_thread(self._query_sync, query, limit, region)

        except Exception as e:
            logger.debug(f"DDGS search failed: {e}")
            return []

    def _query_sync(self, query: str, limit: int, region: str) -> list[DDGResult]:
        from duckduckgo_search import DDGS

        with DDGS(timeout=int(self._timeout)) as ddgs:
            raw = list(ddgs.text(keywords=query, max_results=min(limit, 20), region=region))
            return [
                DDGResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    summary=r.get("body", ""),
                )
                for r in raw
            ]
        except Exception as e:
            logger.debug(f"DDGS: {e}")
            return []

    def format_results(self, results: list[DDGResult], max_results: int = 10) -> str:
        if not results:
            return "[dim]No results found[/dim]"

        lines = [f"[bold #fea62b]DDG Search Results ({len(results)}):[/bold #fea62b]"]
        for r in results[:max_results]:
            lines.append(f"  [bold #58a6ff]{r.title[:80]}[/bold #58a6ff]")
            lines.append(f"    [dim]{r.url}[/dim]")
            if r.summary:
                lines.append(f"    {r.summary[:150]}")
            lines.append("")

        return "\n".join(lines)
