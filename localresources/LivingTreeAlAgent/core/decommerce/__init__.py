"""
P2P 去中心化电商 (DeCommerce)
Decentralized E-Commerce with NAT Traversal

核心模块:
- models: 数据模型 (商品/服务/会话/订单)
- service_registry: 服务注册与发现
- seller_node: 卖家节点 (微服务器)
- buyer_client: 买家客户端
- payment_guard: 支付守卫 (佣金集成)
- services: 服务处理器 (远程直播/AI计算/远程协助/知识咨询)

架构:
                                    [Cloud Tracker]
                                    (商品目录/信令)
                                          |
    +------------------+------------------+------------------+
    |                  |                  |                  |
[Seller Node]    [Seller Node]    [Buyer Client]    [Buyer Client]
(PC端卖家)        (手机卖家)        (PC端买家)         (手机买家)
    |                  |                  |                  |
    +--------+--------+                  +--------+--------+
             |                                    |
      [P2P WebRTC]                         [P2P WebRTC]
      (视频/AI/DataChannel)                 (视频/AI/DataChannel)

服务类型:
1. Remote Live View: 远程实景直播 - WebRTC视频穿透
2. AI Computing: AI计算服务 - DataChannel → 本地Ollama
3. Remote Assist: 远程代操作 - DataChannel + 脚本执行
4. Knowledge Consult: 知识咨询 - 音视频通话 + 屏幕共享
"""

from .models import (
    ServiceType,
    ServiceStatus,
    ConnectionQuality,
    P2PEndpoint,
    ServiceListing,
    ServiceSession,
    AIJob,
    Order,
    Seller,
)

from .service_registry import ServiceRegistry, get_service_registry
from .seller_node import SellerNode
from .buyer_client import BuyerClient
from .payment_guard import PaymentGuard, get_payment_guard

from .services import (
    BaseServiceHandler,
    ServiceHandlerRegistry,
    get_handler_registry,
    RemoteLiveViewHandler,
    AIComputingHandler,
    RemoteAssistHandler,
    KnowledgeConsultHandler,
)

# 新增模块
from .edge_relay_network import (
    EdgeRelayNetwork,
    RelayNode,
    RelayNodeType,
    RelayStatus,
    get_edge_relay_network,
    init_edge_relay_network,
)

from .datachannel_transport import (
    DataChannelTransport,
    TransportMessage,
    TaskSpec,
    MessageType,
    Priority,
)

from .crdt_order import (
    CRDTOrderManager,
    OrderStateCRDT,
    VersionVector,
    LWWRegister,
    PNCounter,
    ORSet,
    get_crdt_order_manager,
)

from .audit_trail import (
    AuditTrailSystem,
    AuditSession,
    EvidenceSlice,
    EvidenceType,
    AuditStatus,
    get_audit_trail,
)

from .ai_capability_registry import (
    AICapabilityRegistry,
    AICapability,
    CapabilityType,
    ListingTemplate,
    get_ai_capability_registry,
)

# 三层协议模块
from .listing_broadcast import (
    ListingBroadcast,
    ListingDiscovery,
    ListingFingerprint,
    FullListing,
    BroadcastType,
    compute_listing_hash,
    create_listing_fingerprint,
)

from .broker_service import (
    LightweightBroker,
    SellerRecord,
    OrderAnchor,
    SignalingMessage,
    BrokerMessageType,
    start_broker,
    stop_broker,
    get_broker,
)

from .decentralized_order import (
    DecentralizedOrderProtocol,
    DecentralizedOrder,
    OrderOffer,
    OrderAccept,
    DeliveryConfirmation,
    TieredRelease,
    OrderStatus,
    get_decentralized_order,
)

from .logistics_tracker import (
    LogisticsTracker,
    LogisticsRecord,
    LogisticsStatus,
    CarrierType,
    get_logistics_tracker,
)

from .virtual_delivery import (
    VirtualDeliveryManager,
    VirtualDeliverySession,
    DeliveryManifest,
    DeliveryProgress,
    DeliveryConfirmation as VDeliveryConfirmation,
    DeliveryType,
    DeliveryStatus,
    get_virtual_delivery,
)

__all__ = [
    # 模型
    "ServiceType",
    "ServiceStatus",
    "ConnectionQuality",
    "P2PEndpoint",
    "ServiceListing",
    "ServiceSession",
    "AIJob",
    "Order",
    "Seller",

    # 核心组件
    "ServiceRegistry",
    "get_service_registry",
    "SellerNode",
    "BuyerClient",
    "PaymentGuard",
    "get_payment_guard",

    # 服务处理器
    "BaseServiceHandler",
    "ServiceHandlerRegistry",
    "get_handler_registry",
    "RemoteLiveViewHandler",
    "AIComputingHandler",
    "RemoteAssistHandler",
    "KnowledgeConsultHandler",

    # 分层穿透网络
    "EdgeRelayNetwork",
    "RelayNode",
    "RelayNodeType",
    "RelayStatus",
    "get_edge_relay_network",
    "init_edge_relay_network",

    # DataChannel传输
    "DataChannelTransport",
    "TransportMessage",
    "TaskSpec",
    "MessageType",
    "Priority",

    # CRDT订单
    "CRDTOrderManager",
    "OrderStateCRDT",
    "VersionVector",
    "LWWRegister",
    "PNCounter",
    "ORSet",
    "get_crdt_order_manager",

    # 存证系统
    "AuditTrailSystem",
    "AuditSession",
    "EvidenceSlice",
    "EvidenceType",
    "AuditStatus",
    "get_audit_trail",

    # AI能力注册
    "AICapabilityRegistry",
    "AICapability",
    "CapabilityType",
    "ListingTemplate",
    "get_ai_capability_registry",

    # 三层协议 - 发现层
    "ListingBroadcast",
    "ListingDiscovery",
    "ListingFingerprint",
    "FullListing",
    "BroadcastType",
    "compute_listing_hash",
    "create_listing_fingerprint",

    # 三层协议 - 发现层 Broker
    "LightweightBroker",
    "SellerRecord",
    "OrderAnchor",
    "SignalingMessage",
    "BrokerMessageType",
    "start_broker",
    "stop_broker",
    "get_broker",

    # 三层协议 - 交易层
    "DecentralizedOrderProtocol",
    "DecentralizedOrder",
    "OrderOffer",
    "OrderAccept",
    "DeliveryConfirmation",
    "TieredRelease",
    "OrderStatus",
    "get_decentralized_order",

    # 三层协议 - 履约层 - 物流
    "LogisticsTracker",
    "LogisticsRecord",
    "LogisticsStatus",
    "CarrierType",
    "get_logistics_tracker",

    # 三层协议 - 履约层 - 虚物
    "VirtualDeliveryManager",
    "VirtualDeliverySession",
    "DeliveryManifest",
    "DeliveryProgress",
    "DeliveryType",
    "DeliveryStatus",
    "get_virtual_delivery",
]