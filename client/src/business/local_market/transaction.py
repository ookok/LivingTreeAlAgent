# -*- coding: utf-8 -*-
"""
交易协议模块
============

四步交易法：
1. 发现与连接
2. 协商与确认
3. 执行与验证
4. 评价与反馈

核心类：
- Transaction: 交易数据模型
- TransactionManager: 交易管理器
- TransactionStatus: 交易状态枚举
- NegotiationOffer: 议价Offer
"""

import uuid
import time
import hashlib
import json
import asyncio
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass


class TransactionStatus(Enum):
    """交易状态"""
    # 初始状态
    CREATED = "created"                    # 创建（待确认）

    # 协商阶段
    PENDING_ACCEPT = "pending_accept"      # 待接受
    NEGOTIATING = "negotiating"             # 协商中

    # 执行阶段
    CONFIRMED = "confirmed"                # 已确认
    PAYMENT_LOCKED = "payment_locked"       # 支付已锁定
    IN_DELIVERY = "in_delivery"             # 交付中
    DELIVERED = "delivered"                # 已交付（待确认）

    # 完结状态
    COMPLETED = "completed"                 # 已完成
    CANCELLED = "cancelled"                 # 已取消
    DISPUTED = "disputed"                   # 有争议

    # 特殊状态
    EXPIRED = "expired"                    # 已过期
    REFUNDED = "refunded"                  # 已退款

    @property
    def is_terminal(self) -> bool:
        """是否为终态"""
        return self in [
            TransactionStatus.COMPLETED,
            TransactionStatus.CANCELLED,
            TransactionStatus.REFUNDED,
        ]

    @property
    def can_cancel(self) -> bool:
        """是否可以取消"""
        return self in [
            TransactionStatus.CREATED,
            TransactionStatus.PENDING_ACCEPT,
            TransactionStatus.NEGOTIATING,
            TransactionStatus.CONFIRMED,
        ]

    @property
    def can_dispute(self) -> bool:
        """是否可以发起争议"""
        return self in [
            TransactionStatus.PAYMENT_LOCKED,
            TransactionStatus.IN_DELIVERY,
            TransactionStatus.DELIVERED,
        ]


class PaymentType(Enum):
    """支付类型"""
    DIRECT = "direct"                      # 直接支付
    ESCROW = "escrow"                      # 托管支付
    TIME_LOCK = "time_lock"                # 时间锁定支付


@dataclass
class NegotiationOffer:
    """议价Offer"""
    offer_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str = ""
    offerer_id: str = ""                   # 出价方ID
    price: float = 0.0                      # 出价
    message: str = ""                        # 留言
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0                  # 过期时间
    accepted: bool = False
    rejected: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'NegotiationOffer':
        return cls(**data)


