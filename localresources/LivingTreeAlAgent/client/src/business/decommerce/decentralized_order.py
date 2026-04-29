"""
P2P 去中心化电商 - 去中心化订单协议
Decentralized Order Protocol

密码学保证订单不可抵赖,平台只做见证。

核心设计:
1. 订单握手 (Offer-Accept): 买家签名 → Broker锚定哈希
2. 佣金锁定: 资金托管 → 分段解冻
3. 交付确认: 双向确认 → 自动结算
4. 争议仲裁: 证据链 → 平台仲裁

订单数据结构不上传到Broker,只在买卖双方间传递
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import uuid
import hashlib
import json

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """订单状态"""
    # 初始状态
    CREATED = "created"           # 订单创建
    OFFER_SIGNED = "offer_signed"  # 买家签名
    ACCEPT_SIGNED = "accept_signed"  # 卖家签名

    # 资金状态
    FROZEN = "frozen"           # 资金冻结
    PARTIAL_RELEASE = "partial_release"  # 部分解冻
    RELEASED = "released"       # 全部解冻

    # 最终状态
    COMPLETED = "completed"      # 订单完成
    CANCELLED = "cancelled"     # 已取消
    REFUNDED = "refunded"        # 已退款
    DISPUTED = "disputed"        # 争议中


@dataclass
class OrderOffer:
    """订单报价 (买家发起)"""
    # 订单ID
    order_id: str = ""

    # 商品信息
    listing_id: str = ""
    listing_hash: str = ""  # 商品内容哈希

    # 价格
    price: int = 0  # 分
    currency: str = "CNY"

    # 买家信息
    buyer_id: str = ""
    buyer_nonce: str = ""  # 防重放

    # 签名
    buyer_signature: str = ""  # 买家私钥签名

    # 时间戳
    created_at: float = 0
    expires_at: float = 0  # 报价过期时间

    def compute_hash(self) -> str:
        """计算订单哈希"""
        content = f"{self.order_id}|{self.listing_id}|{self.listing_hash}|{self.price}|{self.currency}|{self.buyer_id}|{self.buyer_nonce}"
        return hashlib.sha256(content.encode()).hexdigest()

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "listing_id": self.listing_id,
            "listing_hash": self.listing_hash,
            "price": self.price,
            "currency": self.currency,
            "buyer_id": self.buyer_id,
            "buyer_nonce": self.buyer_nonce,
            "buyer_signature": self.buyer_signature,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


@dataclass
class OrderAccept:
    """订单接受 (卖家确认)"""
    # 关联的Offer
    order_id: str = ""
    offer_hash: str = ""  # 原Offer哈希

    # 卖家信息
    seller_id: str = ""
    seller_nonce: str = ""
    seller_signature: str = ""

    # Broker锚定
    anchor_hash: str = ""  # Broker锚定的哈希
    anchored_at: float = 0

    # 时间戳
    created_at: float = 0
    expires_at: float = 0  # 接受过期时间 (超时未付款取消)

    def compute_hash(self) -> str:
        """计算接受订单哈希"""
        content = f"{self.order_id}|{self.offer_hash}|{self.seller_id}|{self.seller_nonce}|{self.anchor_hash}"
        return hashlib.sha256(content.encode()).hexdigest()

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "offer_hash": self.offer_hash,
            "seller_id": self.seller_id,
            "seller_nonce": self.seller_nonce,
            "seller_signature": self.seller_signature,
            "anchor_hash": self.anchor_hash,
            "anchored_at": self.anchored_at,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


@dataclass
class DeliveryConfirmation:
    """交付确认 (双向确认)"""
    # 关联订单
    order_id: str = ""

    # 买家确认
    buyer_confirmed: bool = False
    buyer_confirm_hash: str = ""  # 买家确认内容哈希
    buyer_signature: str = ""
    buyer_confirmed_at: float = 0

    # 卖家确认
    seller_confirmed: bool = False
    seller_confirm_hash: str = ""
    seller_signature: str = ""
    seller_confirmed_at: float = 0

    # 最终交付哈希
    final_delivery_hash: str = ""

    def is_fully_confirmed(self) -> bool:
        return self.buyer_confirmed and self.seller_confirmed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "buyer_confirmed": self.buyer_confirmed,
            "buyer_confirm_hash": self.buyer_confirm_hash,
            "buyer_signature": self.buyer_signature,
            "buyer_confirmed_at": self.buyer_confirmed_at,
            "seller_confirmed": self.seller_confirmed,
            "seller_confirm_hash": self.seller_confirm_hash,
            "seller_signature": self.seller_signature,
            "seller_confirmed_at": self.seller_confirmed_at,
            "final_delivery_hash": self.final_delivery_hash,
        }


@dataclass
class TieredRelease:
    """分段解冻配置"""
    # 分段点 (0.0 - 1.0)
    tiers: List[tuple] = field(default_factory=lambda: [
        (0.3, 0.1),  # 30%进度, 解冻10%
        (0.6, 0.4),  # 60%进度, 解冻40%
        (1.0, 1.0),  # 100%完成, 解冻100%
    ])

    def get_release_amount(self, total_amount: int, progress: float) -> int:
        """根据进度计算应解冻金额"""
        release_ratio = 0.0

        for threshold, ratio in self.tiers:
            if progress >= threshold:
                release_ratio = ratio

        return int(total_amount * release_ratio)


@dataclass
class DecentralizedOrder:
    """
    去中心化订单

    不上传完整数据到Broker,只在买卖双方间传递
    """
    # 基础信息
    order_id: str = ""

    # 关联的Offer/Accept
    offer: Optional[OrderOffer] = None
    accept: Optional[OrderAccept] = None
    confirmation: Optional[DeliveryConfirmation] = None

    # 交付方式
    delivery_type: str = "instant"  # instant | scheduled | live | download

    # 物流信息 (实物)
    logistics_info: Dict[str, Any] = field(default_factory=dict)

    # 虚拟交付信息 (虚物)
    virtual_delivery_hash: str = ""  # 交付内容哈希

    # 分段解冻配置
    tiered_release: TieredRelease = field(default_factory=TieredRelease)

    # 当前进度 (0.0 - 1.0)
    progress: float = 0.0

    # 状态
    status: OrderStatus = OrderStatus.CREATED

    # Broker锚定ID
    anchor_id: str = ""

    # 时间戳
    created_at: float = 0
    updated_at: float = 0

    def compute_order_hash(self) -> str:
        """计算订单完整哈希"""
        if not self.offer:
            return ""

        content = f"{self.offer.compute_hash()}"
        if self.accept:
            content += f"|{self.accept.compute_hash()}"
        if self.confirmation:
            content += f"|{self.confirmation.final_delivery_hash}"

        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "delivery_type": self.delivery_type,
            "progress": self.progress,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_broker_anchor(self) -> Dict[str, Any]:
        """生成Broker锚定数据 (不上传完整订单)"""
        return {
            "order_id": self.order_id,
            "anchor_hash": self.compute_order_hash(),
            "buyer_id": self.offer.buyer_id if self.offer else "",
            "seller_id": self.accept.seller_id if self.accept else "",
        }


class DecentralizedOrderProtocol:
    """
    去中心化订单协议管理器

    流程:
    1. Offer: 买家创建订单并签名
    2. Accept: 卖家确认并签名
    3. Anchor: Broker锚定订单哈希
    4. Freeze: 资金冻结
    5. Deliver: 交付 (实物物流/虚物直连)
    6. Confirm: 双向确认
    7. Release: 分段解冻
    8. Complete: 完成
    """

    def __init__(self):
        # 订单存储
        self._orders: Dict[str, DecentralizedOrder] = {}

        # 待处理的Offer/Accept
        self._pending_offers: Dict[str, OrderOffer] = {}
        self._pending_accepts: Dict[str, OrderAccept] = {}

        # 回调
        self._on_order_created: List[Callable] = []
        self._on_order_completed: List[Callable] = []
        self._on_order_disputed: List[Callable] = []

        # Broker集成
        self._broker = None

        logger.info("[DecentralizedOrder] Initialized")

    def set_broker(self, broker) -> None:
        """设置Broker引用"""
        self._broker = broker

    # ==================== Offer阶段 ====================

    def create_offer(
        self,
        listing_id: str,
        listing_hash: str,
        price: int,
        currency: str,
        buyer_id: str,
        private_key: Optional[str] = None,  # 用于签名
    ) -> OrderOffer:
        """创建订单报价 (买家)"""
        order_id = str(uuid.uuid4())[:12]

        offer = OrderOffer(
            order_id=order_id,
            listing_id=listing_id,
            listing_hash=listing_hash,
            price=price,
            currency=currency,
            buyer_id=buyer_id,
            buyer_nonce=self._generate_nonce(),
            created_at=time.time(),
            expires_at=time.time() + 300,  # 5分钟过期
        )

        # 签名
        if private_key:
            offer.buyer_signature = self._sign(offer.compute_hash(), private_key)

        self._pending_offers[order_id] = offer

        # 创建订单
        order = DecentralizedOrder(
            order_id=order_id,
            offer=offer,
            created_at=time.time(),
            updated_at=time.time(),
        )
        self._orders[order_id] = order

        logger.info(f"[DecentralizedOrder] Created offer {order_id}")

        return offer

    async def accept_offer(
        self,
        order_id: str,
        seller_id: str,
        private_key: Optional[str] = None,
    ) -> Optional[OrderAccept]:
        """接受订单报价 (卖家)"""
        offer = self._pending_offers.get(order_id)
        if not offer:
            logger.warning(f"[DecentralizedOrder] Offer not found: {order_id}")
            return None

        if offer.is_expired():
            logger.warning(f"[DecentralizedOrder] Offer expired: {order_id}")
            return None

        # 创建接受
        accept = OrderAccept(
            order_id=order_id,
            offer_hash=offer.compute_hash(),
            seller_id=seller_id,
            seller_nonce=self._generate_nonce(),
            created_at=time.time(),
            expires_at=time.time() + 600,  # 10分钟过期
        )

        # 签名
        if private_key:
            accept.seller_signature = self._sign(accept.compute_hash(), private_key)

        self._pending_accepts[order_id] = accept

        # 更新订单
        order = self._orders.get(order_id)
        if order:
            order.accept = accept
            order.status = OrderStatus.OFFER_SIGNED
            order.updated_at = time.time()

        logger.info(f"[DecentralizedOrder] Accepted offer {order_id}")

        return accept

    # ==================== Anchor阶段 ====================

    async def anchor_order(self, order_id: str) -> Optional[str]:
        """Broker锚定订单哈希"""
        order = self._orders.get(order_id)
        if not order or not order.accept:
            return None

        # 生成锚定数据
        anchor_data = order.to_broker_anchor()

        # 调用Broker锚定
        if self._broker:
            anchor = await self._broker.anchor_order(
                order_id=order_id,
                order_hash=anchor_data["anchor_hash"],
                buyer_id=anchor_data["buyer_id"],
                seller_id=anchor_data["seller_id"],
            )
            order.anchor_id = anchor.order_id if anchor else ""

        # 更新状态
        order.status = OrderStatus.ACCEPT_SIGNED
        order.updated_at = time.time()

        logger.info(f"[DecentralizedOrder] Anchored order {order_id}")

        return order.anchor_id

    # ==================== 资金阶段 ====================

    async def freeze_funds(self, order_id: str) -> bool:
        """冻结资金"""
        order = self._orders.get(order_id)
        if not order:
            return False

        order.status = OrderStatus.FROZEN
        order.updated_at = time.time()

        logger.info(f"[DecentralizedOrder] Froze funds for order {order_id}")
        return True

    async def release_funds(
        self,
        order_id: str,
        progress: Optional[float] = None,
    ) -> int:
        """
        解冻资金 (支持分段)

        Returns:
            解冻金额(分)
        """
        order = self._orders.get(order_id)
        if not order or not order.offer:
            return 0

        # 更新进度
        if progress is not None:
            order.progress = progress

        # 计算解冻金额
        total = order.offer.price
        release_amount = order.tiered_release.get_release_amount(total, order.progress)

        if release_amount >= total:
            order.status = OrderStatus.RELEASED
        else:
            order.status = OrderStatus.PARTIAL_RELEASE

        order.updated_at = time.time()

        logger.info(f"[DecentralizedOrder] Released {release_amount} for order {order_id}, progress: {order.progress}")

        return release_amount

    # ==================== 交付阶段 ====================

    def set_logistics_info(
        self,
        order_id: str,
        carrier: str,
        tracking_number: str,
    ) -> bool:
        """设置物流信息 (实物)"""
        order = self._orders.get(order_id)
        if not order:
            return False

        order.logistics_info = {
            "carrier": carrier,
            "tracking_number": tracking_number,
            "status": "shipped",
            "shipped_at": time.time(),
        }

        order.updated_at = time.time()

        logger.info(f"[DecentralizedOrder] Set logistics for order {order_id}: {carrier} {tracking_number}")

        return True

    def set_virtual_delivery(
        self,
        order_id: str,
        delivery_hash: str,
    ) -> bool:
        """设置虚拟交付哈希 (虚物)"""
        order = self._orders.get(order_id)
        if not order:
            return False

        order.virtual_delivery_hash = delivery_hash

        # 计算最终交付哈希
        content = f"{order.offer.compute_hash() if order.offer else ''}|{order.accept.compute_hash() if order.accept else ''}|{delivery_hash}"
        delivery_hash_full = hashlib.sha256(content.encode()).hexdigest()

        # 创建确认对象
        order.confirmation = DeliveryConfirmation(
            order_id=order_id,
            final_delivery_hash=delivery_hash_full,
        )

        order.updated_at = time.time()

        logger.info(f"[DecentralizedOrder] Set virtual delivery for order {order_id}")

        return True

    # ==================== 确认阶段 ====================

    def buyer_confirm(
        self,
        order_id: str,
        delivery_verified: bool,
        private_key: Optional[str] = None,
    ) -> bool:
        """买家确认交付"""
        order = self._orders.get(order_id)
        if not order or not order.confirmation:
            return False

        if delivery_verified:
            order.confirmation.buyer_confirmed = True
            order.confirmation.buyer_confirm_hash = hashlib.sha256(
                f"{order_id}|buyer_confirm|{time.time()}".encode()
            ).hexdigest()
            order.confirmation.buyer_confirmed_at = time.time()

            if private_key:
                order.confirmation.buyer_signature = self._sign(
                    order.confirmation.buyer_confirm_hash,
                    private_key
                )

        order.updated_at = time.time()

        logger.info(f"[DecentralizedOrder] Buyer confirmed order {order_id}")

        return True

    def seller_confirm(
        self,
        order_id: str,
        delivery_completed: bool,
        private_key: Optional[str] = None,
    ) -> bool:
        """卖家确认交付"""
        order = self._orders.get(order_id)
        if not order or not order.confirmation:
            return False

        if delivery_completed:
            order.confirmation.seller_confirmed = True
            order.confirmation.seller_confirm_hash = hashlib.sha256(
                f"{order_id}|seller_confirm|{time.time()}".encode()
            ).hexdigest()
            order.confirmation.seller_confirmed_at = time.time()

            if private_key:
                order.confirmation.seller_signature = self._sign(
                    order.confirmation.seller_confirm_hash,
                    private_key
                )

        order.updated_at = time.time()

        logger.info(f"[DecentralizedOrder] Seller confirmed order {order_id}")

        return True

    def is_fully_confirmed(self, order_id: str) -> bool:
        """检查是否双向确认"""
        order = self._orders.get(order_id)
        if not order or not order.confirmation:
            return False

        return order.confirmation.is_fully_confirmed()

    # ==================== 完成阶段 ====================

    async def complete_order(self, order_id: str) -> bool:
        """完成订单"""
        order = self._orders.get(order_id)
        if not order:
            return False

        if not self.is_fully_confirmed(order_id):
            logger.warning(f"[DecentralizedOrder] Order not fully confirmed: {order_id}")
            return False

        order.status = OrderStatus.COMPLETED
        order.progress = 1.0
        order.updated_at = time.time()

        # 触发回调
        for cb in self._on_order_completed:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(order_id, order)
                else:
                    cb(order_id, order)
            except Exception as e:
                logger.error(f"[DecentralizedOrder] Complete callback error: {e}")

        logger.info(f"[DecentralizedOrder] Completed order {order_id}")

        return True

    async def cancel_order(self, order_id: str, reason: str = "") -> bool:
        """取消订单"""
        order = self._orders.get(order_id)
        if not order:
            return False

        order.status = OrderStatus.CANCELLED
        order.updated_at = time.time()

        logger.info(f"[DecentralizedOrder] Cancelled order {order_id}: {reason}")

        return True

    async def dispute_order(self, order_id: str, evidence: Dict[str, Any]) -> bool:
        """发起争议"""
        order = self._orders.get(order_id)
        if not order:
            return False

        order.status = OrderStatus.DISPUTED
        order.updated_at = time.time()

        logger.info(f"[DecentralizedOrder] Disputed order {order_id}")

        # 触发回调
        for cb in self._on_order_disputed:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(order_id, evidence)
                else:
                    cb(order_id, evidence)
            except Exception as e:
                logger.error(f"[DecentralizedOrder] Dispute callback error: {e}")

        return True

    # ==================== 查询 ====================

    def get_order(self, order_id: str) -> Optional[DecentralizedOrder]:
        """获取订单"""
        return self._orders.get(order_id)

    def get_order_summary(self, order_id: str) -> Optional[Dict[str, Any]]:
        """获取订单摘要 (不上传完整数据)"""
        order = self._orders.get(order_id)
        if not order:
            return None

        return {
            "order_id": order.order_id,
            "status": order.status.value,
            "progress": order.progress,
            "delivery_type": order.delivery_type,
            "has_logistics": bool(order.logistics_info),
            "has_confirmation": order.confirmation is not None,
            "buyer_confirmed": order.confirmation.buyer_confirmed if order.confirmation else False,
            "seller_confirmed": order.confirmation.seller_confirmed if order.confirmation else False,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }

    def get_orders_by_buyer(self, buyer_id: str) -> List[Dict[str, Any]]:
        """获取买家的订单"""
        result = []
        for order in self._orders.values():
            if order.offer and order.offer.buyer_id == buyer_id:
                result.append(self.get_order_summary(order.order_id))
        return result

    def get_orders_by_seller(self, seller_id: str) -> List[Dict[str, Any]]:
        """获取卖家的订单"""
        result = []
        for order in self._orders.values():
            if order.accept and order.accept.seller_id == seller_id:
                result.append(self.get_order_summary(order.order_id))
        return result

    # ==================== 工具 ====================

    def _generate_nonce(self) -> str:
        """生成防重放nonce"""
        return hashlib.sha256(f"{time.time()}|{uuid.uuid4()}".encode()).hexdigest()[:16]

    def _sign(self, content: str, private_key: str) -> str:
        """签名 (简化版,实际应使用真正的非对称签名)"""
        # 这里应该使用真正的ECDSA或其他非对称签名算法
        # 简化实现: 用私钥和内容做SHA256
        return hashlib.sha256(f"{private_key}|{content}".encode()).hexdigest()

    def _verify_signature(self, content: str, signature: str, public_key: str) -> bool:
        """验证签名"""
        expected = self._sign(content, public_key)
        return signature == expected

    # ==================== 回调 ====================

    def on_order_created(self, callback: Callable) -> None:
        """监听订单创建"""
        self._on_order_created.append(callback)

    def on_order_completed(self, callback: Callable) -> None:
        """监听订单完成"""
        self._on_order_completed.append(callback)

    def on_order_disputed(self, callback: Callable) -> None:
        """监听订单争议"""
        self._on_order_disputed.append(callback)

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        orders = list(self._orders.values())

        return {
            "total_orders": len(orders),
            "pending_offers": len(self._pending_offers),
            "pending_accepts": len(self._pending_accepts),
            "by_status": {
                status.value: sum(1 for o in orders if o.status == status)
                for status in OrderStatus
            },
        }


# ==================== 全局实例 ====================

_decentralized_order: Optional[DecentralizedOrderProtocol] = None


def get_decentralized_order() -> DecentralizedOrderProtocol:
    """获取去中心化订单协议管理器"""
    global _decentralized_order
    if _decentralized_order is None:
        _decentralized_order = DecentralizedOrderProtocol()
    return _decentralized_order
