# -*- coding: utf-8 -*-
"""
佣金系统模块
============

多层佣金体系：
1. 发现佣金（10%）：帮助发现商品的节点获得
2. 见证佣金（5%）：见证交易的节点获得
3. 推荐佣金（5%）：成功推荐的节点获得
4. 网络维护佣金（5%）：存储商品索引的节点获得

特点：
- 全自动计算和分配
- 无平台抽成
- 透明公开
"""

import uuid
import time
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable
from collections import defaultdict


class CommissionType(Enum):
    """佣金类型"""
    DISCOVERY = "discovery"                # 发现佣金
    WITNESS = "witness"                    # 见证佣金
    REFERRAL = "referral"                  # 推荐佣金
    NETWORK = "network"                    # 网络维护佣金


@dataclass
class CommissionRecord:
    """佣金记录"""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str = ""

    # 佣金类型
    commission_type: CommissionType = CommissionType.DISCOVERY

    # 金额
    transaction_amount: float = 0.0       # 交易金额
    commission_rate: float = 0.0           # 佣金率
    commission_amount: float = 0.0         # 佣金金额

    # 受益人
    recipient_id: str = ""                 # 接收者
    recipient_role: str = ""                # discovery_node/witness/referrer/index_node

    # 状态
    status: str = "pending"                # pending/paid/cancelled

    # 关联
    related_node_ids: List[str] = field(default_factory=list)  # 涉及的节点

    # 时间
    created_at: float = field(default_factory=time.time)
    paid_at: float = 0

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['commission_type'] = self.commission_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'CommissionRecord':
        data = data.copy()
        data['commission_type'] = CommissionType(data.get('commission_type', 'discovery'))
        return cls(**data)