@dataclass
class Transaction:
    """交易数据模型"""
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # 参与者
    buyer_id: str = ""                      # 买家ID
    seller_id: str = ""                      # 卖家ID
    witness_ids: List[str] = field(default_factory=list)  # 见证人ID列表

    # 商品信息
    product_id: str = ""
    product_snapshot: Dict = field(default_factory=dict)  # 商品快照

    # 价格
    original_price: float = 0.0            # 原价
    final_price: float = 0.0                # 最终成交价

    # 支付
    payment_type: PaymentType = PaymentType.DIRECT
    payment_status: str = "pending"         # pending/locked/released/refunded

    # 状态
    status: TransactionStatus = TransactionStatus.CREATED

    # 时间戳
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    confirmed_at: float = 0                 # 确认时间
    completed_at: float = 0                  # 完成时间
    expires_at: float = 0                   # 过期时间

    # 交付
    delivery_type: str = "pickup"           # pickup/delivery/safe_point
    delivery_address: str = ""               # 交付地址
    delivery_time_window: str = ""           # 时间窗口

    # 协商记录
    negotiation_history: List[Dict] = field(default_factory=list)

    # 完成确认
    buyer_confirmed: bool = False
    seller_confirmed: bool = False

    # 元数据
    trace_id: str = ""                      # 追踪ID
    notes: List[str] = field(default_factory=list)  # 备注

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['status'] = self.status.value
        data['payment_type'] = self.payment_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'Transaction':
        data = data.copy()
        data['status'] = TransactionStatus(data.get('status', 'created'))
        data['payment_type'] = PaymentType(data.get('payment_type', 'direct'))
        return cls(**data)

    def add_negotiation(self, offer: NegotiationOffer):
        """添加协商记录"""
        self.negotiation_history.append({
            "offer_id": offer.offer_id,
            "offerer_id": offer.offerer_id,
            "price": offer.price,
            "message": offer.message,
            "created_at": offer.created_at,
            "accepted": offer.accepted,
            "rejected": offer.rejected,
        })
        self.updated_at = time.time()

    def confirm_by_buyer(self):
        """买家确认"""
        self.buyer_confirmed = True
        self._check_completion()

    def confirm_by_seller(self):
        """卖家确认"""
        self.seller_confirmed = True
        self._check_completion()

    def _check_completion(self):
        """检查是否双方都确认"""
        if self.buyer_confirmed and self.seller_confirmed:
            self.status = TransactionStatus.COMPLETED
            self.completed_at = time.time()

    def update_timestamp(self):
        self.updated_at = time.time()

    def get_trace_id(self) -> str:
        """获取追踪ID（首次访问时生成）"""
        if not self.trace_id:
            self.trace_id = hashlib.sha256(
                f"{self.transaction_id}:{time.time()}".encode()
            ).hexdigest()[:16]
        return self.trace_id


