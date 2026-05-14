"""SearXNGSearcher — free SearXNG public instance meta-search engine.

Queries public SearXNG instances (no API key needed). Returns aggregated
results from multiple search engines (Google, Bing, DDG, etc.) via SearXNG.

Usage:
    from .searxng_search import SearXNGSearcher, search_searxng
    engine = SearXNGSearcher()
    results = await engine.query("Python async best practices")
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass

from loguru import logger

from ..network.resilience import resilient_fetch_json

SEARXNG_INSTANCES = [
    "https://search.bus-hit.me",
    "https://searx.be",
    "https://search.sapti.me",
    "https://search.smnz.de",
    "https://search.zzls.xyz",
    "https://searx.tuxcloud.net",
    "https://search.inetol.net",
]


@dataclass
class SearXNGResult:
    title: str
    url: str
    snippet: str = ""
    engine: str = ""

    def format_display(self) -> str:
        lines = [f"[bold]{self.title[:80]}[/bold]"]
        lines.append(f"  [dim]{self.url}[/dim]")
        if self.snippet:
            lines.append(f"  {self.snippet[:150]}")
        return "\n".join(lines)


class SearXNGSearcher:
    """Free SearXNG meta-search via public instances."""

    def __init__(self, timeout: int = 8, max_instances: int = 3):
        self._timeout = timeout
        self._max_instances = max_instances
        self._working_instances: list[str] = []
        self._probed = False

    async def _probe_instances(self) -> list[str]:
        if self._probed:
            return self._working_instances

        for instance in SEARXNG_INSTANCES[: self._max_instances * 2]:
            try:
                await resilient_fetch_json(
                    url=f"{instance}/search", timeout=5, max_retries=1,
                    params={"q": "test", "format": "json"},
                    headers={"Accept": "application/json"},
                    use_proxy=True, use_accelerator=True,
                )
                self._working_instances.append(instance)
                if len(self._working_instances) >= self._max_instances:
                    break
            except Exception:
                continue

        self._probed = True
        if not self._working_instances:
            self._working_instances = SEARXNG_INSTANCES[:1]
        logger.debug(f"SearXNG working instances: {len(self._working_instances)}")
        return self._working_instances

    async def query(self, q: str, limit: int = 10) -> list[SearXNGResult]:
        if not q or not q.strip():
            return []

        instances = await self._probe_instances()

        for instance in instances:
            try:
                url = f"{instance}/search"
                data = await resilient_fetch_json(
                    url=url, timeout=8, max_retries=2,
                    params={"q": q, "format": "json", "categories": "general"},
                    headers={
                        "User-Agent": "LivingTree/2.4 SearXNG Searcher",
                        "Accept": "application/json",
                    },
                    use_proxy=True, use_accelerator=True,
                )

                results: list[SearXNGResult] = []
                for r in data.get("results", []):
                    results.append(SearXNGResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=(r.get("content", "") or "")[:300],
                        engine=",".join(r.get("engines", [])) if isinstance(r.get("engines", []), list) else str(r.get("engines", "")),
                    ))
                    if len(results) >= limit:
                        break

                if results:
                    logger.debug(f"SearXNG ({instance.split('//')[1][:20]}): {len(results)} results for '{q[:50]}'")
                    return results

            except Exception as e:
                logger.debug(f"SearXNG {instance.split('//')[1][:20]} failed: {e}")
                continue

        return []

    def format_results(self, results: list[SearXNGResult], max_results: int = 10) -> str:
        if not results:
            return "[dim]No SearXNG results[/dim]"
        lines = [f"[bold]SearXNG Results ({len(results)}):[/bold]"]
        for r in results[:max_results]:
            lines.append(f"  [bold #58a6ff]{r.title[:80]}[/bold #58a6ff]")
            lines.append(f"    [dim]{r.url}[/dim]")
            if r.snippet:
                lines.append(f"    {r.snippet[:150]}")
            lines.append("")
        return "\n".join(lines)


_searxng_search: SearXNGSearcher | None = None


def get_searxng_search() -> SearXNGSearcher:
    global _searxng_search
    if _searxng_search is None:
        _searxng_search = SearXNGSearcher()
    return _searxng_search


async def search_searxng(query: str, limit: int = 10) -> list[SearXNGResult]:
    return await get_searxng_search().query(query, limit=limit)
