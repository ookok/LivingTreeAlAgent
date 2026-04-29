"""
Credit Network - 贡献证明与激励网络
===================================

功能：
- 贡献证明生成与验证
- 贡献账本
- 声誉评分
- 资源配额计算

Author: LivingTreeAI Community
"""

import asyncio
import hashlib
import time
import json
import random
import struct
from dataclasses import dataclass, field
from typing import Optional, Any, Callable, Awaitable
from enum import Enum
from collections import defaultdict


class ContributionType(Enum):
    """贡献类型"""
    SEARCH_EXECUTED = "search_executed"      # 执行搜索
    CACHE_PROVIDED = "cache_provided"        # 提供缓存
    DATA_RELAYED = "data_relayed"            # 数据转发
    COMPUTE_SHARED = "compute_shared"         # 共享算力
    BANDWIDTH_DONATED = "bandwidth_donated"  # 捐赠带宽
    KNOWLEDGE_SHARED = "knowledge_shared"     # 共享知识


@dataclass
class ContributionProof:
    """贡献证明"""
    proof_id: str
    node_id: str
    event_type: ContributionType
    resource_consumed: float
    beneficiary: str  # 受益者node_id或"network"
    timestamp: int
    nonce: int
    pow: str  # 工作量证明
    signature: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "proof_id": self.proof_id,
            "node_id": self.node_id,
            "event_type": self.event_type.value,
            "resource_consumed": self.resource_consumed,
            "beneficiary": self.beneficiary,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "pow": self.pow,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContributionProof":
        return cls(
            proof_id=data["proof_id"],
            node_id=data["node_id"],
            event_type=ContributionType(data["event_type"]),
            resource_consumed=data["resource_consumed"],
            beneficiary=data["beneficiary"],
            timestamp=data["timestamp"],
            nonce=data["nonce"],
            pow=data["pow"],
            signature=data.get("signature"),
        )


@dataclass
class ReputationScore:
    """声誉评分"""
    node_id: str
    total_contributions: int = 0
    successful_contributions: int = 0
    failed_contributions: int = 0
    total_rewards: float = 0.0
    avg_quality: float = 1.0  # 0-1
    response_time_score: float = 1.0  # 0-1
    reliability_score: float = 1.0  # 0-1
    last_updated: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float:
        if self.total_contributions == 0:
            return 1.0
        return self.successful_contributions / self.total_contributions

    @property
    def overall_score(self) -> float:
        """综合声誉分"""
        return (
            self.success_rate * 0.3 +
            self.avg_quality * 0.3 +
            self.response_time_score * 0.2 +
            self.reliability_score * 0.2
        )

    def update_contribution(self, success: bool, quality: float = 1.0):
        """更新贡献记录"""
        self.total_contributions += 1
        if success:
            self.successful_contributions += 1
        else:
            self.failed_contributions += 1

        # 滑动平均更新质量分
        self.avg_quality = self.avg_quality * 0.9 + quality * 0.1
        self.last_updated = time.time()

    def update_response_time(self, latency_ms: float):
        """更新响应时间评分"""
        # 响应时间越短越好
        if latency_ms < 100:
            score = 1.0
        elif latency_ms < 500:
            score = 0.9
        elif latency_ms < 1000:
            score = 0.7
        elif latency_ms < 3000:
            score = 0.5
        else:
            score = 0.3

        self.response_time_score = self.response_time_score * 0.8 + score * 0.2


class ContributionLedger:
    """贡献账本（本地）"""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._records: list[ContributionProof] = []
        self._pending_broadcasts: list[ContributionProof] = []

    def add_record(self, proof: ContributionProof):
        """添加贡献记录"""
        self._records.append(proof)

    def get_recent_records(
        self,
        hours: int = 24,
        node_id: Optional[str] = None
    ) -> list[ContributionProof]:
        """获取最近的贡献记录"""
        cutoff = time.time() - hours * 3600
        records = [r for r in self._records if r.timestamp > cutoff]

        if node_id:
            records = [r for r in records if r.node_id == node_id]

        return records

    def get_total_contributions(self, node_id: Optional[str] = None) -> dict:
        """获取总贡献统计"""
        records = self._records if not node_id else [
            r for r in self._records if r.node_id == node_id
        ]

        totals = defaultdict(float)
        for record in records:
            totals[record.event_type.value] += 1
            totals["total_resource"] += record.resource_consumed

        return dict(totals)

    def get_pending_broadcasts(self) -> list[ContributionProof]:
        """获取待广播的贡献"""
        pending = self._pending_broadcasts.copy()
        self._pending_broadcasts.clear()
        return pending

    def mark_broadcast_sent(self, proof_ids: list[str]):
        """标记已广播的贡献"""
        # 实际实现中可能需要持久化