class TransactionManager:
    """交易管理器"""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.transactions: Dict[str, Transaction] = {}  # transaction_id -> Transaction
        self.user_transactions: Dict[str, List[str]] = {}  # user_id -> [transaction_ids]

        # 协商记录
        self.pending_offers: Dict[str, NegotiationOffer] = {}  # offer_id -> offer

        # 回调
        self.on_transaction_update: Optional[Callable] = None
        self.on_payment_required: Optional[Callable] = None
        self.on_delivery_required: Optional[Callable] = None

    def create_transaction(
        self,
        buyer_id: str,
        seller_id: str,
        product_id: str,
        product_snapshot: Dict,
        price: float,
        payment_type: PaymentType = PaymentType.DIRECT,
    ) -> Transaction:
        """创建交易"""
        tx = Transaction(
            buyer_id=buyer_id,
            seller_id=seller_id,
            product_id=product_id,
            product_snapshot=product_snapshot,
            original_price=price,
            final_price=price,
            payment_type=payment_type,
            status=TransactionStatus.PENDING_ACCEPT,
        )

        self.transactions[tx.transaction_id] = tx

        # 更新用户交易索引
        self._index_user_transaction(buyer_id, tx.transaction_id)
        self._index_user_transaction(seller_id, tx.transaction_id)

        return tx

    def accept_transaction(self, transaction_id: str) -> bool:
        """接受交易"""
        tx = self.transactions.get(transaction_id)
        if not tx:
            return False

        if tx.status != TransactionStatus.PENDING_ACCEPT:
            return False

        if tx.seller_id != self.node_id:
            return False

        tx.status = TransactionStatus.CONFIRMED
        tx.confirmed_at = time.time()
        tx.update_timestamp()

        self._notify_update(tx)

        return True

    def reject_transaction(self, transaction_id: str, reason: str = "") -> bool:
        """拒绝交易"""
        tx = self.transactions.get(transaction_id)
        if not tx:
            return False

        if tx.status != TransactionStatus.PENDING_ACCEPT:
            return False

        if tx.seller_id != self.node_id:
            return False

        tx.status = TransactionStatus.CANCELLED
        tx.notes.append(f"Rejected by seller: {reason}")
        tx.update_timestamp()

        self._notify_update(tx)

        return True

    def propose_counter_offer(
        self,
        transaction_id: str,
        buyer_id: str,
        new_price: float,
        message: str = "",
    ) -> NegotiationOffer:
        """提出还价"""
        tx = self.transactions.get(transaction_id)
        if not tx:
            raise ValueError("Transaction not found")

        if tx.status not in [TransactionStatus.PENDING_ACCEPT, TransactionStatus.NEGOTIATING]:
            raise ValueError("Cannot negotiate in current state")

        offer = NegotiationOffer(
            transaction_id=transaction_id,
            offerer_id=buyer_id,
            price=new_price,
            message=message,
            expires_at=time.time() + 3600,  # 1小时过期
        )

        self.pending_offers[offer.offer_id] = offer
        tx.status = TransactionStatus.NEGOTIATING
        tx.add_negotiation(offer)
        tx.update_timestamp()

        return offer

    def accept_offer(self, offer_id: str) -> bool:
        """接受还价"""
        offer = self.pending_offers.get(offer_id)
        if not offer:
            return False

        tx = self.transactions.get(offer.transaction_id)
        if not tx:
            return False

        # 更新交易价格
        tx.final_price = offer.price
        offer.accepted = True
        tx.status = TransactionStatus.CONFIRMED
        tx.confirmed_at = time.time()
        tx.update_timestamp()

        # 删除其他pending offer
        self._cancel_other_offers(tx.transaction_id, offer_id)

        self._notify_update(tx)

        return True

    def reject_offer(self, offer_id: str) -> bool:
        """拒绝还价"""
        offer = self.pending_offers.get(offer_id)
        if not offer:
            return False

        offer.rejected = True

        tx = self.transactions.get(offer.transaction_id)
        if tx:
            tx.update_timestamp()
            self._notify_update(tx)

        return True

    def lock_payment(self, transaction_id: str) -> bool:
        """锁定支付"""
        tx = self.transactions.get(transaction_id)
        if not tx:
            return False

        if tx.status != TransactionStatus.CONFIRMED:
            return False

        if tx.buyer_id != self.node_id:
            return False

        tx.status = TransactionStatus.PAYMENT_LOCKED
        tx.payment_status = "locked"
        tx.update_timestamp()

        self._notify_update(tx)

        if self.on_payment_required:
            asyncio.create_task(self.on_payment_required(tx))

        return True

    def release_payment(self, transaction_id: str) -> bool:
        """释放支付给卖家"""
        tx = self.transactions.get(transaction_id)
        if not tx:
            return False

        if tx.status != TransactionStatus.DELIVERED:
            return False

        if tx.buyer_id != self.node_id:
            return False

        tx.payment_status = "released"
        tx.status = TransactionStatus.COMPLETED
        tx.completed_at = time.time()
        tx.update_timestamp()

        self._notify_update(tx)

        return True

    def initiate_delivery(self, transaction_id: str, delivery_info: Dict) -> bool:
        """发起交付"""
        tx = self.transactions.get(transaction_id)
        if not tx:
            return False

        if tx.status != TransactionStatus.PAYMENT_LOCKED:
            return False

        if tx.seller_id != self.node_id:
            return False

        tx.status = TransactionStatus.IN_DELIVERY
        tx.delivery_address = delivery_info.get("address", "")
        tx.delivery_time_window = delivery_info.get("time_window", "")
        tx.update_timestamp()

        self._notify_update(tx)

        return True

    def confirm_delivery(self, transaction_id: str) -> bool:
        """确认交付完成"""
        tx = self.transactions.get(transaction_id)
        if not tx:
            return False

        if tx.status != TransactionStatus.IN_DELIVERY:
            return False

        tx.status = TransactionStatus.DELIVERED
        tx.update_timestamp()

        # 通知买家确认
        self._notify_update(tx)

        return True

    def cancel_transaction(self, transaction_id: str, reason: str = "") -> bool:
        """取消交易"""
        tx = self.transactions.get(transaction_id)
        if not tx:
            return False

        if not tx.status.can_cancel:
            return False

        if self.node_id not in [tx.buyer_id, tx.seller_id]:
            return False

        tx.status = TransactionStatus.CANCELLED
        tx.notes.append(f"Cancelled by {self.node_id}: {reason}")
        tx.update_timestamp()

        self._notify_update(tx)

        return True

    def initiate_dispute(self, transaction_id: str, reason: str, evidence: List[str] = None) -> bool:
        """发起争议"""
        tx = self.transactions.get(transaction_id)
        if not tx:
            return False

        if not tx.status.can_dispute:
            return False

        if self.node_id not in [tx.buyer_id, tx.seller_id]:
            return False

        tx.status = TransactionStatus.DISPUTED
        tx.notes.append(f"Dispute opened by {self.node_id}: {reason}")
        if evidence:
            tx.notes.append(f"Evidence: {', '.join(evidence)}")
        tx.update_timestamp()

        self._notify_update(tx)

        return True

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """获取交易"""
        return self.transactions.get(transaction_id)

    def get_my_transactions(self, as_buyer: bool = True, as_seller: bool = True) -> List[Transaction]:
        """获取我的交易"""
        result = []

        for tx in self.transactions.values():
            if as_buyer and tx.buyer_id == self.node_id:
                result.append(tx)
            elif as_seller and tx.seller_id == self.node_id:
                result.append(tx)

        # 按时间倒序
        result.sort(key=lambda x: x.updated_at, reverse=True)

        return result

    def get_pending_transactions(self) -> List[Transaction]:
        """获取待处理交易"""
        return [
            tx for tx in self.transactions.values()
            if tx.status in [
                TransactionStatus.PENDING_ACCEPT,
                TransactionStatus.NEGOTIATING,
                TransactionStatus.PAYMENT_LOCKED,
                TransactionStatus.IN_DELIVERY,
            ]
            and self.node_id in [tx.buyer_id, tx.seller_id]
        ]

    def _index_user_transaction(self, user_id: str, transaction_id: str):
        """索引用户交易"""
        if user_id not in self.user_transactions:
            self.user_transactions[user_id] = []
        if transaction_id not in self.user_transactions[user_id]:
            self.user_transactions[user_id].append(transaction_id)

    def _cancel_other_offers(self, transaction_id: str, except_offer_id: str):
        """取消其他pending offers"""
        for offer_id, offer in list(self.pending_offers.items()):
            if offer.transaction_id == transaction_id and offer_id != except_offer_id:
                offer.rejected = True

    def _notify_update(self, tx: Transaction):
        """通知交易更新"""
        if self.on_transaction_update:
            asyncio.create_task(self.on_transaction_update(tx))

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        total = len(self.transactions)
        completed = sum(1 for tx in self.transactions.values() if tx.status == TransactionStatus.COMPLETED)
        disputed = sum(1 for tx in self.transactions.values() if tx.status == TransactionStatus.DISPUTED)

        return {
            "total": total,
            "completed": completed,
            "disputed": disputed,
            "completion_rate": completed / total if total > 0 else 0,
        }


if __name__ == "__main__":
    # 简单测试
    manager = TransactionManager("buyer_123")

    # 创建交易
    tx = manager.create_transaction(
        buyer_id="buyer_123",
        seller_id="seller_456",
        product_id="prod_789",
        product_snapshot={"title": "iPhone 14", "price": 6999},
        price=6500,
        payment_type=PaymentType.ESCROW,
    )

    print(f"Created transaction: {tx.transaction_id}")
    print(f"Status: {tx.status.value}")

    # 卖家接受
    manager.accept_transaction(tx.transaction_id)
    print(f"After accept: {tx.status.value}")

    # 买家还价
    offer = manager.propose_counter_offer(tx.transaction_id, "buyer_123", 6000, "便宜点吧")
    print(f"Counter offer: {offer.price}")

    # 卖家接受还价
    manager.accept_offer(offer.offer_id)
    print(f"Final price: {tx.final_price}")
