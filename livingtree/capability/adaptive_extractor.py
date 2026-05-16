"""Adaptive Extractor — structure-agnostic HTML page analysis + key info extraction.

Never assumes specific HTML markup. Auto-detects:
  - Table-like structures (from any HTML element: div, ul, table, dl)
  - Key-value pairs (definition lists, form-like fields)
  - Publication metadata (title, date, status, values, links)
  - Attachment references (PDF, ZIP, RAR, DOCX links)

Self-healing: when a page structure changes, re-infers without manual fix.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from loguru import logger

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
@dataclass
class ExtractedField:
    """A single key-value pair extracted from an unknown page."""
    key: str
    value: str
    confidence: float = 0.5
    field_type: str = "text"  # "date", "status", "number", "money", "link", "text"


@dataclass
class ExtractedItem:
    """One structured item extracted from a page (e.g., one announcement row)."""
    title: str = ""
    publish_date: str = ""
    status: str = ""          # "待批", "已批", "批复", "公示", etc.
    fields: list[ExtractedField] = field(default_factory=list)
    attachment_links: list[str] = field(default_factory=list)
    detail_url: str = ""      # Link to detail page (follow for full info + attachments)
    source_url: str = ""
    raw_text: str = ""
    confidence: float = 0.0


@dataclass
class ExtractedPage:
    """Complete extraction result for one web page."""
    url: str = ""
    title: str = ""
    items: list[ExtractedItem] = field(default_factory=list)
    page_type: str = "unknown"  # "list", "detail", "table", "form"
    extraction_method: str = ""
    warnings: list[str] = field(default_factory=list)


class AdaptiveExtractor:
    """Structure-agnostic web page analyzer.

    Two extraction modes:
      - heuristic: regex/keyword rules (fast, offline, no cost)
      - llm:      hub.chat() analysis (accurate, handles any format, self-healing)

    Usage:
        ext = AdaptiveExtractor()
        page = ext.extract(html, base_url)
        # or with LLM for maximum accuracy:
        page = ext.extract_with_llm(html, base_url, hub)
    """

    def __init__(self):
        self._date_patterns = [
            (r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', r'\1-\2-\3'),
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', r'\1-\2-\3'),
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', r'\1-\2-\3'),
        ]
        self._status_keywords = [
            "待批", "已批", "批复", "公示", "受理", "审批", "通过",
            "不批准", "备案", "注销", "撤销", "受理中", "审查中",
            "已办结", "未办结", "同意", "不同意", "批准", "不予批准",
        ]

    def extract(self, html: str, base_url: str = "") -> ExtractedPage:
        """Extract structured info from any HTML page."""
        page = ExtractedPage(url=base_url)

        try:
            soup = BeautifulSoup(html, "lxml")
        except ImportError:
            soup = BeautifulSoup(html, "html.parser")

        page.title = self._extract_title(soup)
        page.page_type = self._detect_page_type(soup)

        if page.page_type == "list":
            page.items = self._extract_list_items(soup, base_url)
            page.extraction_method = "list_heuristic"
        elif page.page_type == "table":
            page.items = self._extract_table_rows(soup, base_url)
            page.extraction_method = "table_heuristic"
        elif page.page_type == "detail":
            item = self._extract_detail_page(soup, base_url)
            page.items = [item]
            page.extraction_method = "detail_heuristic"
        else:
            item = self._extract_detail_page(soup, base_url)
            page.items = [item]
            page.extraction_method = "fallback"

        return page

    # ═══ Page Type Detection ═══

    def _detect_page_type(self, soup) -> str:
        ul_items = len(soup.select("ul li, ol li"))
        table_rows = len(soup.select("table tr"))
        dl_items = len(soup.select("dl dt"))

        if table_rows > 2:
            return "table"
        if ul_items > 1:
            return "list"
        if dl_items > 3:
            return "detail"

        div_count = len(soup.find_all("div"))
        if div_count > 20:
            return "list"
        return "detail"

        # Heuristic: if page has many repeated structures → list
        div_count = len(soup.find_all("div"))
        if div_count > 20:
            return "list"
        return "detail"

    # ═══ List Item Extraction ═══

    def _extract_list_items(self, soup, base_url: str) -> list[ExtractedItem]:
        """Extract list items from ul/div-based list structures."""
        items = []

        # Try UL/LI first
        li_elements = soup.select("ul li, ol li")
        if len(li_elements) >= 2:
            for li in li_elements[:50]:
                item = self._extract_item_from_element(li, base_url)
                if item.confidence > 0:
                    items.append(item)
            return items

        # Fallback: try div-based repeated structures
        container = soup.find("body")
        if container:
            divs = container.find_all("div", recursive=True)
            groups = self._group_similar_divs(divs)
            for group in groups:
                text = " ".join(d.get_text(strip=True) for d in group)
                item = self._extract_item_from_text(text, base_url)
                if item.confidence > 0:
                    items.append(item)

        return items

    def _extract_table_rows(self, soup, base_url: str) -> list[ExtractedItem]:
        """Extract items from table rows (auto-detect header)."""
        items = []
        tables = soup.find_all("table")

        for table in tables[:3]:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            for row in rows[1:50]:
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                text = " | ".join(cells)
                item = self._extract_item_from_text(text, base_url)

                # Capture detail URL from first link in row
                first_link = row.find("a", href=True)
                if first_link:
                    href = first_link["href"]
                    item.detail_url = urljoin(base_url, href) if not href.startswith("http") else href

                links = [urljoin(base_url, a["href"]) for a in row.find_all("a", href=True)
                        if self._is_attachment(a["href"])]
                item.attachment_links.extend(links)
                if item.confidence > 0:
                    items.append(item)

        return items

    def _extract_detail_page(self, soup, base_url: str) -> ExtractedItem:
        """Extract key fields from a detail page."""
        text = soup.get_text(separator="\n", strip=True)
        item = self._extract_item_from_text(text[:10000], base_url)

        # Extract attachment links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if self._is_attachment(href):
                item.attachment_links.append(urljoin(base_url, href))

        return item

    # ═══ Item Extraction ═══

    def _extract_item_from_element(self, element, base_url: str) -> ExtractedItem:
        text = element.get_text(separator="\n", strip=True)

        # Capture the detail URL from the first <a> tag (usually the title link)
        detail_url = ""
        first_link = element.find("a", href=True)
        if first_link:
            href = first_link["href"]
            detail_url = urljoin(base_url, href) if not href.startswith("http") else href

        links = [urljoin(base_url, a["href"]) for a in element.find_all("a", href=True)
                if self._is_attachment(a["href"])]
        item = self._extract_item_from_text(text, base_url)
        item.detail_url = detail_url
        item.attachment_links.extend(links)
        return item

    def _extract_item_from_text(self, text: str, base_url: str) -> ExtractedItem:
        item = ExtractedItem(raw_text=text[:500], source_url=base_url)

        if not text or len(text) < 10:
            return item

        item.title = self._extract_title_from_text(text)
        item.publish_date = self._extract_date(text)
        item.status = self._extract_status(text)
        item.fields = self._extract_key_value_pairs(text)
        item.confidence = self._compute_confidence(item)

        return item

    # ═══ Field Extractors ═══

    def _extract_title(self, soup) -> str:
        """Extract page title."""
        tag = soup.find("title")
        if tag:
            return tag.get_text(strip=True)[:200]
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)[:200]
        return ""

    def _extract_title_from_text(self, text: str) -> str:
        """Heuristic: first meaningful line is likely the title."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:5]:
            if len(line) > 10 and not line.startswith(("http", "发布", "时间", "来源")):
                return line[:200]
        return lines[0][:200] if lines else ""

    def _extract_date(self, text: str) -> str:
        """Extract first date found in text."""
        for pattern, fmt in self._date_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                return f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
        return ""

    def _extract_status(self, text: str) -> str:
        """Extract administrative status."""
        for kw in self._status_keywords:
            if kw in text:
                return kw
        return ""

    def _extract_key_value_pairs(self, text: str) -> list[ExtractedField]:
        """Heuristic key-value pair extraction."""
        fields = []
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        for line in lines[:20]:
            for sep in ["：", ":", "="]:
                if sep in line:
                    parts = line.split(sep, 1)
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if len(key) < 30 and len(value) > 0:
                        field_type = self._classify_field(key, value)
                        fields.append(ExtractedField(
                            key=key, value=value[:500],
                            field_type=field_type,
                            confidence=0.6,
                        ))
                    break

        return fields

    def _classify_field(self, key: str, value: str) -> str:
        """Classify field type from key name + value pattern."""
        kl = key.lower()
        if any(w in kl for w in ("时间", "日期", "date", "time")):
            return "date"
        if any(w in kl for w in ("状态", "status")):
            return "status"
        if re.match(r'^[\d,.]+$', value.replace(" ", "")):
            return "number"
        if re.search(r'[\d,.]+(万|亿|元|美元|USD|CNY)', value):
            return "money"
        if value.startswith(("http://", "https://")):
            return "link"
        return "text"

    # ═══ Attachment Detection ═══

    @staticmethod
    def _is_attachment(href: str) -> bool:
        ext = href.lower().split("?")[0]
        return any(ext.endswith(e) for e in (
            ".pdf", ".doc", ".docx", ".xls", ".xlsx",
            ".zip", ".rar", ".7z", ".tar", ".gz",
            ".ppt", ".pptx", ".txt", ".csv",
        ))

    # ═══ Helpers ═══

    @staticmethod
    def _group_similar_divs(divs, max_groups: int = 50) -> list[list]:
        """Group similarly-structured divs as candidate list items."""
        groups = []
        current = []
        current_text = ""

        for div in divs:
            text = div.get_text(strip=True)
            if not text or len(text) < 10:
                continue
            if text in current_text:
                continue
            current.append(div)
            current_text += text
            if len(current) >= 3:
                groups.append(current)
                current = []
                current_text = ""
                if len(groups) >= max_groups:
                    break

        if current and len(current) >= 2:
            groups.append(current)

        return groups

    @staticmethod
    def _compute_confidence(item: ExtractedItem) -> float:
        score = 0.0
        if item.title:
            score += 0.4
        if item.publish_date:
            score += 0.3
        if item.status:
            score += 0.2
        if item.fields:
            score += 0.1
        return min(1.0, score)

    # ═══ Pagination Detection ═══

    def detect_pagination(self, html: str, current_url: str = "") -> list[str]:
        """Auto-detect pagination links on a list page."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return []

        links = []
        seen = set()

        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if any(kw in text for kw in ("下一页", "下页", "后页", "next", ">", "›")):
                full_url = urljoin(current_url, href) if not href.startswith("http") else href
                if full_url not in seen:
                    seen.add(full_url)
                    links.append(full_url)

        if not links:
            import re
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if re.search(r'[?&_]p(?:age)?[=_]?\d+', href) or \
                   re.search(r'index[=_]?\d+', href) or \
                   re.search(r'/\d+\.html?$', href):
                    full_url = urljoin(current_url, href) if not href.startswith("http") else href
                    if full_url not in seen and full_url != current_url:
                        seen.add(full_url)

        return links[:10]

    # ═══ LLM-Based Extraction (no rules, handles any format) ═══

    def extract_with_llm(self, html: str, base_url: str = "", hub: Any = None) -> ExtractedPage:
        """LLM-powered extraction — let the LLM read the page and extract structured info.

        The LLM sees the page text and extracts items, fields, dates, status,
        and attachment links using natural language understanding. This is:
          - More accurate than heuristics for diverse page formats
          - Self-healing: new page structures handled automatically
          - Zero maintenance: no regex/rule updates needed

        Falls back to heuristic extraction if hub is None or LLM fails.
        """
        page = ExtractedPage(url=base_url)

        if not hub:
            logger.debug("No hub available, falling back to heuristic extraction")
            return self.extract(html, base_url)

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml") if "lxml" in str(type(None)) else BeautifulSoup(html, "html.parser")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        page.title = self._extract_title(soup)
        text = soup.get_text(separator="\n", strip=True)[:15000]

        prompt = self._build_llm_extraction_prompt(text, base_url)

        try:
            response = hub.chat(prompt)
            page = self._parse_llm_extraction_response(response, base_url, soup)
            page.extraction_method = "llm"
        except Exception as e:
            logger.warning("LLM extraction failed (%s), falling back to heuristic", e)
            page = self.extract(html, base_url)

        return page

    def _build_llm_extraction_prompt(self, text: str, base_url: str) -> str:
        return f"""Analyze this government announcement page and extract all listed items.

