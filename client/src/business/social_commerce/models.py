# core/social_commerce/models.py
# 社交化撮合引擎 - 核心数据模型
#
# 从"人找货"到"货找人"的智能交易网络
# 核心概念：意图雷达、时空引力、AI破冰、去中心化信用

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
import uuid
import hashlib
import json


# ========== 枚举定义 ==========

class NodeType(Enum):
    """节点类型"""
    BUYER = "buyer"           # 买家
    SELLER = "seller"         # 卖家
    BOTH = "both"             # 兼有 (工贸一体)
    SERVICE = "service"       # 服务商 (物流/质检)


class IntentLevel(Enum):
    """意图强度"""
    NONE = "none"             # 无意图
    BROWSING = "browsing"     # 浏览中
    COMPARING = "comparing"   # 比价中
    READY = "ready"           # 准备交易
    URGENT = "urgent"         # 急需


class MatchStrength(Enum):
    """匹配强度"""
    NONE = "none"
    WEAK = "weak"             # 弱匹配
    MEDIUM = "medium"         # 中匹配
    STRONG = "strong"         # 强匹配
    PERFECT = "perfect"       # 完美匹配


class GeoPrecision(Enum):
    """地理精度"""
    EXACT = "exact"           # 精确坐标
    NEIGHBORHOOD = "neighborhood"  # 模糊区域 (GeoHash 6位)
    DISTRICT = "district"      # 区县 (GeoHash 5位)
    CITY = "city"             # 城市 (GeoHash 4位)


class TradeStatus(Enum):
    """交易状态"""
    PROPOSED = "proposed"      # 已提议
    NEGOTIATING = "negotiating"  # 协商中
    AGREED = "agreed"         # 已达成
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"    # 已完成
    CANCELLED = "cancelled"   # 已取消


class CreditAction(Enum):
    """信用行为"""
    LISTING = "listing"        # 上架商品
    VIEWING = "viewing"        # 查看商品
    INQUIRY = "inquiry"        # 询价
    NEGOTIATION = "negotiation"  # 协商
    DEAL = "deal"              # 成交
    RATING = "rating"          # 评价
    REFERRAL = "referral"      # 推荐


# ========== GeoHash 工具 ==========

class GeoHash:
    """GeoHash 编码器 (简化版)"""

    BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

    @classmethod
    def encode(cls, lat: float, lon: float, precision: int = 6) -> str:
        """将经纬度编码为 GeoHash"""
        lat_range, lon_range = (-90.0, 90.0), (-180.0, 180.0)
        hash_bits = []
        is_lon = True
        bit = 0
        ch = 0

        while len(hash_bits) < precision * 5:
            if is_lon:
                mid = (lon_range[0] + lon_range[1]) / 2
                if lon >= mid:
                    hash_bits.append(1)
                    lon_range = (mid, lon_range[1])
                else:
                    hash_bits.append(0)
                    lon_range = (lon_range[0], mid)
                is_lon = False
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if lat >= mid:
                    hash_bits.append(1)
                    lat_range = (mid, lat_range[1])
                else:
                    hash_bits.append(0)
                    lat_range = (lat_range[0], mid)
                is_lon = True

            bit += 1
            if bit == 5:
                idx = 0
                for i in range(5):
                    idx = idx * 2 + hash_bits[-(5 - i)]
                hash_bits.append(idx) if idx < 32 else None
                bit = 0

        return "".join(cls.BASE32[i] for i in hash_bits[-precision * 5:])

    @classmethod
    def neighbors(cls, geohash: str) -> List[str]:
        """获取相邻的 GeoHash (简化)"""
        # 简化实现，返回同前缀的变体
        return [geohash[:-1] + c for c in cls.BASE32 if c != geohash[-1]][:8]


# ========== 节点画像 ==========

