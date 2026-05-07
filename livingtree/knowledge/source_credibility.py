"""SourceCredibility — LDR-inspired data source quality scoring for EIA domain.

LDR's journal quality system (212K+ sources, predatory detection) adapted
for Environmental Impact Assessment data sources. Scores sources on:
  1. Source type (national standard > government > academic > corporate > unknown)
  2. Recency (newer data preferred, but older standards still valid)
  3. Citation density (does the source reference known standards?)
  4. Domain authority (URL-based heuristics)

Usage:
    from livingtree.knowledge.source_credibility import SourceCredibility
    scorer = SourceCredibility()
    score = scorer.score("https://www.mee.gov.cn/standard/GB3095-2012")
    score = scorer.score_url("https://example.com/blog/air-quality")
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CredibilityScore:
    url: str
    source_type: str
    overall: float
    authority: float
    recency: float
    citations: float
    flags: list[str] = field(default_factory=list)
    recommendation: str = ""

    @property
    def is_reliable(self) -> bool:
        return self.overall >= 0.6

    @property
    def is_caution(self) -> bool:
        return 0.3 <= self.overall < 0.6

    @property
    def is_unreliable(self) -> bool:
        return self.overall < 0.3


class SourceCredibility:
    """EIA data source quality scorer.

    Scored on 0.0-1.0 scale with weighted sub-scores.
    Designed for Chinese environmental regulatory domain.
    """

    HIGH_AUTHORITY_DOMAINS = {
        "mee.gov.cn": 0.95, "gov.cn": 0.85, "std.gov.cn": 0.9,
        "cnki.net": 0.8, "wanfangdata.com.cn": 0.8,
        "epa.gov": 0.9, "who.int": 0.9, "un.org": 0.85,
        "edu.cn": 0.75, "ac.cn": 0.8,
    }

    LOW_AUTHORITY_DOMAINS = {
        "zhihu.com": 0.35, "baidu.com": 0.3, "weibo.com": 0.2,
        "douyin.com": 0.15, "xiaohongshu.com": 0.15,
        "blogspot.com": 0.25, "wordpress.com": 0.2,
        "medium.com": 0.3,
    }

    KNOWN_STANDARDS = [
        "GB", "GB/T", "GBZ", "HJ", "HJ/T", "CJ", "CJJ", "SL",
        "ISO", "WHO", "EPA", "USEPA", "EU",
    ]

    PREDATORY_INDICATORS = [
        "guaranteed-acceptance", "fast-publication", "no-peer-review",
        "payment-required", "predatory-journal",
    ]

    def score(self, url: str, title: str = "", snippet: str = "",
              year: int = 0) -> CredibilityScore:
        authority = self._score_authority(url)
        recency = self._score_recency(url, snippet, year)
        citations = self._score_citations(title, snippet)
        flags = self._detect_flags(url, title, snippet)

        source_type = self._classify_source(url, title)
        overall = authority * 0.50 + recency * 0.25 + citations * 0.25

        for flag in flags:
            if "predatory" in flag:
                overall = min(overall, 0.2)
            elif "personal_blog" in flag:
                overall = min(overall, 0.35)
            elif "outdated" in flag:
                overall *= 0.7
            elif "no_standard_ref" in flag:
                overall *= 0.85

        overall = round(min(overall, 1.0), 3)

        if overall >= 0.8:
            rec = "可信 — 可直接引用"
        elif overall >= 0.6:
            rec = "基本可信 — 建议交叉验证"
        elif overall >= 0.3:
            rec = "谨慎使用 — 需要额外验证"
        else:
            rec = "不可靠 — 不推荐引用"

        return CredibilityScore(
            url=url, source_type=source_type, overall=overall,
            authority=round(authority, 3), recency=round(recency, 3),
            citations=round(citations, 3), flags=flags,
            recommendation=rec,
        )

    def score_url(self, url: str) -> CredibilityScore:
        return self.score(url)

    def batch_score(self, urls: list[str]) -> list[CredibilityScore]:
        return [self.score(u) for u in urls]

    def _score_authority(self, url: str) -> float:
        url_lower = url.lower()

        for domain, score in self.HIGH_AUTHORITY_DOMAINS.items():
            if domain in url_lower:
                if "/standard/" in url_lower or "/bz/" in url_lower:
                    return min(score + 0.05, 1.0)
                return score

        for domain, score in self.LOW_AUTHORITY_DOMAINS.items():
            if domain in url_lower:
                return score

        if url_lower.endswith(".gov.cn"):
            return 0.85
        if ".gov." in url_lower:
            return 0.8
        if url_lower.endswith(".edu.cn") or ".edu." in url_lower:
            return 0.7
        if url_lower.endswith(".org.cn") or ".org." in url_lower:
            return 0.55
        if url_lower.endswith(".com.cn") or ".com" in url_lower:
            return 0.4
        if url_lower.endswith(".cn"):
            return 0.35

        return 0.25

    def _score_recency(self, url: str, snippet: str, year: int) -> float:
        if year == 0:
            year_match = re.search(r'(?:19|20)(\d{2})', url, re.ASCII)
            if year_match:
                year = int(f"20{year_match.group(1)}")

            year_match = re.search(r'(?:19|20)(\d{2})', snippet, re.ASCII)
            if year_match:
                year = int(f"20{year_match.group(1)}")

        if year == 0:
            return 0.5

        current_year = time.localtime().tm_year
        age = current_year - year

        if age <= 1:
            return 1.0
        if age <= 3:
            return 0.9
        if age <= 5:
            return 0.8
        if age <= 10:
            return 0.6
        if age <= 20:
            return 0.4
        return 0.2

    def _score_citations(self, title: str, snippet: str) -> float:
        combined = (title + " " + snippet).upper()
        hits = 0
        for std in self.KNOWN_STANDARDS:
            if std.upper() in combined:
                hits += 1

        if hits >= 3:
            return 0.95
        if hits >= 2:
            return 0.8
        if hits >= 1:
            return 0.6
        return 0.3

    def _classify_source(self, url: str, title: str) -> str:
        url_lower = url.lower()
        if "mee.gov.cn" in url_lower or "gov.cn" in url_lower:
            return "政府机构"
        if "cnki.net" in url_lower or "wanfang" in url_lower:
            return "学术数据库"
        if ".edu" in url_lower or ".ac." in url_lower:
            return "学术机构"
        if "标准" in title or "GB" in title or "HJ" in title:
            return "技术标准"
        if "journal" in url_lower or "学报" in title:
            return "学术期刊"
        return "一般来源"

    @staticmethod
    def _detect_flags(url: str, title: str, snippet: str) -> list[str]:
        flags = []
        combined = (url + title + snippet).lower()

        if any(ind in combined for ind in SourceCredibility.PREDATORY_INDICATORS):
            flags.append("predatory")

        blog_domains = ["blog", "weibo", "zhihu", "douyin", "xiaohongshu",
                        "medium.com", "substack.com"]
        if any(d in combined for d in blog_domains):
            flags.append("personal_blog")

        if re.search(r'(?:19[5-9]\d)', combined, re.ASCII):
            flags.append("outdated")

        has_std_ref = any(std.lower() in combined
                           for std in SourceCredibility.KNOWN_STANDARDS)
        if not has_std_ref and ("标准" in title or "环评" in title):
            flags.append("no_standard_ref")

        return flags


_source_credibility: SourceCredibility | None = None


def get_source_credibility() -> SourceCredibility:
    global _source_credibility
    if _source_credibility is None:
        _source_credibility = SourceCredibility()
    return _source_credibility