class CommissionCalculator:
    """佣金计算器"""

    # 佣金率配置
    RATES = {
        CommissionType.DISCOVERY: 0.10,    # 10%
        CommissionType.WITNESS: 0.05,       # 5%
        CommissionType.REFERRAL: 0.05,      # 5%
        CommissionType.NETWORK: 0.05,       # 5%
    }

    # 单笔佣金上下限
    MIN_COMMISSION = 0.01                  # 最小佣金
    MAX_COMMISSION = 100.0                 # 单笔最大佣金

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.records: Dict[str, CommissionRecord] = {}  # record_id -> record

        # 索引
        self.node_commissions: Dict[str, List[str]] = defaultdict(list)  # node_id -> [record_ids]
        self.transaction_commissions: Dict[str, List[str]] = defaultdict(list)  # tx_id -> [record_ids]

        # 累计
        self.total_commissions_paid: float = 0.0

        # 回调
        self.on_commission_calculated: Optional[Callable] = None
        self.on_commission_paid: Optional[Callable] = None

    def calculate_commission(
        self,
        transaction_id: str,
        transaction_amount: float,
        commission_type: CommissionType,
        recipient_id: str,
        recipient_role: str,
        related_node_ids: List[str] = None,
    ) -> CommissionRecord:
        """计算佣金"""
        rate = self.RATES.get(commission_type, 0)
        amount = transaction_amount * rate

        # 限制范围
        amount = max(self.MIN_COMMISSION, min(amount, self.MAX_COMMISSION))

        record = CommissionRecord(
            transaction_id=transaction_id,
            commission_type=commission_type,
            transaction_amount=transaction_amount,
            commission_rate=rate,
            commission_amount=amount,
            recipient_id=recipient_id,
            recipient_role=recipient_role,
            related_node_ids=related_node_ids or [],
        )

        self.records[record.record_id] = record
        self.node_commissions[recipient_id].append(record.record_id)
        self.transaction_commissions[transaction_id].append(record.record_id)

        if self.on_commission_calculated:
            self.on_commission_calculated(record)

        return record

    def calculate_discovery_commission(
        self,
        transaction_id: str,
        transaction_amount: float,
        discovery_node_id: str,
        referrer_id: str = None,
    ) -> List[CommissionRecord]:
        """计算发现相关佣金"""
        records = []

        # 发现佣金
        if discovery_node_id:
            record = self.calculate_commission(
                transaction_id=transaction_id,
                transaction_amount=transaction_amount,
                commission_type=CommissionType.DISCOVERY,
                recipient_id=discovery_node_id,
                recipient_role="discovery_node",
            )
            records.append(record)

        # 推荐佣金
        if referrer_id:
            record = self.calculate_commission(
                transaction_id=transaction_id,
                transaction_amount=transaction_amount,
                commission_type=CommissionType.REFERRAL,
                recipient_id=referrer_id,
                recipient_role="referrer",
            )
            records.append(record)

        return records

    def calculate_witness_commission(
        self,
        transaction_id: str,
        transaction_amount: float,
        witness_ids: List[str],
    ) -> List[CommissionRecord]:
        """计算见证佣金"""
        if not witness_ids:
            return []

        # 均分见证佣金
        witness_rate = self.RATES[CommissionType.WITNESS]
        total_witness_amount = transaction_amount * witness_rate
        per_witness_amount = total_witness_amount / len(witness_ids)

        records = []
        for witness_id in witness_ids:
            record = self.calculate_commission(
                transaction_id=transaction_id,
                transaction_amount=transaction_amount,
                commission_type=CommissionType.WITNESS,
                recipient_id=witness_id,
                recipient_role="witness",
                related_node_ids=witness_ids,
            )
            records.append(record)

        return records

    def calculate_network_commission(
        self,
        transaction_id: str,
        transaction_amount: float,
        index_node_ids: List[str],
    ) -> List[CommissionRecord]:
        """计算网络维护佣金"""
        if not index_node_ids:
            return []

        # 按存储量加权分配（简化：均分）
        network_rate = self.RATES[CommissionType.NETWORK]
        total_network_amount = transaction_amount * network_rate
        per_node_amount = total_network_amount / len(index_node_ids)

        records = []
        for node_id in index_node_ids:
            record = self.calculate_commission(
                transaction_id=transaction_id,
                transaction_amount=transaction_amount,
                commission_type=CommissionType.NETWORK,
                recipient_id=node_id,
                recipient_role="index_node",
                related_node_ids=index_node_ids,
            )
            records.append(record)

        return records

    def mark_paid(self, record_id: str) -> bool:
        """标记佣金已支付"""
        record = self.records.get(record_id)
        if not record:
            return False

        if record.status == "paid":
            return False

        record.status = "paid"
        record.paid_at = time.time()
        self.total_commissions_paid += record.commission_amount

        if self.on_commission_paid:
            self.on_commission_paid(record)

        return True

    def mark_paid_by_transaction(self, transaction_id: str) -> int:
        """标记交易关联的所有佣金已支付"""
        record_ids = self.transaction_commissions.get(transaction_id, [])
        count = 0
        for record_id in record_ids:
            if self.mark_paid(record_id):
                count += 1
        return count

    def get_node_commissions(
        self,
        node_id: str,
        status: str = None,
        commission_type: CommissionType = None,
    ) -> List[CommissionRecord]:
        """获取节点佣金记录"""
        record_ids = self.node_commissions.get(node_id, [])
        results = []

        for record_id in record_ids:
            record = self.records.get(record_id)
            if not record:
                continue

            if status and record.status != status:
                continue

            if commission_type and record.commission_type != commission_type:
                continue

            results.append(record)

        return sorted(results, key=lambda x: x.created_at, reverse=True)

    def get_pending_commissions(self, node_id: str) -> List[CommissionRecord]:
        """获取待支付佣金"""
        return self.get_node_commissions(node_id, status="pending")

    def get_total_commissions(self, node_id: str) -> Dict:
        """获取节点累计佣金"""
        records = self.get_node_commissions(node_id)

        total_pending = sum(r.commission_amount for r in records if r.status == "pending")
        total_paid = sum(r.commission_amount for r in records if r.status == "paid")

        by_type = defaultdict(float)
        for r in records:
            by_type[r.commission_type.value] += r.commission_amount

        return {
            "total_pending": total_pending,
            "total_paid": total_paid,
            "by_type": dict(by_type),
        }

    def get_transaction_commissions(self, transaction_id: str) -> List[CommissionRecord]:
        """获取交易关联的佣金记录"""
        record_ids = self.transaction_commissions.get(transaction_id, [])
        return [self.records[rid] for rid in record_ids if rid in self.records]

    def get_commission_summary(self) -> Dict:
        """获取佣金汇总"""
        all_records = list(self.records.values())

        pending = sum(1 for r in all_records if r.status == "pending")
        paid = sum(1 for r in all_records if r.status == "paid")

        pending_amount = sum(r.commission_amount for r in all_records if r.status == "pending")
        paid_amount = sum(r.commission_amount for r in all_records if r.status == "paid")

        by_type = defaultdict(lambda: {"count": 0, "amount": 0.0})
        for r in all_records:
            by_type[r.commission_type.value]["count"] += 1
            by_type[r.commission_type.value]["amount"] += r.commission_amount

        return {
            "total_records": len(all_records),
            "pending_count": pending,
            "paid_count": paid,
            "pending_amount": pending_amount,
            "paid_amount": paid_amount,
            "by_type": dict(by_type),
        }

    def export_records(self) -> List[Dict]:
        """导出佣金记录"""
        return [r.to_dict() for r in self.records.values()]

    def import_records(self, data: List[Dict]):
        """导入佣金记录"""
        for item in data:
            record = CommissionRecord.from_dict(item)
            self.records[record.record_id] = record
            self.node_commissions[record.recipient_id].append(record.record_id)
            self.transaction_commissions[record.transaction_id].append(record.record_id)

            if record.status == "paid":
                self.total_commissions_paid += record.commission_amount


if __name__ == "__main__":
    # 简单测试
    calculator = CommissionCalculator("node_001")

    # 计算发现佣金
    records = calculator.calculate_discovery_commission(
        transaction_id="tx_001",
        transaction_amount=1000.0,
        discovery_node_id="node_002",
        referrer_id="node_003",
    )

    print(f"Created {len(records)} commission records")
    for r in records:
        print(f"  - {r.commission_type.value}: {r.commission_amount} to {r.recipient_id}")

    # 计算见证佣金
    witness_records = calculator.calculate_witness_commission(
        transaction_id="tx_001",
        transaction_amount=1000.0,
        witness_ids=["node_004", "node_005"],
    )

    print(f"\nCreated {len(witness_records)} witness records")
    for r in witness_records:
        print(f"  - {r.commission_type.value}: {r.commission_amount} to {r.recipient_id}")

    # 汇总
    summary = calculator.get_commission_summary()
    print(f"\nTotal pending: {summary['pending_amount']}")
