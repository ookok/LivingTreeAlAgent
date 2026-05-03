"""
免费网络搜索API分层策略 - 核心模块

四级免费API分层架构：
- Tier 1: 国内高稳定性免费API（百度、搜狗、360）
- Tier 2: 国内专业垂直免费API（知乎、豆瓣、天气等）
- Tier 3: 国外免费API（DuckDuckGo、Wikipedia、GitHub）
- Tier 4: 备用方案（本地缓存、离线数据）

核心特性：
- 智能路由：根据查询类型自动选择最优API
- 结果融合：多源结果智能去重和排序
- 失败降级：API失效自动切换备用方案
- 健康监控：实时监控API可用性和响应时间
"""

from .models import (
    TierLevel,
    QueryType,
    APIStatus,
    APIConfig,
    APIHealth,
    SearchResult,
    FusionResult,
    QueryContext,
    RateLimiter,
)
from .tier1_engines import (
    BaiduEngine,
    SogouEngine,
    So360Engine,
    TiangongEngine,
    JuhuasuanEngine,
)
from .tier2_engines import (
    ZhihuEngine,
    DoubanEngine,
    GaodeEngine,
    HefengEngine,
    GithubEngine,
)
from .tier3_engines import (
    DuckDuckGoEngine,
    WikipediaEngine,
    OpenLibraryEngine,
)
from .tier4_engines import (
    LocalCacheEngine,
    KnowledgeBaseEngine,
)
from .tier_router import TierRouter
from .result_fusion import ResultFusion
from .api_monitor import APIMonitor
from .search_scheduler import SearchScheduler
from .tiered_adapter import TieredSearchAdapter, get_tiered_adapter, tiered_search

__all__ = [
    # 模型
    "TierLevel",
    "QueryType",
    "APIStatus",
    "APIConfig",
    "APIHealth",
    "SearchResult",
    "FusionResult",
    "QueryContext",
    "RateLimiter",
    
    # 引擎
    "BaiduEngine",
    "SogouEngine",
    "So360Engine",
    "TiangongEngine",
    "JuhuasuanEngine",
    "ZhihuEngine",
    "DoubanEngine",
    "GaodeEngine",
    "HefengEngine",
    "GithubEngine",
    "DuckDuckGoEngine",
    "WikipediaEngine",
    "OpenLibraryEngine",
    "LocalCacheEngine",
    "KnowledgeBaseEngine",
    
    # 核心组件
    "TierRouter",
    "ResultFusion",
    "APIMonitor",
    "SearchScheduler",
    "TieredSearchAdapter",
    "get_tiered_adapter",
    "tiered_search",
]
