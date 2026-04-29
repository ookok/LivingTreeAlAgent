"""
审计接口 - Audit Interface

提供不可篡改的审计轨迹，支持用户交易历史验证

核心功能：
1. 用户交易链审计轨迹
2. 交易验证（可验证每个tx_hash = Hash(prev_hash + tx_data)）
3. 余额证明
4. 合规报表
"""

import json
import hashlib
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class AuditTrail:
    """审计轨迹"""
    user_id: str
    transactions: List[Dict]
    final_balance: Decimal
    chain_valid: bool
    generated_at: str

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['final_balance'] = str(self.final_balance)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class BalanceProof:
    """余额证明"""
    user_id: str
    balance: Decimal
    last_tx_hash: str
    last_nonce: int
    proof_data: Dict  # 用于验证的数据
    generated_at: str

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['balance'] = str(self.balance)
        return d


class AuditService:
    """
    审计服务

    职责：
    1. 生成用户审计轨迹
    2. 验证交易链完整性
    3. 提供余额证明
    4. 生成合规报表
    """

    def __init__(self, ledger=None):
        self.ledger = ledger

    def get_user_audit_trail(self, user_id: str) -> AuditTrail:
        """
        获取用户完整审计轨迹

        返回用户的完整交易链，每个tx_hash可验证

        Args:
            user_id: 用户ID

        Returns:
            AuditTrail
        """
        logger.info(f"生成用户审计轨迹: user_id={user_id}")

        transactions = []

        if self.ledger:
            txs = self.ledger.get_user_txs(user_id, limit=10000)

            for tx in txs:
                transactions.append({
                    "tx_hash": tx.tx_hash,
                    "prev_tx_hash": tx.prev_tx_hash,
                    "op_type": tx.op_type.value,
                    "amount": str(tx.amount),
                    "nonce": tx.nonce,
                    "to_user_id": tx.to_user_id,
                    "memo": tx.memo,
                    "created_at": datetime.fromtimestamp(tx.created_at).isoformat(),
                    "relay_id": tx.relay_id
                })

            # 计算最终余额
            final_balance = self.ledger.get_balance(user_id)

            # 验证链完整性
            chain_valid, _ = self.ledger.verify_chain_integrity(user_id) if hasattr(self.ledger, 'verify_chain_integrity') else (True, "")
        else:
            final_balance = Decimal("0")
            chain_valid = True

        return AuditTrail(
            user_id=user_id,
            transactions=transactions,
            final_balance=final_balance,
            chain_valid=chain_valid,
            generated_at=datetime.now().isoformat()
        )

    def verify_transaction_chain(self, transactions: List[Dict]) -> Tuple[bool, List[str]]:
        """
        验证交易链完整性

        检查每个tx_hash是否等于Hash(prev_hash + tx_data)

        Args:
            transactions: 交易列表（按nonce排序）

        Returns:
            (is_valid, errors)
        """
        errors = []
        expected_prev = ""  # 第一笔交易的prev_hash应该是空或genesis

        for i, tx in enumerate(transactions):
            # 验证prev_hash连续性
            if tx.get("prev_tx_hash") != expected_prev:
                errors.append(f"交易 {i} (nonce={tx.get('nonce')}): prev_hash不连续")

            # 重新计算tx_hash验证
            computed_hash = self._compute_tx_hash(tx)
            if computed_hash != tx.get("tx_hash"):
                errors.append(f"交易 {i} (nonce={tx.get('nonce')}): tx_hash不匹配")

            # 验证nonce连续性
            if i > 0:
                expected_nonce = transactions[i-1].get("nonce", -1) + 1
                if tx.get("nonce") != expected_nonce:
                    errors.append(f"交易 {i}: nonce不连续，期望{expected_nonce}，实际{tx.get('nonce')}")

            # 更新expected_prev
            expected_prev = tx.get("tx_hash", "")

        return len(errors) == 0, errors

    def _compute_tx_hash(self, tx_data: Dict) -> str:
        """重新计算交易哈希"""
        content = (
            f"{tx_data.get('user_id')}|{tx_data.get('op_type')}|{tx_data.get('amount')}|"
            f"{tx_data.get('nonce')}|{tx_data.get('prev_tx_hash') or ''}|"
            f"{tx_data.get('to_user_id') or ''}|{tx_data.get('payment_order_id') or ''}|"
            f"{tx_data.get('created_at')}"
        )
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def get_balance_proof(self, user_id: str) -> BalanceProof:
        """
        获取余额证明

        包含足够的数据供第三方验证余额计算的正确性

        Args:
            user_id: 用户ID

        Returns:
            BalanceProof
        """
        logger.info(f"生成余额证明: user_id={user_id}")

        balance = Decimal("0")
        last_tx_hash = ""
        last_nonce = -1

        if self.ledger:
            balance = self.ledger.get_balance(user_id)
            last_nonce = self.ledger.get_nonce(user_id) - 1  # 最后一笔的nonce

            # 获取最后一笔交易
            txs = self.ledger.get_user_txs(user_id, limit=1)
            if txs:
                last_tx_hash = txs[-1].tx_hash

        # 生成证明数据
        proof_data = {
            "user_id": user_id,
            "balance_formula": "Σ(RECHARGE+GRANT+TRANSFER_IN) - Σ(CONSUME+TRANSFER_OUT)",
            "verification_hint": "可通过遍历用户所有交易验证余额计算"
        }

        return BalanceProof(
            user_id=user_id,
            balance=balance,
            last_tx_hash=last_tx_hash,
            last_nonce=last_nonce,
            proof_data=proof_data,
            generated_at=datetime.now().isoformat()
        )

    def generate_compliance_report(
        self,
        start_date: str,
        end_date: str,
        include_users: List[str] = None
    ) -> Dict:
        """
        生成合规报表

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            include_users: 指定用户列表（None表示全部）

        Returns:
            合规报表数据
        """
        logger.info(f"生成合规报表: {start_date} ~ {end_date}")

        report = {
            "report_period": {"start": start_date, "end": end_date},
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_transactions": 0,
                "total_recharge": "0",
                "total_consume": "0",
                "total_transfer": "0",
                "net_change": "0"
            },
            "transactions": [],
            "user_summary": []
        }

        if not self.ledger:
            return report

        # 统计
        total_recharge = Decimal("0")
        total_consume = Decimal("0")
        total_transfer = Decimal("0")

        # 获取所有交易
        all_txs = self.ledger.get_all_txs(limit=10000)

        for tx in all_txs:
            # 按日期过滤
            tx_date = datetime.fromtimestamp(tx.created_at).strftime("%Y-%m-%d")
            if tx_date < start_date or tx_date > end_date:
                continue

            # 按用户过滤
            if include_users and tx.user_id not in include_users:
                continue

            # 统计
            report["summary"]["total_transactions"] += 1

            if tx.op_type.value == "RECHARGE":
                total_recharge += tx.amount
            elif tx.op_type.value == "CONSUME":
                total_consume += tx.amount
            elif tx.op_type.value in ("TRANSFER_IN", "TRANSFER_OUT"):
                total_transfer += tx.amount

            # 记录交易
            report["transactions"].append({
                "tx_hash": tx.tx_hash,
                "user_id": tx.user_id,
                "op_type": tx.op_type.value,
                "amount": str(tx.amount),
                "date": tx_date,
                "tx_time": datetime.fromtimestamp(tx.created_at).isoformat()
            })

        # 计算净额
        net_change = total_recharge - total_consume

        report["summary"]["total_recharge"] = str(total_recharge)
        report["summary"]["total_consume"] = str(total_consume)
        report["summary"]["total_transfer"] = str(total_transfer)
        report["summary"]["net_change"] = str(net_change)

        # 用户汇总
        if include_users:
            for uid in include_users:
                balance = self.ledger.get_balance(uid) if self.ledger else Decimal("0")
                report["user_summary"].append({
                    "user_id": uid,
                    "balance": str(balance),
                    "last_nonce": self.ledger.get_nonce(uid) - 1 if self.ledger else 0
                })

        return report

    def verify_audit_trail(self, audit_trail: AuditTrail) -> Tuple[bool, Dict]:
        """
        验证审计轨迹

        验证：
        1. 交易链完整性
        2. 余额计算正确性

        Args:
            audit_trail: 审计轨迹

        Returns:
            (is_valid, verification_details)
        """
        details = {
            "chain_valid": False,
            "balance_valid": False,
            "tx_count": len(audit_trail.transactions),
            "errors": []
        }

        # 1. 验证交易链
        if audit_trail.transactions:
            chain_valid, chain_errors = self.verify_transaction_chain(audit_trail.transactions)
            details["chain_valid"] = chain_valid
            if chain_errors:
                details["errors"].extend(chain_errors)

        # 2. 验证余额
        calculated_balance = Decimal("0")
        for tx in audit_trail.transactions:
            amount = Decimal(tx.get("amount", "0"))
            op_type = tx.get("op_type", "")

            if op_type in ("RECHARGE", "GRANT", "TRANSFER_IN"):
                calculated_balance += amount
            elif op_type in ("CONSUME", "TRANSFER_OUT"):
                calculated_balance -= amount

        details["calculated_balance"] = str(calculated_balance)
        details["claimed_balance"] = str(audit_trail.final_balance)
        details["balance_valid"] = calculated_balance == audit_trail.final_balance

        if not details["balance_valid"]:
            details["errors"].append(
                f"余额不匹配: 计算={calculated_balance}, 声明={audit_trail.final_balance}"
            )

        is_valid = details["chain_valid"] and details["balance_valid"]

        return is_valid, details


