"""WebToolRouter — unified web access routing layer.

Call chain logic:
  User query → classify → route → execute → return

  Classification:
    URL present + needs interaction → browser_agent.browse()
    URL present + static page      → web_fetch (light_crawler)
    Matches registered API name     → api_map.call()
    Natural language search         → web_search (DuckDuckGo → browser_agent if needed)

Tools:
  - api_map.call()    : REST/JSON APIs, 28 endpoints
  - web_fetch()       : Static HTTP GET, returns raw HTML  
  - browser_agent()   : LLM-driven Playwright, JS rendering + interaction
  - web_search()      : Search engine → decide if further extraction needed
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from logging import getLogger
from typing import Any, Optional
from urllib.parse import urlparse

logger = getLogger(__name__)

URL_RE = re.compile(r'https?://[^\s<>"\')\]},，。]+')


@dataclass
class WebResult:
    """Unified result from any web tool."""
    source: str = ""          # "api_map" | "web_fetch" | "browser_agent" | "web_search" | "llm_knowledge"
    url: str = ""
    title: str = ""
    data: dict = field(default_factory=dict)
    text: str = ""
    status: int = 0
    found: bool = False
    error: str = ""
    elapsed_ms: float = 0.0


class WebToolRouter:
    """Routes web information requests to the appropriate tool."""

    def __init__(self, llm=None):
        self._llm = llm

    async def _get_llm(self):
        if self._llm:
            return self._llm
        try:
            from livingtree.treellm.core import TreeLLM
            self._llm = TreeLLM.from_config()
            return self._llm
        except Exception:
            pass
        return None

    # ═══ Public API ════════════════════════════════════════════════

    async def lookup(self, query: str = "", url: str = "",
                     task: str = "", prefer: str = "") -> WebResult:
        """Main entry point. Classify and route.

        Args:
            query: Natural language search query
            url: Explicit URL to fetch/browse
            task: What to do with the page (search, extract, etc.)
            prefer: Force tool selection ("api" | "fetch" | "browser" | "search")
        """
        t0 = time.time()
        result = WebResult()

        # ── Route: Force tool ──
        if prefer == "api" and query:
            return await self._route_api(query)

        if prefer == "browser" and url:
            return await self._route_browser(url, task or query)

        if prefer == "fetch" and url:
            return await self._route_fetch(url)

        if prefer == "search" and query:
            return await self._route_search(query, task)

        # ── Route: Auto-classify ──
        # Has explicit URL?
        if url:
            return await self._route_url(url, task or query)

        # Extracted URL from query?
        urls = URL_RE.findall(query or "")
        if urls:
            return await self._route_url(urls[0], task or query)

        # Looks like API call?
        api_result = await self._try_api(query)
        if api_result:
            return api_result

        # Default: web search
        return await self._route_search(query, task)

    # ═══ Route Handlers ════════════════════════════════════════════

    async def _route_url(self, url: str, task: str) -> WebResult:
        """Route URL-based queries: browser for interaction, fetch for static."""
        # If task implies interaction (search, type, find, click)
        interactive_keywords = ["搜索", "search", "查找", "find", "输入", "type",
                                "点击", "click", "提交", "submit", "登录", "login",
                                "下载", "download", "填写", "fill"]
        needs_interaction = any(k in (task or "").lower() for k in interactive_keywords)

        if needs_interaction:
            return await self._route_browser(url, task)
        else:
            return await self._route_fetch(url)

    async def _route_api(self, query: str) -> WebResult:
        """Route to api_map by matching query against registered APIs."""
        try:
            from livingtree.treellm.api_map import get_api_map
            m = get_api_map()
            results = m.search(query)
            if results:
                api_name = results[0]["name"]
                params = {}
                if "weather" in api_name or "meteo" in api_name:
                    params = {"latitude": 39.9, "longitude": 116.4, "current_weather": "true"}
                r = await m.call(api_name, params)
                return WebResult(
                    source="api_map", url=m._apis[api_name].url,
                    data=r.data if isinstance(r.data, dict) else {"response": str(r.data)[:1000]},
                    status=r.status_code, found=r.status_code < 400,
                    elapsed_ms=r.elapsed_ms,
                )
        except Exception as e:
            logger.debug(f"API route: {e}")
        return WebResult(source="api_map", found=False, error="No matching API")

    async def _try_api(self, query: str) -> WebResult | None:
        """Check if query matches a known API endpoint."""
        try:
            from livingtree.treellm.api_map import get_api_map
            m = get_api_map()
            results = m.search(query)
            if results and results[0]["score"] >= 5:
                return await self._route_api(query)
        except Exception:
            pass
        return None

    async def _route_browser(self, url: str, task: str) -> WebResult:
        """Route to browser_agent for JS-rendered / interactive pages."""
        try:
            from livingtree.capability.browser_agent import get_browser_agent
            agent = get_browser_agent()
            r = await agent.browse(url=url, task=task)
            return WebResult(
                source="browser_agent", url=url, title=r.title,
                data=r.data, found=r.found, error=r.error,
                elapsed_ms=r.elapsed_ms,
            )
        except Exception as e:
            return WebResult(source="browser_agent", url=url, error=str(e)[:200])

    async def _route_fetch(self, url: str) -> WebResult:
        """Route to static HTTP fetch (light_crawler or aiohttp)."""
        t0 = time.time()
        try:
            from livingtree.capability.light_crawler import LightCrawler, LightPage
            crawler = LightCrawler()
            pages = await crawler.fetch([url])
            if pages and pages[0].status and pages[0].status < 400:
                return WebResult(
                    source="web_fetch", url=url, title=pages[0].title or "",
                    text=pages[0].text or "", status=pages[0].status or 200,
                    found=True, elapsed_ms=(time.time() - t0) * 1000,
                )
        except Exception as e:
            logger.debug(f"LightCrawler fetch: {e}")

        # Fallback: aiohttp
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                r = await s.get(url, timeout=aiohttp.ClientTimeout(total=15))
                text = await r.text()
                title_m = re.search(r'<title[^>]*>(.*?)</title>', text, re.I)
                return WebResult(
                    source="web_fetch", url=url,
                    title=title_m.group(1).strip() if title_m else url,
                    text=text[:30_000], status=r.status,
                    found=r.status < 400,
                    elapsed_ms=(time.time() - t0) * 1000,
                )
        except Exception as e:
            return WebResult(source="web_fetch", url=url, error=str(e)[:200])

    async def _route_search(self, query: str, task: str = "") -> WebResult:
        """General web search via UnifiedSearch (SparkSearch+Bing+DDG+Wikipedia+SearXNG)."""
        t0 = time.time()
        text = query or task

        try:
            from livingtree.capability.unified_search import get_unified_search
            us = get_unified_search()
            results = await us.query(text, limit=5)
            if results:
                items = [{"title": r.title, "url": r.url, "snippet": r.summary[:200]}
                         for r in results]
                return WebResult(
                    source="web_search", title=text,
                    data={"items": items, "count": len(items)},
                    found=True,
                    elapsed_ms=(time.time() - t0) * 1000,
                )
        except Exception as e:
            logger.debug(f"UnifiedSearch: {e}")

        # Last resort: DuckDuckGo
        try:
            from duckduckgo_search import DDGS
            results = DDGS().text(text, max_results=5)
            items = [{"title": r["title"], "href": r["href"], "body": r["body"]}
                     for r in results]
            return WebResult(
                source="web_search", title=text,
                data={"items": items, "count": len(items)},
                found=bool(items),
                elapsed_ms=(time.time() - t0) * 1000,
            )
        except Exception as e:
            logger.debug(f"DDG: {e}")

        return WebResult(source="web_search", found=False, error="No search engine available")

    # ═══ Stats ════════════════════════════════════════════════════

    def describe(self) -> dict:
        return {
            "tools": {
                "api_map": "REST/JSON APIs (28 endpoints). For structured data: weather, maps, translation, etc.",
                "web_fetch": "Static HTTP GET. For simple web pages without JS.",
                "browser_agent": "LLM-driven browser (Playwright). For SPA sites, interactive search, JS-rendered pages.",
                "web_search": "Search engine (DuckDuckGo). For general web search without specific data source.",
            },
            "routing": {
                "has_url + needs_interaction": "browser_agent",
                "has_url + static": "web_fetch",
                "matches_api": "api_map",
                "natural_language": "web_search → browser_agent",
            },
        }


# ═══ Singleton ═══

_router: Optional[WebToolRouter] = None


def get_web_router(llm=None) -> WebToolRouter:
    global _router
    if _router is None or llm:
        _router = WebToolRouter(llm)
    return _router