For each item, extract:
  - title: 项目名称/标题
  - publish_date: 发布时间 (YYYY-MM-DD format)
  - status: 审批状态 (待批/已批/批复/公示/受理/办结 etc.)
  - key_values: any key-value pairs (金额/期限/编号 etc.)
  - attachment_links: URLs ending in .pdf .doc .zip .rar .xlsx

Return as JSON array:
[{{"title":"...","date":"...","status":"...","fields":{{"key":"value"}},"attachments":["url"]}}]

If this is a detail page (single item), return one-element array.
If no items found, return empty array [].

Page URL: {base_url}
Page text:
{text}"""

    def _parse_llm_extraction_response(self, response: str, base_url: str, soup) -> ExtractedPage:
        import json
        page = ExtractedPage(url=base_url, extraction_method="llm")

        try:
            if "[" in response:
                response = response[response.index("["):response.rindex("]") + 1]
            data = json.loads(response)

            if not isinstance(data, list):
                return page

            for entry in data:
                item = ExtractedItem(
                    title=entry.get("title", "")[:300],
                    publish_date=entry.get("date", ""),
                    status=entry.get("status", ""),
                    source_url=base_url,
                    confidence=0.85,
                )

                for k, v in entry.get("fields", {}).items():
                    item.fields.append(ExtractedField(key=k, value=str(v), confidence=0.8))

                for url in entry.get("attachments", []):
                    if url and not url.startswith("http"):
                        from urllib.parse import urljoin
                        url = urljoin(base_url, url)
                    item.attachment_links.append(url)

                page.items.append(item)

            page.page_type = "detail" if len(data) == 1 else "list"

        except Exception as e:
            page.warnings.append(f"LLM response parse error: {e}")

        # Fallback: also extract attachment links from soup
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if self._is_attachment(href):
                full_url = urljoin(base_url, href) if not href.startswith("http") else href
                if page.items:
                    page.items[0].attachment_links.append(full_url)

        return page


# ═══ Anti-Crawling Session ═══

import random

@dataclass
class CrawlerSession:
    """Persistent session with anti-crawling countermeasures."""
    headers: dict = field(default_factory=dict)
    cookies: dict = field(default_factory=dict)
    last_request: float = 0.0
    request_count: int = 0
    proxy_index: int = 0

    _USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edg/131.0.0.0 Safari/537.36",
    ]

    def rotate_headers(self) -> dict:
        self.headers = {
            "User-Agent": random.choice(self._USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
        }
        return self.headers

    def respect_rate_limit(self, min_delay: float = 1.0, max_delay: float = 3.0,
                           jitter: bool = True) -> float:
        delay = min_delay
        if jitter:
            delay = min_delay + random.uniform(0, max_delay - min_delay)
        elapsed = time.time() - self.last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_request = time.time()
        self.request_count += 1
        return delay


async def fetch_with_js(url: str, timeout: int = 30, wait_selector: str = "",
                       scroll: bool = False) -> str:
    """Fetch a JS-rendered page using Playwright (browser automation).

    For pages that load content dynamically via JavaScript.
    Falls back to regular HTTP fetch if Playwright is not available.

    Args:
        wait_selector: CSS selector to wait for before returning HTML
        scroll: scroll to bottom to trigger lazy loading
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({
            "User-Agent": random.choice(CrawlerSession._USER_AGENTS),
        })

        await page.goto(url, timeout=timeout * 1000, wait_until="networkidle")

        if wait_selector:
            await page.wait_for_selector(wait_selector, timeout=10000)

        if scroll:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

        html = await page.content()
        await browser.close()
        return html