class QuotaManager:
    """资源配额管理器"""

    BASE_QUOTAS = {
        "search_queries": 50,      # 基础搜索配额
        "bandwidth_mb": 100,        # 基础带宽配额(MB)
        "cache_mb": 500,            # 基础缓存配额(MB)
        "api_calls": 100,           # 基础API调用配额
    }

    CONTRIBUTION_BONUS = {
        ContributionType.SEARCH_EXECUTED: {"search_queries": 2},
        ContributionType.CACHE_PROVIDED: {"cache_mb": 10},
        ContributionType.DATA_RELAYED: {"bandwidth_mb": 5},
        ContributionType.COMPUTE_SHARED: {"api_calls": 10},
        ContributionType.BANDWIDTH_DONATED: {"bandwidth_mb": 20},
        ContributionType.KNOWLEDGE_SHARED: {"search_queries": 5, "cache_mb": 20},
    }

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.quotas: dict[str, float] = self.BASE_QUOTAS.copy()
        self.used: dict[str, float] = defaultdict(float)

    def calculate_quotas(self, node_id: str, contributions: list[ContributionProof]) -> dict:
        """基于历史贡献计算配额"""
        quotas = self.BASE_QUOTAS.copy()

        for contrib in contributions:
            bonuses = self.CONTRIBUTION_BONUS.get(contrib.event_type, {})
            for resource, bonus in bonuses.items():
                quotas[resource] = quotas.get(resource, 0) + bonus

        self.quotas = quotas
        return quotas

    def check_quota(self, resource: str, amount: float = 1) -> bool:
        """检查配额是否足够"""
        available = self.quotas.get(resource, 0) - self.used.get(resource, 0)
        return available >= amount

    def consume_quota(self, resource: str, amount: float = 1):
        """消耗配额"""
        self.used[resource] = self.used.get(resource, 0) + amount

    def get_available(self, resource: str) -> float:
        """获取可用配额"""
        return max(0, self.quotas.get(resource, 0) - self.used.get(resource, 0))

    def reset_daily(self):
        """重置每日配额"""
        for key in self.used:
            self.used[key] = 0


