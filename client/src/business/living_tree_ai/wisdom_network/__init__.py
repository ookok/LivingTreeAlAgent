"""
LivingTreeAI Wisdom Network - 去中心化智慧网络
================================================

三网合一架构：
┌─────────────────────────────────────────────────────┐
│              去中心化智慧网络 (Wisdom Network)         │
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Search Net │  │  Cache Net  │  │ Credit Net  │ │
│  │   搜索网     │  │   缓存网     │  │   贡献网     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
├─────────────────────────────────────────────────────┤
│              共享基础设施层                           │
│  (通信协议栈 / 节点管理 / 安全层)                      │
└─────────────────────────────────────────────────────┘

模块：
- search_routing.py : 智能搜索路由
- distributed_cache.py : 分布式缓存网络
- credit_network.py : 贡献证明与激励

Author: LivingTreeAI Community
License: Apache 2.0
"""

__version__ = "1.0.0"

from .search_routing import (
    SearchRouter,
    SearchRequest,
    SearchResult,
    SpecialtyGraph,
    NodePerformanceStats,
    QueryContext,
    get_search_router,
)

from .distributed_cache import (
    DistributedCache,
    CacheEntry,
    CacheNotice,
    CacheRoutingTable,
    CacheHeatMap,
    get_distributed_cache,
)

from .credit_network import (
    CreditNetwork,
    ContributionProof,
    ContributionLedger,
    ContributionType,
    ReputationScore,
    QuotaManager,
    get_credit_network,
)

from .wisdom_workflow import (
    WisdomNetwork,
    WisdomWorkflow,
    NetworkStats,
    get_wisdom_network,
)

__all__ = [
    # 版本
    "__version__",
    # 搜索网
    "SearchRouter",
    "SearchRequest",
    "SearchResult",
    "SpecialtyGraph",
    "NodePerformanceStats",
    "QueryContext",
    "get_search_router",
    # 缓存网
    "DistributedCache",
    "CacheEntry",
    "CacheNotice",
    "CacheRoutingTable",
    "CacheHeatMap",
    "get_distributed_cache",
    # 贡献网
    "CreditNetwork",
    "ContributionProof",
    "ContributionLedger",
    "ContributionType",
    "ReputationScore",
    "QuotaManager",
    "get_credit_network",
    # 工作流
    "WisdomNetwork",
    "WisdomWorkflow",
    "NetworkStats",
    "get_wisdom_network",
]