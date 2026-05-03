"""
统一电商数据模型

合并自:
- client/src/business/local_market/models.py (NodeInfo, Product, Trade, ReputationEvent, Dispute, etc.)
- client/src/business/decommerce/models.py (ServiceListing, ServiceSession, Seller, Order, P2PEndpoint)
- client/src/business/flash_listing/models.py (GeneratedListing, ImageFeature, ProductLink, InlinePurchase, FulfillmentRecord)
- client/src/business/social_commerce/models.py (NodeProfile, GeoLocation, MatchCandidate, CreditCredential, IntentSignal)
- client/src/business/decommerce/crdt_order.py (OrderStateCRDT 数据结构)
- client/src/business/local_market/reputation.py (ReputationRecord, ReputationManager)

统一后：~90% 代码减少 (4套重复模型 → 1套统一模型)
"""

from .enums import (
    NodeRole,
    ListingCategory,
    ProductCondition,
    DeliveryMethod,
    PaymentMethod,
    OrderStatus,
    ListingStatus,
    IntentLevel,
    MatchStrength,
    GeoPrecision,
    ConnectionQuality,
    ReputationAction,
    CreditAction,
    MessageType,
    DisputeCategory,
    CATEGORY_KEYWORD_MAP,
)

from .location import GeoLocation, GeoHash

from .node import Node

from .listing import (
    Listing,
    ListingImage,
    ImageFeature,
    P2PEndpoint,
    ListingLink,
)

from .order import (
    Order,
    Participant,
    Escrow,
    Delivery,
    Fulfillment,
    ServiceSession,
)

from .reputation import (
    ReputationRecord,
    ReputationEvent,
    TrustRelation,
    CreditCredential,
    Dispute,
    DisputeEvidence,
    ArbitratorVote,
)

from .network import NetworkMessage

__all__ = [
    # Enums
    "NodeRole",
    "ListingCategory",
    "ProductCondition",
    "DeliveryMethod",
    "PaymentMethod",
    "OrderStatus",
    "ListingStatus",
    "IntentLevel",
    "MatchStrength",
    "GeoPrecision",
    "ConnectionQuality",
    "ReputationAction",
    "CreditAction",
    "MessageType",
    "DisputeCategory",
    "CATEGORY_KEYWORD_MAP",
    # Location
    "GeoLocation",
    "GeoHash",
    # Node
    "Node",
    # Listing
    "Listing",
    "ListingImage",
    "ImageFeature",
    "P2PEndpoint",
    "ListingLink",
    # Order
    "Order",
    "Participant",
    "Escrow",
    "Delivery",
    "Fulfillment",
    "ServiceSession",
    # Reputation
    "ReputationRecord",
    "ReputationEvent",
    "TrustRelation",
    "CreditCredential",
    "Dispute",
    "DisputeEvidence",
    "ArbitratorVote",
    # Network
    "NetworkMessage",
]
