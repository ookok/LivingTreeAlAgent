# -*- coding: utf-8 -*-
"""
统一佣金系统 - 支付服务工厂
Unified Commission System - Payment Service Factory

创建和管理多种支付服务实例
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .config_manager import get_config_manager, UnifiedConfigManager
from .calculator import get_calculator
from .models import (
    ModuleType,
    PaymentProvider,
    PaymentOrder,
    OrderStatus,
    Refund,
    RefundStatus,
    TestResult
)

logger = logging.getLogger(__name__)


class PaymentService(ABC):
    """支付服务抽象基类"""
    
    def __init__(self, config: Dict[str, Any], provider: PaymentProvider):
        self.config = config
        self.provider = provider
        self.is_sandbox = config.get("sandbox", True)
    
    @abstractmethod
    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建支付订单
        返回: {"success": bool, "order_id": str, "payment_data": Any, "qr_code": str}
        """
        pass
    
    @abstractmethod
    def query_order(self, order_id: str) -> Dict[str, Any]:
        """
        查询订单状态
        返回: {"status": str, "paid_at": str, ...}
        """
        pass
    
    @abstractmethod
    def refund(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        申请退款
        返回: {"success": bool, "refund_id": str, ...}
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """
        测试支付连接
        """
        pass


class MockPaymentService(PaymentService):
    """
    模拟支付服务（用于测试和沙箱环境）
    """
    
    def __init__(self, config: Dict[str, Any], provider: PaymentProvider):
        super().__init__(config, provider)
        self._orders: Dict[str, PaymentOrder] = {}
        self._refunds: Dict[str, Refund] = {}
    
    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建模拟订单"""
        order_id = order_data.get("order_id", f"MOCK_{int(time.time())}")
        
        # 创建订单对象
        order = PaymentOrder(
            order_id=order_id,
            module_type=ModuleType(order_data.get("module_type", "deep_search")),
            provider=self.provider,
            original_amount=order_data.get("original_amount", 0),
            commission_amount=order_data.get("commission_amount", 0),
            total_amount=order_data.get("total_amount", 0),
            status=OrderStatus.PENDING,
            subject=order_data.get("subject", ""),
            body=order_data.get("body", ""),
            user_id=order_data.get("user_id", "")
        )
        
        self._orders[order_id] = order
        
        # 模拟支付二维码
        qr_code = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={order_id}"
        
        logger.info(f"[Mock] 创建订单: {order_id}")
        
        return {
            "success": True,
            "order_id": order_id,
            "payment_data": {
                "provider": self.provider.value,
                "amount": order.total_amount,
                "subject": order.subject
            },
            "qr_code": qr_code,
            "expire_time": int(time.time()) + 1800  # 30分钟过期
        }
    
    def simulate_payment(self, order_id: str) -> Dict[str, Any]:
        """
        模拟支付成功回调（仅用于测试）
        """
        if order_id in self._orders:
            order = self._orders[order_id]
            order.status = OrderStatus.PAID
            from datetime import datetime
            order.paid_at = datetime.now()
            logger.info(f"[Mock] 模拟支付成功: {order_id}")
            return {"success": True, "status": "PAID"}
        
        return {"success": False, "message": "订单不存在"}
    
    def query_order(self, order_id: str) -> Dict[str, Any]:
        """查询模拟订单"""
        if order_id in self._orders:
            order = self._orders[order_id]
            return {
                "success": True,
                "order_id": order_id,
                "status": order.status.value,
                "paid_at": order.paid_at.isoformat() if order.paid_at else None,
                "total_amount": order.total_amount
            }
        
        return {
            "success": False,
            "message": "订单不存在"
        }
    
    def refund(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """申请模拟退款"""
        order_id = refund_data.get("order_id")
        refund_amount = refund_data.get("refund_amount", 0)
        
        if order_id not in self._orders:
            return {"success": False, "message": "订单不存在"}
        
        refund_id = f"REFUND_{int(time.time())}"
        
        refund = Refund(
            refund_id=refund_id,
            order_id=order_id,
            refund_amount=refund_amount,
            refund_type=refund_data.get("refund_type", "USER_CANCEL"),
            reason=refund_data.get("reason", ""),
            status=RefundStatus.COMPLETED  # 模拟直接完成
        )
        
        self._refunds[refund_id] = refund
        
        # 更新订单状态
        self._orders[order_id].status = OrderStatus.REFUNDED
        
        return {
            "success": True,
            "refund_id": refund_id,
            "refund_amount": refund_amount
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """测试模拟连接"""
        return {
            "success": True,
            "message": f"模拟{self.provider.value}支付服务连接正常",
            "sandbox": self.is_sandbox
        }
    
    def get_order(self, order_id: str) -> Optional[PaymentOrder]:
        """获取订单对象"""
        return self._orders.get(order_id)
    
    def list_orders(self) -> list:
        """列出所有订单"""
        return [order.to_dict() for order in self._orders.values()]


class WeChatPayService(PaymentService):
    """
    微信支付服务
    
    注意: 需要配置 app_id, mch_id, api_key
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, PaymentProvider.WECHAT)
        self.app_id = config.get("app_id", "")
        self.mch_id = config.get("mch_id", "")
        self.api_key = config.get("api_key", "")
    
    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建微信支付订单
        
        实际实现需要调用微信支付API:
        https://api.mch.weixin.qq.com/pay/unifiedorder
        """
        # 检查是否配置
        if not self.app_id or not self.mch_id:
            logger.warning("微信支付未配置，使用模拟服务")
            mock = MockPaymentService(self.config, self.provider)
            return mock.create_order(order_data)
        
        # TODO: 实现真实的微信支付调用
        # 实际实现代码:
        # url = "https://api.mch.weixin.qq.com/pay/unifiedorder"
        # params = {
        #     "appid": self.app_id,
        #     "mch_id": self.mch_id,
        #     "nonce_str": generate_nonce_str(),
        #     "body": order_data.get("subject", ""),
        #     "out_trade_no": order_data.get("order_id", ""),
        #     "total_fee": int(order_data.get("total_amount", 0) * 100),  # 单位：分
        #     "spbill_create_ip": "127.0.0.1",
        #     "notify_url": self.config.get("notify_url", ""),
        #     "trade_type": "NATIVE"
        # }
        # sign = self._generate_sign(params)
        # params["sign"] = sign
        
        logger.info(f"[WeChat] 创建订单: {order_data.get('order_id')}")
        
        # 返回模拟数据
        return {
            "success": True,
            "order_id": order_data.get("order_id"),
            "payment_data": {},
            "qr_code": f"weixin://wxpay/bizpayurl?pr=mock",
            "expire_time": int(time.time()) + 1800
        }
    
    def query_order(self, order_id: str) -> Dict[str, Any]:
        """查询微信订单"""
        # TODO: 实现真实的订单查询
        return {
            "success": True,
            "order_id": order_id,
            "status": "NOTFOUND"
        }
    
    def refund(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """申请微信退款"""
        # TODO: 实现真实的退款申请
        return {
            "success": True,
            "refund_id": f"REFUND_{order_id}"
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """测试微信支付连接"""
        if not self.app_id:
            return {
                "success": False,
                "message": "微信支付未配置app_id"
            }
        
        return {
            "success": True,
            "message": "微信支付配置正常",
            "app_id": self.app_id[:8] + "****"
        }


class AlipayService(PaymentService):
    """
    支付宝支付服务
    
    注意: 需要配置 app_id, app_private_key, alipay_public_key
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, PaymentProvider.ALIPAY)
        self.app_id = config.get("app_id", "")
    
    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建支付宝订单
        
        实际实现需要调用支付宝API
        """
        if not self.app_id:
            logger.warning("支付宝未配置，使用模拟服务")
            mock = MockPaymentService(self.config, self.provider)
            return mock.create_order(order_data)
        
        # TODO: 实现真实的支付宝调用
        logger.info(f"[Alipay] 创建订单: {order_data.get('order_id')}")
        
        return {
            "success": True,
            "order_id": order_data.get("order_id"),
            "payment_data": {},
            "qr_code": f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=alipay",
            "expire_time": int(time.time()) + 1800
        }
    
    def query_order(self, order_id: str) -> Dict[str, Any]:
        """查询支付宝订单"""
        return {
            "success": True,
            "order_id": order_id,
            "status": "NOTFOUND"
        }
    
    def refund(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """申请支付宝退款"""
        return {
            "success": True,
            "refund_id": f"REFUND_{order_id}"
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """测试支付宝连接"""
        if not self.app_id:
            return {
                "success": False,
                "message": "支付宝未配置app_id"
            }
        
        return {
            "success": True,
            "message": "支付宝配置正常",
            "app_id": self.app_id[:8] + "****"
        }


class PaymentServiceFactory:
    """
    支付服务工厂
    根据配置创建对应的支付服务实例
    """
    
    def __init__(self, config_manager: Optional[UnifiedConfigManager] = None):
        self.config = config_manager or get_config_manager()
        self._services: Dict[str, PaymentService] = {}
    
    def get_payment_service(self, provider: str = None) -> PaymentService:
        """
        获取支付服务实例
        
        Args:
            provider: 支付提供商 (wechat, alipay, internal)
        """
        if provider is None:
            provider = self.config.get_config_value("payment.default_provider", "wechat")
        
        # 如果已缓存，直接返回
        if provider in self._services:
            return self._services[provider]
        
        # 根据提供商创建服务
        if provider == "wechat":
            wechat_config = self.config.get_payment_config("wechat")
            if wechat_config.get("enabled", False) and wechat_config.get("app_id"):
                service = WeChatPayService(wechat_config)
            else:
                service = MockPaymentService(wechat_config, PaymentProvider.WECHAT)
        elif provider == "alipay":
            alipay_config = self.config.get_payment_config("alipay")
            if alipay_config.get("enabled", False) and alipay_config.get("app_id"):
                service = AlipayService(alipay_config)
            else:
                service = MockPaymentService(alipay_config, PaymentProvider.ALIPAY)
        else:
            # 默认使用模拟服务
            service = MockPaymentService({}, PaymentProvider(provider))
        
        self._services[provider] = service
        return service
    
    def create_order(
        self,
        module: str,
        amount: float,
        user_id: str = "",
        subject: str = "",
        body: str = ""
    ) -> Dict[str, Any]:
        """
        创建支付订单（快捷方法）
        """
        calculator = get_calculator(self.config)
        commission_result = calculator.calculate_commission(module, amount)
        
        # 获取提供商
        default_provider = self.config.get_config_value("payment.default_provider", "wechat")
        service = self.get_payment_service(default_provider)
        
        order_data = {
            "module_type": module,
            "original_amount": amount,
            "commission_amount": commission_result.commission_amount,
            "total_amount": commission_result.total_amount,
            "subject": subject or f"{module}打赏",
            "body": body or f"用户{user_id}对{module}的打赏",
            "user_id": user_id
        }
        
        return service.create_order(order_data)
    
    def query_order(
        self,
        order_id: str,
        provider: str = None
    ) -> Dict[str, Any]:
        """查询订单状态"""
        service = self.get_payment_service(provider)
        return service.query_order(order_id)
    
    def refund_order(
        self,
        order_id: str,
        refund_amount: float,
        reason: str = "",
        provider: str = None
    ) -> Dict[str, Any]:
        """申请退款"""
        service = self.get_payment_service(provider)
        
        refund_data = {
            "order_id": order_id,
            "refund_amount": refund_amount,
            "reason": reason
        }
        
        return service.refund(refund_data)
    
    def test_connection(self, provider: str = None) -> Dict[str, Any]:
        """测试支付连接"""
        service = self.get_payment_service(provider)
        return service.test_connection()
    
    def clear_cache(self):
        """清除服务缓存"""
        self._services.clear()


# 全局工厂实例
_factory_instance = None

def get_payment_factory(config_manager: Optional[UnifiedConfigManager] = None) -> PaymentServiceFactory:
    """获取支付工厂实例"""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = PaymentServiceFactory(config_manager)
    return _factory_instance
