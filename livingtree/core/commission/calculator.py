# -*- coding: utf-8 -*-
"""
统一佣金系统 - 佣金计算引擎
Unified Commission System - Commission Calculator

支持多模块、可配置的佣金计算
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional, Tuple

from .config_manager import get_config_manager, UnifiedConfigManager
from .models import (
    ModuleType,
    CommissionResult,
    PaymentOrder,
    Settlement,
    SettlementStatus
)

logger = logging.getLogger(__name__)


class CommissionCalculator:
    """
    佣金计算引擎
    支持多模块、可配置的佣金计算
    """
    
    def __init__(self, config_manager: Optional[UnifiedConfigManager] = None):
        self.config = config_manager or get_config_manager()
        self._cache: Dict[str, Any] = {}  # 计算结果缓存
    
    def calculate_commission(
        self,
        module: str,
        base_amount: float,
        currency: str = "CNY"
    ) -> CommissionResult:
        """
        计算佣金
        
        Args:
            module: 模块名称
            base_amount: 原始金额（打赏金额）
            currency: 货币类型
            
        Returns:
            CommissionResult: 佣金计算结果
            
        计算公式:
        - 佣金金额 = 原始金额 × 佣金比例
        - 总支付金额 = 原始金额 + 佣金金额
        - 作者实收 = 原始金额（作者获得全部打赏）
        - 开发者实收 = 佣金金额
        """
        # 获取模块配置
        module_config = self.config.get_module_config(module)
        
        # 验证金额范围
        is_valid, error_msg = self.validate_amount(module, base_amount)
        if not is_valid:
            logger.warning(f"金额验证失败: {error_msg}")
            # 返回零值结果而不是抛出异常
            return CommissionResult(
                original_amount=base_amount,
                commission_amount=0.0,
                total_amount=base_amount,
                commission_rate=module_config.commission_rate,
                module_type=ModuleType(module),
                currency=currency
            )
        
        # 计算佣金（使用Decimal确保精度）
        base_decimal = Decimal(str(base_amount))
        rate_decimal = Decimal(str(module_config.commission_rate))
        
        commission_decimal = base_decimal * rate_decimal
        
        # 确保最小佣金
        min_commission = Decimal(str(self.config.get_config_value("global.min_commission", 0.01)))
        if commission_decimal < min_commission and base_amount > 0:
            commission_decimal = min_commission
        
        # 转换为float
        commission_amount = float(commission_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        total_amount = base_amount + commission_amount
        
        # 缓存结果
        cache_key = f"{module}:{base_amount}:{currency}"
        self._cache[cache_key] = commission_amount
        
        result = CommissionResult(
            original_amount=base_amount,
            commission_amount=commission_amount,
            total_amount=total_amount,
            commission_rate=module_config.commission_rate,
            module_type=ModuleType(module),
            currency=currency
        )
        
        logger.debug(f"佣金计算: 原始={base_amount}, 佣金={commission_amount}, 总计={total_amount}")
        
        return result
    
    def calculate_settlement(
        self,
        commission_result: CommissionResult
    ) -> Dict[str, float]:
        """
        计算分账金额
        
        分账规则:
        - 作者获得原始金额（100%打赏归作者）
        - 开发者获得佣金金额
        
        Returns:
            Dict包含: author_amount, developer_amount, commission_amount
        """
        settlement_config = self.config.get_settlement_config()
        developer_rate = settlement_config.developer.get("commission_rate", 0.0003)
        
        author_amount = commission_result.original_amount
        commission_amount = commission_result.commission_amount
        developer_amount = commission_amount
        
        return {
            "author_amount": round(author_amount, 2),
            "developer_amount": round(developer_amount, 2),
            "commission_amount": round(commission_amount, 2)
        }
    
    def calculate_settlement_for_order(
        self,
        order: PaymentOrder
    ) -> Settlement:
        """
        为订单创建结算记录
        """
        commission_result = CommissionResult(
            original_amount=order.original_amount,
            commission_amount=order.commission_amount,
            total_amount=order.total_amount,
            commission_rate=order.commission_amount / order.original_amount if order.original_amount > 0 else 0,
            module_type=order.module_type
        )
        
        amounts = self.calculate_settlement(commission_result)
        
        settlement = Settlement(
            order_id=order.order_id,
            module_type=order.module_type,
            author_amount=amounts["author_amount"],
            developer_amount=amounts["developer_amount"],
            commission_amount=amounts["commission_amount"],
            status=SettlementStatus.PENDING
        )
        
        return settlement
    
    def validate_amount(
        self,
        module: str,
        amount: float
    ) -> Tuple[bool, str]:
        """
        验证金额是否有效
        
        Returns:
            (是否有效, 错误信息)
        """
        if amount <= 0:
            return False, "金额必须大于0"
        
        # 检查全局最大金额限制
        max_order = self.config.get_config_value("global.max_order_amount", 50000)
        if amount > max_order:
            return False, f"金额不能超过全局限制 {max_order} 元"
        
        # 检查模块特定限制
        module_config = self.config.get_module_config(module)
        
        if amount < module_config.min_amount:
            return False, f"金额不能低于模块最低限制 {module_config.min_amount} 元"
        
        if amount > module_config.max_amount:
            return False, f"金额不能超过模块最高限制 {module_config.max_amount} 元"
        
        return True, ""
    
    def get_module_limits(self, module: str) -> Dict[str, float]:
        """
        获取模块金额限制
        """
        module_config = self.config.get_module_config(module)
        
        return {
            "min_amount": module_config.min_amount,
            "max_amount": module_config.max_amount,
            "default_amounts": module_config.default_amounts,
            "commission_rate": module_config.commission_rate
        }
    
    def get_commission_preview(
        self,
        module: str,
        amount: float,
        currency: str = "CNY"
    ) -> Dict[str, Any]:
        """
        获取佣金预览信息
        
        用于在用户确认支付前显示明细
        """
        result = self.calculate_commission(module, amount, currency)
        settlement = self.calculate_settlement(result)
        
        return {
            "original_amount": result.original_amount,
            "commission_rate": f"{result.commission_rate * 100:.4f}%",
            "commission_amount": result.commission_amount,
            "total_amount": result.total_amount,
            "author_amount": settlement["author_amount"],
            "developer_amount": settlement["developer_amount"],
            "currency": currency,
            "module_type": module
        }
    
    def format_amount(
        self,
        amount: float,
        currency: str = "CNY"
    ) -> str:
        """
        格式化金额显示
        """
        if currency == "CNY":
            return f"¥{amount:.2f}"
        else:
            return f"{amount:.2f} {currency}"
    
    def batch_calculate(
        self,
        orders: list
    ) -> list:
        """
        批量计算佣金
        
        Args:
            orders: [(module, amount), ...]
            
        Returns:
            [CommissionResult, ...]
        """
        results = []
        for module, amount in orders:
            result = self.calculate_commission(module, amount)
            results.append(result)
        return results
    
    def get_total_commission(
        self,
        module: str,
        orders: list
    ) -> float:
        """
        计算某模块一系列订单的总佣金
        """
        total = 0.0
        for amount in orders:
            result = self.calculate_commission(module, amount)
            total += result.commission_amount
        return round(total, 2)


# 获取全局计算器实例
_calculator_instance = None

def get_calculator(config_manager: Optional[UnifiedConfigManager] = None) -> CommissionCalculator:
    """获取佣金计算器实例"""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = CommissionCalculator(config_manager)
    return _calculator_instance
