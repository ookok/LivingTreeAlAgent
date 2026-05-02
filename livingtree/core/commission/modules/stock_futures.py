# -*- coding: utf-8 -*-
"""
统一佣金系统 - 股票期货模块
"""

from typing import Any, Dict, Tuple

from .base_module import BaseModule, register_module
from ..models import PaymentOrder


class StockFuturesModule(BaseModule):
    """股票期货分析模块"""
    
    def __init__(self, config_manager=None):
        super().__init__("stock_futures", config_manager)
    
    def get_module_info(self) -> Dict[str, Any]:
        return {
            "name": "股票期货分析",
            "description": "专业金融数据分析工具",
            "features": ["实时行情", "技术分析", "策略回测", "风险预警"],
            "risk_warning": "投资有风险，入市需谨慎",
            "commission_rate": self.module_config.commission_rate
        }
    
    def _validate_module_specific(self, order_data: Dict[str, Any]) -> Tuple[bool, str]:
        """股票期货模块特定验证"""
        # 检查风险确认
        if not order_data.get("risk_acknowledged", False):
            return False, "请先阅读并确认风险提示"
        return True, ""
    
    def process_payment_success(self, order: PaymentOrder) -> Dict[str, Any]:
        amount = order.original_amount
        
        features = ["去广告", "基础行情"]
        vip_level = "普通会员"
        
        if amount >= 20:
            features.extend(["实时行情", "基础技术指标"])
            vip_level = "白银会员"
        
        if amount >= 50:
            features.extend(["Level2行情", "自定义指标", "自选股提醒"])
            vip_level = "黄金会员"
        
        if amount >= 100:
            features.extend(["策略回测", "风险预警", "专业研报"])
            vip_level = "铂金会员"
        
        if amount >= 500:
            features.extend(["API量化接口", "专属客服", "线下活动"])
            vip_level = "钻石会员"
        
        return {
            "success": True,
            "message": f"股票期货分析开通成功！当前{vip_level}",
            "data": {
                "vip_level": vip_level,
                "feature_unlocked": features,
                "expire_days": 30,
                "risk_warning": self.module_config.risk_warning,
                "order_id": order.order_id
            }
        }
    
    def get_quota_by_amount(self, amount: float) -> int:
        """股票期货模块配额: 次数/天"""
        return int(amount)  # 每1元 = 1次/天
    
    def process_refund(self, order: PaymentOrder) -> Dict[str, Any]:
        return {
            "success": True,
            "message": "退款成功，会员特权已回收",
            "data": {
                "vip_level_recovered": True,
                "features_recovered": True
            }
        }


register_module("stock_futures", StockFuturesModule)