@dataclass
class NodeProfile:
    """节点画像 - 基于行为的交易意愿标签"""

    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    user_id: str = ""

    # 基础信息
    name: str = ""
    avatar_url: Optional[str] = None
    node_type: NodeType = NodeType.BUYER

    # 行为信号
    search_history: List[str] = field(default_factory=list)      # 搜索词
    view_history: List[str] = field(default_factory=list)        # 查看的商品ID
    inquiry_count: int = 0                                        # 询价次数
    compare_count: int = 0                                         # 比价次数

    # 意图分析
    intent_level: IntentLevel = IntentLevel.NONE
    intent_tags: List[str] = field(default_factory=list)          # ["B端潜力", "跨境", "工贸一体"]
    intent_keywords: List[str] = field(default_factory=list)      # 意图关键词

    # 交易历史
    total_deals: int = 0
    category_expertise: Dict[str, int] = field(default_factory=dict)  # 品类专长
    buyer_rating: float = 0.0
    seller_rating: float = 0.0

    # 时间特征
    active_hours: Set[int] = field(default_factory=set)           # 活跃小时 (0-23)
    timezone: str = "Asia/Shanghai"

    # 信用
    credit_score: float = 50.0                                    # 信用分 0-100
    credit_history: List[str] = field(default_factory=list)        # 信用事件哈希

    # 关联
    related_nodes: List[str] = field(default_factory=list)       # 关联节点ID
    trusted_by: List[str] = field(default_factory=list)           # 信任该节点

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    last_active_at: float = field(default_factory=lambda: datetime.now().timestamp())

    def update_intent(self, action: str, keywords: List[str]):
        """更新意图"""
        self.intent_keywords.extend(keywords)
        self.intent_keywords = list(set(self.intent_keywords))[-50:]  # 保留最近50个

        # 更新意图强度
        if action == "search":
            self.inquiry_count += 1
            if self.inquiry_count >= 5:
                self.intent_level = IntentLevel.READY
        elif action == "compare":
            self.compare_count += 1
            if self.compare_count >= 3:
                self.intent_level = max(self.intent_level, IntentLevel.COMPARING)
        elif action == "view":
            if self.intent_level == IntentLevel.NONE:
                self.intent_level = IntentLevel.BROWSING

        self.last_active_at = datetime.now().timestamp()

    def add_tag(self, tag: str):
        """添加标签"""
        if tag not in self.intent_tags:
            self.intent_tags.append(tag)

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "user_id": self.user_id,
            "name": self.name,
            "node_type": self.node_type.value,
            "intent_level": self.intent_level.value,
            "intent_tags": self.intent_tags,
            "intent_keywords": self.intent_keywords,
            "total_deals": self.total_deals,
            "credit_score": self.credit_score,
            "last_active_at": self.last_active_at,
        }


# ========== 地理位置 ==========

@dataclass
class GeoLocation:
    """地理位置 (模糊化)"""

    latitude: float = 0.0
    longitude: float = 0.0
    precision: GeoPrecision = GeoPrecision.CITY

    # GeoHash 表示
    geohash: str = ""

    # 可交易时段
    available_hours: Set[int] = field(default_factory=set)       # 可交易小时
    is_traveling: bool = False                                    # 是否出差中
    travel_destination: Optional[str] = None                     # 目的地 GeoHash

    @classmethod
    def from_coords(cls, lat: float, lon: float, precision: GeoPrecision = GeoPrecision.NEIGHBORHOOD):
        """从坐标创建"""
        p = 6 if precision == GeoPrecision.NEIGHBORHOOD else (5 if precision == GeoPrecision.DISTRICT else 4)
        geohash = GeoHash.encode(lat, lon, p)
        return cls(
            latitude=lat,
            longitude=lon,
            precision=precision,
            geohash=geohash,
        )

    def distance_to(self, other: "GeoLocation") -> float:
        """计算模糊距离 (基于 GeoHash 前缀匹配)"""
        if not self.geohash or not other.geohash:
            return float("inf")

        # 计算前缀匹配长度
        match_len = 0
        for a, b in zip(self.geohash, other.geohash):
            if a == b:
                match_len += 1
            else:
                break

        # 匹配长度越短，距离越远
        max_len = max(len(self.geohash), len(other.geohash))
        return (max_len - match_len) / max_len

    def can_trade_with(self, other: "GeoLocation", hour: int) -> bool:
        """检查是否可以在指定小时交易"""
        if hour not in self.available_hours or hour not in other.available_hours:
            return False

        # 检查地理距离
        if self.distance_to(other) > 0.3:  # 约30km
            return False

        return True


# ========== 匹配候选 ==========

@dataclass
class MatchCandidate:
    """匹配候选"""

    candidate_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    buyer_id: str = ""
    seller_id: str = ""

    # 匹配信息
    match_strength: MatchStrength = MatchStrength.NONE
    match_reasons: List[str] = field(default_factory=list)

    # 商品匹配
    buyer_wants: List[str] = field(default_factory=list)         # 买家想要的商品
    seller_offers: List[str] = field(default_factory=list)       # 卖家提供的商品

    # 互补性
    is上下游: bool = False                                        # 上下游关系
    is同行: bool = False                                          # 同行竞争
    is拼单: bool = False                                          # 可拼单

    # 地理
    buyer_location: Optional[GeoLocation] = None
    seller_location: Optional[GeoLocation] = None
    geo_score: float = 0.0                                       # 地理匹配分

    # 时间
    time_score: float = 0.0                                      # 时间匹配分

    # AI 破冰
    icebreaker_message: Optional[str] = None
    icebreaker_type: Optional[str] = None                         # "same_search"/"supply_chain"/"location_nearby"

    # 状态
    status: TradeStatus = TradeStatus.PROPOSED
    proposed_at: float = field(default_factory=lambda: datetime.now().timestamp())
    responded_at: Optional[float] = None

    def compute_match_score(self) -> float:
        """计算综合匹配分"""
        strength_weights = {
            MatchStrength.NONE: 0,
            MatchStrength.WEAK: 0.2,
            MatchStrength.MEDIUM: 0.5,
            MatchStrength.STRONG: 0.8,
            MatchStrength.PERFECT: 1.0,
        }

        score = strength_weights.get(self.match_strength, 0) * 0.4
        score += self.geo_score * 0.3
        score += self.time_score * 0.2

        if self.is上下游:
            score += 0.1

        return min(score, 1.0)


