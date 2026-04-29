# -*- coding: utf-8 -*-
"""
Competitor Monitor 竞品监控流
Intelligence Center - Competitor Monitoring Pipeline
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    DANGER = "danger"
    UNKNOWN = "unknown"


@dataclass
class CompetitorProfile:
    competitor_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    aliases: List[str] = field(default_factory=list)
    website: str = ""
    social_media: Dict[str, str] = field(default_factory=dict)
    keywords: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    price_range: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class CompetitorHealth:
    competitor_id: str = ""
    competitor_name: str = ""
    update_frequency: float = 0.0
    social_engagement: float = 0.0
    sentiment_score: float = 0.0
    review_rating: float = 0.0
    negative_ratio: float = 0.0
    rumor_count: int = 0
    complaint_count: int = 0
    health_score: float = 0.0
    status: HealthStatus = HealthStatus.UNKNOWN
    trend: str = "stable"
    trend_change: float = 0.0
    analyzed_at: datetime = field(default_factory=datetime.now)


@dataclass
class CompetitorIntel:
    intel_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    competitor_id: str = ""
    competitor_name: str = ""
    intel_type: str = ""
    title: str = ""
    content: str = ""
    url: str = ""
    source: str = ""
    sentiment: str = "neutral"
    importance: float = 0.0
    collected_at: datetime = field(default_factory=datetime.now)


class HealthEvaluator:
    @classmethod
    def evaluate(cls, health: CompetitorHealth) -> CompetitorHealth:
        update_score = min(1.0, health.update_frequency / 5) * 25
        social_score = health.social_engagement * 25
        sentiment_score = ((health.sentiment_score + 1) / 2) * 25
        review_score = (health.review_rating / 5) * 25

        base_score = update_score + social_score + sentiment_score + review_score
        penalty = health.negative_ratio * 20 + health.rumor_count * 5 + health.complaint_count * 3

        health.health_score = max(0, min(100, base_score - penalty))

        if health.health_score >= 80:
            health.status = HealthStatus.EXCELLENT
        elif health.health_score >= 60:
            health.status = HealthStatus.GOOD
        elif health.health_score >= 40:
            health.status = HealthStatus.WARNING
        elif health.health_score >= 20:
            health.status = HealthStatus.DANGER
        else:
            health.status = HealthStatus.UNKNOWN

        return health


class CompetitorMonitor:
    def __init__(self, search_pipeline=None, rumor_detector=None):
        self.search_pipeline = search_pipeline
        self.rumor_detector = rumor_detector
        self.profiles: Dict[str, CompetitorProfile] = {}
        self.intel_cache: Dict[str, List[CompetitorIntel]] = {}

    def add_competitor(self, profile: CompetitorProfile) -> str:
        self.profiles[profile.competitor_id] = profile
        self.intel_cache[profile.competitor_id] = []
        return profile.competitor_id

    def remove_competitor(self, competitor_id: str) -> bool:
        if competitor_id in self.profiles:
            del self.profiles[competitor_id]
            if competitor_id in self.intel_cache:
                del self.intel_cache[competitor_id]
            return True
        return False

    def list_competitors(self) -> List[CompetitorProfile]:
        return list(self.profiles.values())

    async def collect_intel(self, competitor_id: str) -> List[CompetitorIntel]:
        profile = self.profiles.get(competitor_id)
        if not profile:
            return []

        intel_list = []
        tasks = [
            self._collect_product_intel(profile),
            self._collect_sentiment_intel(profile),
        ]

        for result in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(result, list):
                intel_list.extend(result)

        self.intel_cache[competitor_id] = intel_list
        return intel_list

    async def _collect_product_intel(self, profile: CompetitorProfile) -> List[CompetitorIntel]:
        if not self.search_pipeline:
            return []
        intel_list = []
        try:
            response = await self.search_pipeline.search_product_releases(profile.name)
            for result in response.results[:5]:
                intel_list.append(CompetitorIntel(
                    competitor_id=profile.competitor_id,
                    competitor_name=profile.name,
                    intel_type="product",
                    title=result.title,
                    content=result.snippet,
                    url=result.url,
                    source=result.source,
                    importance=result.relevance_score,
                ))
        except Exception as e:
            logger.warning(f"收集产品动态失败: {e}")
        return intel_list

    async def _collect_sentiment_intel(self, profile: CompetitorProfile) -> List[CompetitorIntel]:
        if not self.search_pipeline:
            return []
        intel_list = []
        try:
            response = await self.search_pipeline.search_sentiment(profile.name)
            for result in response.results[:5]:
                intel_list.append(CompetitorIntel(
                    competitor_id=profile.competitor_id,
                    competitor_name=profile.name,
                    intel_type="complaint" if result.relevance_score < 0.5 else "news",
                    title=result.title,
                    content=result.snippet,
                    url=result.url,
                    source=result.source,
                    sentiment="negative" if result.relevance_score < 0.5 else "neutral",
                    importance=result.relevance_score,
                ))
        except Exception as e:
            logger.warning(f"收集舆情失败: {e}")
        return intel_list

    async def evaluate_health(self, competitor_id: str) -> Optional[CompetitorHealth]:
        profile = self.profiles.get(competitor_id)
        if not profile:
            return None

        intel_list = self.intel_cache.get(competitor_id, [])
        health = CompetitorHealth(competitor_id=competitor_id, competitor_name=profile.name)

        if intel_list:
            sentiments = [i.sentiment for i in intel_list]
            neg_count = sentiments.count("negative")
            health.negative_ratio = neg_count / len(sentiments) if sentiments else 0
            health.sentiment_score = sum(i.importance for i in intel_list) / len(intel_list) - 0.5
            health.rumor_count = sum(1 for i in intel_list if i.intel_type == "rumor")
            health.complaint_count = sum(1 for i in intel_list if i.intel_type == "complaint")

        return HealthEvaluator.evaluate(health)

    async def run_monitoring_cycle(self) -> Dict[str, List[CompetitorIntel]]:
        results = {}
        tasks = [self.collect_intel(cid) for cid in self.profiles if self.profiles[cid].is_active]

        for cid, result in zip([cid for cid in self.profiles if self.profiles[cid].is_active],
                               await asyncio.gather(*tasks, return_exceptions=True)):
            results[cid] = result if isinstance(result, list) else []

        return results


class MonitoringScheduler:
    def __init__(self, monitor: CompetitorMonitor):
        self.monitor = monitor
        self._running = False

    async def start(self, interval_seconds: int = 3600):
        self._running = True
        while self._running:
            try:
                await self.monitor.run_monitoring_cycle()
                logger.info("竞品监控周期完成")
            except Exception as e:
                logger.error(f"监控周期失败: {e}")
            await asyncio.sleep(interval_seconds)

    def stop(self):
        self._running = False


__all__ = ["HealthStatus", "CompetitorProfile", "CompetitorHealth", "CompetitorIntel",
           "CompetitorMonitor", "HealthEvaluator", "MonitoringScheduler"]