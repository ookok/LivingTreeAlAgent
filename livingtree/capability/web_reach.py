"""WebReach — Agentic web scraping with structured content extraction.

Combines:
- readability-lxml: Firefox Reader View-style main content extraction
- BeautifulSoup4 + lxml: HTML parsing and link discovery
- aiohttp: async HTTP fetching
- LLM integration: intelligent link selection + content summarization

Agent Reach concept: the agent autonomously decides what to scrape,
follows relevant links, and extracts structured information from pages.

Usage:
    reach = WebReach()
    page = await reach.fetch("https://docs.python.org/3/")
    # → PageContent(title, text, links, metadata)
    
    results = await reach.search_and_extract("Python async best practices")
    # → [ScrapedPage, ...] with main content extracted
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from ..network.resilience import resilient_fetch, with_resilience

try:
    from readability import Document as ReadabilityDocument
    HAS_READABILITY = True
except ImportError:
    HAS_READABILITY = False


@dataclass
class PageContent:
    url: str
    title: str = ""
    text: str = ""
    html: str = ""
    summary: str = ""
    links: list[dict] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    status_code: int = 0
    content_type: str = ""
    fetch_time_ms: float = 0.0

    def snippet(self, max_chars: int = 200) -> str:
        return self.text[:max_chars].strip()

    def format_display(self) -> str:
        lines = [f"[bold #58a6ff]{self.title or self.url}[/bold #58a6ff]"]
        lines.append(f"  [dim]{self.url}[/dim]")
        if self.text:
            lines.append(f"  {self.snippet(150)}")
        if self.links:
            internal = [l for l in self.links if l.get("type") == "internal"]
            if internal:
                lines.append(f"  [dim]{len(internal)} internal links[/dim]")
        return "\n".join(lines)


class WebReach:
    """Agentic web scraper with content extraction and link discovery.

    Fetch → Parse → Extract main content → Discover links → (optional) follow.
    """

    USER_AGENT = "LivingTree/2.1 WebReach (Mozilla/5.0 compatible)"
    TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5)
    MAX_CONTENT_LENGTH = 500_000
    MAX_LINKS = 50

    def __init__(self, consciousness: Any = None):
        self._consciousness = consciousness

    async def fetch(self, url: str) -> PageContent:
        t0 = time.monotonic()
        page = PageContent(url=url)

        try:
            status, body, final_url = await resilient_fetch(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=15.0,
                max_retries=2,
                use_mirror=False,  # generic URLs don't have mirrors
                use_proxy=True,
            )

            page.status_code = status
            page.url = final_url

            if status != 200:
                page.text = f"HTTP {status}"
                page.fetch_time_ms = (time.monotonic() - t0) * 1000
                return page

            raw = body.decode(errors="replace")
            if len(raw) > self.MAX_CONTENT_LENGTH:
                raw = raw[:self.MAX_CONTENT_LENGTH]

            page.html = raw
            page = self._extract_content(page, raw, url)
            page.fetch_time_ms = (time.monotonic() - t0) * 1000

        except Exception as e:
            page.text = f"Error: {e}"
            page.fetch_time_ms = (time.monotonic() - t0) * 1000

        return page

    async def fetch_multiple(self, urls: list[str]) -> list[PageContent]:
        tasks = [self.fetch(u) for u in urls]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def search_and_extract(self, query: str,
                                  max_pages: int = 5,
                                  spark_search=None) -> list[PageContent]:
        pages = []

        if spark_search:
            results = await spark_search.query(query, limit=max_pages)
            urls = [r.url for r in results if r.url]
            if urls:
                logger.info(f"WebReach fetching {len(urls)} URLs from search")
                pages = await self.fetch_multiple(urls[:max_pages])
                return pages

        return pages

    async def fetch_with_links(self, url: str, follow_internal: bool = False,
                                max_depth: int = 1) -> list[PageContent]:
        pages = [await self.fetch(url)]
        if not follow_internal or max_depth <= 1:
            return pages

        current = pages[0]
        internal_links = [
            l for l in current.links
            if l.get("type") == "internal" and l.get("url")
        ]

        if self._consciousness and len(internal_links) > 5:
            links_text = "\n".join(
                f"{i}. [{l['text'][:60]}] {l['url']}"
                for i, l in enumerate(internal_links[:20])
            )
            prompt = (
                f"From this page '{current.title}', select up to {max_pages - 1} "
                f"most relevant internal links to follow for deeper context:\n{links_text}\n"
                "Output only link numbers, comma-separated: 0,3,7"
            )
            try:
                result = await self._consciousness.chain_of_thought(prompt, steps=1, max_tokens=100)
                selected = [int(x.strip()) for x in result.split(",") if x.strip().isdigit()]
                for idx in selected[:max_pages - 1]:
                    if 0 <= idx < len(internal_links):
                        deeper = await self.fetch(internal_links[idx]["url"])
                        pages.append(deeper)
            except Exception:
                pass

        return pages

    # ── Private ──

    def _extract_content(self, page: PageContent, html: str, base_url: str) -> PageContent:
        if HAS_READABILITY:
            try:
                doc = ReadabilityDocument(html)
                page.title = doc.title() or ""
                page.summary = doc.summary() or ""
            except Exception:
                pass

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            try:
                soup = BeautifulSoup(html, "html.parser")
            except Exception:
                return page

        if not page.title:
            title_tag = soup.find("title")
            if title_tag:
                page.title = title_tag.get_text(strip=True)

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe"]):
            tag.decompose()

        body = soup.find("body") or soup
        text = body.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        page.text = text[:10000]

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            page.metadata["description"] = meta_desc.get("content", "")

        page.links = self._extract_links(soup, base_url)
        page.images = self._extract_images(soup, base_url)

        return page

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        links = []
        base_domain = urlparse(base_url).netloc
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            full_url = urljoin(base_url, href)
            if full_url in seen:
                continue
            seen.add(full_url)

            link_domain = urlparse(full_url).netloc
            link_type = "internal" if link_domain == base_domain else "external"

            links.append({
                "url": full_url,
                "text": a.get_text(strip=True)[:80],
                "type": link_type,
            })

            if len(links) >= self.MAX_LINKS:
                break

        return links

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        images = []
        for img in soup.find_all("img", src=True):
            src = img["src"].strip()
            if src:
                images.append(urljoin(base_url, src))
            if len(images) >= 20:
                break
        return images

    def format_search_results(self, pages: list[PageContent]) -> str:
        if not pages:
            return "[dim]No pages fetched[/dim]"

        lines = [f"[bold #58a6ff]WebReach: {len(pages)} pages[/bold #58a6ff]"]
        for p in pages:
            status = f"[#3fb950]{p.status_code}[/#3fb950]" if p.status_code == 200 else f"[#f85149]{p.status_code}[/#f85149]"
            lines.append(f"  {status} [bold]{p.title[:80]}[/bold]")
            lines.append(f"  [dim]{p.url}[/dim]")
            lines.append(f"  {p.snippet(120)}")
            if p.links:
                lines.append(f"  [dim]{len(p.links)} links | {len(p.images)} images[/dim]")
            lines.append("")

        return "\n".join(lines)
