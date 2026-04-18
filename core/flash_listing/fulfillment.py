# core/flash_listing/fulfillment.py
# 履约与信任闭环
#
# 处理订单履约全流程：
# - 发货确认
# - 物流跟踪
# - 收货确认
# - 自动放款
# - 双向评价

import asyncio
import logging
import json
import uuid
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from .models import (
    FulfillmentRecord,
    PurchaseStatus,
    InlinePurchase,
    CreditCredential,
)

logger = logging.getLogger(__name__)


class FulfillmentManager:
    """
    履约管理器

    核心功能：
    1. 发货处理
    2. 物流跟踪
    3. 收货确认
    4. 自动放款（超时）
    5. 双向评价
    6. 信用凭证生成
    """

    def __init__(self, node_id: str, config: Optional[Dict] = None):
        """
        Args:
            node_id: 当前节点ID
            config: 配置字典
        """
        self.node_id = node_id
        self.config = config or {}

        # 履约记录存储
        self.records: Dict[str, FulfillmentRecord] = {}

        # 自动放款检查间隔（秒）
        self.auto_confirm_interval = self.config.get("auto_confirm_interval", 3600)  # 1小时

        # 超时自动放款时间（小时）
        self.default_auto_confirm_hours = self.config.get("auto_confirm_hours", 72)  # 72小时

        # P2P 网络（待集成）
        self.p2p_client = None

        # 信用系统（待集成）
        self.credit_system = None

        # 回调
        self.on_fulfillment_update: Optional[Callable] = None
        self.on_rating_submitted: Optional[Callable] = None

    async def create_fulfillment(
        self,
        purchase: InlinePurchase,
    ) -> FulfillmentRecord:
        """
        创建履约记录

        Args:
            purchase: 购买订单

        Returns:
            履约记录
        """
        record = FulfillmentRecord(
            record_id=str(uuid.uuid4())[:12],
            purchase_id=purchase.purchase_id,
            listing_id=purchase.listing_id,
            status="pending",
            auto_confirm_hours=self.default_auto_confirm_hours,
        )

        self.records[record.record_id] = record

        logger.info(f"[FulfillmentManager] 创建履约记录: {record.record_id}")
        return record

    async def submit_tracking(
        self,
        purchase_id: str,
        tracking_number: str,
        carrier: str,
    ) -> bool:
        """
        卖家提交物流单号

        Args:
            purchase_id: 购买ID
            tracking_number: 物流单号
            carrier: 承运商

        Returns:
            是否成功
        """
        # 查找履约记录
        record = self._find_record_by_purchase(purchase_id)
        if not record:
            # 创建新记录
            # 注意：需要传入 purchase 对象
            return False

        record.tracking_number = tracking_number
        record.carrier = carrier
        record.status = "shipped"

        logger.info(f"[FulfillmentManager] 物流单号已提交: {tracking_number} ({carrier})")

        # 通知买家
        await self._notify_buyer_shipped(record)

        return True

    async def confirm_delivery(
        self,
        purchase_id: str,
        buyer_id: str,
    ) -> bool:
        """
        买家确认收货

        Args:
            purchase_id: 购买ID
            buyer_id: 买家ID（验证身份）

        Returns:
            是否成功
        """
        record = self._find_record_by_purchase(purchase_id)
        if not record:
            return False

        # 验证买家身份
        # TODO: 实际验证

        record.buyer_confirmed = True
        record.confirmed_at = datetime.now().timestamp()
        record.status = "delivered"

        # 计算是否应放款
        if record.tracking_number:
            record.status = "confirmed"

        logger.info(f"[FulfillmentManager] 买家确认收货: {purchase_id}")

        # 触发放款
        await self._release_funds(record)

        # 生成信用凭证
        await self._generate_credit_credential(record)

        return True

    async def auto_confirm_if_timeout(self, record_id: str) -> bool:
        """
        超时自动确认（模拟快递已送达）

        Args:
            record_id: 履约记录ID

        Returns:
            是否执行了自动确认
        """
        record = self.records.get(record_id)
        if not record:
            return False

        # 检查是否超时
        if not record.created_at:
            return False

        elapsed_hours = (datetime.now().timestamp() - record.created_at) / 3600

        if elapsed_hours >= record.auto_confirm_hours and not record.buyer_confirmed:
            # 自动确认
            record.buyer_confirmed = True
            record.confirmed_at = datetime.now().timestamp()
            record.status = "auto_confirmed"

            logger.info(f"[FulfillmentManager] 超时自动确认: {record_id}")

            # 放款
            await self._release_funds(record)

            # 生成信用凭证（负面）
            await self._generate_credit_credential(record, auto_confirmed=True)

            return True

        return False

    async def submit_rating(
        self,
        purchase_id: str,
        from_node: str,
        rating: float,
        comment: str = "",
        tags: Optional[List[str]] = None,
    ) -> Optional[CreditCredential]:
        """
        提交评价

        Args:
            purchase_id: 购买ID
            from_node: 评价方节点ID
            rating: 评分 1-5
            comment: 评价内容
            tags: 标签，如 ["准时", "货真价实"]

        Returns:
            信用凭证（如果成功）
        """
        record = self._find_record_by_purchase(purchase_id)
        if not record:
            return None

        # 判断是买家评价还是卖家评价
        is_buyer = from_node == record._buyer_id if hasattr(record, "_buyer_id") else True

        if is_buyer:
            record.buyer_rating = rating
            record.buyer_comment = comment
            record.buyer_tags = tags or []
        else:
            record.seller_rating = rating
            record.seller_comment = comment

        logger.info(f"[FulfillmentManager] 收到评价: {from_node} -> {rating}分")

        # 回调
        if self.on_rating_submitted:
            await self.on_rating_submitted(record, from_node, rating)

        # 检查是否双方都评价了
        if record.buyer_rating and record.seller_rating:
            # 生成信用凭证
            return await self._generate_credit_credential(record)

        return None

    async def _release_funds(self, record: FulfillmentRecord):
        """
        释放款项给卖家

        简化实现：记录放款事件
        实际应调用支付系统
        """
        logger.info(f"[FulfillmentManager] 款项已释放: {record.purchase_id}")

        # TODO: 集成真实支付系统
        # - 担保交易放款
        # - 加密货币转账

        if self.on_fulfillment_update:
            await self.on_fulfillment_update(record, "funds_released")

    async def _generate_credit_credential(
        self,
        record: FulfillmentRecord,
        auto_confirmed: bool = False,
    ) -> Optional[CreditCredential]:
        """
        生成信用凭证

        Args:
            record: 履约记录
            auto_confirmed: 是否为自动确认（负面评价）

        Returns:
            信用凭证
        """
        try:
            # 创建凭证
            credential = CreditCredential(
                credential_id=str(uuid.uuid4())[:12],
                from_node=record._buyer_id if hasattr(record, "_buyer_id") else "",
                to_node=record._seller_id if hasattr(record, "_seller_id") else "",
                deal_id=record.purchase_id,
                deal_amount=int(record._amount * 100) if hasattr(record, "_amount") else 0,
                rating=record.buyer_rating or 3.0,  # 默认3分
                comment=record.buyer_comment or "",
                tags=record.buyer_tags if not auto_confirmed else ["超时未确认"],
            )

            # 计算哈希
            credential.credential_hash = credential.compute_hash()

            logger.info(f"[FulfillmentManager] 生成信用凭证: {credential.credential_id}")

            # TODO: 存储到信用网络
            # if self.credit_system:
            #     await self.credit_system.add_credential(credential)

            return credential

        except Exception as e:
            logger.error(f"[FulfillmentManager] 信用凭证生成失败: {e}")
            return None

    async def _notify_buyer_shipped(self, record: FulfillmentRecord):
        """通知买家已发货"""
        logger.info(f"[FulfillmentManager] 通知买家发货: {record.purchase_id}")
        # TODO: 通过 P2P/消息系统通知买家

    def _find_record_by_purchase(self, purchase_id: str) -> Optional[FulfillmentRecord]:
        """通过购买ID查找履约记录"""
        for record in self.records.values():
            if record.purchase_id == purchase_id:
                return record
        return None

    def get_fulfillment(self, record_id: str) -> Optional[FulfillmentRecord]:
        """获取履约记录"""
        return self.records.get(record_id)

    def get_node_fulfillments(
        self,
        node_id: str,
        as_seller: bool = True,
    ) -> List[FulfillmentRecord]:
        """获取节点相关的履约记录"""
        result = []
        for record in self.records.values():
            if as_seller:
                if hasattr(record, "_seller_id") and record._seller_id == node_id:
                    result.append(record)
            else:
                if hasattr(record, "_buyer_id") and record._buyer_id == node_id:
                    result.append(record)
        return result


