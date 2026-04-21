"""
支付守卫 (PaymentGuard)
Payment Guard with Commission Integration

功能:
- 资金冻结/解冻
- 佣金计算与扣除
- 退款处理
- 与佣金系统的集成
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging
import time
import uuid

from .models import Order, ServiceSession

logger = logging.getLogger(__name__)


class PaymentStatus(Enum):
    """支付状态"""
    PENDING = "pending"
    FROZEN = "frozen"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


@dataclass
class PaymentGuardConfig:
    """支付守卫配置"""
    # 佣金率 (0.0 - 1.0)
    commission_rate: float = 0.05  # 5%

    # 最低佣金 (分)
    min_commission: int = 1

    # 最高佣金 (分)
    max_commission: int = 10000

    # 退款费率 (0.0 - 1.0)
    refund_rate: float = 0.0  # 无退款费率

    # 心跳超时 (秒)
    heartbeat_timeout: int = 30

    # 自动完成宽限期 (秒)
    auto_complete_grace_period: int = 60


class PaymentGuard:
    """
    支付守卫

    流程:
    1. 买家付款 -> 资金冻结
    2. 服务开始 -> 冻结转活跃
    3. 服务完成 -> 扣除佣金,打款卖家
    4. 异常/取消 -> 退款/解冻
    """

    _instance = None

    def __new__(cls, config: Optional[PaymentGuardConfig] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[PaymentGuardConfig] = None):
        if self._initialized:
            return

        self._initialized = True
        self.config = config or PaymentGuardConfig()

        # 本地存储
        self._orders: Dict[str, Order] = {}
        self._payments: Dict[str, Dict[str, Any]] = {}  # payment_id -> payment info

        # 活跃的支付会话
        self._active_payments: Dict[str, Dict[str, Any]] = {}

        # 回调
        self._on_payment_frozen: List[Callable] = []
        self._on_payment_released: List[Callable] = []
        self._on_commission_collected: List[Callable] = []
        self._on_refund_processed: List[Callable] = []

        # 佣金系统集成
        self._commission_module = None

    def set_commission_module(self, commission_module) -> None:
        """设置佣金模块引用"""
        self._commission_module = commission_module

    # ==================== 支付流程 ====================

    async def create_order(
        self,
        listing_id: str,
        seller_id: str,
        buyer_id: str,
        amount: int,  # 总金额(分)
        payment_method: str = "balance",
    ) -> Order:
        """
        创建订单并冻结资金

        Args:
            listing_id: 商品ID
            seller_id: 卖家ID
            buyer_id: 买家ID
            amount: 总金额(分)
            payment_method: 支付方式

        Returns:
            Order对象
        """
        order_id = str(uuid.uuid4())[:12]

        # 计算佣金
        commission = self._calculate_commission(amount)

        order = Order(
            id=order_id,
            listing_id=listing_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            total_amount=amount,
            commission_fee=commission,
            net_amount=amount - commission,
            status="frozen",
            payment_method=payment_method,
        )

        self._orders[order_id] = order

        # 冻结资金 (调用佣金系统)
        if self._commission_module:
            try:
                await self._commission_module.freeze_funds(
                    buyer_id=buyer_id,
                    amount=amount,
                    order_id=order_id,
                )
            except Exception as e:
                logger.error(f"[PaymentGuard] Failed to freeze funds: {e}")

        logger.info(f"[PaymentGuard] Created order {order_id}: {amount} (commission: {commission})")

        # 触发回调
        for cb in self._on_payment_frozen:
            asyncio.create_task(self._safe_call(cb, order))

        return order

    async def activate_order(self, order_id: str) -> bool:
        """
        激活订单 (服务开始)

        将冻结资金转为服务中状态
        """
        order = self._orders.get(order_id)
        if not order:
            return False

        if order.status != "frozen":
            logger.warning(f"[PaymentGuard] Order {order_id} is not frozen")
            return False

        order.status = "active"

        # 创建活跃支付记录
        payment_id = str(uuid.uuid4())[:12]
        self._active_payments[payment_id] = {
            "order_id": order_id,
            "start_time": time.time(),
            "last_heartbeat": time.time(),
        }

        logger.info(f"[PaymentGuard] Activated order {order_id}")

        return True

    async def complete_order(
        self,
        order_id: str,
        actual_amount: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        完成订单 (服务完成)

        扣除佣金,打款卖家
        """
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        if order.status not in ("frozen", "active"):
            raise ValueError(f"Order {order_id} cannot be completed (status: {order.status})")

        # 计算实际金额
        if actual_amount is None:
            actual_amount = order.total_amount

        # 重新计算佣金
        commission = self._calculate_commission(actual_amount)
        net_amount = actual_amount - commission

        # 更新订单
        order.commission_fee = commission
        order.net_amount = net_amount
        order.status = "completed"
        order.completed_at = time.time()

        # 释放资金给卖家
        if self._commission_module:
            try:
                await self._commission_module.release_funds(
                    seller_id=order.seller_id,
                    amount=net_amount,
                    order_id=order_id,
                )

                # 记录佣金
                await self._commission_module.record_commission(
                    order_id=order_id,
                    seller_id=order.seller_id,
                    buyer_id=order.buyer_id,
                    amount=commission,
                )
            except Exception as e:
                logger.error(f"[PaymentGuard] Failed to complete order: {e}")

        result = {
            "order_id": order_id,
            "total_amount": actual_amount,
            "commission": commission,
            "net_amount": net_amount,
            "completed_at": order.completed_at,
        }

        logger.info(f"[PaymentGuard] Completed order {order_id}: {net_amount} to seller")

        # 触发回调
        for cb in self._on_payment_released:
            asyncio.create_task(self._safe_call(cb, order, net_amount))

        for cb in self._on_commission_collected:
            asyncio.create_task(self._safe_call(cb, order, commission))

        return result

    async def cancel_order(self, order_id: str, reason: str = "") -> Dict[str, Any]:
        """
        取消订单

        解冻资金给买家
        """
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        if order.status == "completed":
            raise ValueError(f"Order {order_id} already completed")

        if order.status == "refunded":
            raise ValueError(f"Order {order_id} already refunded")

        # 计算退款金额
        refund_amount = order.total_amount
        if self.config.refund_rate > 0:
            refund_amount = int(refund_amount * (1 - self.config.refund_rate))

        # 更新订单
        order.status = "cancelled"

        # 解冻资金
        if self._commission_module:
            try:
                await self._commission_module.unfreeze_funds(
                    buyer_id=order.buyer_id,
                    amount=refund_amount,
                    order_id=order_id,
                )
            except Exception as e:
                logger.error(f"[PaymentGuard] Failed to cancel order: {e}")

        result = {
            "order_id": order_id,
            "refund_amount": refund_amount,
            "reason": reason,
        }

        logger.info(f"[PaymentGuard] Cancelled order {order_id}: {refund_amount} refunded")

        # 触发回调
        for cb in self._on_refund_processed:
            asyncio.create_task(self._safe_call(cb, order, refund_amount))

        return result

    async def refund_order(self, order_id: str, amount: Optional[int] = None) -> Dict[str, Any]:
        """
        退款

        Args:
            order_id: 订单ID
            amount: 退款金额(分),默认全额
        """
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        if amount is None:
            amount = order.total_amount

        # 限制退款金额
        amount = min(amount, order.total_amount)

        # 更新订单
        order.status = "refunded"

        # 执行退款
        if self._commission_module:
            try:
                await self._commission_module.refund(
                    buyer_id=order.buyer_id,
                    amount=amount,
                    order_id=order_id,
                )
            except Exception as e:
                logger.error(f"[PaymentGuard] Failed to refund: {e}")

        result = {
            "order_id": order_id,
            "refund_amount": amount,
        }

        logger.info(f"[PaymentGuard] Refunded order {order_id}: {amount}")

        # 触发回调
        for cb in self._on_refund_processed:
            asyncio.create_task(self._safe_call(cb, order, amount))

        return result

    # ==================== 心跳监控 ====================

    async def record_heartbeat(self, order_id: str, user_id: str) -> None:
        """记录心跳"""
        for payment in self._active_payments.values():
            if payment["order_id"] == order_id:
                payment["last_heartbeat"] = time.time()

    async def check_heartbeats(self) -> List[Dict[str, Any]]:
        """
        检查所有活跃支付的心跳

        Returns:
            超时的支付列表
        """
        timeout_payments = []
        now = time.time()

        for payment_id, payment in list(self._active_payments.items()):
            elapsed = now - payment["last_heartbeat"]
            if elapsed > self.config.heartbeat_timeout:
                timeout_payments.append({
                    "payment_id": payment_id,
                    "order_id": payment["order_id"],
                    "elapsed": elapsed,
                })

        return timeout_payments

    async def handle_timeout(self, order_id: str) -> Dict[str, Any]:
        """
        处理支付超时

        自动取消订单并退款
        """
        order = self._orders.get(order_id)
        if not order:
            return {}

        logger.warning(f"[PaymentGuard] Payment timeout for order {order_id}")

        # 取消订单
        return await self.cancel_order(order_id, reason="timeout")

    # ==================== 查询 ====================

    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单"""
        return self._orders.get(order_id)

    def get_orders_by_buyer(self, buyer_id: str) -> List[Order]:
        """获取买家的订单"""
        return [
            o for o in self._orders.values()
            if o.buyer_id == buyer_id
        ]

    def get_orders_by_seller(self, seller_id: str) -> List[Order]:
        """获取卖家的订单"""
        return [
            o for o in self._orders.values()
            if o.seller_id == seller_id
        ]

    def get_active_orders(self) -> List[Order]:
        """获取活跃订单"""
        return [
            o for o in self._orders.values()
            if o.status in ("frozen", "active")
        ]

    # ==================== 工具 ====================

    def _calculate_commission(self, amount: int) -> int:
        """计算佣金"""
        commission = int(amount * self.config.commission_rate)

        # 应用限制
        commission = max(commission, self.config.min_commission)
        commission = min(commission, self.config.max_commission)

        return commission

    def get_commission_rate(self) -> float:
        """获取佣金率"""
        return self.config.commission_rate

    def set_commission_rate(self, rate: float) -> None:
        """设置佣金率"""
        if 0.0 <= rate <= 1.0:
            self.config.commission_rate = rate

    # ==================== 回调 ====================

    def on_payment_frozen(self, callback: Callable) -> None:
        """监听支付冻结"""
        self._on_payment_frozen.append(callback)

    def on_payment_released(self, callback: Callable) -> None:
        """监听支付释放"""
        self._on_payment_released.append(callback)

    def on_commission_collected(self, callback: Callable) -> None:
        """监听佣金收取"""
        self._on_commission_collected.append(callback)

    def on_refund_processed(self, callback: Callable) -> None:
        """监听退款处理"""
        self._on_refund_processed.append(callback)

    async def _safe_call(self, callback: Callable, *args, **kwargs) -> None:
        """安全调用回调"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"[PaymentGuard] Callback error: {e}")

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        orders = list(self._orders.values())

        total_frozen = sum(
            o.total_amount for o in orders
            if o.status == "frozen"
        )

        total_completed = sum(
            o.total_amount for o in orders
            if o.status == "completed"
        )

        total_commission = sum(
            o.commission_fee for o in orders
            if o.status == "completed"
        )

        return {
            "total_orders": len(orders),
            "active_orders": len([o for o in orders if o.status in ("frozen", "active")]),
            "completed_orders": len([o for o in orders if o.status == "completed"]),
            "total_frozen": total_frozen,
            "total_completed": total_completed,
            "total_commission": total_commission,
            "commission_rate": self.config.commission_rate,
        }


# 全局单例
_payment_guard: Optional[PaymentGuard] = None


def get_payment_guard() -> PaymentGuard:
    """获取支付守卫单例"""
    global _payment_guard
    if _payment_guard is None:
        _payment_guard = PaymentGuard()
    return _payment_guard