class CreditNetwork:
    """
    贡献证明与激励网络

    功能：
    1. 贡献证明生成
    2. 工作量证明
    3. 贡献广播
    4. 声誉更新
    5. 配额管理
    """

    def __init__(
        self,
        node_id: str,
        broadcast_func: Optional[Callable[[dict], Awaitable]] = None,
        db_path: Optional[str] = None,
    ):
        self.node_id = node_id
        self.ledger = ContributionLedger(node_id)
        self.reputations: dict[str, ReputationScore] = {}
        self.quota_manager = QuotaManager(node_id)

        # 广播函数（由外部注入）
        self._broadcast_func = broadcast_func

        # 可选数据库路径
        self._db_path = db_path

        # 配置
        self._pow_difficulty = 4  # 工作量证明难度（前4位为0）

    async def record_contribution(
        self,
        event_type: ContributionType,
        details: dict,
        broadcast: bool = True,
    ) -> ContributionProof:
        """
        记录一次贡献

        流程：
        1. 生成贡献证明
        2. 计算工作量证明
        3. 记录到本地账本
        4. 广播贡献证明（可选）
        5. 更新声誉评分
        """
        # 1. 生成贡献数据
        resource_consumed = self._calculate_resource_consumed(event_type, details)
        beneficiary = details.get("beneficiary", "network")

        proof_data = {
            "node_id": self.node_id,
            "event_type": event_type,
            "resource_consumed": resource_consumed,
            "beneficiary": beneficiary,
            "timestamp": int(time.time()),
            "nonce": random.randint(0, 100000),
        }

        # 2. 生成工作量证明
        proof_data["pow"] = self._generate_pow(proof_data)
        proof_data["proof_id"] = self._generate_proof_id(proof_data)

        proof = ContributionProof(**proof_data)

        # 3. 记录到本地账本
        self.ledger.add_record(proof)

        # 4. 广播
        if broadcast and self._should_broadcast(event_type):
            self.ledger._pending_broadcasts.append(proof)

        # 5. 更新声誉
        self._update_reputation(self.node_id, success=True, quality=1.0)

        return proof

    def _calculate_resource_consumed(self, event_type: ContributionType, details: dict) -> float:
        """计算消耗的资源量"""
        if event_type == ContributionType.SEARCH_EXECUTED:
            return details.get("query_complexity", 1.0)
        elif event_type == ContributionType.CACHE_PROVIDED:
            return details.get("cache_size_kb", 0) / 1024  # MB
        elif event_type == ContributionType.DATA_RELAYED:
            return details.get("data_size_mb", 0)
        elif event_type == ContributionType.COMPUTE_SHARED:
            return details.get("compute_units", 1.0)
        elif event_type == ContributionType.BANDWIDTH_DONATED:
            return details.get("bandwidth_mb", 0)
        elif event_type == ContributionType.KNOWLEDGE_SHARED:
            return details.get("knowledge_size_mb", 0)
        return 0.0

    def _generate_proof_id(self, proof_data: dict) -> str:
        """生成证明ID"""
        data = json.dumps(proof_data, sort_keys=True).encode()
        return hashlib.sha256(data).hexdigest()[:16]

    def _generate_pow(self, proof_data: dict) -> str:
        """
        生成工作量证明

        简单实现：找到以指定数量0开头的哈希
        """
        target = "0" * self._pow_difficulty

        base_data = {
            "node_id": proof_data["node_id"],
            "event_type": proof_data["event_type"].value,
            "timestamp": proof_data["timestamp"],
            "nonce": proof_data["nonce"],
        }

        # 简单的工作量证明
        for i in range(1000000):
            test_data = base_data.copy()
            test_data["nonce"] = proof_data["nonce"] + i
            data_str = json.dumps(test_data, sort_keys=True)
            hash_result = hashlib.sha256(data_str.encode()).hexdigest()

            if hash_result.startswith(target):
                return hash_result

        # 如果找不到，返回简单哈希
        data_str = json.dumps(base_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def verify_pow(self, proof: ContributionProof) -> bool:
        """验证工作量证明"""
        target = "0" * self._pow_difficulty
        return proof.pow.startswith(target)

    def _should_broadcast(self, event_type: ContributionType) -> bool:
        """判断是否应该广播"""
        # 高价值贡献才广播
        return event_type in [
            ContributionType.CACHE_PROVIDED,
            ContributionType.KNOWLEDGE_SHARED,
            ContributionType.COMPUTE_SHARED,
        ]

    async def broadcast_pending_contributions(self):
        """广播待处理的贡献"""
        pending = self.ledger.get_pending_broadcasts()

        for proof in pending:
            if self._broadcast_func:
                try:
                    await self._broadcast_func(proof.to_dict())
                except Exception:
                    pass

    def _update_reputation(
        self,
        node_id: str,
        success: bool,
        quality: float = 1.0,
        latency_ms: Optional[float] = None,
    ):
        """更新节点声誉"""
        if node_id not in self.reputations:
            self.reputations[node_id] = ReputationScore(node_id)

        rep = self.reputations[node_id]
        rep.update_contribution(success, quality)

        if latency_ms is not None:
            rep.update_response_time(latency_ms)

    async def process_contribution_proof(self, proof: ContributionProof):
        """处理收到的贡献证明"""
        # 验证工作量证明
        if not self.verify_pow(proof):
            return False

        # 验证时间戳（不接受太老的）
        now = time.time()
        if abs(now - proof.timestamp) > 3600:  # 1小时外的不接受
            return False

        # 更新声誉
        self._update_reputation(proof.node_id, success=True, quality=1.0)

        # 记录到账本（如果是自己节点的）
        if proof.beneficiary == self.node_id:
            self.ledger.add_record(proof)

        return True

    def calculate_quotas(self, node_id: str, hours: int = 24) -> dict:
        """计算节点资源配额"""
        contributions = self.ledger.get_recent_records(hours=hours, node_id=node_id)
        return self.quota_manager.calculate_quotas(node_id, contributions)

    def get_network_stats(self) -> dict:
        """获取网络统计"""
        return {
            "total_records": len(self.ledger._records),
            "pending_broadcasts": len(self.ledger._pending_broadcasts),
            "node_count": len(self.reputations),
            "quotas": self.quota_manager.quotas,
            "used": dict(self.quota_manager.used),
        }

    def get_reputation_leaderboard(self, top_k: int = 10) -> list[dict]:
        """获取声誉排行榜"""
        sorted_reps = sorted(
            self.reputations.items(),
            key=lambda x: x[1].overall_score,
            reverse=True
        )

        return [
            {
                "node_id": node_id,
                "score": rep.overall_score,
                "total_contributions": rep.total_contributions,
                "success_rate": rep.success_rate,
            }
            for node_id, rep in sorted_reps[:top_k]
        ]


# 全局单例
_credit_instance: Optional[CreditNetwork] = None


def get_credit_network(node_id: str = "local") -> CreditNetwork:
    """获取信用网络单例"""
    global _credit_instance
    if _credit_instance is None:
        _credit_instance = CreditNetwork(node_id)
    return _credit_instance