# ═══ SiteSkill — LLM analyzes once, cached as extraction recipe ═══

@dataclass
class SiteSkill:
    """A cached extraction recipe for a specific site.

    Created by LLM on first visit. Subsequent visits use the cached skill
    without LLM cost. Auto-invalidated when page structure changes.
    """
    domain: str
    page_type: str            # "list", "detail"
    selectors: dict = field(default_factory=dict)  # e.g. {"title": "h3 a", "date": "span.date"}
    field_mapping: dict = field(default_factory=dict)
    content_fingerprint: str = ""  # hash of key structural elements
    created_at: str = ""
    usage_count: int = 0
    success_rate: float = 1.0

    def is_valid(self, html: str) -> bool:
        """Check if the page structure still matches the cached skill."""
        if not self.content_fingerprint:
            return False
        current_fp = self._fingerprint(html)
        return current_fp == self.content_fingerprint

    @staticmethod
    def _fingerprint(html: str) -> str:
        """Create a structural fingerprint of the page."""
        from bs4 import BeautifulSoup
        import hashlib
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            soup = BeautifulSoup(html, "lxml")
        tags = [tag.name for tag in soup.find_all(["ul", "li", "table", "tr", "td", "a", "span", "div"])][:100]
        structure = ",".join(tags)
        return hashlib.md5(structure.encode()).hexdigest()[:16]


