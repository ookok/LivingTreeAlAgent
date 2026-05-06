"""Trend Radar — multi-platform hot-topic aggregation + smart filtering.

Inspired by TrendRadar (popnets/TrendRadar):
  - 35+ platforms: Weibo, Zhihu, Bilibili, Toutiao, Baidu, Douyin, etc.
  - Smart keyword filtering aligned with LivingTree knowledge domains
  - Auto-generate trend analysis reports (daily/weekly)
  - Push notifications via message gateway
  - Integrates with NetworkBrain → KnowledgeBase → EvolutionEngine

LivingTree knowledge domains:
  环评/环境    — 大气, 噪声, 水污染, 排放标准, 监测, GB/HJ标准
  AI/模型      — 大模型, LLM, GPT, 训练, 推理, 开源
  工程/开发    — 代码, 架构, Docker, K8s, API, 微服务
  数据/科学    — 数据分析, 机器学习, 论文, arXiv
  法规/标准    — 法律, 条例, 合规, 知识产权

Architecture:
  TrendSource → TrendItem → TrendClassifier → TrendFilter → TrendReporter
                    ↕
              KnowledgeBase (存储) + EvolutionEngine (触发学习)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import threading
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══ Data Models ═══

class TrendSource(str, Enum):
    """Platform sources for trend data."""
    WEIBO = "weibo"
    ZHIHU = "zhihu"
    BILIBILI = "bilibili"
    DOUYIN = "douyin"
    TOUTIAO = "toutiao"
    BAIDU = "baidu"
    GITHUB = "github"
    ARXIV = "arxiv"
    HACKERNEWS = "hackernews"
    STACKOVERFLOW = "stackoverflow"
    REDDIT = "reddit"
    RSS = "rss"
    CUSTOM = "custom"


class TrendDomain(str, Enum):
    """LivingTree knowledge domains."""
    ENVIRONMENT = "environment"     # 环评/环境
    AI_MODEL = "ai_model"          # AI/模型
    ENGINEERING = "engineering"    # 工程/开发
    DATA_SCIENCE = "data_science"  # 数据/科学
    REGULATION = "regulation"      # 法规/标准
    GENERAL = "general"            # 综合


@dataclass
class TrendItem:
    """A single trending topic from any platform."""
    id: str
    title: str
    source: str
    url: str = ""
    summary: str = ""
    heat_score: float = 0.0       # 平台热度分 (0-100)
    relevance_score: float = 0.0   # 与 LivingTree 知识域的相关性 (0-1)
    domain: TrendDomain = TrendDomain.GENERAL
    keywords: list[str] = field(default_factory=list)
    published_at: str = ""
    fetched_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)
    # Horizon-style AI scoring + enrichment
    ai_score: float = 0.0          # LLM 评分 0-10
    ai_reason: str = ""            # LLM 打分理由
    enriched_context: str = ""     # Web搜索补充的背景上下文
    comments_summary: str = ""     # 社区评论摘要
    duplicate_of: str = ""         # 指向去重后的主条目ID

    @property
    def composite_score(self) -> float:
        """Composite importance = heat × relevance + AI boost."""
        base = self.heat_score * self.relevance_score
        if self.ai_score > 0:
            base = base * 0.6 + self.ai_score * 4.0  # AI score weighted 40%
        return base

    @property
    def is_high_value(self) -> bool:
        return self.composite_score >= 30.0


@dataclass
class TrendReport:
    """Generated trend analysis report."""
    title: str = ""
    period: str = ""               # "daily", "weekly"
    generated_at: str = ""
    total_items: int = 0
    high_value_items: int = 0
    by_domain: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    top_trends: list[TrendItem] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    raw_text: str = ""


# ═══ Trend Classifier ═══

class TrendClassifier:
    """Domain-aware keyword matching + importance scoring.

    Maps free-text topics to LivingTree knowledge domains with
    multi-level keyword matching and relevance scoring.
    """

    DOMAIN_KEYWORDS = {
        TrendDomain.ENVIRONMENT: {
            "primary": ["环评", "环境影响", "大气", "大气污染", "噪声", "水污染", "排放标准",
                       "环境监测", "固废", "生态", "碳排放", "碳中和",
                       "GB3095", "GB12348", "HJ2.2", "HJ2.4", "EIA", "HJ"],
            "secondary": ["监测", "浓度", "扩散", "防护", "治理", "绿化", "排放",
                        "排污", "达标", "超标", "批复", "验收", "扩散模型", "高斯"],
            "weight": 1.0,
        },
        TrendDomain.AI_MODEL: {
            "primary": ["大模型", "LLM", "GPT", "DeepSeek", "ChatGPT", "Claude",
                       "训练", "微调", "推理", "transformer", "扩散模型",
                       "AI agent", "智能体", "强化学习", "RLHF"],
            "secondary": ["模型", "参数", "token", "embedding", "向量", "API",
                        "开源模型", "benchmark", "MLOps"],
            "weight": 0.9,
        },
        TrendDomain.ENGINEERING: {
            "primary": ["Docker", "Kubernetes", "微服务", "API", "架构",
                       "DevOps", "CI/CD", "gRPC", "Protobuf", "MQ",
                       "数据库", "缓存", "分布式", "高并发"],
            "secondary": ["部署", "运维", "监控", "日志", "网关", "负载均衡",
                        "容器", "编排", "Git", "GitHub"],
            "weight": 0.85,
        },
        TrendDomain.DATA_SCIENCE: {
            "primary": ["机器学习", "深度学习", "数据挖掘", "NLP", "CV",
                       "论文", "arXiv", "数据集", "benchmark", "SOTA",
                       "Python", "PyTorch", "TensorFlow"],
            "secondary": ["算法", "特征", "分类", "回归", "聚类", "预测",
                        "可视化", "统计", "实验", "对比"],
            "weight": 0.8,
        },
        TrendDomain.REGULATION: {
            "primary": ["标准", "规范", "法规", "条例", "政策", "合规",
                       "GB", "HJ", "ISO", "IEEE", "国标", "行标"],
            "secondary": ["发布", "修订", "实施", "废止", "替代", "更新",
                        "审批", "备案", "许可", "资质"],
            "weight": 0.75,
        },
    }

    def classify(self, title: str, summary: str = "") -> tuple[TrendDomain, float, list[str]]:
        """Classify a trend item into a domain + relevance score.

        Returns (domain, relevance_score, matched_keywords).
        """
        text = (title + " " + summary).lower()
        best_domain = TrendDomain.GENERAL
        best_score = 0.0
        best_keywords: list[str] = []

        for domain, keyword_config in self.DOMAIN_KEYWORDS.items():
            matched_primary = [kw for kw in keyword_config["primary"] if kw.lower() in text]
            matched_secondary = [kw for kw in keyword_config["secondary"] if kw.lower() in text]

            if not matched_primary and not matched_secondary:
                continue

            score = (
                len(matched_primary) * 0.5 +
                len(matched_secondary) * 0.1
            ) * keyword_config["weight"]

            score = min(1.0, score)

            if score > best_score:
                best_score = score
                best_domain = domain
                best_keywords = matched_primary + matched_secondary

        return best_domain, best_score, best_keywords

    def get_monitoring_keywords(self, domains: list[TrendDomain] = None) -> list[str]:
        """Get all keywords to monitor for given domains."""
        if domains is None:
            domains = list(TrendDomain)

        keywords = []
        seen = set()
        for domain in domains:
            config = self.DOMAIN_KEYWORDS.get(domain, {})
            for kw in config.get("primary", []) + config.get("secondary", []):
                kw_lower = kw.lower()
                if kw_lower not in seen:
                    seen.add(kw_lower)
                    keywords.append(kw)
        return keywords


# ═══ Trend Radar Engine ═══

class TrendRadar:
    """Multi-platform trend aggregation + smart filtering engine.

    Usage:
        radar = TrendRadar()
        await radar.initialize()

        # Fetch trends from all sources
        items = await radar.scan()

        # Filter high-value items for LivingTree
        top = radar.top_trends(min_composite=30, limit=10)

        # Generate daily report
        report = radar.generate_report(items, period="daily")
    """

    def __init__(self, cache_dir: str = ""):
        self._cache_dir = cache_dir or os.path.expanduser("~/.livingtree/trend_radar")
        self._classifier = TrendClassifier()
        self._items: list[TrendItem] = []
        self._lock = threading.RLock()
        self._scan_count: int = 0
        self._last_scan: float = 0.0

        self._source_connectors = {
            TrendSource.GITHUB: self._scan_github,
            TrendSource.HACKERNEWS: self._scan_hackernews,
            TrendSource.ARXIV: self._scan_arxiv,
            TrendSource.RSS: self._scan_rss,
            TrendSource.CUSTOM: self._scan_custom,
        }

    async def initialize(self) -> None:
        os.makedirs(self._cache_dir, exist_ok=True)
        self._load_cache()
        logger.info("TrendRadar: initialized (%d cached items)", len(self._items))

    async def scan(
        self,
        sources: list[TrendSource] = None,
        keywords: list[str] = None,
    ) -> list[TrendItem]:
        """Scan all configured platforms for trending topics.

        Args:
            sources: specific sources to scan (None = all available)
            keywords: filter keywords (None = use domain keywords)
        """
        if sources is None:
            sources = list(self._source_connectors.keys())

        if keywords is None:
            keywords = self._classifier.get_monitoring_keywords()

        new_items = []
        tasks = []

        for source in sources:
            connector = self._source_connectors.get(source)
            if connector:
                tasks.append(connector(keywords))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                new_items.extend(result)
            elif isinstance(result, Exception):
                logger.debug("TrendRadar source error: %s", result)

        classified = []
        for item in new_items:
            domain, relevance, matched_kw = self._classifier.classify(item.title, item.summary)
            item.domain = domain
            item.relevance_score = relevance
            item.keywords = matched_kw
            classified.append(item)

        classified.sort(key=lambda x: -x.composite_score)

        with self._lock:
            self._items = classified
            self._scan_count += 1
            self._last_scan = time.time()

        self._save_cache()

        high_value = sum(1 for i in classified if i.is_high_value)
        logger.info(
            "TrendRadar: scan #%d — %d items from %d sources, %d high-value",
            self._scan_count, len(classified), len(sources), high_value,
        )

        return classified

    def top_trends(
        self,
        domain: TrendDomain = None,
        min_composite: float = 30.0,
        limit: int = 10,
    ) -> list[TrendItem]:
        """Get top trends filtered by domain and score."""
        with self._lock:
            items = self._items
            if domain:
                items = [i for i in items if i.domain == domain]
            items = [i for i in items if i.composite_score >= min_composite]
            return items[:limit]

    def generate_report(
        self,
        items: list[TrendItem] = None,
        period: str = "daily",
    ) -> TrendReport:
        """Generate a trend analysis report.

        Formats: daily briefing, weekly analysis, domain deep-dive.
        """
        if items is None:
            with self._lock:
                items = list(self._items)

        report = TrendReport(
            title=f"LivingTree 趋势{'日报' if period == 'daily' else '周报'}",
            period=period,
            generated_at=time.strftime("%Y-%m-%d %H:%M"),
            total_items=len(items),
            high_value_items=sum(1 for i in items if i.is_high_value),
        )

        by_domain = Counter(i.domain.value for i in items)
        report.by_domain = dict(by_domain)
        by_source = Counter(i.source for i in items)
        report.by_source = dict(by_source)

        high_value = sorted(
            [i for i in items if i.is_high_value],
            key=lambda x: -x.composite_score,
        )

        report.top_trends = high_value[:15]
        report.recommendations = self._generate_recommendations(high_value)
        report.raw_text = self._format_report_text(report)

        return report

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_items": len(self._items),
                "scan_count": self._scan_count,
                "last_scan_seconds_ago": time.time() - self._last_scan if self._last_scan else -1,
                "by_domain": dict(Counter(i.domain.value for i in self._items)),
                "by_source": dict(Counter(i.source for i in self._items)),
                "high_value_count": sum(1 for i in self._items if i.is_high_value),
                "avg_relevance": (
                    sum(i.relevance_score for i in self._items) / max(len(self._items), 1)
                ),
            }

    # ═══ Horizon-style: AI Scoring + Enrichment + Dedup + Delivery ═══

    async def ai_score(self, items: list[TrendItem], hub: Any,
                       batch_size: int = 10) -> list[TrendItem]:
        """Horizon-style LLM scoring (0-10) for trend items.

        Uses LivingTree's dual-model consciousness (hub.chat) to score
        each trend on a 0-10 scale based on relevance to LivingTree
        knowledge domains. This replaces/supplements keyword matching.
        """
        if not hub:
            return items

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            if not batch:
                continue

            prompt = self._build_scoring_prompt(batch)
            try:
                response = hub.chat(prompt)
                scores = self._parse_scores(response, len(batch))
                for item, (score, reason) in zip(batch, scores):
                    item.ai_score = float(score)
                    item.ai_reason = reason
            except Exception as e:
                logger.debug("AI scoring failed: %s", e)

        with self._lock:
            self._items.sort(key=lambda x: -(x.composite_score))

        ai_scored = sum(1 for i in items if i.ai_score > 0)
        logger.info("TrendRadar: AI scored %d/%d items", ai_scored, len(items))
        return items

    async def enrich_trend(self, item: TrendItem, hub: Any) -> TrendItem:
        """Web-search background enrichment for a single trend.

        Uses MaterialCollector to fetch additional context from web,
        then LLM to summarize into a concise background paragraph.
        """
        if not hub or not item.title:
            return item

        try:
            from .material_collector import MaterialCollector
            collector = MaterialCollector(rate_limit_per_sec=1)
            materials = await collector.collect_from_web(item.title)
            if materials:
                context_text = "\n".join(m.get("text", "")[:500] for m in materials[:3])
                if context_text:
                    prompt = (
                        f"Summarize key background context for this news item in 2-3 sentences:\n"
                        f"Title: {item.title}\nSummary: {item.summary[:200]}\n"
                        f"Search results:\n{context_text[:1500]}\n\n"
                        f"Focus on: what is this about, why it matters, key players/technologies."
                    )
                    item.enriched_context = hub.chat(prompt)
        except Exception as e:
            logger.debug("Trend enrichment failed for '%s': %s", item.title[:40], e)

        return item

    async def enrich_all(self, items: list[TrendItem], hub: Any,
                         max_enrich: int = 10) -> list[TrendItem]:
        """Enrich top-N trends with web-search context."""
        top_items = sorted(items, key=lambda x: -(x.composite_score))[:max_enrich]
        tasks = [self.enrich_trend(item, hub) for item in top_items]
        await asyncio.gather(*tasks, return_exceptions=True)
        enriched = sum(1 for i in items if i.enriched_context)
        logger.info("TrendRadar: enriched %d/%d trends", enriched, len(top_items))
        return items

    def dedup_trends(self, items: list[TrendItem]) -> list[TrendItem]:
        """Cross-source deduplication — merge same story from different platforms.

        Uses title-level Jaccard similarity to identify duplicates
        across sources (e.g., same news on HN + Reddit + GitHub).
        Keeps the highest-scored version; marks others as duplicates.
        """
        if len(items) <= 1:
            return items

        SIMILARITY_THRESHOLD = 0.25  # char n-gram Jaccard
        deduped = []
        seen = set()

        for item in sorted(items, key=lambda x: (-x.composite_score, -x.heat_score)):
            is_dup = False
            for existing in deduped:
                sim = self._title_similarity(item.title, existing.title)
                if sim >= SIMILARITY_THRESHOLD:
                    item.duplicate_of = existing.id
                    existing.metadata.setdefault("duplicate_sources", []).append(item.source)
                    is_dup = True
                    break
            if not is_dup:
                deduped.append(item)

        dups = len(items) - len(deduped)
        if dups > 0:
            logger.debug("TrendRadar: deduped %d duplicate items (kept %d)", dups, len(deduped))

        return deduped

    async def deliver_report(self, report: TrendReport, channels: list[str] = None,
                            hub: Any = None) -> dict:
        """Multi-channel delivery of trend report.

        Channels: "console", "log", "knowledge_base", "feishu", "webhook"
        """
        results = {}
        channels = channels or ["console", "log"]

        if "console" in channels:
            print(report.raw_text[:2000])
            results["console"] = "ok"

        if "log" in channels:
            logger.info("TrendRadar Report: %s — %d trends", report.title, report.total_items)
            results["log"] = "ok"

        if "knowledge_base" in channels:
            try:
                from ..knowledge.document_kb import DocumentKB
                kb = DocumentKB()
                kb.ingest(report.raw_text, title=report.title, source="trend_radar")
                results["knowledge_base"] = "ok"
            except Exception as e:
                results["knowledge_base"] = str(e)

        if "feishu" in channels and hub:
            try:
                await self._deliver_feishu(report, hub)
                results["feishu"] = "ok"
            except Exception as e:
                results["feishu"] = str(e)

        if "webhook" in channels and hub:
            try:
                await self._deliver_webhook(report, hub)
                results["webhook"] = "ok"
            except Exception as e:
                results["webhook"] = str(e)

        return results

    async def full_pipeline(self, hub: Any = None, channels: list[str] = None) -> TrendReport:
        """Horizon full pipeline: scan → score → enrich → dedup → report → deliver."""
        items = await self.scan()

        if hub:
            items = await self.ai_score(items, hub)
            items = await self.enrich_all(items, hub)

        items = self.dedup_trends(items)

        with self._lock:
            self._items = items

        report = self.generate_report(items)
        await self.deliver_report(report, channels, hub)
        return report

    # ═══ Private Helpers ═══

    def _build_scoring_prompt(self, items: list[TrendItem]) -> str:
        lines = [
            "Score each news item 0-10 based on relevance to these domains:",
            "  环境/环评: air quality, noise, water, emission standards, environmental impact assessment",
            "  AI/大模型: LLM, GPT, DeepSeek, machine learning, training, inference",
            "  工程/开发: Docker, K8s, architecture, API, DevOps, open source tools",
            "  数据/科学: papers, datasets, benchmarks, statistics, research",
            "  法规/标准: regulations, compliance, ISO, GB standards, policy",
            "",
            "Return JSON array: [{\"score\": int, \"reason\": \"1 sentence\"}, ...]",
            "",
        ]
        for i, item in enumerate(items):
            lines.append(f"{i+1}. [{item.source}] {item.title}")
            if item.summary:
                lines.append(f"   {item.summary[:150]}")
        return "\n".join(lines)

    @staticmethod
    def _parse_scores(response: str, count: int) -> list[tuple[int, str]]:
        """Parse LLM response into score list."""
        defaults = [(5, "") for _ in range(count)]
        try:
            if "[" in response:
                response = response[response.index("["):response.rindex("]") + 1]
            import json
            data = json.loads(response)
            if isinstance(data, list):
                return [
                    (max(0, min(10, int(d.get("score", 5)))), d.get("reason", ""))
                    for d in data[:count]
                ]
        except Exception:
            pass

        # Fallback: extract numbers
        import re
        nums = re.findall(r'\b([0-9]|10)\b', response)
        return [(int(n), "") for n in nums[:count]] or defaults

    @staticmethod
    def _title_similarity(a: str, b: str) -> float:
        """Character n-gram Jaccard for cross-language dedup."""
        if not a or not b:
            return 0.0
        n = 3
        def ngrams(s):
            return {s[i:i+n] for i in range(len(s) - n + 1)}
        a_set = ngrams(a.lower())
        b_set = ngrams(b.lower())
        if not a_set or not b_set:
            return 0.0
        return len(a_set & b_set) / len(a_set | b_set)

    async def _deliver_feishu(self, report: TrendReport, hub: Any) -> None:
        """Deliver report to Feishu/Lark via message gateway."""
        try:
            from ..integration.message_gateway import MessageGateway
            gw = MessageGateway()
            summary = f"## {report.title}\n\n热点: {report.high_value_items}/{report.total_items}"
            await gw.send_text(summary)
        except Exception:
            pass

    async def _deliver_webhook(self, report: TrendReport, hub: Any) -> None:
        """Deliver report to webhook URL."""
        webhook_url = os.environ.get("LIVINGTREE_WEBHOOK_URL", "")
        if not webhook_url:
            return
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                await s.post(webhook_url, json={
                    "title": report.title,
                    "summary": report.raw_text[:4000],
                    "high_value": report.high_value_items,
                })
        except Exception:
            pass

    # ═══ Source Connectors ═══

    async def _scan_github(self, keywords: list[str]) -> list[TrendItem]:
        """Scan GitHub Trending for relevant repos."""
        items = []
        try:
            from ..network.site_accelerator import get_accelerator
            accel = get_accelerator()
            await accel.initialize()

            content = await accel.accelerated_fetch(
                "https://api.github.com/search/repositories?q=trending&sort=stars&order=desc&per_page=10"
            )
            if content:
                data = json.loads(content)
                for repo in data.get("items", [])[:10]:
                    title = repo.get("full_name", "")
                    desc = repo.get("description", "") or ""
                    stars = repo.get("stargazers_count", 0)

                    matched = any(kw.lower() in (title + " " + desc).lower() for kw in keywords)
                    if matched or True:
                        items.append(TrendItem(
                            id=hashlib.md5(title.encode()).hexdigest()[:12],
                            title=title,
                            source="github",
                            url=repo.get("html_url", ""),
                            summary=desc[:300],
                            heat_score=min(100, stars / 100),
                            metadata={"stars": stars, "language": repo.get("language", "")},
                        ))
        except Exception as e:
            logger.debug("TrendRadar GitHub: %s", e)

        return items

    async def _scan_hackernews(self, keywords: list[str]) -> list[TrendItem]:
        """Scan HackerNews top stories."""
        items = []
        try:
            from ..network.site_accelerator import get_accelerator
            accel = get_accelerator()
            await accel.initialize()

            content = await accel.accelerated_fetch(
                "https://hacker-news.firebaseio.com/v0/topstories.json"
            )
            if content:
                ids = json.loads(content)[:20]
                tasks = []
                for story_id in ids:
                    tasks.append(accel.accelerated_fetch(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    ))
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, result in enumerate(results):
                    if isinstance(result, str):
                        try:
                            story = json.loads(result)
                            title = story.get("title", "")
                            text = story.get("text", "") or ""
                            score = story.get("score", 0)

                            items.append(TrendItem(
                                id=hashlib.md5(title.encode()).hexdigest()[:12],
                                title=title,
                                source="hackernews",
                                url=story.get("url", ""),
                                summary=text[:300],
                                heat_score=min(100, score / 5),
                                metadata={"score": score, "comments": story.get("descendants", 0)},
                            ))
                        except Exception:
                            pass
        except Exception as e:
            logger.debug("TrendRadar HN: %s", e)

        return items

    async def _scan_arxiv(self, keywords: list[str]) -> list[TrendItem]:
        """Scan arXiv for recent papers in monitored domains."""
        items = []
        try:
            from ..network.site_accelerator import get_accelerator
            accel = get_accelerator()
            await accel.initialize()

            queries = ["LLM agent", "environmental AI", "machine learning"]
            for q in queries[:2]:
                content = await accel.accelerated_fetch(
                    f"http://export.arxiv.org/api/query?search_query=all:{q}"
                    f"&start=0&max_results=5&sortBy=submittedDate&sortOrder=descending"
                )
                if content:
                    entries = re.findall(r'<entry>(.*?)</entry>', content, re.DOTALL)
                    for entry in entries[:5]:
                        title_m = re.search(r'<title>(.*?)</title>', entry)
                        summary_m = re.search(r'<summary>(.*?)</summary>', entry)
                        if title_m:
                            title = title_m.group(1).strip()
                            items.append(TrendItem(
                                id=hashlib.md5(title.encode()).hexdigest()[:12],
                                title=title,
                                source="arxiv",
                                summary=summary_m.group(1).strip()[:300] if summary_m else "",
                                heat_score=30.0,
                                metadata={"query": q},
                            ))
        except Exception as e:
            logger.debug("TrendRadar arXiv: %s", e)

        return items

    async def _scan_rss(self, keywords: list[str]) -> list[TrendItem]:
        """Scan configured RSS feeds."""
        return []  # Placeholder — RSS sources configured via config

    async def _scan_custom(self, keywords: list[str]) -> list[TrendItem]:
        """Scan custom sources (configured per deployment)."""
        return []

    # ═══ Report Generation ═══

    def _generate_recommendations(self, high_value: list[TrendItem]) -> list[str]:
        recommendations = []

        by_domain = Counter(i.domain for i in high_value)
        top_domain = by_domain.most_common(1)
        if top_domain:
            recommendations.append(
                f"重点关注领域: {top_domain[0][0].value} ({top_domain[0][1]}条高价值趋势)"
            )

        env_items = [i for i in high_value if i.domain == TrendDomain.ENVIRONMENT]
        if env_items:
            recommendations.append(
                f"建议更新环境知识库: {len(env_items)}条相关趋势，涉及标准/政策/技术"
            )

        ai_items = [i for i in high_value if i.domain == TrendDomain.AI_MODEL]
        if ai_items:
            recommendations.append(
                f"AI模型演进: {len(ai_items)}条趋势，建议评估模型切换/升级方案"
            )

        return recommendations

    def _format_report_text(self, report: TrendReport) -> str:
        lines = [
            f"# {report.title}",
            f"生成时间: {report.generated_at}",
            f"趋势总数: {report.total_items} (高价值: {report.high_value_items})",
            "",
            "## 领域分布",
        ]

        for domain, count in sorted(report.by_domain.items(), key=lambda x: -x[1]):
            lines.append(f"- {domain}: {count}")

        lines.append("")
        lines.append("## 高价值趋势")

        for i, item in enumerate(report.top_trends[:10], 1):
            lines.append(f"{i}. [{item.source}] **{item.title}**")
            if item.summary:
                lines.append(f"   {item.summary[:150]}")
            lines.append(f"   热度: {item.heat_score:.0f} | 相关度: {item.relevance_score:.2f} | 域: {item.domain.value}")
            if item.url:
                lines.append(f"   🔗 {item.url}")
            lines.append("")

        if report.recommendations:
            lines.append("## 建议行动")
            for rec in report.recommendations:
                lines.append(f"- {rec}")

        return "\n".join(lines)

    # ═══ Cache ═══

    def _save_cache(self) -> None:
        try:
            data = [
                {
                    "id": i.id, "title": i.title, "source": i.source,
                    "url": i.url, "summary": i.summary,
                    "heat_score": i.heat_score, "relevance_score": i.relevance_score,
                    "domain": i.domain.value, "keywords": i.keywords,
                    "fetched_at": i.fetched_at,
                }
                for i in self._items[:500]
            ]
            cache_file = os.path.join(self._cache_dir, "trends.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug("TrendRadar cache save: %s", e)

    def _load_cache(self) -> None:
        try:
            cache_file = os.path.join(self._cache_dir, "trends.json")
            if not os.path.exists(cache_file):
                return
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
            for item_data in data:
                self._items.append(TrendItem(
                    id=item_data["id"],
                    title=item_data["title"],
                    source=item_data["source"],
                    url=item_data.get("url", ""),
                    summary=item_data.get("summary", ""),
                    heat_score=item_data.get("heat_score", 0),
                    relevance_score=item_data.get("relevance_score", 0),
                    domain=TrendDomain(item_data.get("domain", "general")),
                    keywords=item_data.get("keywords", []),
                    fetched_at=item_data.get("fetched_at", time.time()),
                ))
        except Exception as e:
            logger.debug("TrendRadar cache load: %s", e)


# ═══ Singleton ═══

_radar: Optional[TrendRadar] = None
_radar_lock = threading.Lock()


def get_trend_radar() -> TrendRadar:
    global _radar
    if _radar is None:
        with _radar_lock:
            if _radar is None:
                _radar = TrendRadar()
    return _radar
