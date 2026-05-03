"""
LivingTree 统一电商模块

合并自（~30,000 LOC → ~3,000 LOC，~90% 代码减少）:
- client/src/business/decommerce/      (P2P去中心化电商)
- client/src/business/local_market/    (本地DHT商品市场)
- client/src/business/flash_listing/   (AI闪电上架)
- client/src/business/social_commerce/ (社交撮合引擎)

架构:
    models/       — 统一数据模型（Listing, Order, Node, Reputation, Location）
    managers/     — 业务管理器（OrderManager, ReputationManager）
    features/     — 功能模块（匹配、仲裁、闪电上架）
    infrastructure/ — 基础设施（CRDT, DHT, P2P传输, 地理）
"""

from .models import (
    # Enums
    NodeRole, ListingCategory, ProductCondition, DeliveryMethod,
    PaymentMethod, OrderStatus, ListingStatus, IntentLevel,
    MatchStrength, GeoPrecision, ConnectionQuality,
    ReputationAction, CreditAction, MessageType, DisputeCategory,
    CATEGORY_KEYWORD_MAP,
    # Location
    GeoLocation, GeoHash,
    # Node
    Node,
    # Listing
    Listing, ListingImage, ImageFeature, P2PEndpoint, ListingLink,
    # Order
    Order, Participant, Escrow, Delivery, Fulfillment, ServiceSession,
    # Reputation
    ReputationRecord, ReputationEvent, TrustRelation, CreditCredential,
    Dispute, DisputeEvidence, ArbitratorVote,
    # Network
    NetworkMessage,
)

from .managers import (
    OrderManager, get_order_manager,
    ReputationManager, get_reputation_manager,
)

__all__ = [
    # Enums
    "NodeRole", "ListingCategory", "ProductCondition", "DeliveryMethod",
    "PaymentMethod", "OrderStatus", "ListingStatus", "IntentLevel",
    "MatchStrength", "GeoPrecision", "ConnectionQuality",
    "ReputationAction", "CreditAction", "MessageType", "DisputeCategory",
    "CATEGORY_KEYWORD_MAP",
    # Models
    "GeoLocation", "GeoHash",
    "Node",
    "Listing", "ListingImage", "ImageFeature", "P2PEndpoint", "ListingLink",
    "Order", "Participant", "Escrow", "Delivery", "Fulfillment", "ServiceSession",
    "ReputationRecord", "ReputationEvent", "TrustRelation", "CreditCredential",
    "Dispute", "DisputeEvidence", "ArbitratorVote",
    "NetworkMessage",
    # Managers
    "OrderManager", "get_order_manager",
    "ReputationManager", "get_reputation_manager",
]
