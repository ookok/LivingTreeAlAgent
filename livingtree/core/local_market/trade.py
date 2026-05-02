"""
去中心化交易系统

实现商品交易的完整流程：协商 → 托管 → 交付 → 确认 → 评价
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import random
import string

from .models import (
    Trade, TradeParticipant, TransactionStatus, PaymentType, DeliveryType,
    EscrowInfo, DeliveryInfo, Product, NodeInfo, NetworkMessage, MessageType,
    ReputationAction, ReputationEvent
)


logger = logging.getLogger(__name__)


class TradeError(Exception):
    """交易错误异常"""
    pass


@dataclass
class NegotiationOffer:
    """协商报价"""
    offer_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    from_node: str = ""
    price: float = 0.0
    delivery_type: DeliveryType = DeliveryType.PICKUP
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    accepted: bool = False
    rejected: bool = False


class TradeManager:
    """交易管理器"""

    def __init__(
        self,
        node_id: str,
        node_info: NodeInfo,
        send_message_fn: Callable
    ):
        self.node_id = node_id
        self.node_info = node_info
        self.send_message = send_message_fn

        # 活跃交易
        self.active_trades: Dict[str, Trade] = {}

        # 待处理的协商
        self.pending_negotiations: Dict[str, NegotiationOffer] = {}

        # 交易超时时间
        self.TRADE_TIMEOUT = 3600  # 1小时
        self.ESCROW_TIMEOUT = 86400  # 24小时
        self.DELIVERY_TIMEOUT = 172800  # 48小时

        # 回调
        self.on_trade_update: Optional[Callable] = None
        self.on_trade_complete: Optional[Callable] = None
        self.on_dispute_opened: Optional[Callable] = None

    # ========================================================================
    # 交易创建
    # ========================================================================

    async def initiate_trade(
        self,
        product: Product,
        buyer_info: NodeInfo,
        seller_info: NodeInfo
    ) -> Trade:
        """发起交易"""
        # 创建交易
        trade = Trade(
            trade_id=str(uuid.uuid4())[:12],
            product_id=product.product_id,
            buyer=TradeParticipant(
                node_id=buyer_info.node_id,
                node_name=buyer_info.name,
                role="buyer",
                reputation=buyer_info.reputation,
                location=buyer_info.location
            ),
            seller=TradeParticipant(
                node_id=seller_info.node_id,
                node_name=seller_info.name,
                role="seller",
                reputation=seller_info.reputation,
                location=seller_info.location
            ),
            final_price=product.price,
            original_price=product.price,
            status=TransactionStatus.INITIATED
        )

        self.active_trades[trade.trade_id] = trade

        # 通知卖家
        await self._send_trade_message(
            seller_info.node_id,
            MessageType.TRADE_REQUEST,
            {
                "trade_id": trade.trade_id,
                "product": product.to_dict(),
                "buyer": buyer_info.to_dict(),
                "action": "new_trade"
            }
        )

        logger.info(f"Trade {trade.trade_id} initiated")
        return trade

    async def accept_trade(self, trade_id: str, buyer_info: NodeInfo) -> bool:
        """买家接受交易"""
        if trade_id not in self.active_trades:
            raise TradeError(f"Trade {trade_id} not found")

        trade = self.active_trades[trade_id]

        if trade.status != TransactionStatus.INITIATED:
            raise TradeError(f"Trade {trade_id} cannot be accepted in status {trade.status}")

        # 如果需要协商，进入协商阶段
        if trade.final_price != trade.original_price or trade.product.condition == "used":
            trade.status = TransactionStatus.NEGOTIATING
            trade.negotiated_at = datetime.now()
        else:
            # 直接进入托管
            trade.status = TransactionStatus.ESCROW
            trade.negotiated_at = datetime.now()

        await self._notify_trade_update(trade)
        return True

    async def reject_trade(self, trade_id: str, reason: str = "") -> bool:
        """拒绝交易"""
        if trade_id not in self.active_trades:
            raise TradeError(f"Trade {trade_id} not found")

        trade = self.active_trades[trade_id]
        trade.status = TransactionStatus.CANCELLED
        trade.cancelled_at = datetime.now()
        trade.metadata["cancel_reason"] = reason

        # 通知对方
        receiver_id = trade.buyer.node_id if trade.seller.node_id == self.node_id else trade.seller.node_id
        await self._send_trade_message(
            receiver_id,
            MessageType.TRADE_UPDATE,
            {
                "trade_id": trade.trade_id,
                "status": TransactionStatus.CANCELLED.value,
                "reason": reason
            }
        )

        await self._notify_trade_update(trade)
        return True

    # ========================================================================
    # 价格协商
    # ========================================================================

    async def make_offer(
        self,
        trade_id: str,
        price: float,
        delivery_type: DeliveryType = DeliveryType.PICKUP,
        message: str = ""
    ) -> NegotiationOffer:
        """发起报价"""
        if trade_id not in self.active_trades:
            raise TradeError(f"Trade {trade_id} not found")

        trade = self.active_trades[trade_id]

        offer = NegotiationOffer(
            from_node=self.node_id,
            price=price,
            delivery_type=delivery_type,
            message=message
        )

        self.pending_negotiations[offer.offer_id] = offer

        # 发送报价给对方
        receiver_id = trade.buyer.node_id if self.node_id == trade.seller.node_id else trade.seller.node_id
        await self._send_trade_message(
            receiver_id,
            MessageType.TRADE_REQUEST,
            {
                "trade_id": trade.trade_id,
                "offer": offer.__dict__,
                "action": "offer"
            }
        )

        return offer

    async def accept_offer(self, offer_id: str) -> bool:
        """接受报价"""
        if offer_id not in self.pending_negotiations:
            raise TradeError(f"Offer {offer_id} not found")

        offer = self.pending_negotiations[offer_id]
        offer.accepted = True

        # 找到对应的交易
        trade = None
        for t in self.active_trades.values():
            if t.status == TransactionStatus.NEGOTIATING:
                if (t.buyer.node_id in [offer.from_node, self.node_id] and
                    t.seller.node_id in [offer.from_node, self.node_id]):
                    trade = t
                    break

        if not trade:
            raise TradeError("Trade not found for offer")

        # 更新交易
        trade.final_price = offer.price
        trade.delivery = DeliveryInfo(delivery_type=offer.delivery_type)
        trade.status = TransactionStatus.ESCROW
        trade.negotiated_at = datetime.now()

        # 通知对方
        receiver_id = trade.buyer.node_id if self.node_id == trade.seller.node_id else trade.seller.node_id
        await self._send_trade_message(
            receiver_id,
            MessageType.TRADE_UPDATE,
            {
                "trade_id": trade.trade_id,
                "offer_accepted": True,
                "final_price": offer.price
            }
        )

        await self._notify_trade_update(trade)
        return True

    async def reject_offer(self, offer_id: str, reason: str = "") -> bool:
        """拒绝报价"""
        if offer_id not in self.pending_negotiations:
            raise TradeError(f"Offer {offer_id} not found")

        offer = self.pending_negotiations[offer_id]
        offer.rejected = True

        # 通知对方
        for trade in self.active_trades.values():
            if trade.status == TransactionStatus.NEGOTIATING:
                if (trade.buyer.node_id in [offer.from_node, self.node_id] and
                    trade.seller.node_id in [offer.from_node, self.node_id]):
                    receiver_id = trade.buyer.node_id if self.node_id == trade.seller.node_id else trade.seller.node_id
                    await self._send_trade_message(
                        receiver_id,
                        MessageType.TRADE_UPDATE,
                        {
                            "trade_id": trade.trade_id,
                            "offer_rejected": True,
                            "reason": reason
                        }
                    )
                    break

        return True

    # ========================================================================
    # 支付托管
    # ========================================================================

    async def initiate_escrow(
        self,
        trade_id: str,
        payment_type: PaymentType = PaymentType.ESCROW_2OF3,
        witness_ids: List[str] = None
    ) -> EscrowInfo:
        """发起托管"""
        if trade_id not in self.active_trades:
            raise TradeError(f"Trade {trade_id} not found")

        trade = self.active_trades[trade_id]

        if trade.status != TransactionStatus.ESCROW:
            raise TradeError(f"Trade {trade_id} not in escrow status")

        # 生成托管地址
        escrow_address = self._generate_escrow_address(trade)

        # 选择见证节点
        if witness_ids is None:
            witness_ids = await self._select_witness_nodes(trade, 3)

        escrow = EscrowInfo(
            escrow_address=escrow_address,
            amount=trade.final_price,
            witnesses=witness_ids,
            required_signatures=2
        )

        trade.escrow = escrow
        trade.payment_type = payment_type

        # 通知买家付款
        await self._send_trade_message(
            trade.buyer.node_id,
            MessageType.TRADE_UPDATE,
            {
                "trade_id": trade.trade_id,
                "escrow": escrow.__dict__,
                "action": "pay_escrow"
            }
        )

        logger.info(f"Escrow initiated for trade {trade_id}")
        return escrow

    async def confirm_payment(
        self,
        trade_id: str,
        payment_proof: str
    ) -> bool:
        """确认付款"""
        if trade_id not in self.active_trades:
            raise TradeError(f"Trade {trade_id} not found")

        trade = self.active_trades[trade_id]

        trade.payment_proof = payment_proof
        trade.paid_at = datetime.now()
        trade.status = TransactionStatus.DELIVERING

        # 通知卖家已付款，可以发货
        await self._send_trade_message(
            trade.seller.node_id,
            MessageType.TRADE_UPDATE,
            {
                "trade_id": trade.trade_id,
                "payment_confirmed": True,
                "delivery_type": trade.delivery.delivery_type.value if trade.delivery else "pickup"
            }
        )

        await self._notify_trade_update(trade)
        return True

    def _generate_escrow_address(self, trade: Trade) -> str:
        """生成托管地址"""
        # 简化实现：实际应该使用多签地址
        raw = f"{trade.trade_id}:{trade.final_price}:{datetime.now().isoformat()}"
        return f"ESCROW:{uuid.uuid5(uuid.NAMESPACE_DNS, raw).hex[:16].upper()}"

    async def _select_witness_nodes(
        self,
        trade: Trade,
        count: int
    ) -> List[str]:
        """选择见证节点"""
        # 简化实现：随机选择在线节点
        # 实际应该基于信誉、地理位置、负载等选择
        return [f"witness_{i}" for i in range(count)]

    # ========================================================================
    # 交付确认
    # ========================================================================

    async def generate_pickup_code(self, trade_id: str) -> str:
        """生成自提验证码"""
        if trade_id not in self.active_trades:
            raise TradeError(f"Trade {trade_id} not found")

        trade = self.active_trades[trade_id]

        # 生成6位验证码
        code = ''.join(random.choices(string.digits, k=6))

        if not trade.delivery:
            trade.delivery = DeliveryInfo()

        trade.delivery.pickup_code = code

        # 通知买家
        await self._send_trade_message(
            trade.buyer.node_id,
            MessageType.TRADE_UPDATE,
            {
                "trade_id": trade.trade_id,
                "pickup_code": code,
                "action": "pickup_code_ready"
            }
        )

        return code

    async def confirm_delivery(
        self,
        trade_id: str,
        delivery_code: str = None
    ) -> bool:
        """确认交付"""
        if trade_id not in self.active_trades:
            raise TradeError(f"Trade {trade_id} not found")

        trade = self.active_trades[trade_id]

        # 验证交付码
        if trade.delivery and trade.delivery.pickup_code:
            if delivery_code != trade.delivery.pickup_code:
                raise TradeError("Invalid delivery code")

        trade.delivered_at = datetime.now()

        # 请求释放托管
        await self._request_escrow_release(trade)

        await self._notify_trade_update(trade)
        return True

    async def _request_escrow_release(self, trade: Trade):
        """请求释放托管"""
        # 通知见证节点确认交付
        if trade.escrow and trade.escrow.witnesses:
            for witness_id in trade.escrow.witnesses:
                await self._send_trade_message(
                    witness_id,
                    MessageType.TRADE_UPDATE,
                    {
                        "trade_id": trade.trade_id,
                        "action": "confirm_delivery",
                        "delivery_verified": True
                    }
                )

    async def release_escrow(self, trade_id: str, witness_id: str) -> bool:
        """见证节点确认释放托管"""
        if trade_id not in self.active_trades:
            raise TradeError(f"Trade {trade_id} not found")

        trade = self.active_trades[trade_id]

        if not trade.escrow:
            raise TradeError("No escrow for this trade")

        # 记录见证节点确认
        if witness_id not in trade.escrow.witnesses:
            trade.escrow.witnesses.append(witness_id)

        # 检查是否达到释放条件
        confirmed_count = len([w for w in trade.escrow.witnesses if w])
        if confirmed_count >= trade.escrow.required_signatures:
            # 释放托管
            await self._execute_escrow_release(trade)

        return True

    async def _execute_escrow_release(self, trade: Trade):
        """执行托管释放"""
        trade.escrow.released_at = datetime.now()
        trade.status = TransactionStatus.COMPLETED
        trade.completed_at = datetime.now()

        # 通知双方
        await self._send_trade_message(
            trade.buyer.node_id,
            MessageType.TRADE_UPDATE,
            {"trade_id": trade.trade_id, "escrow_released": True}
        )
        await self._send_trade_message(
            trade.seller.node_id,
            MessageType.TRADE_UPDATE,
            {"trade_id": trade.trade_id, "escrow_released": True}
        )

        await self._notify_trade_complete(trade)
        logger.info(f"Trade {trade.trade_id} completed, escrow released")

    # ========================================================================
    # 交易取消与退款
    # ========================================================================

    async def cancel_trade(self, trade_id: str, reason: str) -> bool:
        """取消交易"""
        if trade_id not in self.active_trades:
            raise TradeError(f"Trade {trade_id} not found")

        trade = self.active_trades[trade_id]

        if trade.status in [TransactionStatus.COMPLETED, TransactionStatus.REFUNDED]:
            raise TradeError(f"Cannot cancel completed trade")

        # 如果有托管，执行退款
        if trade.escrow and trade.paid_at:
            await self._execute_refund(trade)

        trade.status = TransactionStatus.CANCELLED
        trade.cancelled_at = datetime.now()
        trade.metadata["cancel_reason"] = reason

        # 通知对方
        receiver_id = trade.buyer.node_id if self.node_id == trade.seller.node_id else trade.seller.node_id
        await self._send_trade_message(
            receiver_id,
            MessageType.TRADE_UPDATE,
            {"trade_id": trade.trade_id, "trade_cancelled": True, "reason": reason}
        )

        await self._notify_trade_update(trade)
        return True

    async def _execute_refund(self, trade: Trade):
        """执行退款"""
        trade.status = TransactionStatus.REFUNDED

        # 通知买家退款
        await self._send_trade_message(
            trade.buyer.node_id,
            MessageType.TRADE_UPDATE,
            {"trade_id": trade.trade_id, "refund_completed": True, "amount": trade.escrow.amount}
        )

    # ========================================================================
    # 评价系统
    # ========================================================================

    async def submit_review(
        self,
        trade_id: str,
        rating: int,  # 1-5
        comment: str = ""
    ) -> bool:
        """提交评价"""
        if trade_id not in self.active_trades:
            raise TradeError(f"Trade {trade_id} not found")

        trade = self.active_trades[trade_id]

        review = {
            "rating": rating,
            "comment": comment,
            "timestamp": datetime.now().isoformat()
        }

        if self.node_id == trade.buyer.node_id:
            trade.buyer_review = review
        elif self.node_id == trade.seller.node_id:
            trade.seller_review = review

        # 双方都评价后，更新信誉
        if trade.buyer_review and trade.seller_review:
            await self._update_reputation(trade)

        return True

    async def _update_reputation(self, trade: Trade):
        """更新信誉"""
        # 好评 +5，中评 +2，差评 -5
        rep_changes = {}

        if trade.buyer_review and trade.seller_review:
            buyer_rating = trade.buyer_review["rating"]
            seller_rating = trade.seller_review["rating"]

            # 卖家获得评价
            if seller_rating >= 4:
                rep_changes[trade.seller.node_id] = 5
            elif seller_rating == 3:
                rep_changes[trade.seller.node_id] = 2
            else:
                rep_changes[trade.seller.node_id] = -5

            # 买家获得评价（简化）
            if buyer_rating >= 4:
                rep_changes[trade.buyer.node_id] = 2
            else:
                rep_changes[trade.buyer.node_id] = -3

        # 发送信誉更新消息
        for node_id, change in rep_changes.items():
            await self._send_trade_message(
                node_id,
                MessageType.REPUTATION,
                {
                    "action": ReputationAction.SUCCESSFUL_TRADE.value,
                    "trade_id": trade.trade_id,
                    "reputation_change": change,
                    "counterparty": trade.buyer.node_id if node_id == trade.seller.node_id else trade.seller.node_id
                }
            )

    # ========================================================================
    # 消息发送
    # ========================================================================

    async def _send_trade_message(
        self,
        receiver_id: str,
        msg_type: MessageType,
        payload: Dict[str, Any]
    ):
        """发送交易消息"""
        msg = NetworkMessage(
            msg_type=msg_type,
            sender_id=self.node_id,
            sender_name=self.node_info.name,
            receiver_id=receiver_id,
            payload=payload
        )

        await self.send_message(msg)

    # ========================================================================
    # 回调
    # ========================================================================

    async def _notify_trade_update(self, trade: Trade):
        """通知交易更新"""
        if self.on_trade_update:
            await self.on_trade_update(trade)

    async def _notify_trade_complete(self, trade: Trade):
        """通知交易完成"""
        if self.on_trade_complete:
            await self.on_trade_complete(trade)

    # ========================================================================
    # 查询
    # ========================================================================

    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """获取交易"""
        return self.active_trades.get(trade_id)

    def get_my_trades(self, role: str = None) -> List[Trade]:
        """获取我的交易"""
        trades = []
        for trade in self.active_trades.values():
            if role == "buyer" and trade.buyer.node_id == self.node_id:
                trades.append(trade)
            elif role == "seller" and trade.seller.node_id == self.node_id:
                trades.append(trade)
            elif role is None:
                if trade.buyer.node_id == self.node_id or trade.seller.node_id == self.node_id:
                    trades.append(trade)
        return trades

    def get_trades_by_status(self, status: TransactionStatus) -> List[Trade]:
        """按状态获取交易"""
        return [
            t for t in self.active_trades.values()
            if t.status == status and (t.buyer.node_id == self.node_id or t.seller.node_id == self.node_id)
        ]
