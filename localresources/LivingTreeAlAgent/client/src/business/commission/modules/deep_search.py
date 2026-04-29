# -*- coding: utf-8 -*-
"""
统一佣金系统 - 深度搜索模块
"""

from typing import Any, Dict, Tuple

from .base_module import BaseModule, register_module
from ..models import PaymentOrder


class DeepSearchModule(BaseModule):
    """深度搜索模块"""
    
    def __init__(self, config_manager=None):
        super().__init__("deep_search", config_manager)
    
    def get_module_info(self) -> Dict[str, Any]:
        return {
            "name": "深度搜索",
            "description": "高级搜索功能，提供精准结果",
            "features": ["语义搜索", "多源聚合", "智能排序", "历史记录"],
            "commission_rate": self.module_config.commission_rate
        }
    
    def _validate_module_specific(self, order_data: Dict[str, Any]) -> Tuple[bool, str]:
        search_query = order_data.get("search_query", "")
        if len(search_query) > 500:
            return False, "搜索关键词过长"
        return True, ""
    
    def process_payment_success(self, order: PaymentOrder) -> Dict[str, Any]:
        amount = order.original_amount
        quota_increase = self.get_quota_by_amount(amount)
        
        return {
            "success": True,
            "message": "深度搜索打赏成功，感谢支持！",
            "data": {
                "quota_added": quota_increase,
                "feature_unlocked": self.get_features_by_amount(amount),
                "expire_days": 30,
                "order_id": order.order_id
            }
        }
    
    def process_refund(self, order: PaymentOrder) -> Dict[str, Any]:
        quota_used = self.get_quota_by_amount(order.original_amount)
        
        return {
            "success": True,
            "message": f"退款成功，已恢复{quota_used}次搜索配额",
            "data": {
                "quota_restored": quota_used,
                "features_recovered": True
            }
        }
    
    def get_usage_stats(self, user_id: str) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "total_quota": 100,
            "used_quota": 45,
            "remaining_quota": 55,
            "unlocked_features": ["去广告", "语义搜索增强"],
            "daily_stats": [
                {"date": "2024-01-01", "searches": 10},
                {"date": "2024-01-02", "searches": 15}
            ]
        }


register_module("deep_search", DeepSearchModule)
