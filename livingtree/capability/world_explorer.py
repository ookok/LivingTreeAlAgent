"""World Explorer — Spontaneous domain exploration and World Knowledge generation.

arXiv:2604.18131 Phase 1 (Native Evolution): systematically explore unseen
websites during idle time, cluster URL prefixes, compress page observations
into compact World Knowledge Markdown.

Pipeline: URL crawl → page fetch → structure extraction → prefix clustering
         → navigation map → World Knowledge generation → KnowledgeBase storage
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

from loguru import logger

from ..knowledge.world_knowledge import PageSummary, WorldKnowledge


@dataclass
class ExploreConfig:
    max_pages: int = 30
    max_depth: int = 2
    max_concurrent: int = 5
    delay_seconds: float = 0.5
    timeout_seconds: float = 15.0
    include_external: bool = False
    cluster_min_size: int = 2
    user_agent: str = "LivingTree/2.5 WorldExplorer"


@dataclass
class ExploreResult:
    domain: str
    pages_fetched: int
    pages_failed: int
    crawl_time_ms: float
    world_knowledge: Any = None   # WorldKnowledge instance
    errors: list[str] = field(default_factory=list)


class WorldExplorer:
    """Orchestrate Phase 1: explore domain → compress → World Knowledge.

    Integrates: LightCrawler (crawl) → WebReach/IntelligenceCollector (fetch+extract)
              → WorldKnowledge (compress) → KnowledgeBase (store).
    """

    def __init__(self, config: ExploreConfig | None = None):
        self.config = config or ExploreConfig()
        self._crawler = None
        self._reach = None
        self._collector = None
        self._kb = None

    async def explore(self, domain_or_url: str) -> ExploreResult:
        """Full pipeline: crawl → fetch → compress → World Knowledge."""
        t0 = time.perf_counter()
        domain = self._normalize_domain(domain_or_url)
        errors: list[str] = []
        pages: list[PageSummary] = []

        start_url = f"https://{domain}" if not domain_or_url.startswith("http") else domain_or_url

        try:
            urls = await self._crawl_urls(start_url)
        except Exception as e:
            logger.warning(f"WorldExplorer crawl failed for {domain}: {e}")
            errors.append(f"crawl: {e}")
            urls = [start_url]

        urls = urls[:self.config.max_pages]
        logger.info(f"WorldExplorer exploring {domain}: {len(urls)} URLs")

        sem = asyncio.Semaphore(self.config.max_concurrent)

        async def _fetch_one(url: str) -> PageSummary | None:
            async with sem:
                try:
                    await asyncio.sleep(self.config.delay_seconds)
                    return await self._fetch_and_summarize(url)
                except Exception as e:
                    logger.debug(f"WorldExplorer fetch failed {url}: {e}")
                    return None

        tasks = [_fetch_one(u) for u in urls]
        results = await asyncio.gather(*tasks)
        pages = [r for r in results if r is not None]
        pages_failed = len(urls) - len(pages)

        crawl_time_ms = (time.perf_counter() - t0) * 1000

        if not pages:
            errors.append("no pages fetched")
            return ExploreResult(domain=domain, pages_fetched=0,
                                 pages_failed=pages_failed or len(urls),
                                 crawl_time_ms=crawl_time_ms, errors=errors)

        from ..knowledge.world_knowledge import WorldKnowledge
        wk = WorldKnowledge.from_exploration(domain, pages, crawl_time_ms)

        return ExploreResult(domain=domain, pages_fetched=len(pages),
                             pages_failed=pages_failed, crawl_time_ms=crawl_time_ms,
                             world_knowledge=wk, errors=errors)

    async def _crawl_urls(self, start_url: str) -> list[str]:
        """Discover URLs via LightCrawler Spider or simple aiohttp fetch."""
        try:
            from ..capability.light_crawler import LightCrawler
            crawler = LightCrawler()
            page = await crawler.fetch(start_url)
            urls = [start_url]
            seen = {start_url}
            if page and page.items:
                for item in page.items:
                    link = item.get("url", "")
                    if link and link not in seen and self._is_same_domain(start_url, link):
                        urls.append(link)
                        seen.add(link)
                        if len(urls) >= self.config.max_pages:
                            break
            return urls
        except Exception:
            return [start_url]

    async def _fetch_and_summarize(self, url: str) -> PageSummary | None:
        """Fetch page and extract structured summary."""
        try:
            from ..network.resilience import resilient_fetch_text
            html = await resilient_fetch_text(url, timeout=self.config.timeout_seconds)
            if not html:
                return None

            title, summary, page_type, links = self._extract_page_info(html, url)
            actionable = any(kw in html.lower() for kw in
                           ["<form", "download", "api/", ".pdf", "submit"])

            return PageSummary(
                url=url, title=title, summary=summary[:100],
                page_type=page_type, actionable=actionable,
                internal_links=links,
            )
        except Exception:
            return None

    def _extract_page_info(self, html: str, base_url: str) -> tuple[str, str, str, list[str]]:
        title = base_url.split("/")[-1] or base_url
        summary = ""
        page_type = "detail"
        internal_links: list[str] = []

        try:
            import re
            m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            if m:
                title = m.group(1).strip()[:120]

            text = re.sub(r"<[^>]+>", " ", html[:8000])
            text = re.sub(r"\s+", " ", text).strip()
            summary = text[:100]

            if re.search(r"<ul|<ol|<li", html[:4000], re.IGNORECASE):
                page_type = "list"
            elif re.search(r"<table", html[:4000], re.IGNORECASE):
                page_type = "table"
            elif re.search(r"<form", html[:4000], re.IGNORECASE):
                page_type = "form"

            for m in re.finditer(r'href=["\']([^"\']+)["\']', html[:16000]):
                link = m.group(1)
                if link.startswith("#") or link.startswith("javascript:"):
                    continue
                full = urljoin(base_url, link)
                if self._is_same_domain(base_url, full):
                    internal_links.append(full)
        except Exception:
            pass

        return title, summary, page_type, internal_links[:15]

    @staticmethod
    def _normalize_domain(url_or_domain: str) -> str:
        if "://" in url_or_domain:
            return urlparse(url_or_domain).netloc
        return url_or_domain.lstrip("www.")

    @staticmethod
    def _is_same_domain(base: str, other: str) -> bool:
        try:
            return urlparse(base).netloc == urlparse(other).netloc
        except Exception:
            return False


async def explore_domain(domain_or_url: str, max_pages: int = 30) -> ExploreResult:
    explorer = WorldExplorer(ExploreConfig(max_pages=max_pages))
    return await explorer.explore(domain_or_url)


__all__ = ["WorldExplorer", "ExploreConfig", "ExploreResult", "explore_domain"]
