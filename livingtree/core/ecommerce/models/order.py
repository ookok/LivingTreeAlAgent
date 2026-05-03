"""
统一订单/交易模型

合并自:
- local_market/models.py Trade + TradeParticipant + EscrowInfo + DeliveryInfo
- decommerce/models.py Order + ServiceSession
- flash_listing/models.py InlinePurchase + FulfillmentRecord
- decommerce/crdt_order.py OrderStateCRDT (CRDT 状态同步)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import hashlib
import json

from .enums import (
    OrderStatus, PaymentMethod, DeliveryMethod, MessageType
)
from .location import GeoLocation
from .listing import Listing, P2PEndpoint


# ============================================================================
# 参与者
# ============================================================================

@dataclass
class Participant:
    """交易参与者"""
    node_id: str = ""
    node_name: str = ""
    role: str = "buyer"              # "buyer" / "seller" / "witness"
    reputation: int = 100
    location: Optional[GeoLocation] = None


# ============================================================================
# 托管
# ============================================================================

@dataclass
class Escrow:
    """支付托管信息"""
    escrow_address: str = ""
    amount: float = 0.0
    currency: str = "CNY"
    witnesses: List[str] = field(default_factory=list)
    required_signatures: int = 2
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    released_at: Optional[float] = None

    @property
    def is_released(self) -> bool:
        return self.released_at is not None


# ============================================================================
# 交付
# ============================================================================

@dataclass
class Delivery:
    """交付信息"""
    method: DeliveryMethod = DeliveryMethod.PICKUP
    pickup_code: str = ""
    delivery_code: str = ""
    pickup_location: Optional[GeoLocation] = None
    delivery_address: str = ""
    pickup_time_start: Optional[float] = None
    pickup_time_end: Optional[float] = None
    delivery_node_id: Optional[str] = None
    delivery_route: List[GeoLocation] = field(default_factory=list)
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None


# ============================================================================
# 履约记录
# ============================================================================

@dataclass
class Fulfillment:
    """履约记录（合并 flash_listing FulfillmentRecord）"""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    status: str = "pending"
    buyer_confirmed: bool = False
    confirmed_at: Optional[float] = None
    auto_confirm_hours: int = 72
    buyer_rating: Optional[float] = None
    buyer_comment: Optional[str] = None
    buyer_tags: List[str] = field(default_factory=list)
    seller_rating: Optional[float] = None
    seller_comment: Optional[str] = None
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_credential_dict(self) -> dict:
        return {
            "deal_id": self.record_id,
            "rating": self.buyer_rating or 0,
            "comment": self.buyer_comment or "",
            "tags": self.buyer_tags,
            "timestamp": self.confirmed_at or datetime.now().timestamp(),
        }


# ============================================================================
# 服务会话（WebRTC 实时服务）
# ============================================================================

@dataclass
class ServiceSession:
    """实时服务会话（来自 decommerce ServiceSession）"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    listing_id: str = ""
    seller_id: str = ""
    buyer_id: str = ""
    room_id: str = ""
    room_password: str = ""
    buyer_endpoint: Optional[P2PEndpoint] = None
    seller_endpoint: Optional[P2PEndpoint] = None
    seller_sdp_offer: Optional[str] = None
    buyer_sdp_answer: Optional[str] = None
    status: str = "pending"
    billing_start: Optional[float] = None
    billing_end: Optional[float] = None
    billing_duration_seconds: int = 0
    billing_amount: float = 0.0
    access_token: str = ""
    token_expires_at: float = 0.0
    last_heartbeat_seller: float = 0.0
    last_heartbeat_buyer: float = 0.0
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())


# ============================================================================
# 统一 Order
# ============================================================================

