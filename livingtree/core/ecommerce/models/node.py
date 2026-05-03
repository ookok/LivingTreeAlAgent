"""
统一节点/用户模型

合并自:
- local_market/models.py NodeInfo (网络+信誉+社交)
- social_commerce/models.py NodeProfile (意图+行为+信用)
- decommerce/models.py Seller (连接能力+AI服务)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set
from datetime import datetime
import uuid

from .enums import NodeRole, IntentLevel, ConnectionQuality
from .location import GeoLocation


@dataclass
class Node:
    """统一节点档案 — 合并 NodeInfo + NodeProfile + Seller"""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    user_id: str = ""

    # 基础信息
    name: str = ""
    avatar_url: Optional[str] = None
    bio: str = ""
    role: NodeRole = NodeRole.BUYER

    # --- 网络信息（来自 NodeInfo）---
    ip: str = ""
    port: int = 0
    is_relay: bool = False

    # --- 地理位置（统一 GeoLocation）---
    location: Optional[GeoLocation] = None

    # --- 连接能力（来自 Seller）---
    connectivity: ConnectionQuality = ConnectionQuality.POOR
    ice_servers: List[Dict[str, Any]] = field(default_factory=list)
    public_ip: Optional[str] = None
    nat_type: Optional[str] = None

    # --- AI 服务能力（来自 Seller）---
    has_ai_service: bool = False
    ai_models: List[str] = field(default_factory=list)
    ai_capabilities: List[str] = field(default_factory=list)

    # --- 交易统计（来自 NodeInfo + NodeProfile）---
    total_listings: int = 0
    total_orders: int = 0
    good_reviews: int = 0
    bad_reviews: int = 0

    # --- 信誉信息（统一）---
    reputation: int = 100                        # 0-1000（来自 ReputationManager）
    rating: float = 0.0                          # 0-5（平均评价分）
    credit_score: float = 50.0                   # 0-100（信用分）
    credit_history: List[str] = field(default_factory=list)

    # --- 意图标签（来自 NodeProfile）---
    intent_level: IntentLevel = IntentLevel.NONE
    intent_tags: List[str] = field(default_factory=list)
    intent_keywords: List[str] = field(default_factory=list)
    search_history: List[str] = field(default_factory=list)
    view_history: List[str] = field(default_factory=list)
    inquiry_count: int = 0
    compare_count: int = 0

    # --- 品类专长（来自 NodeProfile）---
    category_expertise: Dict[str, int] = field(default_factory=dict)

    # --- 时间特征（来自 NodeProfile + NodeInfo）---
    active_hours: Set[int] = field(default_factory=set)
    timezone: str = "Asia/Shanghai"

    # --- 社交关系（来自 NodeInfo）---
    trusted_nodes: List[str] = field(default_factory=list)
    blocked_nodes: List[str] = field(default_factory=list)
    related_nodes: List[str] = field(default_factory=list)
    trusted_by: List[str] = field(default_factory=list)

    # --- 状态 ---
    is_online: bool = False

    # --- 时间戳 ---
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    last_active_at: float = field(default_factory=lambda: datetime.now().timestamp())
    last_seen_at: float = field(default_factory=lambda: datetime.now().timestamp())

    # --- 元数据 ---
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ========================================================================
    # 意图更新（从 NodeProfile 合并）
    # ========================================================================

    def update_intent(self, action: str, keywords: List[str]) -> None:
        """更新意图信号"""
        self.intent_keywords.extend(keywords)
        self.intent_keywords = list(set(self.intent_keywords))[-50:]

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

    def add_intent_tag(self, tag: str) -> None:
        if tag not in self.intent_tags:
            self.intent_tags.append(tag)

    # ========================================================================
    # 信任管理（从 NodeInfo 合并）
    # ========================================================================

    def trust(self, node_id: str) -> None:
        if node_id not in self.trusted_nodes:
            self.trusted_nodes.append(node_id)

    def untrust(self, node_id: str) -> None:
        if node_id in self.trusted_nodes:
            self.trusted_nodes.remove(node_id)

    def block(self, node_id: str) -> None:
        if node_id not in self.blocked_nodes:
            self.blocked_nodes.append(node_id)
        self.untrust(node_id)

    def unblock(self, node_id: str) -> None:
        if node_id in self.blocked_nodes:
            self.blocked_nodes.remove(node_id)

    # ========================================================================
    # 信誉值计算
    # ========================================================================

    @property
    def reputation_level(self) -> str:
        """信誉等级（SSS → F）"""
        thresholds = [
            (900, "SSS"), (800, "SS"), (700, "S"),
            (600, "AAA"), (500, "AA"), (400, "A"),
            (300, "B"), (200, "C"), (100, "D"), (0, "F"),
        ]
        for threshold, level in thresholds:
            if self.reputation >= threshold:
                return level
        return "F"

    @property
    def is_verified(self) -> bool:
        """是否通过信誉验证"""
        return self.reputation >= 200 and self.credit_score >= 30.0

    # ========================================================================
    # 序列化
    # ========================================================================

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "user_id": self.user_id,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "role": self.role.value,
            "ip": self.ip,
            "port": self.port,
            "is_relay": self.is_relay,
            "location": self.location.to_dict() if self.location else None,
            "connectivity": self.connectivity.value,
            "public_ip": self.public_ip,
            "nat_type": self.nat_type,
            "has_ai_service": self.has_ai_service,
            "ai_models": self.ai_models,
            "ai_capabilities": self.ai_capabilities,
            "total_listings": self.total_listings,
            "total_orders": self.total_orders,
            "good_reviews": self.good_reviews,
            "bad_reviews": self.bad_reviews,
            "reputation": self.reputation,
            "rating": self.rating,
            "credit_score": self.credit_score,
            "intent_level": self.intent_level.value,
            "intent_tags": self.intent_tags,
            "intent_keywords": self.intent_keywords[-20:],
            "category_expertise": self.category_expertise,
            "active_hours": sorted(self.active_hours),
            "trusted_nodes": self.trusted_nodes,
            "blocked_nodes": self.blocked_nodes,
            "related_nodes": self.related_nodes,
            "is_online": self.is_online,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_active_at": self.last_active_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Node:
        location = None
        if data.get("location"):
            location = GeoLocation.from_dict(data["location"])

        return cls(
            node_id=data.get("node_id", ""),
            user_id=data.get("user_id", ""),
            name=data.get("name", ""),
            avatar_url=data.get("avatar_url"),
            bio=data.get("bio", ""),
            role=NodeRole(data.get("role", "buyer")),
            ip=data.get("ip", ""),
            port=data.get("port", 0),
            is_relay=data.get("is_relay", False),
            location=location,
            connectivity=ConnectionQuality(data.get("connectivity", "poor")),
            public_ip=data.get("public_ip"),
            nat_type=data.get("nat_type"),
            has_ai_service=data.get("has_ai_service", False),
            ai_models=data.get("ai_models", []),
            ai_capabilities=data.get("ai_capabilities", []),
            total_listings=data.get("total_listings", 0),
            total_orders=data.get("total_orders", 0),
            good_reviews=data.get("good_reviews", 0),
            bad_reviews=data.get("bad_reviews", 0),
            reputation=data.get("reputation", 100),
            rating=data.get("rating", 0.0),
            credit_score=data.get("credit_score", 50.0),
            credit_history=data.get("credit_history", []),
            intent_level=IntentLevel(data.get("intent_level", "none")),
            intent_tags=data.get("intent_tags", []),
            intent_keywords=data.get("intent_keywords", []),
            search_history=data.get("search_history", []),
            view_history=data.get("view_history", []),
            inquiry_count=data.get("inquiry_count", 0),
            compare_count=data.get("compare_count", 0),
            category_expertise=data.get("category_expertise", {}),
            active_hours=set(data.get("active_hours", [])),
            timezone=data.get("timezone", "Asia/Shanghai"),
            trusted_nodes=data.get("trusted_nodes", []),
            blocked_nodes=data.get("blocked_nodes", []),
            related_nodes=data.get("related_nodes", []),
            trusted_by=data.get("trusted_by", []),
            is_online=data.get("is_online", False),
            created_at=data.get("created_at", datetime.now().timestamp()),
            updated_at=data.get("updated_at", datetime.now().timestamp()),
            last_active_at=data.get("last_active_at", datetime.now().timestamp()),
            last_seen_at=data.get("last_seen_at", datetime.now().timestamp()),
            metadata=data.get("metadata", {}),
        )
