"""BingSearch — free Bing HTML scraping engine (no API key needed).

Async Bing web search via HTML parsing of www.bing.com/search.
Returns structured results with title, url, snippet.

Usage:
    from .bing_search import BingSearch, search_bing
    engine = BingSearch()
    results = await engine.query("Python async best practices")
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass

from loguru import logger

from ..network.resilience import resilient_fetch_text


@dataclass
class BingResult:
    title: str
    url: str
    snippet: str = ""

    def format_display(self) -> str:
        lines = [f"[bold]{self.title[:80]}[/bold]"]
        lines.append(f"  [dim]{self.url}[/dim]")
        if self.snippet:
            lines.append(f"  {self.snippet[:150]}")
        return "\n".join(lines)


class BingSearch:
    """Free Bing web search via HTML scraping."""

    def __init__(self, timeout: int = 10):
        self._timeout = timeout

    async def query(self, q: str, limit: int = 10) -> list[BingResult]:
        if not q or not q.strip():
            return []

        try:
            url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&count=20"
            html = await resilient_fetch_text(
                url=url, timeout=10, max_retries=2,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
                use_proxy=True, use_accelerator=True,
            )

            results: list[BingResult] = []
            blocks = re.split(r'<li class="b_algo">', html)
            for block in blocks[1:]:
                m_link = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
                if not m_link:
                    continue
                url_val = m_link.group(1)
                title = re.sub(r'<[^>]+>', '', m_link.group(2)).strip()

                snippet = ""
                sm = re.search(r'<p[^>]*class="b_lineclamp[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
                if sm:
                    snippet = re.sub(r'<[^>]+>', '', sm.group(1)).strip()[:300]

                if url_val and url_val.startswith("http") and title:
                    results.append(BingResult(title=title, url=url_val, snippet=snippet))

                if len(results) >= limit:
                    break

            logger.debug(f"BingSearch: {len(results)} results for '{q[:50]}'")
            return results

        except Exception as e:
            logger.debug(f"BingSearch failed: {e}")
            return []

    def format_results(self, results: list[BingResult], max_results: int = 10) -> str:
        if not results:
            return "[dim]No Bing results[/dim]"
        lines = [f"[bold]Bing Search Results ({len(results)}):[/bold]"]
        for r in results[:max_results]:
            lines.append(f"  [bold #58a6ff]{r.title[:80]}[/bold #58a6ff]")
            lines.append(f"    [dim]{r.url}[/dim]")
            if r.snippet:
                lines.append(f"    {r.snippet[:150]}")
            lines.append("")
        return "\n".join(lines)


# ── Global singleton ──

_bing_search: BingSearch | None = None


def get_bing_search() -> BingSearch:
    global _bing_search
    if _bing_search is None:
        _bing_search = BingSearch()
    return _bing_search


async def search_bing(query: str, limit: int = 10) -> list[BingResult]:
    return await get_bing_search().query(query, limit=limit)
