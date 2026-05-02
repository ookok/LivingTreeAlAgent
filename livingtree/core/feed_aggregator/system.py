# system.py — 聚合推荐系统统一调度器

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any

from .models import FeedItem, FeedSource, FeedConfig, InterestProfile
from .media_fetcher import MediaFetcher, get_media_fetcher
from .interest_engine import InterestEngine, get_interest_engine
from .safety_filter import FeedSafetyFilter, get_feed_safety_filter


class FeedAggregatorSystem:
    """
    聚合推荐系统 — 统一调度器

    整合四大组件：
    1. MediaFetcher — 媒体增强抓取
    2. InterestEngine — 兴趣驯化
    3. SafetyFilter — 安全守门
    4. FeedCard — UI 卡片组件

    功能：
    - 多来源聚合
    - 个性化排序
    - 双向反馈
    - 安全过滤
    """

    def __init__(self, config: Optional[FeedConfig] = None):
        self.config = config or FeedConfig()

        # 组件
        self._fetcher: Optional[MediaFetcher] = None
        self._interest: Optional[InterestEngine] = None
        self._safety: Optional[FeedSafetyFilter] = None

        # 内存缓存
        self._cached_items: List[FeedItem] = []
        self._last_fetch: Optional[datetime] = None

        # 状态
        self._enabled = True
        self._refreshing = False

    # ============================================================
    # 组件访问
    # ============================================================

    @property
    def fetcher(self) -> MediaFetcher:
        if self._fetcher is None:
            self._fetcher = get_media_fetcher()
        return self._fetcher

    @property
    def interest(self) -> InterestEngine:
        if self._interest is None:
            self._interest = get_interest_engine()
        return self._interest

    @property
    def safety(self) -> FeedSafetyFilter:
        if self._safety is None:
            self._safety = get_feed_safety_filter()
        return self._safety

    # ============================================================
    # 主 API
    # ============================================================

    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    async def refresh(
        self,
        sources: Optional[List[FeedSource]] = None,
        force: bool = False,
    ) -> List[FeedItem]:
        """
        刷新内容

        Args:
            sources: 来源列表，None 表示全部
            force: 是否强制刷新（跳过缓存）

        Returns:
            排序后的内容列表
        """
        if self._refreshing:
            return self._cached_items

        self._refreshing = True

        try:
            if sources is None:
                sources = [
                    FeedSource.REDDIT,
                    FeedSource.GITHUB,
                    FeedSource.WEIBO,
                    FeedSource.ZHIHU,
                    FeedSource.NEWS,
                ]

            # 1. 抓取内容
            all_items = []
            for source in sources:
                if source == FeedSource.REDDIT or source == FeedSource.GITHUB:
                    # 这些来源可以直接抓取
                    items = await self.fetcher.fetch_source(source, self.config.max_items_per_source)
                    all_items.extend(items)

            # 2. 安全过滤
            safe_items = []
            for item in all_items:
                result = self.safety.check(item)
                if result["passed"] or result["level"] == "review":
                    safe_items.append(item)

            # 3. 兴趣排序
            ranked_items = self.interest.rank_items(safe_items)

            # 4. 更新时间
            self._cached_items = ranked_items
            self._last_fetch = datetime.now()

            return ranked_items

        finally:
            self._refreshing = False

    def get_items(
        self,
        limit: int = 50,
        source_filter: Optional[List[FeedSource]] = None,
    ) -> List[FeedItem]:
        """
        获取内容列表

        Args:
            limit: 返回数量
            source_filter: 来源过滤器

        Returns:
            FeedItem 列表
        """
        items = self._cached_items

        if source_filter:
            items = [i for i in items if i.source in source_filter]

        return items[:limit]

    # ============================================================
    # 反馈 API
    # ============================================================

    def record_click(self, item_id: str, stay_seconds: float = 0):
        """记录点击"""
        item = self._find_item(item_id)
        if item:
            self.interest.record_click(item, stay_seconds)

    def record_hide(self, item_id: str, reason: str = "not_interested"):
        """记录不感兴趣"""
        item = self._find_item(item_id)
        if item:
            self.interest.record_hide(item, reason)
            # 从缓存移除
            self._cached_items = [i for i in self._cached_items if i.id != item_id]

    def record_bookmark(self, item_id: str):
        """记录收藏"""
        item = self._find_item(item_id)
        if item:
            self.interest.record_bookmark(item)
            item.is_bookmarked = True

    def record_view(self, item_id: str, duration_seconds: float = 0):
        """记录浏览"""
        item = self._find_item(item_id)
        if item:
            self.interest.record_view(item, duration_seconds)

    def _find_item(self, item_id: str) -> Optional[FeedItem]:
        """查找 item"""
        for item in self._cached_items:
            if item.id == item_id:
                return item
        return None

    # ============================================================
    # 安全 API
    # ============================================================

    def get_review_queue(self) -> List[Dict]:
        """获取待复核队列"""
        return self.safety.get_review_queue()

    def approve_item(self, item_id: str) -> bool:
        """批准内容"""
        return self.safety.approve_item(item_id)

    def reject_item(self, item_id: str) -> bool:
        """拒绝内容"""
        return self.safety.reject_item(item_id)

    def add_block_keyword(self, keyword: str):
        """添加拦截词"""
        self.safety.add_block_keyword(keyword)

    def add_warn_keyword(self, keyword: str):
        """添加警告词"""
        self.safety.add_warn_keyword(keyword)

    # ============================================================
    # 统计
    # ============================================================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "enabled": self._enabled,
            "cached_items": len(self._cached_items),
            "last_fetch": self._last_fetch.isoformat() if self._last_fetch else None,
            "is_refreshing": self._refreshing,
            "interest": self.interest.get_stats(),
            "safety": self.safety.get_stats(),
        }

    def get_interest_profile(self) -> Dict[str, Any]:
        """获取兴趣画像"""
        profile = self.interest.profile
        return {
            "top_tags": self.interest.get_top_tags(10),
            "source_weights": profile.source_weights,
            "type_weights": profile.type_weights,
            "total_clicks": profile.total_clicks,
            "total_views": profile.total_views,
            "total_hides": profile.total_hides,
        }


# 全局单例
_feed_system: Optional[FeedAggregatorSystem] = None


def get_feed_system() -> FeedAggregatorSystem:
    global _feed_system
    if _feed_system is None:
        _feed_system = FeedAggregatorSystem()
    return _feed_system
