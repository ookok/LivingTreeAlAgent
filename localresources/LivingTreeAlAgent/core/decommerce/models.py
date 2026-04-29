"""
P2P 去中心化电商核心数据模型
DeCommerce Core Data Models

定义商品、服务、会话的数据结构
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import json


class ServiceType(Enum):
    """服务类型枚举"""
    # 实物商品 (静态图文)
    PHYSICAL_PRODUCT = "physical_product"

    # 远程实景直播 (WebRTC视频穿透)
    REMOTE_LIVE_VIEW = "remote_live_view"

    # AI 计算服务 (DataChannel → 本地 Ollama/Hermes)
    AI_COMPUTING = "ai_computing"

    # 远程代操作 (DataChannel + 脚本执行)
    REMOTE_ASSIST = "remote_assist"

    # 知识咨询 (音视频通话 + 屏幕共享)
    KNOWLEDGE_CONSULT = "knowledge_consult"

    # 数字商品 (可下载文件)
    DIGITAL_PRODUCT = "digital_product"


class ServiceStatus(Enum):
    """服务状态"""
    DRAFT = "draft"           # 草稿
    ONLINE = "online"         # 上线
    OFFLINE = "offline"       # 下线
    LIVE_ACTIVE = "live_active"  # 实时服务激活
    LIVE_BUSY = "live_busy"   # 服务中
    LIVE_PAUSED = "live_paused"  # 暂停


class ConnectionQuality(Enum):
    """连接质量"""
    EXCELLENT = "excellent"   # P2P直连
    GOOD = "good"            # TURN中继
    FAIR = "fair"            # 弱网
    POOR = "poor"            # 勉强可用


@dataclass
class P2PEndpoint:
    """P2P连接端点信息"""
    # 连接类型
    type: str = "webrtc"  # webrtc | datachannel | relay

    # ICE配置
    ice_servers: List[Dict[str, Any]] = field(default_factory=list)

    # 候选人线索
    public_ip: Optional[str] = None
    nat_type: Optional[str] = None  # full_cone / restricted / symmetric

    # TURN回退
    turn_url: Optional[str] = None
    turn_username: Optional[str] = None
    turn_credential: Optional[str] = None

    # 连接质量评分 (0-100)
    quality_score: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "ice_servers": self.ice_servers,
            "public_ip": self.public_ip,
            "nat_type": self.nat_type,
            "turn_url": self.turn_url,
            "turn_username": self.turn_username,
            "turn_credential": self.turn_credential,
            "quality_score": self.quality_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "P2PEndpoint":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ServiceListing:
    """商品/服务列表项"""
    # 基础信息
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    seller_id: str = ""
    title: str = ""
    description: str = ""
    price: float = 0.0  # 单位: 分 ( cents)
    currency: str = "CNY"

    # 服务类型
    service_type: ServiceType = ServiceType.PHYSICAL_PRODUCT

    # 交付方式
    delivery_type: str = "instant"  # instant | scheduled | live | download

    # 服务端点 (P2P穿透信息)
    endpoint: Optional[P2PEndpoint] = None

    # 媒体信息
    thumbnail_url: Optional[str] = None
    media_urls: List[str] = field(default_factory=list)

    # AI服务特定
    ai_model: Optional[str] = None  # 如 "llama3:8b"
    ai_capabilities: List[str] = field(default_factory=list)  # ["chat", "code", "reasoning"]

    # 实时服务可用性
    is_live_available: bool = False
    max_concurrent: int = 1

    # 状态
    status: ServiceStatus = ServiceStatus.DRAFT
    view_count: int = 0
    order_count: int = 0

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    last_live_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "seller_id": self.seller_id,
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "currency": self.currency,
            "service_type": self.service_type.value,
            "delivery_type": self.delivery_type,
            "endpoint": self.endpoint.to_dict() if self.endpoint else None,
            "thumbnail_url": self.thumbnail_url,
            "media_urls": self.media_urls,
            "ai_model": self.ai_model,
            "ai_capabilities": self.ai_capabilities,
            "is_live_available": self.is_live_available,
            "max_concurrent": self.max_concurrent,
            "status": self.status.value,
            "view_count": self.view_count,
            "order_count": self.order_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_live_at": self.last_live_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceListing":
        data = data.copy()
        if "service_type" in data and isinstance(data["service_type"], str):
            data["service_type"] = ServiceType(data["service_type"])
        if "status" in data and isinstance(data["status"], str):
            data["status"] = ServiceStatus(data["status"])
        if "endpoint" in data and data["endpoint"]:
            data["endpoint"] = P2PEndpoint.from_dict(data["endpoint"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ServiceSession:
    """实时服务会话"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    listing_id: str = ""
    seller_id: str = ""
    buyer_id: str = ""

    # 会话类型
    session_type: ServiceType = ServiceType.REMOTE_LIVE_VIEW

    # WebRTC房间信息
    room_id: str = ""
    room_password: str = ""

    # 连接端点
    buyer_endpoint: Optional[P2PEndpoint] = None
    seller_endpoint: Optional[P2PEndpoint] = None

    # SDP信息 (用于P2P连接建立)
    seller_sdp_offer: Optional[str] = None
    buyer_sdp_answer: Optional[str] = None

    # 状态
    status: str = "pending"  # pending | connecting | active | paused | completed | cancelled | refunded

    # 计费
    billing_start: Optional[float] = None
    billing_end: Optional[float] = None
    billing_duration_seconds: int = 0
    billing_amount: int = 0  # 实际扣费(分)

    # 心跳
    last_heartbeat_seller: float = 0
    last_heartbeat_buyer: float = 0

    # Access Ticket
    access_token: str = ""
    token_expires_at: float = 0

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "listing_id": self.listing_id,
            "seller_id": self.seller_id,
            "buyer_id": self.buyer_id,
            "session_type": self.session_type.value,
            "room_id": self.room_id,
            "room_password": self.room_password,
            "buyer_endpoint": self.buyer_endpoint.to_dict() if self.buyer_endpoint else None,
            "seller_endpoint": self.seller_endpoint.to_dict() if self.seller_endpoint else None,
            "status": self.status,
            "billing_start": self.billing_start,
            "billing_end": self.billing_end,
            "billing_duration_seconds": self.billing_duration_seconds,
            "billing_amount": self.billing_amount,
            "last_heartbeat_seller": self.last_heartbeat_seller,
            "last_heartbeat_buyer": self.last_heartbeat_buyer,
            "access_token": self.access_token,
            "token_expires_at": self.token_expires_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class AIJob:
    """AI计算任务 (DataChannel传输)"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    session_id: str = ""

    # 任务类型
    task_type: str = "chat"  # chat | complete | embed | reasoning

    # 输入
    prompt: str = ""
    model: str = ""  # 如 "llama3:8b"
    parameters: Dict[str, Any] = field(default_factory=dict)

    # 输出
    result: Optional[str] = None
    error: Optional[str] = None

    # 计量
    input_tokens: int = 0
    output_tokens: int = 0

    # 状态
    status: str = "queued"  # queued | running | completed | failed

    # 时间
    queued_at: float = field(default_factory=lambda: datetime.now().timestamp())
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class Order:
    """订单"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    listing_id: str = ""
    session_id: Optional[str] = None

    seller_id: str = ""
    buyer_id: str = ""

    # 金额
    total_amount: int = 0  # 总金额(分)
    commission_fee: int = 0  # 佣金(分)
    net_amount: int = 0  # 净收入(分)

    # 状态
    status: str = "pending"  # pending | frozen | active | completed | cancelled | refunded

    # 支付信息
    payment_method: str = ""
    payment_id: str = ""

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    paid_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class Seller:
    """卖家信息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    user_id: str = ""  # 关联用户系统

    name: str = ""
    avatar_url: Optional[str] = None
    bio: str = ""

    # 连接能力
    connectivity: ConnectionQuality = ConnectionQuality.POOR
    endpoint: Optional[P2PEndpoint] = None

    # 能力验证
    has_ai_service: bool = False
    ai_models: List[str] = field(default_factory=list)

    # 统计
    total_services: int = 0
    total_orders: int = 0
    rating: float = 0.0

    # 状态
    is_online: bool = False
    last_seen_at: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "connectivity": self.connectivity.value,
            "endpoint": self.endpoint.to_dict() if self.endpoint else None,
            "has_ai_service": self.has_ai_service,
            "ai_models": self.ai_models,
            "total_services": self.total_services,
            "total_orders": self.total_orders,
            "rating": self.rating,
            "is_online": self.is_online,
            "last_seen_at": self.last_seen_at,
        }