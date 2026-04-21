# -*- coding: utf-8 -*-
"""
统一佣金系统 - 核心系统
Unified Commission System - Core System

统一的佣金系统入口，整合所有模块
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config_manager import get_config_manager, UnifiedConfigManager
from .calculator import get_calculator, CommissionCalculator
from .database import get_commission_database, CommissionDatabase
from .payment_factory import get_payment_factory, PaymentServiceFactory
from .settlement import get_settlement_service, get_refund_service
from .models import (
    ModuleType, PaymentProvider, OrderStatus,
    PaymentOrder, CommissionResult
)
from .modules import load_modules_from_config, create_module, list_registered_modules

logger = logging.getLogger(__name__)


class CommissionSystem:
    """
    统一佣金系统
    
    整合配置管理、佣金计算、支付、结算、退款等所有功能
    """
    
    _instance = None
    
    def __new__(cls, config_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: str = None):
        if self._initialized:
            return
        
        # 初始化各组件
        self.config_manager = get_config_manager(config_path)
        self.config_manager.load_config()
        
        self.calculator = get_calculator(self.config_manager)
        self.database = get_commission_database()
        self.payment_factory = get_payment_factory(self.config_manager)
        
        # 加载模块
        self.modules = load_modules_from_config(self.config_manager)
        
        self._initialized = True
        logger.info("统一佣金系统初始化完成")
    
    # ========== 配置管理 ==========
    
    def get_module_config(self, module_name: str) -> Dict[str, Any]:
        """获取模块配置"""
        config = self.config_manager.get_module_config(module_name)
        return config.to_dict() if config else {}
    
    def get_all_modules_config(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模块配置"""
        configs = {}
        for module_name in list_registered_modules():
            configs[module_name] = self.get_module_config(module_name)
        return configs
    
    def update_module_config(self, module_name: str, config: Dict[str, Any]) -> bool:
        """更新模块配置"""
        current = self.config_manager.get_all_config()
        if "modules" not in current:
            current["modules"] = {}
        current["modules"][module_name] = config
        return self.config_manager.set_section("modules", current["modules"])
    
    # ========== 佣金计算 ==========
    
    def calculate_commission(
        self,
        module: str,
        amount: float,
        currency: str = "CNY"
    ) -> CommissionResult:
        """计算佣金"""
        return self.calculator.calculate_commission(module, amount, currency)
    
    def get_commission_preview(
        self,
        module: str,
        amount: float
    ) -> Dict[str, Any]:
        """获取佣金预览"""
        return self.calculator.get_commission_preview(module, amount)
    
    # ========== 订单管理 ==========
    
    def create_order(
        self,
        module: str,
        amount: float,
        user_id: str = "",
        provider: str = None,
        subject: str = "",
        body: str = ""
    ) -> Dict[str, Any]:
        """
        创建支付订单
        
        Returns:
            {
                "success": bool,
                "order_id": str,
                "qr_code": str,
                "expire_time": int,
                "commission_preview": {...}
            }
        """
        try:
            # 计算佣金
            commission_result = self.calculate_commission(module, amount)
            
            # 验证订单
            module_instance = create_module(module, self.config_manager)
            if module_instance:
                is_valid, error_msg = module_instance.validate_order({"amount": amount})
                if not is_valid:
                    return {"success": False, "message": error_msg}
            
            # 获取支付服务
            if provider is None:
                provider = self.config_manager.get_config_value("payment.default_provider", "wechat")
            
            payment_service = self.payment_factory.get_payment_service(provider)
            
            # 创建订单数据
            order_data = {
                "module_type": module,
                "original_amount": amount,
                "commission_amount": commission_result.commission_amount,
                "total_amount": commission_result.total_amount,
                "subject": subject or f"{module}打赏",
                "body": body or f"用户{user_id}对{module}的打赏",
                "user_id": user_id
            }
            
            # 创建支付订单
            result = payment_service.create_order(order_data)
            
            if result.get("success"):
                # 保存订单到数据库
                order = PaymentOrder(
                    module_type=ModuleType(module),
                    provider=PaymentProvider(provider),
                    original_amount=amount,
                    commission_amount=commission_result.commission_amount,
                    total_amount=commission_result.total_amount,
                    status=OrderStatus.PENDING,
                    subject=order_data["subject"],
                    body=order_data["body"],
                    user_id=user_id
                )
                order.order_id = result.get("order_id", order.order_id)
                self.database.save_order(order)
                
                # 添加佣金预览
                result["commission_preview"] = self.get_commission_preview(module, amount)
                
                logger.info(f"创建订单成功: {order.order_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"创建订单失败: {e}")
            return {"success": False, "message": str(e)}
    
    def get_order(self, order_id: str) -> Optional[PaymentOrder]:
        """获取订单"""
        return self.database.get_order(order_id)
    
    def list_orders(
        self,
        user_id: str = None,
        status: str = None,
        limit: int = 100
    ) -> List[PaymentOrder]:
        """列出订单"""
        from .models import OrderStatus as OS
        status_enum = OS(status) if status else None
        return self.database.list_orders(user_id, status_enum, limit)
    
    def update_order_status(
        self,
        order_id: str,
        status: str,
        paid_at: datetime = None
    ) -> bool:
        """更新订单状态"""
        from .models import OrderStatus as OS
        return self.database.update_order_status(order_id, OS(status), paid_at)
    
    # ========== 支付处理 ==========
    
    def process_payment_success(self, order_id: str) -> Dict[str, Any]:
        """
        处理支付成功
        
        1. 更新订单状态
        2. 调用模块特定逻辑
        3. 创建结算记录
        """
        try:
            order = self.database.get_order(order_id)
            if not order:
                return {"success": False, "message": "订单不存在"}
            
            # 更新状态
            order.status = OrderStatus.PAID
            order.paid_at = datetime.now()
            self.database.save_order(order)
            
            # 调用模块特定逻辑
            module = create_module(order.module_type.value, self.config_manager)
            module_result = None
            if module:
                module_result = module.process_payment_success(order)
            
            # 创建结算
            settlement_service = get_settlement_service()
            settlement = settlement_service.create_settlement(order)
            settlement_service.process_settlement(settlement.settlement_id)
            
            logger.info(f"支付成功处理完成: {order_id}")
            
            return {
                "success": True,
                "message": "支付成功",
                "order_id": order_id,
                "module_result": module_result,
                "settlement_id": settlement.settlement_id
            }
            
        except Exception as e:
            logger.error(f"处理支付成功失败: {e}")
            return {"success": False, "message": str(e)}
    
    # ========== 退款处理 ==========
    
    def refund_order(
        self,
        order_id: str,
        reason: str = "",
        refund_type: str = "USER_CANCEL"
    ) -> Dict[str, Any]:
        """申请退款"""
        refund_service = get_refund_service()
        return refund_service.create_refund(order_id, reason=reason, refund_type=refund_type)
    
    # ========== 统计 ==========
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.database.get_order_statistics()
        
        # 添加模块统计
        module_stats = {}
        for module_type in ModuleType:
            orders = self.database.list_orders(status=OrderStatus.PAID)
            module_orders = [o for o in orders if o.module_type == module_type]
            if module_orders:
                module_stats[module_type.value] = {
                    "order_count": len(module_orders),
                    "total_amount": sum(o.total_amount for o in module_orders),
                    "total_commission": sum(o.commission_amount for o in module_orders)
                }
        
        stats["module_stats"] = module_stats
        return stats
    
    # ========== 工具方法 ==========
    
    def get_payment_qrcode(self, order_id: str) -> Optional[str]:
        """获取支付二维码URL"""
        payment_service = self.payment_factory.get_payment_service()
        order = self.database.get_order(order_id)
        if order:
            result = payment_service.query_order(order_id)
            if result.get("success"):
                return result.get("qr_code")
        return None
    
    def test_payment_connection(self, provider: str = None) -> Dict[str, Any]:
        """测试支付连接"""
        return self.payment_factory.test_connection(provider)
    
    def export_config(self, format: str = "yaml") -> str:
        """导出配置"""
        return self.config_manager.export_config(format)
    
    def import_config(self, config_data: str, format: str = "yaml") -> bool:
        """导入配置"""
        return self.config_manager.import_config(config_data, format)
    
    def save_config(self) -> bool:
        """保存配置"""
        return self.config_manager.save_config()


# 全局系统实例
_system_instance = None


def get_commission_system(config_path: str = None) -> CommissionSystem:
    """获取佣金系统单例"""
    global _system_instance
    if _system_instance is None:
        _system_instance = CommissionSystem(config_path)
    return _system_instance
