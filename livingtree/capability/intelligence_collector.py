"""Intelligence Collector — complete Hermes intelligence pipeline.

Orchestrates the full workflow as a cognitive research system:

  User intent → AdaptiveExtractor(分析页面结构) → OnlineStreamParser(解析附件)
  → CognitiveDelta(知识比对) → DocumentKB(仅存认知增量) → ResultReport(反馈用户)

Design principles:
  1. Never assume HTML structure — AdaptiveExtractor auto-infers
  2. Attachments online-only — OnlineStreamParser never saves to disk
  3. Only store cognitive increments — CognitiveDelta blocks duplicates
  4. Store only: source, date, summary, diff, conclusion (not full text)
  5. Prefer missing over noise — discard rather than pollute

Usage:
    collector = IntelligenceCollector()
    result = await collector.run("查一下最近的环境影响评价公示")
    print(f"新增: {result.stored}条, 更新: {result.updated}条, 丢弃: {result.skipped}条")
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

from .adaptive_extractor import CrawlerSession, fetch_with_js


@dataclass
class CollectResult:
    """Intelligence collection result report."""
    task: str = ""
    pages_analyzed: int = 0
    items_found: int = 0
    stored: int = 0      # 新增空白
    updated: int = 0     # 更新差异
    skipped: int = 0     # 重复丢弃
    attachments_parsed: int = 0
    elapsed_ms: float = 0
    details: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class IntelligenceCollector:
    """Hermes intelligence collector — complete cognitive pipeline.

    Auto-reasons about user intent:
      - List page → auto-follows detail links → extracts full info
      - Single page → extracts directly
      - Pagination → auto-crawls next pages (bounded)
      - Detail pages → re-extracts for attachment URLs + full content

    Usage:
        collector = IntelligenceCollector()
        result = await collector.collect_from_url(
            "https://example.gov.cn/announcements",
            deep=True,  # auto-follow detail links
        )
    """

    def __init__(self, max_attach_per_page: int = 10, max_detail_pages: int = 20,
                 max_pagination_pages: int = 5):
        self._max_attach = max_attach_per_page
        self._max_detail = max_detail_pages
        self._max_pagination = max_pagination_pages
        self._session = CrawlerSession()
        self._session.rotate_headers()

    async def collect_from_url(
        self,
        url: str,
        intent: str = "",
        max_items: int = 50,
        hub: Any = None,
        use_llm: bool = True,
        js_render: bool = False,
        deep: bool = True,           # Auto-follow detail links
    ) -> CollectResult:
        """Full pipeline for a single URL.

        Args:
            url: target page URL
            intent: user intent description
            hub: LivingTree hub for LLM extraction
            use_llm: use LLM for extraction (recommended)
            js_render: use Playwright for JS-rendered pages
        """
        start = time.time()
        result = CollectResult(task=f"{intent}: {url}")

        try:
            # Anti-crawling: delay + rotate headers
            self._session.respect_rate_limit(min_delay=1.0, max_delay=3.0)

            if js_render:
                html = await fetch_with_js(url, timeout=30, scroll=True)
                if not html:
                    result.errors.append("JS render returned empty")
                    return result
            else:
                from ..network.resilience import resilient_fetch
                status, html_bytes, _ = await resilient_fetch(
                    url,
                    timeout=25,
                    use_accelerator=True,
                    headers=self._session.headers,
                )
                if status != 200 or not html_bytes:
                    result.errors.append(f"HTTP {status}")
                    return result
                html = html_bytes.decode("utf-8", errors="replace")

            result.pages_analyzed = 1
            return await self._collect_from_html_inner(
                html, base_url=url, intent=intent, max_items=max_items,
                hub=hub, use_llm=use_llm, start_time=start,
            )
        except Exception as e:
            result.errors.append(str(e))
            return result

    async def _collect_from_html_inner(
        self,
        html: str,
        base_url: str = "",
        intent: str = "",
        max_items: int = 50,
        hub: Any = None,
        use_llm: bool = True,
        start_time: float = None,
    ) -> CollectResult:
        """Pipeline from HTML content."""
        start = start_time or time.time()
        result = CollectResult(task=f"{intent}: {base_url}")

        # Step 1: Adaptive page structure analysis
        # Strategy: cached skill → LLM analysis (first time) → heuristic fallback
        from .adaptive_extractor import AdaptiveExtractor, get_skill_registry
        extractor = AdaptiveExtractor()
        registry = get_skill_registry()

        # Extract domain from URL
        from urllib.parse import urlparse as _up
        domain = (_up(base_url).hostname or base_url)[:60]

        # Try cached skill first
        skill = registry.get(domain, html)
        if skill:
            logger.debug("IntelligenceCollector: using cached skill for %s (used %dx)", domain, skill.usage_count)
            page = registry.apply(skill, html, base_url)
        elif use_llm and hub:
            # First visit: LLM analyzes + creates skill
            logger.debug("IntelligenceCollector: LLM creating skill for %s", domain)
            page = extractor.extract(html, base_url)  # quick heuristic first
            if page.items:
                registry.learn(domain, hub, html, page.items[:5])
            # Then do full LLM extraction
            page = extractor.extract_with_llm(html, base_url, hub)
        else:
            page = extractor.extract(html, base_url)
        items = page.items[:max_items]

        if not items:
            result.errors.append("No items found on page")
            return result

        result.items_found = len(items)
        logger.debug("IntelligenceCollector: %d items found (%s)", len(items), page.page_type)

        # Step 2: Load existing knowledge for comparison
        existing = self._load_existing_knowledge(base_url)

        # Step 3: Initialize engines
        from .online_stream_parser import OnlineStreamParser
        from ..knowledge.cognitive_delta import CognitiveDelta
        stream_parser = OnlineStreamParser()
        delta = CognitiveDelta()

        # Step 4: Process each item
        for item in items[:max_items]:
            if not item.confidence or item.confidence < 0.2:
                continue

            new_entry = {
                "title": item.title,
                "content": item.raw_text[:1000],
                "source": base_url,
                "date": item.publish_date,
                "status": item.status,
                "fields": {f.key: f.value for f in item.fields},
            }

            # Step 5: Parse attachments (online only)
            attachment_summaries = []
            for att_url in item.attachment_links[:self._max_attach]:
                parse_result = await stream_parser.parse_url(att_url, timeout=15)
                if parse_result.success and parse_result.summary:
                    attachment_summaries.append(parse_result.summary[:500])
                    result.attachments_parsed += 1

            # Step 5b: Deep crawl — auto-follow detail page for full info
            if deep and item.detail_url and item.detail_url != base_url:
                self._session.respect_rate_limit(min_delay=0.5, max_delay=1.5)
                detail_html = await self._fetch_page(item.detail_url)
                if detail_html:
                    detail_page = extractor.extract(detail_html, item.detail_url)
                    if detail_page.items:
                        detail = detail_page.items[0]
                        # Merge: detail page overrides list page data
                        if detail.title and len(detail.title) > len(item.title):
                            new_entry["title"] = detail.title
                        if detail.publish_date:
                            new_entry["date"] = detail.publish_date
                        if detail.status:
                            new_entry["status"] = detail.status
                        # Detail page attachments are the real ones
                        if detail.attachment_links:
                            item.attachment_links = detail.attachment_links
                            for att_url in detail.attachment_links[:self._max_attach]:
                                parse_result = await stream_parser.parse_url(att_url, timeout=15)
                                if parse_result.success and parse_result.summary:
                                    attachment_summaries.append(parse_result.summary[:500])
                                    result.attachments_parsed += 1
                        # Use detail page content as the primary source
                        if detail.raw_text and len(detail.raw_text) > len(new_entry["content"]):
                            new_entry["content"] = detail.raw_text[:2000]

            # Step 6: Cognitive delta comparison
            delta_result = delta.evaluate(new_entry, existing)
            entry = delta.build_entry(new_entry, existing, attachment_summaries)

            # Step 7: Store only if increment
            if delta_result.decision == "gap":
                self._store_entry(entry, update_existing=False)
                result.stored += 1
                result.details.append({
                    "title": item.title[:100],
                    "decision": "新增",
                    "reason": delta_result.reason,
                })
            elif delta_result.decision == "diff":
                self._store_entry(entry, update_existing=True)
                result.updated += 1
                result.details.append({
                    "title": item.title[:100],
                    "decision": "更新",
                    "diff": delta_result.diff_summary[:200],
                })
            else:
                result.skipped += 1

        result.elapsed_ms = (time.time() - start) * 1000
        self._log_result(result)
        return result

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a single page, returning HTML string or None."""
        try:
            from ..network.resilience import resilient_fetch
            status, html_bytes, _ = await resilient_fetch(
                url, timeout=20, use_accelerator=True,
                headers=self._session.headers,
            )
            if status == 200 and html_bytes:
                return html_bytes.decode("utf-8", errors="replace")
        except Exception:
            pass
        return None

    async def _crawl_paginated(self, start_html: str, base_url: str,
                               max_pages: int = 5) -> list[str]:
        """Auto-detect and crawl paginated list pages. Returns all HTML contents."""
        from .adaptive_extractor import AdaptiveExtractor
        extractor = AdaptiveExtractor()
        htmls = [start_html]
        seen_urls = {base_url}

        for _ in range(max_pages - 1):
            pagination_links = extractor.detect_pagination(htmls[-1], base_url)
            found_new = False
            for link in pagination_links:
                if link in seen_urls:
                    continue
                seen_urls.add(link)
                self._session.respect_rate_limit(min_delay=0.5, max_delay=1.5)
                html = await self._fetch_page(link)
                if html:
                    htmls.append(html)
                    found_new = True
                    break
            if not found_new:
                break

        return htmls

    async def collect_from_intent(
        self,
        intent: str,
        urls: list[str] = None,
    ) -> CollectResult:
        """Collect from user intent with optional URL list."""
        aggregated = CollectResult(task=intent)
        urls = urls or []

        for url in urls:
            r = await self.collect_from_url(url, intent)
            aggregated.pages_analyzed += r.pages_analyzed
            aggregated.items_found += r.items_found
            aggregated.stored += r.stored
            aggregated.updated += r.updated
            aggregated.skipped += r.skipped
            aggregated.attachments_parsed += r.attachments_parsed
            aggregated.details.extend(r.details)
            aggregated.errors.extend(r.errors)

        return aggregated

    # ═══ Knowledge Base Interface ═══

    def _load_existing_knowledge(self, source_hint: str = "") -> list[dict]:
        """Load existing entries for comparison."""
        try:
            from ..knowledge.document_kb import DocumentKB
            kb = DocumentKB()
            hits = kb.search(source_hint, top_k=20)
            return [
                {
                    "id": h.chunk.id,
                    "title": getattr(h, 'title', ''),
                    "content": h.chunk.text[:500],
                    "source": getattr(h.chunk, 'doc_id', ''),
                    "date": "",
                }
                for h in hits
            ]
        except Exception:
            return []

    def _store_entry(self, entry: dict, update_existing: bool = False) -> None:
        """Store a cognitive increment to knowledge base."""
        try:
            from ..knowledge.document_kb import DocumentKB
            kb = DocumentKB()
            if update_existing and entry.get("references_existing_id"):
                # Update: overwrite previous version
                kb.ingest(
                    entry.get("summary", "")[:2000],
                    title=entry.get("title", ""),
                    source=entry.get("source", ""),
                )
            else:
                kb.ingest(
                    entry.get("summary", "")[:2000],
                    title=entry.get("title", ""),
                    source=entry.get("source", ""),
                )
        except Exception as e:
            logger.debug("Knowledge store error: %s", e)

    @staticmethod
    def _log_result(result: CollectResult) -> None:
        logger.info(
            "IntelligenceCollector: 新增%d 更新%d 丢弃%d (共%d项, %.0fms)",
            result.stored, result.updated, result.skipped,
            result.items_found, result.elapsed_ms,
        )