# ========== 信用凭证 ==========

@dataclass
class CreditCredential:
    """信用凭证 - 链式评价"""

    credential_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    from_node: str = ""
    to_node: str = ""

    # 交易
    deal_id: Optional[str] = None
    deal_category: Optional[str] = None
    deal_amount: int = 0  # 分

    # 评价
    rating: float = 0.0  # 1-5
    comment: str = ""
    tags: List[str] = field(default_factory=list)               # ["准时", "货真价实"]

    # 链式引用
    previous_credential: Optional[str] = None                    # 前一个凭证哈希
    credential_hash: str = ""

    # 验证
    is_verified: bool = False
    verified_by: List[str] = field(default_factory=list)         # 验证者

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())

    def compute_hash(self) -> str:
        """计算凭证哈希"""
        data = {
            "from": self.from_node,
            "to": self.to_node,
            "deal_id": self.deal_id,
            "rating": self.rating,
            "previous": self.previous_credential or "",
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


# ========== AI 破冰消息 ==========

@dataclass
class IcebreakerMessage:
    """AI 破冰消息"""

    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # 场景
    scene_type: str = ""                                          # "same_search"/"上下游"/"nearby"
    buyer_id: str = ""
    seller_id: str = ""

    # 消息内容
    intro_message: str = ""                                        # AI 生成的开场白
    shared_context: str = ""                                      # 共同语境

    # 状态
    sent_at: Optional[float] = None
    buyer_read: bool = False
    seller_read: bool = False
    buyer_accepted: bool = False
    seller_accepted: bool = False

    # 交换的信息
    shared_listings: List[str] = field(default_factory=list)      # 交换的商品ID
    contact_exchanged: bool = False                              # 是否已交换联系方式

    def can_exchange_contact(self) -> bool:
        """检查是否可以交换联系方式"""
        return self.buyer_accepted and self.seller_accepted


# ========== 撮合会话 ==========

@dataclass
class MatchSession:
    """撮合会话"""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # 参与者
    initiator_id: str = ""
    recipient_id: str = ""

    # 匹配候选
    candidate: Optional[MatchCandidate] = None

    # 破冰
    icebreaker: Optional[IcebreakerMessage] = None

    # 协商
    buyer_offer: Optional[int] = None                              # 买家出价 (分)
    seller_counter: Optional[int] = None                          # 卖家还价 (分)

    # 状态
    status: TradeStatus = TradeStatus.PROPOSED

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    expires_at: float = field(default_factory=lambda: (datetime.now() + timedelta(hours=24)).timestamp())


# ========== 碎片产能节点 ==========

@dataclass
class ProductionNode:
    """碎片产能节点 - 闲散生产力变现"""

    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # 产能类型
    capability_type: str = ""                                       # "3d_print"/"delivery"/"storage"
    capability_detail: str = ""                                   # 具体能力描述

    # 可用时间
    available_slots: List[Dict[str, Any]] = field(default_factory=list)  # [{"date": "2026-04-20", "hours": [9, 10, 11]}]

    # 地理位置
    location: Optional[GeoLocation] = None

    # 评分
    rating: float = 0.0
    completed_orders: int = 0

    # 状态
    is_available: bool = True


@dataclass
class FragmentedOrder:
    """碎片化订单 - 小订单分布式生产"""

    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # 原始需求
    original_requirement: str = ""
    total_quantity: int = 0
    deadline: Optional[float] = None

    # 拆分方案
    fragments: List[Dict[str, Any]] = field(default_factory=list)  # [{"node_id": "xxx", "quantity": 20}]

    # 状态
    status: str = "pending"                                        # pending/splitting/in_progress/completed

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())


# ========== 意图信号 ==========

@dataclass
class IntentSignal:
    """意图信号 - 用于意图雷达分析"""

    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    node_id: str = ""

    # 信号类型
    signal_type: str = ""                                          # "search"/"view"/"inquiry"/"compare"/"deal"
    signal_data: Dict[str, Any] = field(default_factory=dict)       # 原始数据

    # 提取的意图
    extracted_keywords: List[str] = field(default_factory=list)
    inferred_tags: List[str] = field(default_factory=list)        # 推断的标签

    # 置信度
    confidence: float = 0.0                                        # 0-1

    # 时间
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    def is_b2b_signal(self) -> bool:
        """判断是否 B 端信号"""
        b2b_keywords = ["批发", "货源", "工厂", "经销", "代理", "报关", "样品", "MOQ", "批量"]
        return any(k in str(self.signal_data) for k in b2b_keywords)

    def is_crossborder_signal(self) -> bool:
        """判断是否跨境信号"""
        cb_keywords = ["进口", "出口", "海关", "清关", "外贸", "跨境", "退税", "柜"]
        return any(k in str(self.signal_data) for k in cb_keywords)