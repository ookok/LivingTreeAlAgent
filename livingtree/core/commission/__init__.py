"""
统一佣金系统 (Unified Commission System)

支持多模块（深度搜索、创作、股票期货、游戏、IDE）的统一佣金配置与管理
"""

from .commission_system import CommissionSystem, get_commission_system
from .models import ModuleType, PaymentProvider, SettlementStatus, RefundStatus, OrderStatus, PaymentOrder, Settlement, Refund, ModuleConfig, CommissionResult
from .config_manager import get_config_manager, UnifiedConfigManager
from .calculator import get_calculator, CommissionCalculator
from .database import get_commission_database, CommissionDatabase
from .payment_factory import get_payment_factory, PaymentServiceFactory
from .settlement import get_settlement_service, get_refund_service
from .modules import BaseModule, register_module, create_module, list_registered_modules, load_modules_from_config

__version__ = "2.0.0"
__all__ = [
    "CommissionSystem", "get_commission_system",
    "ModuleType", "PaymentProvider", "SettlementStatus", "RefundStatus", "OrderStatus",
    "PaymentOrder", "Settlement", "Refund", "ModuleConfig", "CommissionResult",
    "get_config_manager", "UnifiedConfigManager",
    "get_calculator", "CommissionCalculator",
    "get_commission_database", "CommissionDatabase",
    "get_payment_factory", "PaymentServiceFactory",
    "get_settlement_service", "get_refund_service",
    "BaseModule", "register_module", "create_module", "list_registered_modules", "load_modules_from_config",
]
