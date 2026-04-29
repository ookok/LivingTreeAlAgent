# core/social_commerce/__init__.py
# 社交化撮合引擎 - 从"人找货"到"货找人"
#
# 核心模块:
# - models: 数据模型 (节点画像/匹配候选/信用凭证)
# - intent_radar: 意图雷达 (行为→交易意愿预测)
# - spacetime_matcher: 时空引力匹配 (GeoHash社交层)
# - trust_breaker: AI信任破冰 (场景化开场白)
# - credit_network: 去中心化信用网 (链式评价)
# - matchmaking_engine: 撮合引擎 (整合四大模块)
#
# 架构:
#
# ┌─────────────────────────────────────────────────────────────────┐
# │                     MatchmakingEngine                            │
# │                      (撮合引擎，统一调度)                            │
# ├─────────────────┬─────────────────┬────────────────────────────┤
# │ IntentRadar     │ SpacetimeMatcher │ TrustBreaker              │
# │ (意图雷达)       │ (时空匹配)        │ (AI破冰)                   │
# │                 │                 │                            │
# │ 行为信号分析     │ GeoHash社交层    │ 场景化开场白               │
# │ B端/跨境检测     │ 流动性感知       │ 渐进披露                   │
# │ 动态画像        │ 引力计算         │ 信任评估                   │
# ├─────────────────┴─────────────────┴────────────────────────────┤
# │                      CreditNetwork                               │
# │                    (去中心化信用网)                              │
# │                   链式评价/品类专长/信任关系                       │
# └─────────────────────────────────────────────────────────────────┘
#

from .models import (
    # 枚举
    NodeType,
    IntentLevel,
    MatchStrength,
    GeoPrecision,
    TradeStatus,
    CreditAction,

    # 数据结构
    GeoHash,
    NodeProfile,
    GeoLocation,
    MatchCandidate,
    CreditCredential,
    IcebreakerMessage,
    MatchSession,
    IntentSignal,
    ProductionNode,
    FragmentedOrder,
)

from .intent_radar import (
    IntentRadar,
    IntentRadarManager,
    get_intent_radar,
)

from .spacetime_matcher import (
    SpacetimeMatcher,
    SpacetimeMatcherManager,
    SpacetimeCalculator,
    get_spacetime_matcher,
)

from .trust_breaker import (
    TrustBreaker,
    TrustBreakerManager,
    GradualDisclosure,
    get_trust_breaker,
)

from .credit_network import (
    CreditNetwork,
    CreditNetworkManager,
    CreditEvaluator,
    get_credit_network,
)

from .matchmaking_engine import (
    MatchmakingEngine,
    MatchmakingManager,
    FragmentedMatchmaker,
    EmergencyTradeNetwork,
    get_matchmaking_engine,
)

# 闪电上架（对话式上架）
from ..flash_listing import (
    FlashListingEngine,
    get_flash_listing_engine,
    quick_listing,
    ListingStage,
    ProductCondition,
    DeliveryType,
    PaymentMethod,
    ImageFeature,
    GeneratedListing,
    ProductLink,
    InlinePurchase,
    FulfillmentRecord,
    FlashListingSession,
)

__version__ = "1.0.0"

__all__ = [
    # 模型
    "NodeType",
    "IntentLevel",
    "MatchStrength",
    "GeoPrecision",
    "TradeStatus",
    "CreditAction",
    "GeoHash",
    "NodeProfile",
    "GeoLocation",
    "MatchCandidate",
    "CreditCredential",
    "IcebreakerMessage",
    "MatchSession",
    "IntentSignal",
    "ProductionNode",
    "FragmentedOrder",

    # 意图雷达
    "IntentRadar",
    "IntentRadarManager",
    "get_intent_radar",

    # 时空匹配
    "SpacetimeMatcher",
    "SpacetimeMatcherManager",
    "SpacetimeCalculator",
    "get_spacetime_matcher",

    # AI破冰
    "TrustBreaker",
    "TrustBreakerManager",
    "GradualDisclosure",
    "get_trust_breaker",

    # 信用网络
    "CreditNetwork",
    "CreditNetworkManager",
    "CreditEvaluator",
    "get_credit_network",

    # 撮合引擎
    "MatchmakingEngine",
    "MatchmakingManager",
    "FragmentedMatchmaker",
    "EmergencyTradeNetwork",
    "get_matchmaking_engine",

    # 闪电上架
    "FlashListingEngine",
    "get_flash_listing_engine",
    "quick_listing",
    "ListingStage",
    "ProductCondition",
    "DeliveryType",
    "PaymentMethod",
    "ImageFeature",
    "GeneratedListing",
    "ProductLink",
    "InlinePurchase",
    "FulfillmentRecord",
    "FlashListingSession",
]