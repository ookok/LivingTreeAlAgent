# -*- coding: utf-8 -*-
"""
统一佣金系统 - 基础模块抽象
Unified Commission System - Base Module

定义所有打赏模块的抽象基类和模块注册机制
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type

from ..models import ModuleType, ModuleConfig, PaymentOrder
from ..config_manager import get_config_manager

logger = logging.getLogger(__name__)


class BaseModule(ABC):
    """
    模块抽象基类
    
    所有打赏模块继承此类
    实现支付成功/退款等业务逻辑
    """
    
    def __init__(
        self,
        module_name: str,
        config_manager=None
    ):
        self.module_name = module_name
        self.config = config_manager or get_config_manager()
        self.module_config: ModuleConfig = self.config.get_module_config(module_name)
    
    @abstractmethod
    def get_module_info(self) -> Dict[str, Any]:
        """
        获取模块信息
        """
        pass
    
    def validate_order(self, order_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证订单数据
        
        默认实现只验证金额范围
        子类可以重写添加特定验证
        """
        # 验证金额
        is_valid, error_msg = self._validate_amount(
            order_data.get("amount", 0)
        )
        
        if not is_valid:
            return False, error_msg
        
        # 调用子类特定验证
        return self._validate_module_specific(order_data)
    
    def _validate_amount(self, amount: float) -> Tuple[bool, str]:
        """验证金额范围"""
        if amount <= 0:
            return False, "金额必须大于0"
        
        if amount < self.module_config.min_amount:
            return False, f"金额不能低于 {self.module_config.min_amount} 元"
        
        if amount > self.module_config.max_amount:
            return False, f"金额不能超过 {self.module_config.max_amount} 元"
        
        return True, ""
    
    def _validate_module_specific(self, order_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        模块特定验证
        子类可重写
        """
        return True, ""
    
    @abstractmethod
    def process_payment_success(self, order: PaymentOrder) -> Dict[str, Any]:
        """
        处理支付成功
        模块特定的业务逻辑
        """
        pass
    
    @abstractmethod
    def process_refund(self, order: PaymentOrder) -> Dict[str, Any]:
        """
        处理退款
        模块特定的退款逻辑
        """
        pass
    
    def get_features_by_amount(self, amount: float) -> List[str]:
        """
        根据打赏金额获取解锁的功能列表
        """
        features = []
        features.append("去广告")
        
        if amount >= 10:
            features.append("基础高级功能")
        if amount >= 50:
            features.append("中级高级功能")
        if amount >= 100:
            features.append("高级功能")
        if amount >= 200:
            features.append("专业级功能")
        
        return features
    
    def get_quota_by_amount(self, amount: float) -> int:
        """
        根据打赏金额计算配额
        """
        return int(amount * 10)
    
    def export_module_config(self) -> Dict[str, Any]:
        """导出模块配置"""
        return {
            "module_name": self.module_name,
            "config": self.module_config.to_dict(),
            "info": self.get_module_info()
        }


# 模块注册表
_module_registry: Dict[str, Type[BaseModule]] = {}


def register_module(module_name: str, module_class: Type[BaseModule]):
    """注册模块"""
    _module_registry[module_name] = module_class
    logger.info(f"模块已注册: {module_name} -> {module_class.__name__}")


def get_module_class(module_name: str) -> Optional[Type[BaseModule]]:
    """获取模块类"""
    return _module_registry.get(module_name)


def create_module(module_name: str, config_manager=None) -> Optional[BaseModule]:
    """创建模块实例"""
    module_class = get_module_class(module_name)
    if module_class:
        return module_class(config_manager)
    logger.warning(f"模块未注册: {module_name}")
    return None


def list_registered_modules() -> List[str]:
    """列出已注册的所有模块"""
    return list(_module_registry.keys())


def load_modules_from_config(config_manager=None) -> Dict[str, BaseModule]:
    """从配置加载所有已启用的模块"""
    config = config_manager or get_config_manager()
    modules = {}
    
    for module_type in ModuleType:
        module_name = module_type.value
        module_config = config.get_module_config(module_name)
        
        if module_config.enabled:
            module_instance = create_module(module_name, config)
            if module_instance:
                modules[module_name] = module_instance
    
    return modules
