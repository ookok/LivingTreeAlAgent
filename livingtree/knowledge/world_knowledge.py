"""World Knowledge — Compact structured environment representation.

arXiv:2604.18131 (Zhang et al., 2026): "Training LLM Agents for Spontaneous,
Reward-Free Self-Evolution via World Knowledge Exploration."

World Knowledge (K) is a compact Markdown document per explored environment,
serving as the agent's mental map. Three components:
  - URL Prefixes: clustered path patterns for navigation structure
  - Navigation Map: page-to-page link graph (via KnowledgeGraph)
  - Page Summaries: compressed <100-char descriptions per page

Phase 1 (Native Evolution): spontaneously explore unseen websites during idle,
compress observations to World Knowledge.
Phase 2 (Knowledge-Enhanced Execution): inject World Knowledge as context
BEFORE tasks for navigation and information retrieval efficiency.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
from typing import Any


@dataclass
class PageSummary:
    url: str
    title: str = ""
    path_prefix: str = ""
    summary: str = ""            # <100 char compressed description
    page_type: str = "detail"    # list | detail | table | form | api
    actionable: bool = False     # forms, downloads, API endpoints
    internal_links: list[str] = field(default_factory=list)
    fetch_ms: float = 0.0

    def to_markdown_line(self) -> str:
        tags = [self.page_type]
        if self.actionable:
            tags.append("actionable")
        return f"- [{self.title}]({self.url}) `{'|'.join(tags)}` {self.summary}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url, "title": self.title, "path_prefix": self.path_prefix,
            "summary": self.summary, "page_type": self.page_type,
            "actionable": self.actionable, "internal_links": self.internal_links,
            "fetch_ms": self.fetch_ms,
        }


@dataclass
class WorldKnowledge:
    domain: str
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    url_prefixes: dict[str, list[str]] = field(default_factory=dict)
    navigation_map: dict[str, list[str]] = field(default_factory=dict)
    page_summaries: list[PageSummary] = field(default_factory=list)
    actionable_items: list[str] = field(default_factory=list)
    total_pages: int = 0
    crawl_time_ms: float = 0.0

    @property
    def identifier(self) -> str:
        h = hashlib.md5(self.domain.encode()).hexdigest()[:8]
        return f"wk:{self.domain}:{h}"

    @property
    def page_count(self) -> int:
        return len(self.page_summaries)

    @property
    def freshness_hours(self) -> float:
        return (time.time() - self.updated_at) / 3600.0

    def to_markdown(self) -> str:
        lines = [
            f"# World Knowledge: {self.domain}",
            f"> v{self.version} | {self.page_count} pages | {self.crawl_time_ms:.0f}ms crawl",
            f"> Updated: {time.strftime('%Y-%m-%d %H:%M', time.localtime(self.updated_at))}",
            "",
            "## URL Prefix Map",
            "",
        ]
        if self.url_prefixes:
            for prefix, urls in sorted(self.url_prefixes.items()):
                lines.append(f"### `{prefix}/*` ({len(urls)} pages)")
                for u in urls[:8]:
                    lines.append(f"- {u}")
                if len(urls) > 8:
                    lines.append(f"- ... and {len(urls) - 8} more")
                lines.append("")
        else:
            lines.append("(no URL clusters)\n")

        lines.append("## Page Summaries\n")
        for ps in self.page_summaries:
            lines.append(ps.to_markdown_line())
        lines.append("")

        if self.actionable_items:
            lines.append("## Actionable Items\n")
            for item in self.actionable_items:
                lines.append(f"- {item}")
            lines.append("")

        if self.navigation_map:
            lines.append("## Navigation Map\n")
            for page, linked in sorted(self.navigation_map.items()):
                short = page.split("/")[-1] or page
                lines.append(f"- **{short}** → {len(linked)} pages")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain, "version": self.version,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "url_prefixes": self.url_prefixes,
            "navigation_map": self.navigation_map,
            "page_summaries": [ps.to_dict() for ps in self.page_summaries],
            "actionable_items": self.actionable_items,
            "total_pages": self.total_pages, "crawl_time_ms": self.crawl_time_ms,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "WorldKnowledge":
        return WorldKnowledge(
            domain=data["domain"], version=data.get("version", 1),
            created_at=data.get("created_at", 0), updated_at=data.get("updated_at", 0),
            url_prefixes=data.get("url_prefixes", {}),
            navigation_map=data.get("navigation_map", {}),
            page_summaries=[PageSummary(**ps) for ps in data.get("page_summaries", [])],
            actionable_items=data.get("actionable_items", []),
            total_pages=data.get("total_pages", 0),
            crawl_time_ms=data.get("crawl_time_ms", 0),
        )

    @staticmethod
    def from_exploration(domain: str, pages: list[PageSummary],
                         crawl_time_ms: float = 0.0) -> "WorldKnowledge":
        prefixes: dict[str, list[str]] = {}
        for ps in pages:
            ps.path_prefix = _extract_path_prefix(ps.url)
            prefixes.setdefault(ps.path_prefix, []).append(ps.url)

        nav_map: dict[str, list[str]] = {}
        for ps in pages:
            nav_map[ps.url] = ps.internal_links

        actionable = [ps.url for ps in pages if ps.actionable]

        return WorldKnowledge(
            domain=domain, version=1, url_prefixes=prefixes,
            navigation_map=nav_map, page_summaries=pages,
            actionable_items=actionable, total_pages=len(pages),
            crawl_time_ms=crawl_time_ms,
        )


def _extract_path_prefix(url: str, max_parts: int = 2) -> str:
    path = url.split("/", 3)
    if len(path) < 4:
        return path[-1] if len(path) > 2 else "/"
    segments = path[3].split("/")
    prefix = "/".join(segments[:max_parts])
    return f"/{prefix}" if prefix else "/"


def _cluster_urls(urls: list[str], min_cluster_size: int = 2) -> dict[str, list[str]]:
    clusters: dict[str, list[str]] = defaultdict(list)
    for u in urls:
        prefix = _extract_path_prefix(u)
        clusters[prefix].append(u)
    return {k: v for k, v in clusters.items() if len(v) >= min_cluster_size}


__all__ = ["WorldKnowledge", "PageSummary", "_extract_path_prefix", "_cluster_urls"]
