"""WikipediaSearch — free Wikipedia API search engine (no API key needed).

Uses Wikipedia's REST API and opensearch API for fast, structured results.
Both English (en.wikipedia.org) and Chinese (zh.wikipedia.org) supported.

Usage:
    from .wikipedia_search import WikipediaSearch, search_wiki
    engine = WikipediaSearch()
    results = await engine.query("Python programming language")
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass

from loguru import logger

from ..network.resilience import resilient_fetch_json


@dataclass
class WikiResult:
    title: str
    url: str
    snippet: str = ""
    page_id: int = 0
    language: str = "en"

    def format_display(self) -> str:
        lines = [f"[bold]{self.title[:80]}[/bold] [dim](wikipedia, {self.language})[/dim]"]
        lines.append(f"  [dim]{self.url}[/dim]")
        if self.snippet:
            lines.append(f"  {self.snippet[:150]}")
        return "\n".join(lines)


class WikipediaSearch:
    """Free Wikipedia search via REST + opensearch API."""

    WIKI_LANGS = [
        ("en", "https://en.wikipedia.org"),
        ("zh", "https://zh.wikipedia.org"),
    ]

    def __init__(self, timeout: int = 8):
        self._timeout = timeout

    async def query(self, q: str, limit: int = 10, lang: str = "auto") -> list[WikiResult]:
        if not q or not q.strip():
            return []

        results: list[WikiResult] = []
        langs_to_try = self.WIKI_LANGS
        if lang == "zh":
            langs_to_try = [self.WIKI_LANGS[1]]
        elif lang == "en":
            langs_to_try = [self.WIKI_LANGS[0]]

        for lang_code, base_url in langs_to_try:
            try:
                api_url = f"{base_url}/w/api.php"
                data = await resilient_fetch_json(
                    url=api_url, timeout=8, max_retries=2,
                    params={
                        "action": "query", "format": "json",
                        "list": "search", "srsearch": q,
                        "srlimit": str(min(limit, 15)), "srprop": "snippet",
                    },
                    headers={
                        "User-Agent": "LivingTree/2.4 WikipediaSearcher (research project)",
                        "Accept": "application/json",
                    },
                    use_proxy=True, use_accelerator=True,
                )

                search_results = data.get("query", {}).get("search", [])
                if not search_results:
                    continue

                for r in search_results:
                    title = r.get("title", "")
                    page_id = r.get("pageid", 0)
                    snippet = self._clean_html(r.get("snippet", ""))
                    url = f"{base_url}/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                    results.append(WikiResult(
                        title=title, url=url, snippet=snippet,
                        page_id=page_id, language=lang_code,
                    ))

                logger.debug(f"Wikipedia ({lang_code}): {len(search_results)} results for '{q[:50]}'")
                if results:
                    break

            except Exception as e:
                logger.debug(f"Wikipedia ({lang_code}) failed: {e}")
                continue

        if not results:
            results = await self._opensearch_fallback(q, limit, session)

        return results[:limit]

    async def _opensearch_fallback(self, q: str, limit: int) -> list[WikiResult]:
        results: list[WikiResult] = []
        for lang_code, base_url in self.WIKI_LANGS:
            try:
                api_url = f"{base_url}/w/api.php"
                data = await resilient_fetch_json(
                    url=api_url, timeout=8, max_retries=2,
                    params={
                        "action": "opensearch", "format": "json",
                        "search": q, "limit": str(min(limit, 10)),
                    },
                    headers={
                        "User-Agent": "LivingTree/2.4 WikipediaSearcher (research project)",
                        "Accept": "application/json",
                    },
                    use_proxy=True, use_accelerator=True,
                )

                if len(data) < 4:
                    continue

                titles = data[1]
                snippets = data[2]
                urls = data[3]
                for title, snippet, url in zip(titles, snippets, urls):
                    if title and url:
                        results.append(WikiResult(
                            title=title, url=url, snippet=snippet[:300],
                            language=lang_code,
                        ))

                if results:
                    break

            except Exception:
                continue

        return results

    @staticmethod
    def _clean_html(text: str) -> str:
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&quot;", '"').replace("&#39;", "'")
        return text.strip()[:300]

    async def close(self):
        pass

    def format_results(self, results: list[WikiResult], max_results: int = 10) -> str:
        if not results:
            return "[dim]No Wikipedia results[/dim]"
        lines = [f"[bold]Wikipedia Results ({len(results)}):[/bold]"]
        for r in results[:max_results]:
            lines.append(f"  [bold #58a6ff]{r.title[:80]}[/bold #58a6ff] [dim]({r.language})[/dim]")
            lines.append(f"    [dim]{r.url}[/dim]")
            if r.snippet:
                lines.append(f"    {r.snippet[:150]}")
            lines.append("")
        return "\n".join(lines)


_wiki_search: WikipediaSearch | None = None


def get_wiki_search() -> WikipediaSearch:
    global _wiki_search
    if _wiki_search is None:
        _wiki_search = WikipediaSearch()
    return _wiki_search


async def search_wiki(query: str, limit: int = 10) -> list[WikiResult]:
    return await get_wiki_search().query(query, limit=limit)
