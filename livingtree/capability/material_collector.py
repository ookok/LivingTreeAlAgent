"""MaterialCollector — Multi-source web scraping + file + API collector.

Now backed by WebReach (BeautifulSoup4 + readability-lxml) for real web content
extraction. Replaces the old stub with actual HTML parsing and main content extraction.
"""

from __future__ import annotations

import asyncio
import os
import urllib.request
from typing import Any, Dict, List

from loguru import logger


class MaterialCollector:

    def __init__(self, rate_limit_per_sec: int = 2):
        self._sema = asyncio.Semaphore(rate_limit_per_sec)

    async def collect_from_web(self, query: str) -> list[dict[str, Any]]:
        async with self._sema:
            if not (query.startswith("http://") or query.startswith("https://")):
                try:
                    from .web_reach import WebReach
                    reach = WebReach()
                    from .spark_search import SparkSearch
                    search = SparkSearch()
                    results = await search.query(query, limit=3)
                    urls = [r.url for r in results if r.url]
                    if urls:
                        pages = await reach.fetch_multiple(urls[:3])
                        return [{"source": "web", "url": p.url, "title": p.title,
                                 "content": p.text[:2000], "links": len(p.links)}
                                for p in pages if p.text]
                except ImportError:
                    pass
                return [{"source": "web", "query": query, "content": f"No URLs to fetch for: {query}"}]

            if not self._is_allowed_by_robots(query):
                return [{"source": "web", "url": query, "content": "Blocked by robots.txt"}]

            try:
                from .web_reach import WebReach
                reach = WebReach()
                page = await reach.fetch(query)
                return [{"source": "web", "url": page.url, "title": page.title,
                         "content": page.text[:3000], "links": len(page.links)}]
            except ImportError:
                return [{"source": "web", "url": query, "content": "WebReach not available"}]

    async def collect_from_files(self, paths: list[str]) -> list[dict[str, Any]]:
        results = []
        for p in paths:
            try:
                if os.path.isdir(p):
                    continue
                with open(p, "rb") as f:
                    content = f.read()
                results.append({"source": "file", "path": p, "size": len(content)})
            except Exception:
                continue
        return results

    async def collect_from_api(self, url: str) -> list[dict[str, Any]]:
        loop = asyncio.get_event_loop()
        def _fetch():
            try:
                with urllib.request.urlopen(url, timeout=15) as resp:
                    return resp.read().decode("utf-8")
            except Exception:
                return ""
        content = await loop.run_in_executor(None, _fetch)
        return [{"source": "api", "url": url, "content": content[:3000]}]

    async def collect_page(self, url: str) -> dict[str, Any]:
        try:
            from .web_reach import WebReach
            reach = WebReach()
            page = await reach.fetch(url)
            return {
                "url": page.url, "title": page.title, "content": page.text[:5000],
                "links": page.links[:10], "images": page.images[:5],
                "status": page.status_code, "metadata": page.metadata,
            }
        except ImportError:
            return {"url": url, "error": "WebReach not available"}

    async def aggregate_materials(self, *sources) -> list[dict[str, Any]]:
        materials = []
        for ds in sources:
            materials.extend(ds)
        return materials

    def extract_key_info(self, materials: list[dict[str, Any]]) -> dict[str, Any]:
        keys = set()
        for m in materials:
            keys.update(m.keys())
        return {"keys": list(keys), "count": len(materials)}

    @staticmethod
    def _is_allowed_by_robots(url: str) -> bool:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            with urllib.request.urlopen(robots_url, timeout=5) as resp:
                content = resp.read().decode("utf-8").lower()
            if "disallow: /" in content:
                return False
            return True
        except Exception:
            return True