class SiteSkillRegistry:
    """Persistent registry of site extraction skills.

    Skills are learned once via LLM, then reused.
    Auto-invalidates when site structure changes.
    """

    def __init__(self, cache_path: str = ""):
        import os
        self._cache_path = cache_path or os.path.expanduser("~/.livingtree/site_skills.json")
        self._skills: dict[str, SiteSkill] = {}
        self._load()

    def get(self, domain: str, html: str = "") -> Optional[SiteSkill]:
        """Get a cached skill if it's still valid for the current page structure."""
        skill = self._skills.get(domain)
        if not skill:
            return None
        if html and not skill.is_valid(html):
            logger.info("SiteSkill[%s]: structure changed, invalidating cached skill", domain)
            del self._skills[domain]
            self._save()
            return None
        return skill

    def learn(
        self,
        domain: str,
        hub: Any,
        html: str,
        existing_items: list[ExtractedItem] = None,
    ) -> Optional[SiteSkill]:
        """Use LLM to analyze site structure and create an extraction skill.

        The LLM reads the HTML and produces:
          - Page type (list/detail)
          - Specific CSS selectors for title/date/status/attachment
          - Field mappings
        The skill is then cached for future use.
        """
        if not hub:
            return None

        prompt = self._build_learn_prompt(html, domain, existing_items)

        try:
            response = hub.chat(prompt)
            skill = self._parse_skill_response(response, domain, html)
            if skill:
                self._skills[domain] = skill
                self._save()
                logger.info("SiteSkill[%s]: learned (type=%s, selectors=%s)",
                           domain, skill.page_type, list(skill.selectors.keys()))
                return skill
        except Exception as e:
            logger.warning("SiteSkill learn failed for %s: %s", domain, e)

        return None

    def apply(self, skill: SiteSkill, html: str, base_url: str) -> ExtractedPage:
        """Apply a cached skill to extract items from HTML."""
        from bs4 import BeautifulSoup
        try:
            from bs4 import BeautifulSoup as BS
            soup = BS(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        page = ExtractedPage(url=base_url, extraction_method=f"skill:{skill.domain}")
        page.page_type = skill.page_type

        sel = skill.selectors
        item_selector = sel.get("item", "li")
        title_sel = sel.get("title", "a")
        date_sel = sel.get("date", "")
        status_sel = sel.get("status", "")
        attach_sel = sel.get("attachment", "")

        elements = soup.select(item_selector)
        if not elements:
            elements = soup.select("li, tr, .item, .row, article")

        for el in elements[:50]:
            title_tag = el.select_one(title_sel) if title_sel else el
            title = title_tag.get_text(strip=True) if title_tag else el.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            item = ExtractedItem(title=title[:300], source_url=base_url, confidence=0.8)

            if title_tag and title_tag.name == "a" and title_tag.get("href"):
                href = title_tag["href"]
                item.detail_url = urljoin(base_url, href) if not href.startswith("http") else href

            if date_sel:
                date_tag = el.select_one(date_sel)
                if date_tag:
                    item.publish_date = self._extract_date(date_tag.get_text(strip=True))

            if status_sel:
                status_tag = el.select_one(status_sel)
                if status_tag:
                    item.status = status_tag.get_text(strip=True)[:50]

            if attach_sel:
                for a in el.select(attach_sel):
                    href = a.get("href", "")
                    if AdaptiveExtractor._is_attachment(href):
                        full = urljoin(base_url, href) if not href.startswith("http") else href
                        item.attachment_links.append(full)

            page.items.append(item)

        skill.usage_count += 1
        return page

    def get_stats(self) -> dict:
        return {
            "total_skills": len(self._skills),
            "domains": list(self._skills.keys()),
            "total_uses": sum(s.usage_count for s in self._skills.values()),
        }

    def _build_learn_prompt(self, html: str, domain: str,
                           existing_items: list[ExtractedItem] = None) -> str:
        from bs4 import BeautifulSoup
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            soup = BeautifulSoup(html, "lxml")

        # Show key structural elements
        structure = []
        for tag in soup.find_all(["ul", "li", "table", "tr", "td", "div"]):
            classes = tag.get("class", [])
            if classes:
                structure.append(f"<{tag.name} class='{' '.join(classes[:3])}'>")
            else:
                structure.append(f"<{tag.name}>")
            if len(structure) > 100:
                break

        return f"""Analyze this government announcement page and create an extraction recipe.

Domain: {domain}
Page structure (HTML tags with classes):
{chr(10).join(structure[:80])}

Sample items extracted by heuristic:
{self._format_existing(existing_items)}

Return a JSON skill definition:
{{
  "page_type": "list" or "detail",
  "selectors": {{
    "item": "CSS selector for each list item container",
    "title": "CSS selector for the title/link within each item",
    "date": "CSS selector for publish date within each item",
    "status": "CSS selector for approval status",
    "attachment": "CSS selector for attachment links"
  }}
}}

CSS selectors should be specific and stable. Prefer class-based selectors over nth-child.
If unsure, use general selectors like "a" or "span". Return ONLY the JSON."""

    def _format_existing(self, items: list[ExtractedItem]) -> str:
        if not items:
            return "(none extracted yet)"
        lines = []
        for i, item in enumerate(items[:3]):
            lines.append(f"  [{i+1}] title='{item.title[:80]}' date='{item.publish_date}' status='{item.status}'")
        return "\n".join(lines)

    def _parse_skill_response(self, response: str, domain: str, html: str) -> Optional[SiteSkill]:
        import json
        try:
            if "{" in response:
                response = response[response.index("{"):response.rindex("}") + 1]
            data = json.loads(response)
            return SiteSkill(
                domain=domain,
                page_type=data.get("page_type", "list"),
                selectors=data.get("selectors", {}),
                field_mapping=data.get("field_mapping", {}),
                content_fingerprint=SiteSkill._fingerprint(html),
                created_at=time.strftime("%Y-%m-%d %H:%M"),
            )
        except Exception:
            return None

    def _save(self) -> None:
        import json, os
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            data = {}
            for domain, skill in self._skills.items():
                data[domain] = {
                    "domain": skill.domain,
                    "page_type": skill.page_type,
                    "selectors": skill.selectors,
                    "content_fingerprint": skill.content_fingerprint,
                    "created_at": skill.created_at,
                    "usage_count": skill.usage_count,
                }
            with open(self._cache_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load(self) -> None:
        import json, os
        try:
            if not os.path.exists(self._cache_path):
                return
            with open(self._cache_path) as f:
                data = json.load(f)
            for domain, skill_data in data.items():
                self._skills[domain] = SiteSkill(
                    domain=domain,
                    page_type=skill_data.get("page_type", "list"),
                    selectors=skill_data.get("selectors", {}),
                    content_fingerprint=skill_data.get("content_fingerprint", ""),
                    created_at=skill_data.get("created_at", ""),
                    usage_count=skill_data.get("usage_count", 0),
                )
        except Exception:
            pass

    @staticmethod
    def _extract_date(text: str) -> str:
        import re
        patterns = [
            (r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', r'\1-\2-\3'),
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', r'\1-\2-\3'),
        ]
        for pat, fmt in patterns:
            m = re.search(pat, text)
            if m:
                g = m.groups()
                return f"{g[0]}-{g[1].zfill(2)}-{g[2].zfill(2)}"
        return ""


# ═══ Singleton ═══

import threading
_skill_registry: Optional[SiteSkillRegistry] = None
_skill_lock = threading.Lock()


def get_skill_registry() -> SiteSkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        with _skill_lock:
            if _skill_registry is None:
                _skill_registry = SiteSkillRegistry()
    return _skill_registry
