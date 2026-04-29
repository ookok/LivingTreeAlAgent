"""
本地商品交易市场 - 数据模型

定义去中心化本地商品交易系统的核心数据结构
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import json


class NodeType(Enum):
    """节点类型"""
    SELLER = "seller"      # 卖家节点
    BUYER = "buyer"       # 买家节点
    WITNESS = "witness"   # 见证节点
    RELAY = "relay"       # 中继节点


class ProductCategory(Enum):
    """商品分类"""
    ELECTRONICS = "electronics"      # 电子产品
    FASHION = "fashion"              # 服饰箱包
    HOME = "home"                   # 家居用品
    FOOD = "food"                   # 食品生鲜
    BOOKS = "books"                 # 图书二手
    SERVICES = "services"           # 本地服务
    VEHICLES = "vehicles"           # 车辆交通工具
    OTHER = "other"                 # 其他


class TransactionStatus(Enum):
    """交易状态"""
    INITIATED = "initiated"         # 已发起
    NEGOTIATING = "negotiating"     # 协商中
    ESCROW = "escrow"               # 托管中
    DELIVERING = "delivering"       # 交付中
    COMPLETED = "completed"         # 已完成
    CANCELLED = "cancelled"         # 已取消
    DISPUTED = "disputed"           # 争议中
    REFUNDED = "refunded"           # 已退款


class PaymentType(Enum):
    """支付类型"""
    DIRECT = "direct"               # 直接支付
    ESCROW_2OF3 = "escrow_2of3"    # 2/3多签托管
    TIMELOCK = "timelock"          # 时间锁定支付


class DeliveryType(Enum):
    """交付方式"""
    PICKUP = "pickup"              # 买家自提
    NODE_DELIVERY = "node_delivery" # 节点配送
    SAFEPOINT = "safepoint"        # 安全交付点


class ReputationAction(Enum):
    """信誉操作"""
    SUCCESSFUL_TRADE = "successful_trade"  # 成功交易 +5
    GOOD_REVIEW = "good_review"            # 好评 +2
    QUICK_CONFIRM = "quick_confirm"         # 快速确认 +1
    DISPUTE_RESOLVE = "dispute_resolve"     # 纠纷主动和解 +3
    TRADE_CANCEL = "trade_cancel"          # 交易取消 -3
    BAD_REVIEW = "bad_review"              # 差评 -5
    FALSE_PRODUCT = "false_product"         # 虚假商品 -20
    FRAUD = "fraud"                        # 欺诈行为 -100


# ============================================================================
# 节点相关模型
# ============================================================================

@dataclass
class GeoLocation:
    """地理位置"""
    latitude: float           # 纬度
    longitude: float         # 经度
    geohash: str = ""        # Geohash编码
    district: str = ""       # 行政区划
    precision: int = 3       # 精度级别（1-12，越高越精确）

    def __post_init__(self):
        if not self.geohash:
            self.geohash = self._compute_geohash()

    def _compute_geohash(self) -> str:
        """计算Geohash（简化版）"""
        BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
        lat, lon = self.latitude, self.longitude
        lat_range, lon_range = (-90.0, 90.0), (-180.0, 180.0)
        hash_bits = []

        for _ in range(self.precision * 5):
            if len(hash_bits) % 2 == 0:
                mid = (lon_range[0] + lon_range[1]) / 2
                hash_bits.append(0 if lon < mid else 1)
                lon_range = (lon_range[0], mid) if lon < mid else (mid, lon_range[1])
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                hash_bits.append(0 if lat < mid else 1)
                lat_range = (lat_range[0], mid) if lat < mid else (mid, lat_range[1])

        result = ""
        for i in range(0, len(hash_bits), 5):
            bits = hash_bits[i:i+5]
            if len(bits) == 5:
                result += BASE32[sum(b << (4-j) for j, b in enumerate(bits[:5]))]

        return result

    def distance_to(self, other: 'GeoLocation') -> float:
        """计算两点间距离（公里）"""
        import math
        R = 6371  # 地球半径

        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        return R * c


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    node_type: NodeType = NodeType.BUYER
    name: str = ""
    avatar: str = ""

    # 网络信息
    ip: str = ""
    port: int = 0
    is_relay: bool = False

    # 地理位置
    location: Optional[GeoLocation] = None

    # 信誉信息
    reputation: int = 100
    total_trades: int = 0
    good_reviews: int = 0
    bad_reviews: int = 0

    # 状态
    is_online: bool = False
    last_seen: datetime = field(default_factory=datetime.now)
    active_hours: List[int] = field(default_factory=list)  # 0-23

    # 社交关系
    trusted_nodes: List[str] = field(default_factory=list)  # 直接信任的节点ID
    blocked_nodes: List[str] = field(default_factory=list)  # 拉黑的节点ID

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "name": self.name,
            "avatar": self.avatar,
            "ip": self.ip,
            "port": self.port,
            "is_relay": self.is_relay,
            "location": {
                "latitude": self.location.latitude,
                "longitude": self.location.longitude,
                "geohash": self.location.geohash,
                "district": self.location.district,
                "precision": self.location.precision
            } if self.location else None,
            "reputation": self.reputation,
            "total_trades": self.total_trades,
            "good_reviews": self.good_reviews,
            "bad_reviews": self.bad_reviews,
            "is_online": self.is_online,
            "last_seen": self.last_seen.isoformat(),
            "active_hours": self.active_hours,
            "trusted_nodes": self.trusted_nodes,
            "blocked_nodes": self.blocked_nodes,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NodeInfo':
        location = None
        if data.get("location"):
            loc_data = data["location"]
            location = GeoLocation(
                latitude=loc_data["latitude"],
                longitude=loc_data["longitude"],
                geohash=loc_data.get("geohash", ""),
                district=loc_data.get("district", ""),
                precision=loc_data.get("precision", 3)
            )

        return cls(
            node_id=data["node_id"],
            node_type=NodeType(data.get("node_type", "buyer")),
            name=data.get("name", ""),
            avatar=data.get("avatar", ""),
            ip=data.get("ip", ""),
            port=data.get("port", 0),
            is_relay=data.get("is_relay", False),
            location=location,
            reputation=data.get("reputation", 100),
            total_trades=data.get("total_trades", 0),
            good_reviews=data.get("good_reviews", 0),
            bad_reviews=data.get("bad_reviews", 0),
            is_online=data.get("is_online", False),
            last_seen=datetime.fromisoformat(data["last_seen"]) if data.get("last_seen") else datetime.now(),
            active_hours=data.get("active_hours", []),
            trusted_nodes=data.get("trusted_nodes", []),
            blocked_nodes=data.get("blocked_nodes", []),
            metadata=data.get("metadata", {})
        )


# ============================================================================
# 商品相关模型
# ============================================================================

@dataclass
class ProductImage:
    """商品图片"""
    url: str = ""                    # IPFS URL 或本地路径
    ipfs_hash: str = ""              # IPFS 哈希
    thumbnail: str = ""              # 缩略图
    order: int = 0                   # 排序


@dataclass
class Product:
    """商品信息"""
    product_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    seller_id: str = ""

    # 基础信息
    title: str = ""
    description: str = ""
    category: ProductCategory = ProductCategory.OTHER
    tags: List[str] = field(default_factory=list)

    # 价格信息
    price: float = 0.0
    price_unit: str = "CNY"          # 货币单位
    negotiable: bool = True           # 是否可议价

    # 商品属性
    condition: str = "new"           # new / like_new / used / refurbished
    quantity: int = 1
    images: List[ProductImage] = field(default_factory=list)

    # 交付信息
    delivery_type: DeliveryType = DeliveryType.PICKUP
    delivery_range: float = 5.0     # 可配送范围（公里）

    # 地理位置
    location: Optional[GeoLocation] = None

    # 状态
    status: str = "active"           # active / reserved / sold / removed
    view_count: int = 0
    favorite_count: int = 0

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None

    # 分布式存储
    ipfs_hash: str = ""              # 商品详情的 IPFS 哈希
    local_node_id: str = ""          # 本地存储的节点ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "seller_id": self.seller_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "tags": self.tags,
            "price": self.price,
            "price_unit": self.price_unit,
            "negotiable": self.negotiable,
            "condition": self.condition,
            "quantity": self.quantity,
            "images": [
                {"url": img.url, "ipfs_hash": img.ipfs_hash, "thumbnail": img.thumbnail, "order": img.order}
                for img in self.images
            ],
            "delivery_type": self.delivery_type.value,
            "delivery_range": self.delivery_range,
            "location": {
                "latitude": self.location.latitude,
                "longitude": self.location.longitude,
                "geohash": self.location.geohash,
                "district": self.location.district,
                "precision": self.location.precision
            } if self.location else None,
            "status": self.status,
            "view_count": self.view_count,
            "favorite_count": self.favorite_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "ipfs_hash": self.ipfs_hash,
            "local_node_id": self.local_node_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Product':
        images = []
        for img_data in data.get("images", []):
            images.append(ProductImage(
                url=img_data.get("url", ""),
                ipfs_hash=img_data.get("ipfs_hash", ""),
                thumbnail=img_data.get("thumbnail", ""),
                order=img_data.get("order", 0)
            ))

        location = None
        if data.get("location"):
            loc_data = data["location"]
            location = GeoLocation(
                latitude=loc_data["latitude"],
                longitude=loc_data["longitude"],
                geohash=loc_data.get("geohash", ""),
                district=loc_data.get("district", ""),
                precision=loc_data.get("precision", 3)
            )

        return cls(
            product_id=data["product_id"],
            seller_id=data["seller_id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            category=ProductCategory(data.get("category", "other")),
            tags=data.get("tags", []),
            price=data.get("price", 0.0),
            price_unit=data.get("price_unit", "CNY"),
            negotiable=data.get("negotiable", True),
            condition=data.get("condition", "new"),
            quantity=data.get("quantity", 1),
            images=images,
            delivery_type=DeliveryType(data.get("delivery_type", "pickup")),
            delivery_range=data.get("delivery_range", 5.0),
            location=location,
            status=data.get("status", "active"),
            view_count=data.get("view_count", 0),
            favorite_count=data.get("favorite_count", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            ipfs_hash=data.get("ipfs_hash", ""),
            local_node_id=data.get("local_node_id", "")
        )


# ============================================================================
# 交易相关模型
# ============================================================================

@dataclass
class TradeParticipant:
    """交易参与者"""
    node_id: str
    node_name: str
    role: str                    # "buyer" / "seller" / "witness"
    reputation: int = 100
    location: Optional[GeoLocation] = None


@dataclass
class EscrowInfo:
    """托管信息"""
    escrow_address: str = ""     # 托管地址
    amount: float = 0.0
    currency: str = "CNY"
    created_at: datetime = field(default_factory=datetime.now)
    released_at: Optional[datetime] = None
    witnesses: List[str] = field(default_factory=list)  # 见证节点ID列表
    required_signatures: int = 2  # 需要多少签名才能释放


@dataclass
class DeliveryInfo:
    """交付信息"""
    delivery_type: DeliveryType = DeliveryType.PICKUP
    pickup_code: str = ""         # 自提验证码
    delivery_code: str = ""      # 配送验证码

    # 位置信息
    pickup_location: Optional[GeoLocation] = None
    delivery_address: str = ""

    # 时间窗口
    pickup_time_start: Optional[datetime] = None
    pickup_time_end: Optional[datetime] = None

    # 配送节点
    delivery_node_id: Optional[str] = None
    delivery_route: List[GeoLocation] = field(default_factory=list)


@dataclass
class Trade:
    """交易记录"""
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    product_id: str = ""

    # 参与者
    buyer: Optional[TradeParticipant] = None
    seller: Optional[TradeParticipant] = None
    witnesses: List[TradeParticipant] = field(default_factory=list)

    # 价格
    final_price: float = 0.0
    original_price: float = 0.0
    discount_applied: float = 0.0

    # 支付信息
    payment_type: PaymentType = PaymentType.DIRECT
    escrow: Optional[EscrowInfo] = None
    payment_proof: str = ""       # 支付凭证

    # 交付信息
    delivery: Optional[DeliveryInfo] = None

    # 状态
    status: TransactionStatus = TransactionStatus.INITIATED

    # 时间戳
    initiated_at: datetime = field(default_factory=datetime.now)
    negotiated_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    # 评价
    buyer_review: Optional[Dict[str, Any]] = None
    seller_review: Optional[Dict[str, Any]] = None

    # 争议
    dispute_id: Optional[str] = None
    dispute_reason: str = ""

    # 证据
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "product_id": self.product_id,
            "buyer": self.buyer.__dict__ if self.buyer else None,
            "seller": self.seller.__dict__ if self.seller else None,
            "witnesses": [w.__dict__ for w in self.witnesses],
            "final_price": self.final_price,
            "original_price": self.original_price,
            "discount_applied": self.discount_applied,
            "payment_type": self.payment_type.value,
            "escrow": self.escrow.__dict__ if self.escrow else None,
            "payment_proof": self.payment_proof,
            "delivery": self.delivery.__dict__ if self.delivery else None,
            "status": self.status.value,
            "initiated_at": self.initiated_at.isoformat(),
            "negotiated_at": self.negotiated_at.isoformat() if self.negotiated_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "buyer_review": self.buyer_review,
            "seller_review": self.seller_review,
            "dispute_id": self.dispute_id,
            "dispute_reason": self.dispute_reason,
            "evidence": self.evidence,
            "metadata": self.metadata
        }


# ============================================================================
# 信誉相关模型
# ============================================================================

@dataclass
class ReputationEvent:
    """信誉事件"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    node_id: str = ""

    # 事件类型
    action: ReputationAction = ReputationAction.SUCCESSFUL_TRADE
    trade_id: Optional[str] = None
    counterparty_id: Optional[str] = None

    # 变化
    reputation_change: int = 0
    reason: str = ""

    # 时间
    timestamp: datetime = field(default_factory=datetime.now)

    # 证据
    evidence_hash: str = ""
    witnesses: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "node_id": self.node_id,
            "action": self.action.value,
            "trade_id": self.trade_id,
            "counterparty_id": self.counterparty_id,
            "reputation_change": self.reputation_change,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "evidence_hash": self.evidence_hash,
            "witnesses": self.witnesses
        }


