# core/flash_listing/inline_purchase.py
# 聊天内嵌购买模块
#
# 在聊天窗口内完成购买流程：
# - 订单生成
# - 支付路由
# - P2P 交易握手

import asyncio
import logging
import json
import uuid
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime

from .models import (
    InlinePurchase,
    PurchaseStatus,
    PaymentMethod,
)

logger = logging.getLogger(__name__)


class InlinePurchaseManager:
    """
    聊天内嵌购买管理器

    核心功能：
    1. 创建购买订单
    2. 处理支付
    3. P2P 交易握手
    4. 订单状态同步
    """

    def __init__(self, node_id: str, config: Optional[Dict] = None):
        """
        Args:
            node_id: 当前节点ID
            config: 配置字典
        """
        self.node_id = node_id
        self.config = config or {}

        # 订单存储
        self.purchases: Dict[str, InlinePurchase] = {}

        # P2P 连接（待集成）
        self.p2p_client = None

        # 支付处理器（待集成）
        self.payment_handlers: Dict[PaymentMethod, Callable] = {}

        # 回调
        self.on_payment_request: Optional[Callable] = None
        self.on_order_update: Optional[Callable] = None

    async def create_purchase(
        self,
        listing_id: str,
        buyer_id: str,
        seller_id: str,
        product_info: Dict[str, Any],
        listed_price: float,
    ) -> InlinePurchase:
        """
        创建购买订单

        Args:
            listing_id: 商品ID
            buyer_id: 买家ID
            seller_id: 卖家ID
            product_info: 商品信息
            listed_price: 标价

        Returns:
            购买订单
        """
        purchase_id = str(uuid.uuid4())[:12]

        purchase = InlinePurchase(
            purchase_id=purchase_id,
            listing_id=listing_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            product_title=product_info.get("title", ""),
            product_link=product_info.get("product_link", ""),
            product_image=product_info.get("image_url"),
            listed_price=listed_price,
            selected_payment=PaymentMethod.ESCROW,  # 默认担保交易
            payment_status=PurchaseStatus.PENDING_PAYMENT,
        )

        # 计算订单哈希
        purchase.order_hash = purchase.compute_order_hash()

        # 存储
        self.purchases[purchase_id] = purchase

        logger.info(f"[InlinePurchaseManager] 创建购买订单: {purchase_id}")
        return purchase

    async def initiate_payment(
        self,
        purchase_id: str,
        payment_method: PaymentMethod,
        amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        发起支付

        Args:
            purchase_id: 购买ID
            payment_method: 支付方式
            amount: 支付金额（可选，默认使用标价）

        Returns:
            支付结果
        """
        purchase = self.purchases.get(purchase_id)
        if not purchase:
            raise ValueError(f"订单不存在: {purchase_id}")

        # 更新支付方式和金额
        purchase.selected_payment = payment_method
        if amount:
            purchase.negotiated_price = amount

        final_amount = amount or purchase.listed_price

        # 调用支付处理器
        if payment_method in self.payment_handlers:
            handler = self.payment_handlers[payment_method]
            result = await handler(purchase, final_amount)
            return result

        # 默认实现：生成支付链接
        payment_result = await self._generate_payment_link(purchase, payment_method, final_amount)

        # 更新状态
        purchase.payment_status = PurchaseStatus.PAID if payment_result["success"] else PurchaseStatus.PENDING_PAYMENT

        return payment_result

    async def _generate_payment_link(
        self,
        purchase: InlinePurchase,
        method: PaymentMethod,
        amount: float,
    ) -> Dict[str, Any]:
        """
        生成支付链接/二维码

        目前返回模拟数据，后续集成真实支付
        """
        # TODO: 集成真实支付 SDK（微信/支付宝）
        payment_id = f"pay_{uuid.uuid4().hex[:16]}"

        result = {
            "success": True,
            "payment_id": payment_id,
            "payment_url": f"payment://{method.value}/{payment_id}",
            "qr_code_data": f"{method.value}:{payment_id}",
            "amount": amount,
            "expire_time": datetime.now().timestamp() + 1800,  # 30分钟过期
        }

        logger.info(f"[InlinePurchaseManager] 生成支付链接: {result['payment_url']}")
        return result

    async def confirm_payment(
        self,
        purchase_id: str,
        payment_proof: Dict[str, Any],
    ) -> bool:
        """
        确认支付完成

        Args:
            purchase_id: 购买ID
            payment_proof: 支付凭证

        Returns:
            是否成功
        """
        purchase = self.purchases.get(purchase_id)
        if not purchase:
            return False

        # 验证支付凭证
        if self._verify_payment_proof(purchase, payment_proof):
            purchase.payment_status = PurchaseStatus.PAID
            purchase.paid_at = datetime.now().timestamp()

            # 通知卖家
            await self._notify_seller_payment(purchase)

            logger.info(f"[InlinePurchaseManager] 支付确认: {purchase_id}")
            return True

        return False

    async def submit_shipping_info(
        self,
        purchase_id: str,
        shipping_address: str,
        invoice_info: Optional[str] = None,
    ) -> bool:
        """
        提交收货信息（买家）

        Args:
            purchase_id: 购买ID
            shipping_address: 收货地址
            invoice_info: 发票信息

        Returns:
            是否成功
        """
        purchase = self.purchases.get(purchase_id)
        if not purchase:
            return False

        purchase.shipping_address = shipping_address
        purchase.invoice_info = invoice_info

        # 加密存储（简化实现）
        logger.info(f"[InlinePurchaseManager] 收货信息已提交: {purchase_id}")

        # 通知卖家
        await self._notify_seller_shipping(purchase)

        return True

    async def start_negotiation(
        self,
        purchase_id: str,
        counter_price: float,
    ) -> bool:
        """
        开始还价/议价

        Args:
            purchase_id: 购买ID
            counter_price: 还价金额

        Returns:
            是否成功
        """
        purchase = self.purchases.get(purchase_id)
        if not purchase:
            return False

        purchase.negotiated_price = counter_price
        purchase.payment_status = PurchaseStatus.NEGOTIATING

        logger.info(f"[InlinePurchaseManager] 还价: {purchase_id} -> {counter_price}")

        # TODO: 通知卖家还价
        return True

    async def agree_on_price(
        self,
        purchase_id: str,
    ) -> bool:
        """
        接受当前价格，达成协议

        Args:
            purchase_id: 购买ID

        Returns:
            是否成功
        """
        purchase = self.purchases.get(purchase_id)
        if not purchase:
            return False

        purchase.payment_status = PurchaseStatus.PENDING_PAYMENT

        logger.info(f"[InlinePurchaseManager] 价格协议达成: {purchase_id}")

        return True

    def _verify_payment_proof(
        self,
        purchase: InlinePurchase,
        proof: Dict[str, Any],
    ) -> bool:
        """验证支付凭证"""
        # TODO: 实现真实的支付验证
        # 目前简单检查
        return proof.get("status") == "success"

    async def _notify_seller_payment(self, purchase: InlinePurchase):
        """通知卖家买家已付款"""
        # TODO: 通过 P2P 网络通知卖家
        logger.info(f"[InlinePurchaseManager] 通知卖家付款: {purchase.seller_id}")

    async def _notify_seller_shipping(self, purchase: InlinePurchase):
        """通知卖家买家已填写收货信息"""
        # TODO: 通过 P2P 网络通知卖家
        logger.info(f"[InlinePurchaseManager] 通知卖家发货: {purchase.seller_id}")

    def get_purchase(self, purchase_id: str) -> Optional[InlinePurchase]:
        """获取购买订单"""
        return self.purchases.get(purchase_id)

    def get_user_purchases(self, user_id: str, as_buyer: bool = True) -> List[InlinePurchase]:
        """获取用户的购买/销售订单"""
        result = []
        for p in self.purchases.values():
            if as_buyer and p.buyer_id == user_id:
                result.append(p)
            elif not as_buyer and p.seller_id == user_id:
                result.append(p)
        return result

    def to_dict(self, purchase: InlinePurchase) -> Dict[str, Any]:
        """转换购买订单为字典"""
        data = asdict(purchase)
        data["payment_status"] = purchase.payment_status.value
        data["selected_payment"] = purchase.selected_payment.value
        return data


# ========== 支付处理器 ==========

class PaymentRouter:
    """
    支付路由

    根据支付方式路由到不同的支付处理器
    """

    # 支付方式对应的处理函数
    HANDLERS = {
        PaymentMethod.WECHAT_PAY: "_handle_wechat",
        PaymentMethod.ALIPAY: "_handle_alipay",
        PaymentMethod.BANK_TRANSFER: "_handle_bank",
        PaymentMethod.CRYPTO: "_handle_crypto",
        PaymentMethod.ESCROW: "_handle_escrow",
        PaymentMethod.COD: "_handle_cod",
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    async def route(
        self,
        method: PaymentMethod,
        purchase: InlinePurchase,
        amount: float,
    ) -> Dict[str, Any]:
        """
        路由支付请求

        Args:
            method: 支付方式
            purchase: 购买订单
            amount: 金额

        Returns:
            支付结果
        """
        handler_name = self.HANDLERS.get(method)
        if not handler_name:
            return {"success": False, "error": f"不支持的支付方式: {method}"}

        handler = getattr(self, handler_name)
        return await handler(purchase, amount)

    async def _handle_wechat(
        self,
        purchase: InlinePurchase,
        amount: float,
    ) -> Dict[str, Any]:
        """处理微信支付"""
        # TODO: 集成微信支付 H5 SDK
        return {
            "success": True,
            "payment_url": f"weixin://wxpay/bizpayurl?pr={amount}",
            "qr_code_data": f"wxp://{purchase.purchase_id}",
        }

    async def _handle_alipay(
        self,
        purchase: InlinePurchase,
        amount: float,
    ) -> Dict[str, Any]:
        """处理支付宝"""
        # TODO: 集成支付宝 H5 SDK
        return {
            "success": True,
            "payment_url": f"alipay://alipay.com?order={purchase.purchase_id}",
            "qr_code_data": f"alipay://{purchase.purchase_id}",
        }

    async def _handle_bank(
        self,
        purchase: InlinePurchase,
        amount: float,
    ) -> Dict[str, Any]:
        """处理银行转账"""
        return {
            "success": True,
            "instructions": "请转账至指定账户，转账时备注订单号",
            "account_info": "****1234",  # 脱敏
        }

    async def _handle_crypto(
        self,
        purchase: InlinePurchase,
        amount: float,
    ) -> Dict[str, Any]:
        """处理加密货币"""
        # TODO: 集成 BTC/Lightning/USDT
        return {
            "success": True,
            "crypto_address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
            "amount_btc": amount / 50000,  # 简化计算
        }

    async def _handle_escrow(
        self,
        purchase: InlinePurchase,
        amount: float,
    ) -> Dict[str, Any]:
        """处理担保交易"""
        return {
            "success": True,
            "escrow_id": f"escrow_{purchase.purchase_id}",
            "message": "款项由平台担保，确认收货后放款给卖家",
        }

    async def _handle_cod(
        self,
        purchase: InlinePurchase,
        amount: float,
    ) -> Dict[str, Any]:
        """处理货到付款"""
        return {
            "success": True,
            "message": "货到付款，请准备好现金",
        }


# ========== 便捷函数 ==========

async def create_purchase_order(
    node_id: str,
    listing_id: str,
    buyer_id: str,
    seller_id: str,
    product_info: Dict[str, Any],
    price: float,
) -> InlinePurchase:
    """快捷函数：创建购买订单"""
    manager = InlinePurchaseManager(node_id)
    return await manager.create_purchase(listing_id, buyer_id, seller_id, product_info, price)


async def initiate_payment(
    node_id: str,
    purchase_id: str,
    payment_method: PaymentMethod,
    amount: Optional[float] = None,
) -> Dict[str, Any]:
    """快捷函数：发起支付"""
    manager = InlinePurchaseManager(node_id)
    return await manager.initiate_payment(purchase_id, payment_method, amount)