@dataclass
class Order:
    """统一订单/交易记录
    
    合并 Trade + Order + InlinePurchase + OrderStateCRDT。
    
    生命周期: INITIATED → NEGOTIATING → AGREED → PENDING_PAYMENT → PAID/ESCROW
              → PENDING_SHIPMENT → SHIPPED/DELIVERING → CONFIRMED → COMPLETED
              
    争议路径: 任意阶段 → DISPUTED → COMPLETED/REFUNDED
    取消路径: 任意阶段 → CANCELLED → REFUNDED
    """
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    listing_id: str = ""

    # --- 商品快照（冗余存储）---
    product_title: str = ""
    product_image: Optional[str] = None
    product_link: str = ""

    # --- 参与者 ---
    buyer: Optional[Participant] = None
    seller: Optional[Participant] = None
    witnesses: List[Participant] = field(default_factory=list)

    # --- 价格 ---
    listed_price: float = 0.0          # 标价
    negotiated_price: float = 0.0      # 协商价
    final_price: float = 0.0           # 最终成交价
    discount: float = 0.0              # 折扣额
    currency: str = "CNY"

    # --- 支付 ---
    payment_method: PaymentMethod = PaymentMethod.DIRECT
    payment_id: str = ""
    payment_proof: str = ""
    escrow: Optional[Escrow] = None

    # --- 交付 ---
    delivery: Optional[Delivery] = None
    fulfillment: Optional[Fulfillment] = None

    # --- 服务会话（可选）---
    session: Optional[ServiceSession] = None

    # --- CRDT 状态（去中心化同步）---
    crdt_version: Dict[str, float] = field(default_factory=dict)   # node_id → timestamp
    frozen_amount: float = 0.0

    # --- 状态 ---
    status: OrderStatus = OrderStatus.INITIATED
    dispute_id: Optional[str] = None
    dispute_reason: str = ""
    cancel_reason: str = ""

    # --- 证据 ---
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    order_hash: str = ""

    # --- 评价 ---
    buyer_review: Optional[Dict[str, Any]] = None
    seller_review: Optional[Dict[str, Any]] = None

    # --- 时间戳 ---
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    negotiated_at: Optional[float] = None
    paid_at: Optional[float] = None
    shipped_at: Optional[float] = None
    delivered_at: Optional[float] = None
    confirmed_at: Optional[float] = None
    completed_at: Optional[float] = None
    cancelled_at: Optional[float] = None
    refunded_at: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    # ========================================================================
    # 状态判断
    # ========================================================================

    @property
    def is_paid(self) -> bool:
        return self.status in (
            OrderStatus.PAID, OrderStatus.ESCROW, OrderStatus.PENDING_SHIPMENT,
            OrderStatus.SHIPPED, OrderStatus.DELIVERING, OrderStatus.CONFIRMED,
            OrderStatus.COMPLETED,
        )

    @property
    def is_completed(self) -> bool:
        return self.status == OrderStatus.COMPLETED

    @property
    def is_cancelled(self) -> bool:
        return self.status in (OrderStatus.CANCELLED, OrderStatus.REFUNDED)

    @property
    def is_disputed(self) -> bool:
        return self.status == OrderStatus.DISPUTED

    @property
    def buyer_id(self) -> str:
        return self.buyer.node_id if self.buyer else ""

    @property
    def seller_id(self) -> str:
        return self.seller.node_id if self.seller else ""

    # ========================================================================
    # 状态转换
    # ========================================================================

    def negotiate(self, price: float) -> bool:
        if self.status != OrderStatus.INITIATED:
            return False
        self.negotiated_price = price
        self.status = OrderStatus.NEGOTIATING
        self.negotiated_at = datetime.now().timestamp()
        return True

    def agree(self) -> bool:
        if self.status not in (OrderStatus.INITIATED, OrderStatus.NEGOTIATING):
            return False
        self.final_price = self.negotiated_price or self.listed_price
        self.status = OrderStatus.AGREED
        return True

    def pay(self, payment_id: str = "", proof: str = "") -> bool:
        if self.status not in (OrderStatus.AGREED, OrderStatus.PENDING_PAYMENT):
            return False
        self.payment_id = payment_id
        self.payment_proof = proof
        if self.payment_method in (PaymentMethod.ESCROW, PaymentMethod.ESCROW_2OF3):
            self.status = OrderStatus.ESCROW
        else:
            self.status = OrderStatus.PAID
        self.paid_at = datetime.now().timestamp()
        return True

    def ship(self, tracking_number: str = "", carrier: str = "") -> bool:
        if not self.is_paid:
            return False
        self.status = OrderStatus.SHIPPED
        self.shipped_at = datetime.now().timestamp()
        if self.fulfillment:
            self.fulfillment.tracking_number = tracking_number
            self.fulfillment.carrier = carrier
            self.fulfillment.status = "shipped"
        return True

    def confirm(self) -> bool:
        if self.status not in (OrderStatus.SHIPPED, OrderStatus.DELIVERING):
            return False
        self.status = OrderStatus.CONFIRMED
        self.confirmed_at = datetime.now().timestamp()
        return True

    def complete(self) -> bool:
        if self.status not in (OrderStatus.CONFIRMED, OrderStatus.PAID):
            return False
        self.status = OrderStatus.COMPLETED
        self.completed_at = datetime.now().timestamp()
        return True

    def cancel(self, reason: str = "") -> bool:
        if self.is_completed or self.is_cancelled:
            return False
        self.status = OrderStatus.CANCELLED
        self.cancel_reason = reason
        self.cancelled_at = datetime.now().timestamp()
        return True

    def refund(self) -> bool:
        if self.status not in (OrderStatus.CANCELLED, OrderStatus.DISPUTED):
            return False
        self.status = OrderStatus.REFUNDED
        self.refunded_at = datetime.now().timestamp()
        return True

    def dispute(self, reason: str = "") -> bool:
        if self.is_completed or self.is_cancelled or self.is_disputed:
            return False
        self.status = OrderStatus.DISPUTED
        self.dispute_reason = reason
        return True

    # ========================================================================
    # 哈希
    # ========================================================================

    def compute_hash(self) -> str:
        data = {
            "order_id": self.order_id,
            "listing_id": self.listing_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "final_price": self.final_price,
            "status": self.status.value,
            "created_at": self.created_at,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:24]

    # ========================================================================
    # 序列化
    # ========================================================================

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "listing_id": self.listing_id,
            "product_title": self.product_title,
            "product_image": self.product_image,
            "product_link": self.product_link,
            "buyer": {"node_id": self.buyer.node_id, "node_name": self.buyer.node_name,
                       "role": self.buyer.role, "reputation": self.buyer.reputation}
            if self.buyer else None,
            "seller": {"node_id": self.seller.node_id, "node_name": self.seller.node_name,
                        "role": self.seller.role, "reputation": self.seller.reputation}
            if self.seller else None,
            "witnesses": [{"node_id": w.node_id, "node_name": w.node_name,
                            "role": w.role, "reputation": w.reputation}
                           for w in self.witnesses],
            "listed_price": self.listed_price,
            "negotiated_price": self.negotiated_price,
            "final_price": self.final_price,
            "discount": self.discount,
            "currency": self.currency,
            "payment_method": self.payment_method.value,
            "payment_id": self.payment_id,
            "payment_proof": self.payment_proof,
            "status": self.status.value,
            "dispute_id": self.dispute_id,
            "dispute_reason": self.dispute_reason,
            "cancel_reason": self.cancel_reason,
            "evidence": self.evidence,
            "order_hash": self.order_hash,
            "buyer_review": self.buyer_review,
            "seller_review": self.seller_review,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "negotiated_at": self.negotiated_at,
            "paid_at": self.paid_at,
            "shipped_at": self.shipped_at,
            "delivered_at": self.delivered_at,
            "confirmed_at": self.confirmed_at,
            "completed_at": self.completed_at,
            "cancelled_at": self.cancelled_at,
            "refunded_at": self.refunded_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Order:
        buyer = None
        if data.get("buyer"):
            b = data["buyer"]
            buyer = Participant(
                node_id=b.get("node_id", ""),
                node_name=b.get("node_name", ""),
                role=b.get("role", "buyer"),
                reputation=b.get("reputation", 100),
            )

        seller = None
        if data.get("seller"):
            s = data["seller"]
            seller = Participant(
                node_id=s.get("node_id", ""),
                node_name=s.get("node_name", ""),
                role=s.get("role", "seller"),
                reputation=s.get("reputation", 100),
            )

        return cls(
            order_id=data.get("order_id", ""),
            listing_id=data.get("listing_id", ""),
            product_title=data.get("product_title", ""),
            product_image=data.get("product_image"),
            product_link=data.get("product_link", ""),
            buyer=buyer,
            seller=seller,
            listed_price=data.get("listed_price", 0.0),
            negotiated_price=data.get("negotiated_price", 0.0),
            final_price=data.get("final_price", 0.0),
            discount=data.get("discount", 0.0),
            currency=data.get("currency", "CNY"),
            payment_method=PaymentMethod(data.get("payment_method", "direct")),
            payment_id=data.get("payment_id", ""),
            payment_proof=data.get("payment_proof", ""),
            status=OrderStatus(data.get("status", "initiated")),
            dispute_id=data.get("dispute_id"),
            dispute_reason=data.get("dispute_reason", ""),
            cancel_reason=data.get("cancel_reason", ""),
            evidence=data.get("evidence", []),
            order_hash=data.get("order_hash", ""),
            buyer_review=data.get("buyer_review"),
            seller_review=data.get("seller_review"),
            created_at=data.get("created_at", datetime.now().timestamp()),
            updated_at=data.get("updated_at", datetime.now().timestamp()),
            negotiated_at=data.get("negotiated_at"),
            paid_at=data.get("paid_at"),
            shipped_at=data.get("shipped_at"),
            delivered_at=data.get("delivered_at"),
            confirmed_at=data.get("confirmed_at"),
            completed_at=data.get("completed_at"),
            cancelled_at=data.get("cancelled_at"),
            refunded_at=data.get("refunded_at"),
            metadata=data.get("metadata", {}),
        )