@dataclass
class TrustRelation:
    """信任关系"""
    from_node: str
    to_node: str
    direct_trust: float = 0.0      # 直接信任度 0-1
    indirect_trust: float = 0.0    # 间接信任度 0-1
    total_trust: float = 0.0       # 总信任度
    shared_contacts: List[str] = field(default_factory=list)  # 共同联系人
    successful_trades: int = 0
    last_interaction: datetime = field(default_factory=datetime.now)

    def calculate_total_trust(self, decay_factor: float = 0.8) -> float:
        """计算总信任度 = 直接信任 + 间接信任 * 衰减因子"""
        self.total_trust = self.direct_trust + self.indirect_trust * decay_factor
        return self.total_trust


# ============================================================================
# 仲裁相关模型
# ============================================================================

@dataclass
class DisputeEvidence:
    """争议证据"""
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    dispute_id: str = ""

    evidence_type: str = ""        # "chat" / "photo" / "location" / "payment" / "timestamp"
    description: str = ""
    content: str = ""              # 证据内容或IPFS哈希
    submitted_by: str = ""         # 提交者节点ID
    submitted_at: datetime = field(default_factory=datetime.now)

    verified: bool = False
    verified_by: List[str] = field(default_factory=list)


@dataclass
class ArbitratorVote:
    """仲裁员投票"""
    arbitrator_id: str = ""
    vote: str = ""                 # "buyer" / "seller" / "reject"
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Dispute:
    """争议记录"""
    dispute_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    trade_id: str = ""

    # 争议方
    complainant_id: str = ""       # 投诉方
    respondent_id: str = ""        # 被投诉方

    # 原因
    reason: str = ""
    category: str = ""            # "quality" / "non_delivery" / "fraud" / "other"

    # 仲裁员
    arbitrators: List[str] = field(default_factory=list)  # 5个仲裁员节点ID
    votes: List[ArbitratorVote] = field(default_factory=list)

    # 证据
    evidence: List[DisputeEvidence] = field(default_factory=list)

    # 裁决
    verdict: str = ""              # "buyer_wins" / "seller_wins" / "rejected"
    verdict_reason: str = ""
    decided_at: Optional[datetime] = None

    # 执行
    executed: bool = False
    execution_details: Dict[str, Any] = field(default_factory=dict)

    # 状态
    status: str = "open"           # "open" / "voting" / "decided" / "executed"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dispute_id": self.dispute_id,
            "trade_id": self.trade_id,
            "complainant_id": self.complainant_id,
            "respondent_id": self.respondent_id,
            "reason": self.reason,
            "category": self.category,
            "arbitrators": self.arbitrators,
            "votes": [v.__dict__ for v in self.votes],
            "evidence": [e.__dict__ for e in self.evidence],
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "executed": self.executed,
            "execution_details": self.execution_details,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# 消息相关模型
