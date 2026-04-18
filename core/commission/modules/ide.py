# -*- coding: utf-8 -*-
"""
统一佣金系统 - IDE模块
"""

from typing import Any, Dict, Tuple

from .base_module import BaseModule, register_module
from ..models import PaymentOrder


class IDEModule(BaseModule):
    """智能IDE模块"""
    
    def __init__(self, config_manager=None):
        super().__init__("ide", config_manager)
    
    def get_module_info(self) -> Dict[str, Any]:
        return {
            "name": "智能IDE",
            "description": "代码开发工具，AI编程助手",
            "features": ["代码补全", "智能调试", "代码重构", "项目管理"],
            "commission_rate": self.module_config.commission_rate
        }
    
    def process_payment_success(self, order: PaymentOrder) -> Dict[str, Any]:
        amount = order.original_amount
        
        features = ["去广告", "基础代码补全"]
        pro_features = []
        license_type = "基础版"
        
        if amount >= 10:
            features.extend(["智能提示", "错误检测"])
            pro_features.append("基础Pro功能")
            license_type = "基础版"
        
        if amount >= 50:
            features.extend(["代码重构", "代码生成"])
            pro_features.append("中级Pro功能")
            license_type = "专业版"
        
        if amount >= 100:
            features.extend(["高级AI补全", "代码审查", "性能分析"])
            pro_features.append("高级Pro功能")
            license_type = "高级版"
        
        if amount >= 200:
            features.extend(["企业级功能", "团队协作", "专属插件"])
            pro_features.append("企业Pro功能")
            license_type = "企业版"
        
        return {
            "success": True,
            "message": f"智能IDE开通成功！当前{license_type}",
            "data": {
                "license_type": license_type,
                "feature_unlocked": features,
                "pro_features": pro_features,
                "expire_days": 30,
                "order_id": order.order_id
            }
        }
    
    def get_quota_by_amount(self, amount: float) -> int:
        """IDE模块配额: AI请求次数"""
        return int(amount * 20)  # 每1元 = 20次AI请求
    
    def process_refund(self, order: PaymentOrder) -> Dict[str, Any]:
        return {
            "success": True,
            "message": "退款成功，IDE特权已回收",
            "data": {
                "license_recovered": True,
                "features_recovered": True,
                "ai_requests_recovered": self.get_quota_by_amount(order.original_amount)
            }
        }


register_module("ide", IDEModule)
