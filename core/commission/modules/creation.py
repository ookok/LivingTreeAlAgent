# -*- coding: utf-8 -*-
"""
统一佣金系统 - 创作模块
"""

from typing import Any, Dict, Tuple

from .base_module import BaseModule, register_module
from ..models import PaymentOrder


class CreationModule(BaseModule):
    """智能创作模块"""
    
    def __init__(self, config_manager=None):
        super().__init__("creation", config_manager)
    
    def get_module_info(self) -> Dict[str, Any]:
        return {
            "name": "智能创作",
            "description": "AI辅助创作，提升创作效率",
            "features": ["内容生成", "风格模仿", "结构优化", "语法检查"],
            "commission_rate": self.module_config.commission_rate
        }
    
    def process_payment_success(self, order: PaymentOrder) -> Dict[str, Any]:
        amount = order.original_amount
        quota_increase = self.get_quota_by_amount(amount)
        
        features = self.get_features_by_amount(amount)
        # 创作模块特殊功能
        if amount >= 20:
            features.append("长文本生成")
        if amount >= 100:
            features.append("专业模板库")
        
        return {
            "success": True,
            "message": "智能创作打赏成功，感谢支持！",
            "data": {
                "quota_added": quota_increase,
                "feature_unlocked": features,
                "expire_days": 30,
                "order_id": order.order_id
            }
        }
    
    def get_quota_by_amount(self, amount: float) -> int:
        """创作模块配额: 每1元 = 5次生成"""
        return int(amount * 5)
    
    def process_refund(self, order: PaymentOrder) -> Dict[str, Any]:
        quota_used = self.get_quota_by_amount(order.original_amount)
        
        return {
            "success": True,
            "message": f"退款成功，已恢复{quota_used}次生成配额",
            "data": {
                "quota_restored": quota_used,
                "features_recovered": True
            }
        }


register_module("creation", CreationModule)