# ========== 物流追踪（简化实现）============

class SimpleLogisticsTracker:
    """
    简化物流追踪

    实际应集成快递100/菜鸟等API
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    async def query_tracking(
        self,
        tracking_number: str,
        carrier: str,
    ) -> Dict[str, Any]:
        """
        查询物流状态

        Args:
            tracking_number: 物流单号
            carrier: 承运商

        Returns:
            物流状态信息
        """
        # TODO: 集成真实物流 API
        # 目前返回模拟数据

        return {
            "status": "in_transit",
            "last_location": "上海分拨中心",
            "last_update": datetime.now().isoformat(),
            "estimated_delivery": (datetime.now() + timedelta(days=2)).isoformat(),
            "events": [
                {
                    "time": datetime.now().isoformat(),
                    "location": "上海分拨中心",
                    "description": "快件已发往目的地区",
                },
                {
                    "time": (datetime.now() - timedelta(hours=6)).isoformat(),
                    "location": "上海分拨中心",
                    "description": "快件到达上海分拨中心",
                },
                {
                    "time": (datetime.now() - timedelta(hours=12)).isoformat(),
                    "location": "卖家已发货",
                    "description": "商家已发货",
                },
            ],
        }


# ========== 便捷函数 ==========

async def create_fulfillment(
    node_id: str,
    purchase: InlinePurchase,
) -> FulfillmentRecord:
    """快捷函数：创建履约记录"""
    manager = FulfillmentManager(node_id)
    return await manager.create_fulfillment(purchase)


async def submit_shipping(
    node_id: str,
    purchase_id: str,
    tracking_number: str,
    carrier: str,
) -> bool:
    """快捷函数：提交发货"""
    manager = FulfillmentManager(node_id)
    return await manager.submit_tracking(purchase_id, tracking_number, carrier)


async def confirm_receipt(
    node_id: str,
    purchase_id: str,
    buyer_id: str,
) -> bool:
    """快捷函数：确认收货"""
    manager = FulfillmentManager(node_id)
    return await manager.confirm_delivery(purchase_id, buyer_id)


async def rate_transaction(
    node_id: str,
    purchase_id: str,
    from_node: str,
    rating: float,
    comment: str = "",
    tags: Optional[List[str]] = None,
) -> Optional[CreditCredential]:
    """快捷函数：评价交易"""
    manager = FulfillmentManager(node_id)
    return await manager.submit_rating(purchase_id, from_node, rating, comment, tags)
