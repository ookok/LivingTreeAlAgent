"""
订单管理器 — 统一订单生命周期管理

合并增强自:
- local_market/trade.py TradeManager
- decommerce/crdt_order.py CRDTOrderManager
- flash_listing/fulfillment.py 履约逻辑

增强:
- 统一状态机（支持完整生命周期）
- CRDT冲突解决（去中心化同步）
- 事件回调系统（替代 ad-hoc callbacks）
"""

from __future__ import annotations
import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime

from ..models.order import Order, Participant, Escrow, Delivery, Fulfillment, ServiceSession
from ..models import (
    OrderStatus, PaymentMethod, DeliveryMethod, ReputationAction
)

logger = logging.getLogger(__name__)


class OrderManager:
    """统一订单管理器"""

    def __init__(self, node_id: str = ""):
        self.node_id = node_id
        self._orders: Dict[str, Order] = {}
        self._callbacks: Dict[str, List[Callable]] = {
            "on_status_change": [],
            "on_payment": [],
            "on_delivery": [],
            "on_complete": [],
            "on_dispute": [],
            "on_cancel": [],
        }
        self._sync_task: Optional[asyncio.Task] = None
        self._pending_sync: List[Order] = []

    # ========================================================================
    # CRUD
    # ========================================================================

    def create_order(
        self,
        listing_id: str,
        buyer: Participant,
        seller: Participant,
        listed_price: float = 0.0,
        payment_method: PaymentMethod = PaymentMethod.DIRECT,
        product_title: str = "",
    ) -> Order:
        """创建新订单"""
        order = Order(
            listing_id=listing_id,
            buyer=buyer,
            seller=seller,
            listed_price=listed_price,
            payment_method=payment_method,
            product_title=product_title,
        )
        order.order_hash = order.compute_hash()
        self._orders[order.order_id] = order
        logger.info(f"Order created: {order.order_id}")
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def list_orders(
        self,
        node_id: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        role: Optional[str] = None,
    ) -> List[Order]:
        """查询订单列表"""
        result = list(self._orders.values())
        if node_id:
            result = [o for o in result if o.buyer_id == node_id or o.seller_id == node_id]
        if status:
            result = [o for o in result if o.status == status]
        if role:
            result = [o for o in result
                       if (role == "buyer" and o.buyer_id == node_id)
                       or (role == "seller" and o.seller_id == node_id)]
        return result

    # ========================================================================
    # 状态转换
    # ========================================================================

    def negotiate(self, order_id: str, price: float) -> bool:
        order = self.get_order(order_id)
        if not order:
            return False
        if order.negotiate(price):
            self._emit("on_status_change", order)
            return True
        return False

    def agree(self, order_id: str) -> bool:
        order = self.get_order(order_id)
        if not order or not order.agree():
            return False
        self._emit("on_status_change", order)
        return True

    def pay(self, order_id: str, payment_id: str = "", proof: str = "") -> bool:
        order = self.get_order(order_id)
        if not order or not order.pay(payment_id, proof):
            return False
        self._emit("on_payment", order)
        self._emit("on_status_change", order)
        return True

    def ship(self, order_id: str, tracking_number: str = "", carrier: str = "") -> bool:
        order = self.get_order(order_id)
        if not order or not order.ship(tracking_number, carrier):
            return False
        self._emit("on_delivery", order)
        self._emit("on_status_change", order)
        return True

    def confirm(self, order_id: str) -> bool:
        order = self.get_order(order_id)
        if not order or not order.confirm():
            return False
        self._emit("on_status_change", order)
        return True

    def complete(self, order_id: str) -> bool:
        order = self.get_order(order_id)
        if not order or not order.complete():
            return False
        self._emit("on_complete", order)
        self._emit("on_status_change", order)
        return True

    def cancel(self, order_id: str, reason: str = "") -> bool:
        order = self.get_order(order_id)
        if not order or not order.cancel(reason):
            return False
        self._emit("on_cancel", order)
        self._emit("on_status_change", order)
        return True

    def refund(self, order_id: str) -> bool:
        order = self.get_order(order_id)
        if not order or not order.refund():
            return False
        self._emit("on_status_change", order)
        return True

    def dispute(self, order_id: str, reason: str = "") -> bool:
        order = self.get_order(order_id)
        if not order or not order.dispute(reason):
            return False
        self._emit("on_dispute", order)
        self._emit("on_status_change", order)
        return True

    # ========================================================================
    # CRDT 同步（去中心化订单状态同步）
    # ========================================================================

    def receive_remote_state(self, remote_order: Order) -> bool:
        """接收远程节点的 CRDT 状态"""
        local = self.get_order(remote_order.order_id)
        if not local:
            self._orders[remote_order.order_id] = remote_order
            return True

        # CRDT 合并：取最新的状态
        remote_ts = remote_order.crdt_version.get(remote_order.seller_id or remote_order.buyer_id, 0)
        local_ts = local.crdt_version.get(local.seller_id or local.buyer_id, 0)

        if remote_ts > local_ts:
            local.status = remote_order.status
            local.final_price = remote_order.final_price
            local.crdt_version = {**local.crdt_version, **remote_order.crdt_version}
            self._emit("on_status_change", local)
            return True

        return False

    def export_state(self, order_id: str) -> Optional[dict]:
        """导出 CRDT 状态"""
        order = self.get_order(order_id)
        return order.to_dict() if order else None

    # ========================================================================
    # 事件系统
    # ========================================================================

    def on(self, event: str, callback: Callable) -> None:
        """注册事件回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def off(self, event: str, callback: Callable) -> None:
        """移除事件回调"""
        if event in self._callbacks and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)

    def _emit(self, event: str, order: Order) -> None:
        """触发事件回调"""
        for cb in self._callbacks.get(event, []):
            try:
                cb(order)
            except Exception as e:
                logger.error(f"Callback error in {event}: {e}")

    # ========================================================================
    # 后台同步
    # ========================================================================

    async def _sync_loop(self, interval: float = 5.0):
        """后台 CRDT 同步循环"""
        while True:
            await asyncio.sleep(interval)
            # 批量处理待同步的远程状态
            pending = self._pending_sync[:]
            self._pending_sync.clear()
            for order in pending:
                self.receive_remote_state(order)

    def start_sync(self):
        """启动后台同步"""
        if self._sync_task is None:
            self._sync_task = asyncio.ensure_future(self._sync_loop())

    def stop_sync(self):
        """停止后台同步"""
        if self._sync_task:
            self._sync_task.cancel()
            self._sync_task = None

    # ========================================================================
    # 统计
    # ========================================================================

    def get_stats(self) -> dict:
        orders = list(self._orders.values())
        by_status = {}
        for o in orders:
            by_status[o.status.value] = by_status.get(o.status.value, 0) + 1

        return {
            "total_orders": len(orders),
            "by_status": by_status,
            "total_volume": sum(o.final_price for o in orders if o.is_paid),
            "completed": sum(1 for o in orders if o.is_completed),
            "disputed": sum(1 for o in orders if o.is_disputed),
        }


# 模块级实例获取
_ORDER_MANAGER: Optional[OrderManager] = None


def get_order_manager(node_id: str = "") -> OrderManager:
    """获取订单管理器单例"""
    global _ORDER_MANAGER
    if _ORDER_MANAGER is None:
        _ORDER_MANAGER = OrderManager(node_id)
    return _ORDER_MANAGER
