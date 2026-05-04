"""Spark Search Tool — Web search via iFlytek ONE Search API.

Unlimited free web search. Returns title, summary, URL for each result.
Auto-wired into chat: '/search query' triggers this engine.

Usage:
    search = SparkSearch(api_password="...")
    results = await search.query("Python best practices", limit=5)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class SearchResult:
    title: str
    url: str
    summary: str = ""
    content: str = ""
    published_date: str = ""

    def format_display(self) -> str:
        lines = [f"[bold]{self.title}[/bold]"]
        lines.append(f"  [dim]{self.url}[/dim]")
        if self.summary:
            lines.append(f"  {self.summary[:120]}")
        return "\n".join(lines)


class SparkSearch:

    SEARCH_URL = "https://search-api-open.cn-huabei-1.xf-yun.com/v2/search"

    def __init__(self, api_password: str = ""):
        self._api_password = api_password

    async def query(self, query: str, limit: int = 10,
                    open_rerank: bool = True,
                    open_full_text: bool = False) -> list[SearchResult]:
        if not self._api_password or not query.strip():
            return []

        import aiohttp
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    self.SEARCH_URL,
                    json={
                        "search_params": {
                            "query": query[:500],
                            "limit": min(limit, 20),
                            "enhance": {
                                "open_rerank": open_rerank,
                                "open_full_text": open_full_text,
                            },
                        }
                    },
                    headers={
                        "Authorization": f"Bearer {self._api_password}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    if data.get("err_code") != "0":
                        return []

                    docs = data.get("data", {}).get("search_results", {}).get("documents", [])
                    return [
                        SearchResult(
                            title=d.get("name", ""),
                            url=d.get("url", ""),
                            summary=d.get("summary", ""),
                            content=d.get("content", ""),
                            published_date=d.get("published_date", ""),
                        )
                        for d in docs
                    ]

        except Exception as e:
            logger.debug(f"SparkSearch: {e}")
            return []

    def format_results(self, results: list[SearchResult], max_results: int = 10) -> str:
        if not results:
            return "[dim]No results found[/dim]"

        lines = [f"[bold]Search Results ({len(results)}):[/bold]"]
        for r in results[:max_results]:
            lines.append(f"  [bold #58a6ff]{r.title[:80]}[/bold #58a6ff]")
            lines.append(f"    [dim]{r.url}[/dim]")
            if r.summary:
                lines.append(f"    {r.summary[:150]}")
            lines.append("")

        return "\n".join(lines)


def create_spark_search(api_password: str = "") -> SparkSearch:
    from livingtree.config import get_config
    if not api_password:
        c = get_config()
        api_password = getattr(c.model, 'spark_search_key', '') or ""
        if not api_password:
            from livingtree.config.secrets import get_secret_vault
            api_password = get_secret_vault().get("spark_search_key", "")

    return SparkSearch(api_password=api_password)
