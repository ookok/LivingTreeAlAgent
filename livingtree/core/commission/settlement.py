# -*- coding: utf-8 -*-
"""结算与退款服务"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from .config_manager import get_config_manager
from .calculator import get_calculator
from .database import get_commission_database
from .models import (
    PaymentOrder, Settlement, SettlementStatus,
    Refund, RefundStatus, OrderStatus
)
from .modules import create_module

logger = logging.getLogger(__name__)


class SettlementService:
    """结算服务"""
    
    def __init__(self, db=None, config_manager=None):
        self.db = db or get_commission_database()
        self.config = config_manager or get_config_manager()
        self.calculator = get_calculator(self.config)
    
    def create_settlement(self, order: PaymentOrder) -> Settlement:
        settlement = self.calculator.calculate_settlement_for_order(order)
        settlement.status = SettlementStatus.PENDING
        self.db.save_settlement(settlement)
        logger.info(f"创建结算记录: {settlement.settlement_id}")
        return settlement
    
    def process_settlement(self, settlement_id: str) -> Dict[str, Any]:
        settlement = self.db.get_settlement(settlement_id)
        if not settlement:
            return {"success": False, "message": "结算记录不存在"}
        
        if settlement.status != SettlementStatus.PENDING:
            return {"success": False, "message": "结算状态不是待处理"}
        
        try:
            settlement.status = SettlementStatus.COMPLETED
            settlement.completed_at = datetime.now()
            self.db.save_settlement(settlement)
            return {"success": True, "message": "结算成功", "settlement_id": settlement_id}
        except Exception as e:
            settlement.status = SettlementStatus.FAILED
            settlement.notes = str(e)
            return {"success": False, "message": str(e)}


class RefundService:
    """退款服务"""
    
    def __init__(self, db=None, config_manager=None):
        self.db = db or get_commission_database()
        self.config = config_manager or get_config_manager()
    
    def can_refund(self, order: PaymentOrder) -> tuple:
        if order.status not in [OrderStatus.PAID, OrderStatus.COMPLETED]:
            return False, "只有已支付的订单才能退款"
        return True, ""
    
    def create_refund(self, order_id: str, refund_amount: float = None,
                     reason: str = "", refund_type: str = "USER_CANCEL") -> Dict[str, Any]:
        order = self.db.get_order(order_id)
        if not order:
            return {"success": False, "message": "订单不存在"}
        
        can_refund, reason_msg = self.can_refund(order)
        if not can_refund:
            return {"success": False, "message": reason_msg}
        
        if refund_amount is None:
            refund_amount = order.total_amount
        
        refund = Refund(
            order_id=order_id, refund_amount=refund_amount,
            refund_type=refund_type, reason=reason,
            status=RefundStatus.PENDING
        )
        self.db.save_refund(refund)
        return self.process_refund(refund.refund_id)
    
    def process_refund(self, refund_id: str) -> Dict[str, Any]:
        refund = self.db.get_refund(refund_id)
        if not refund:
            return {"success": False, "message": "退款记录不存在"}
        
        if refund.status != RefundStatus.PENDING:
            return {"success": False, "message": "退款状态不是待处理"}
        
        try:
            refund.status = RefundStatus.COMPLETED
            refund.completed_at = datetime.now()
            self.db.save_refund(refund)
            return {"success": True, "message": "退款成功", "refund_id": refund_id}
        except Exception as e:
            refund.status = RefundStatus.FAILED
            refund.notes = str(e)
            return {"success": False, "message": str(e)}
    
    def get_refund_reasons(self) -> List[Dict[str, Any]]:
        return self.config.get_config_value("refund.reasons", [])


_settlement_service = None
_refund_service = None


def get_settlement_service() -> SettlementService:
    global _settlement_service
    if _settlement_service is None:
        _settlement_service = SettlementService()
    return _settlement_service


def get_refund_service() -> RefundService:
    global _refund_service
    if _refund_service is None:
        _refund_service = RefundService()
    return _refund_service