# ============================================================================

class MessageType(Enum):
    """消息类型"""
    DISCOVERY = "discovery"         # 商品发现广播
    PRODUCT_QUERY = "product_query" # 商品查询
    TRADE_REQUEST = "trade_request" # 交易请求
    CHAT = "chat"                   # 聊天消息
    TRADE_UPDATE = "trade_update"   # 交易状态更新
    REPUTATION = "reputation"       # 信誉事件广播
    ARBITRATION = "arbitration"     # 仲裁消息
    HEARTBEAT = "heartbeat"         # 心跳检测
    RELAY = "relay"                 # 中继消息


@dataclass
class NetworkMessage:
    """网络消息"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    msg_type: MessageType = MessageType.CHAT

    # 发送者和接收者
    sender_id: str = ""
    sender_name: str = ""
    receiver_id: Optional[str] = None  # None表示广播

    # 中继信息
    relay_nodes: List[str] = field(default_factory=list)  # 经过的节点ID列表
    ttl: int = 3                       # 生存时间
    hop_count: int = 0                 # 跳数

    # 内容
    payload: Dict[str, Any] = field(default_factory=dict)

    # 加密
    encrypted: bool = False
    signature: str = ""

    # 时间戳
    timestamp: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None

    def to_bytes(self) -> bytes:
        """序列化为字节"""
        data = {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "receiver_id": self.receiver_id,
            "relay_nodes": self.relay_nodes,
            "ttl": self.ttl,
            "hop_count": self.hop_count,
            "payload": self.payload,
            "encrypted": self.encrypted,
            "signature": self.signature,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }
        return json.dumps(data, ensure_ascii=False).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> 'NetworkMessage':
        """从字节反序列化"""
        obj = json.loads(data.decode("utf-8"))
        return cls(
            msg_id=obj["msg_id"],
            msg_type=MessageType(obj["msg_type"]),
            sender_id=obj["sender_id"],
            sender_name=obj["sender_name"],
            receiver_id=obj.get("receiver_id"),
            relay_nodes=obj.get("relay_nodes", []),
            ttl=obj.get("ttl", 3),
            hop_count=obj.get("hop_count", 0),
            payload=obj.get("payload", {}),
            encrypted=obj.get("encrypted", False),
            signature=obj.get("signature", ""),
            timestamp=datetime.fromisoformat(obj["timestamp"]) if obj.get("timestamp") else datetime.now(),
            expires_at=datetime.fromisoformat(obj["expires_at"]) if obj.get("expires_at") else None
        )


# ============================================================================
# DHT 相关模型
# ============================================================================

@dataclass
class DHTEntry:
    """DHT条目"""
    key: str = ""
    value: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    publisher_id: str = ""          # 发布者节点ID
    publisher_rep: int = 100        # 发布者信誉

    # 生命周期
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    version: int = 1

    # 复制
    replica_nodes: List[str] = field(default_factory=list)  # 备份节点ID列表
    replica_count: int = 0

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


@dataclass
class ProductIndex:
    """商品索引（DHT存储结构）"""
    product_id: str = ""

    # 索引键
    geohash_prefix: str = ""        # 地理位置前缀
    category: str = ""              # 分类
    price_range: str = ""           # 价格区间
    seller_rep_min: int = 0         # 最低信誉

    # 索引值（摘要）
    title: str = ""
    price: float = 0.0
    location: str = ""             # geohash
    seller_id: str = ""
    seller_rep: int = 100

    # 节点信息
    storage_node_id: str = ""      # 存储完整信息的节点
    update_node_ids: List[str] = field(default_factory=list)  # 可更新信息的节点

    def match_query(self, query: Dict[str, Any]) -> float:
        """计算匹配度"""
        score = 0.0

        if "geohash_prefix" in query and self.geohash_prefix.startswith(query["geohash_prefix"][:4]):
            score += 0.3

        if "category" in query and self.category == query["category"]:
            score += 0.2

        if "price_max" in query and self.price <= query["price_max"]:
            score += 0.2

        if "seller_rep_min" in query and self.seller_rep >= query["seller_rep_min"]:
            score += 0.3

        return score