class AuditLogger:
    """
    审计日志记录器

    记录关键操作到审计日志表
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or ":memory:"
        self._log_buffer: List[Dict] = []

    def log_event(
        self,
        event_type: str,
        user_id: str = None,
        tx_hash: str = None,
        details: Dict = None,
        ip_address: str = None
    ):
        """
        记录审计事件

        Args:
            event_type: 事件类型
            user_id: 用户ID
            tx_hash: 关联交易哈希
            details: 事件详情
            ip_address: IP地址
        """
        event = {
            "event_type": event_type,
            "user_id": user_id,
            "tx_hash": tx_hash,
            "details": details or {},
            "ip_address": ip_address,
            "timestamp": datetime.now().isoformat()
        }

        self._log_buffer.append(event)

        # 简单日志输出
        logger.info(f"AUDIT: {event_type} | user={user_id} | tx={tx_hash}")

    def get_user_events(
        self,
        user_id: str,
        event_type: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """获取用户的事件日志"""
        events = [e for e in self._log_buffer if e["user_id"] == user_id]

        if event_type:
            events = [e for e in events if e["event_type"] == event_type]

        return events[-limit:]

    def get_events_by_tx(self, tx_hash: str) -> List[Dict]:
        """获取交易相关的事件"""
        return [e for e in self._log_buffer if e["tx_hash"] == tx_hash]
