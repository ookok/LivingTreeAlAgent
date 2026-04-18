# -*- coding: utf-8 -*-
"""
统一佣金系统 - 游戏模块
"""

from typing import Any, Dict, Tuple

from .base_module import BaseModule, register_module
from ..models import PaymentOrder


class GameModule(BaseModule):
    """游戏娱乐模块"""
    
    def __init__(self, config_manager=None):
        super().__init__("game", config_manager)
    
    def get_module_info(self) -> Dict[str, Any]:
        return {
            "name": "游戏娱乐",
            "description": "休闲娱乐，益智游戏",
            "features": ["游戏道具", "虚拟货币", "会员特权", "排行榜奖励"],
            "categories": ["休闲游戏", "竞技游戏", "策略游戏"],
            "commission_rate": self.module_config.commission_rate
        }
    
    def process_payment_success(self, order: PaymentOrder) -> Dict[str, Any]:
        amount = order.original_amount
        
        # 游戏特殊：直接发放虚拟货币和道具
        virtual_coins = amount * 100  # 1元 = 100游戏币
        
        rewards = {
            "virtual_coins": virtual_coins,
            "daily_gifts": 7,  # 7天每日礼包
            "exclusive_title": "",
            "avatar_frame": "",
            "chat_bubble": ""
        }
        
        if amount >= 10:
            rewards["exclusive_title"] = "游戏新秀"
            rewards["avatar_frame"] = "新手光环"
        
        if amount >= 50:
            rewards["exclusive_title"] = "游戏达人"
            rewards["avatar_frame"] = "达人光环"
            rewards["daily_gifts"] = 14
        
        if amount >= 100:
            rewards["exclusive_title"] = "游戏大神"
            rewards["avatar_frame"] = "大神光环"
            rewards["daily_gifts"] = 30
            rewards["chat_bubble"] = "酷炫聊天气泡"
        
        if amount >= 200:
            rewards["exclusive_title"] = "传奇玩家"
            rewards["avatar_frame"] = "传奇光环"
            rewards["chat_bubble"] = "传说聊天气泡"
        
        return {
            "success": True,
            "message": "游戏打赏成功，道具已发放！",
            "data": {
                "rewards": rewards,
                "game_items": self._get_game_items(amount),
                "order_id": order.order_id
            }
        }
    
    def _get_game_items(self, amount: float) -> list:
        """根据金额获取游戏道具"""
        items = []
        
        if amount >= 5:
            items.append({"name": "小礼包", "count": 1})
        if amount >= 20:
            items.append({"name": "中礼包", "count": 1})
        if amount >= 50:
            items.append({"name": "大礼包", "count": 1})
        if amount >= 100:
            items.append({"name": "稀有宝箱", "count": 3})
        
        return items
    
    def get_quota_by_amount(self, amount: float) -> int:
        """游戏模块配额: 体力值"""
        return int(amount * 10)
    
    def process_refund(self, order: PaymentOrder) -> Dict[str, Any]:
        return {
            "success": True,
            "message": "退款成功，虚拟货币已扣除",
            "data": {
                "coins_recovered": order.original_amount * 100,
                "items_recovered": True
            }
        }


register_module("game", GameModule)
