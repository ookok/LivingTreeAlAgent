# -*- coding: utf-8 -*-
"""
统一佣金系统 - 数据库操作
Unified Commission System - Database Operations
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    PaymentOrder,
    Settlement,
    Refund,
    OrderStatus,
    SettlementStatus,
    RefundStatus,
    ModuleType,
    PaymentProvider
)

logger = logging.getLogger(__name__)


class CommissionDatabase:
    """
    佣金系统数据库操作类
    
    使用SQLite存储订单、结算、退款等数据
    """
    
    _instance = None
    
    def __new__(cls, db_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str = None):
        if self._initialized:
            return
        
        if db_path is None:
            db_dir = Path.home() / ".hermes-desktop" / "commission"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(db_dir / "commission.db")
        
        self.db_path = db_path
        self._initialized = True
        
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            conn.close()
    
    def _init_database(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 订单表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    module_type TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    original_amount REAL NOT NULL,
                    commission_amount REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    subject TEXT,
                    body TEXT,
                    user_id TEXT,
                    created_at TEXT NOT NULL,
                    paid_at TEXT,
                    completed_at TEXT,
                    extra_data TEXT
                )
            """)
            
            # 结算表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settlements (
                    settlement_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    module_type TEXT NOT NULL,
                    author_amount REAL NOT NULL,
                    developer_amount REAL NOT NULL,
                    commission_amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    notes TEXT,
                    FOREIGN KEY (order_id) REFERENCES orders(order_id)
                )
            """)
            
            # 退款表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS refunds (
                    refund_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    refund_amount REAL NOT NULL,
                    refund_type TEXT NOT NULL,
                    reason TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    operator TEXT,
                    notes TEXT,
                    FOREIGN KEY (order_id) REFERENCES orders(order_id)
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_settlements_status ON settlements(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_refunds_status ON refunds(status)")
            
            logger.info("数据库初始化完成")
    
    # ========== 订单操作 ==========
    
    def save_order(self, order: PaymentOrder) -> bool:
        """保存订单"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO orders 
                    (order_id, module_type, provider, original_amount, commission_amount,
                     total_amount, status, subject, body, user_id, created_at,
                     paid_at, completed_at, extra_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order.order_id,
                    order.module_type.value,
                    order.provider.value,
                    order.original_amount,
                    order.commission_amount,
                    order.total_amount,
                    order.status.value,
                    order.subject,
                    order.body,
                    order.user_id,
                    order.created_at.isoformat(),
                    order.paid_at.isoformat() if order.paid_at else None,
                    order.completed_at.isoformat() if order.completed_at else None,
                    json.dumps(order.extra_data, ensure_ascii=False)
                ))
            return True
        except Exception as e:
            logger.error(f"保存订单失败: {e}")
            return False
    
    def get_order(self, order_id: str) -> Optional[PaymentOrder]:
        """获取订单"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_order(row)
                return None
        except Exception as e:
            logger.error(f"获取订单失败: {e}")
            return None
    
    def update_order_status(self, order_id: str, status: OrderStatus,
                           paid_at: datetime = None, completed_at: datetime = None) -> bool:
        """更新订单状态"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if paid_at:
                    cursor.execute(
                        "UPDATE orders SET status = ?, paid_at = ? WHERE order_id = ?",
                        (status.value, paid_at.isoformat(), order_id)
                    )
                elif completed_at:
                    cursor.execute(
                        "UPDATE orders SET status = ?, completed_at = ? WHERE order_id = ?",
                        (status.value, completed_at.isoformat(), order_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE orders SET status = ? WHERE order_id = ?",
                        (status.value, order_id)
                    )
            return True
        except Exception as e:
            logger.error(f"更新订单状态失败: {e}")
            return False
    
    def list_orders(self, user_id: str = None, status: OrderStatus = None,
                   limit: int = 100, offset: int = 0) -> List[PaymentOrder]:
        """列出订单"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM orders WHERE 1=1"
                params = []
                
                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)
                
                if status:
                    query += " AND status = ?"
                    params.append(status.value)
                
                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                return [self._row_to_order(row) for row in rows]
        except Exception as e:
            logger.error(f"列出订单失败: {e}")
            return []
    
    def _row_to_order(self, row: sqlite3.Row) -> PaymentOrder:
        """将数据库行转换为PaymentOrder对象"""
        return PaymentOrder(
            order_id=row["order_id"],
            module_type=ModuleType(row["module_type"]),
            provider=PaymentProvider(row["provider"]),
            original_amount=row["original_amount"],
            commission_amount=row["commission_amount"],
            total_amount=row["total_amount"],
            status=OrderStatus(row["status"]),
            subject=row["subject"],
            body=row["body"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            paid_at=datetime.fromisoformat(row["paid_at"]) if row["paid_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            extra_data=json.loads(row["extra_data"]) if row["extra_data"] else {}
        )
    
    # ========== 结算操作 ==========
    
    def save_settlement(self, settlement: Settlement) -> bool:
        """保存结算记录"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO settlements
                    (settlement_id, order_id, module_type, author_amount,
                     developer_amount, commission_amount, status, created_at,
                     completed_at, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    settlement.settlement_id,
                    settlement.order_id,
                    settlement.module_type.value,
                    settlement.author_amount,
                    settlement.developer_amount,
                    settlement.commission_amount,
                    settlement.status.value,
                    settlement.created_at.isoformat(),
                    settlement.completed_at.isoformat() if settlement.completed_at else None,
                    settlement.notes
                ))
            return True
        except Exception as e:
            logger.error(f"保存结算记录失败: {e}")
            return False
    
    def get_settlement(self, settlement_id: str) -> Optional[Settlement]:
        """获取结算记录"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM settlements WHERE settlement_id = ?",
                    (settlement_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_settlement(row)
                return None
        except Exception as e:
            logger.error(f"获取结算记录失败: {e}")
            return None
    
    def get_settlement_by_order(self, order_id: str) -> Optional[Settlement]:
        """根据订单ID获取结算记录"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM settlements WHERE order_id = ?",
                    (order_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_settlement(row)
                return None
        except Exception as e:
            logger.error(f"获取结算记录失败: {e}")
            return None
    
    def list_settlements(self, status: SettlementStatus = None,
                        limit: int = 100, offset: int = 0) -> List[Settlement]:
        """列出结算记录"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM settlements WHERE 1=1"
                params = []
                
                if status:
                    query += " AND status = ?"
                    params.append(status.value)
                
                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                return [self._row_to_settlement(row) for row in rows]
        except Exception as e:
            logger.error(f"列出结算记录失败: {e}")
            return []
    
    def _row_to_settlement(self, row: sqlite3.Row) -> Settlement:
        """将数据库行转换为Settlement对象"""
        return Settlement(
            settlement_id=row["settlement_id"],
            order_id=row["order_id"],
            module_type=ModuleType(row["module_type"]),
            author_amount=row["author_amount"],
            developer_amount=row["developer_amount"],
            commission_amount=row["commission_amount"],
            status=SettlementStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            notes=row["notes"]
        )
    
    # ========== 退款操作 ==========
    
    def save_refund(self, refund: Refund) -> bool:
        """保存退款记录"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO refunds
                    (refund_id, order_id, refund_amount, refund_type, reason,
                     status, created_at, completed_at, operator, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    refund.refund_id,
                    refund.order_id,
                    refund.refund_amount,
                    refund.refund_type,
                    refund.reason,
                    refund.status.value,
                    refund.created_at.isoformat(),
                    refund.completed_at.isoformat() if refund.completed_at else None,
                    refund.operator,
                    refund.notes
                ))
            return True
        except Exception as e:
            logger.error(f"保存退款记录失败: {e}")
            return False
    
    def get_refund(self, refund_id: str) -> Optional[Refund]:
        """获取退款记录"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM refunds WHERE refund_id = ?",
                    (refund_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_refund(row)
                return None
        except Exception as e:
            logger.error(f"获取退款记录失败: {e}")
            return None
    
    def list_refunds(self, status: RefundStatus = None,
                    limit: int = 100, offset: int = 0) -> List[Refund]:
        """列出退款记录"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM refunds WHERE 1=1"
                params = []
                
                if status:
                    query += " AND status = ?"
                    params.append(status.value)
                
                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                return [self._row_to_refund(row) for row in rows]
        except Exception as e:
            logger.error(f"列出退款记录失败: {e}")
            return []
    
    def _row_to_refund(self, row: sqlite3.Row) -> Refund:
        """将数据库行转换为Refund对象"""
        return Refund(
            refund_id=row["refund_id"],
            order_id=row["order_id"],
            refund_amount=row["refund_amount"],
            refund_type=row["refund_type"],
            reason=row["reason"],
            status=RefundStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            operator=row["operator"],
            notes=row["notes"]
        )
    
    # ========== 统计操作 ==========
    
    def get_order_statistics(self, start_date: datetime = None,
                            end_date: datetime = None) -> Dict[str, Any]:
        """获取订单统计"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 总订单数
                query = "SELECT COUNT(*) as total FROM orders WHERE 1=1"
                params = []
                
                if start_date:
                    query += " AND created_at >= ?"
                    params.append(start_date.isoformat())
                if end_date:
                    query += " AND created_at <= ?"
                    params.append(end_date.isoformat())
                
                cursor.execute(query, params)
                total_orders = cursor.fetchone()["total"]
                
                # 总金额
                query = "SELECT SUM(total_amount) as total FROM orders WHERE 1=1"
                cursor.execute(query, params)
                total_amount = cursor.fetchone()["total"] or 0
                
                # 已支付订单
                query = "SELECT COUNT(*) as paid FROM orders WHERE status = 'paid' AND 1=1"
                cursor.execute(query, params)
                paid_orders = cursor.fetchone()["paid"]
                
                # 总佣金
                query = "SELECT SUM(commission_amount) as total FROM orders WHERE status = 'paid' AND 1=1"
                cursor.execute(query, params)
                total_commission = cursor.fetchone()["total"] or 0
                
                return {
                    "total_orders": total_orders,
                    "paid_orders": paid_orders,
                    "total_amount": round(total_amount, 2),
                    "total_commission": round(total_commission, 2)
                }
        except Exception as e:
            logger.error(f"获取订单统计失败: {e}")
            return {}


# 全局数据库实例
_db_instance = None

def get_commission_database(db_path: str = None) -> CommissionDatabase:
    """获取数据库实例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = CommissionDatabase(db_path)
    return _db_instance
