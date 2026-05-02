"""
首页聚合推荐系统
轻量级"召回-排序-展示"架构
支持多源内容：新闻/视频/商品
"""

from .user_profile import UserProfile, UserProfileManager, get_profile_manager
from .recall import RecallEngine, DataSource, get_recall_engine
from .ranking import RankingEngine, RankedItem, ContentType, get_ranking_engine
from .data_adapters import (
    NewsAdapter,
    VideoAdapter,
    ProductAdapter,
    UnifiedItem,
    adapt_items
)

__all__ = [
    # 用户画像
    "UserProfile",
    "UserProfileManager",
    "get_profile_manager",
    # 召回
    "RecallEngine",
    "DataSource",
    "get_recall_engine",
    # 排序
    "RankingEngine",
    "RankedItem",
    "ContentType",
    "get_ranking_engine",
    # 适配器
    "NewsAdapter",
    "VideoAdapter",
    "ProductAdapter",
    "UnifiedItem",
    "adapt_items",
]
