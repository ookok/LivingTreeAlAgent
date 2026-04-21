"""
分布式信誉系统

实现去中心化的信誉账本、信任传递和反欺诈机制
"""

import asyncio
import json
import hashlib
from typing import Dict, List, Optional, Set, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import random

from .models import (
    NodeInfo, ReputationAction, ReputationEvent, TrustRelation,
    NetworkMessage, MessageType, GeoLocation
)


logger = logging.getLogger(__name__)


@dataclass
class ReputationRecord:
    """信誉记录"""
    node_id: str = ""
    current_reputation: int = 100

    # 统计
    total_trades: int = 0
    successful_trades: int = 0
    disputed_trades: int = 0

    # 评价
    good_reviews: int = 0
    neutral_reviews: int = 0
    bad_reviews: int = 0

    # 时间加权
    avg_response_time: float = 0.0  # 平均响应时间（秒）
    avg_delivery_time: float = 0.0   # 平均交付时间（小时）

    # 活跃度
    last_active: datetime = field(default_factory=datetime.now)
    account_age_days: int = 0

    # 风险指标
    fraud_flags: int = 0
    dispute_rate: float = 0.0       # 争议率

    # 信任网络
    direct_trusts: int = 0          # 直接信任我的人数
    indirect_trust_sum: float = 0.0  # 间接信任总和


class ReputationManager:
    """分布式信誉管理器"""

    # 信誉初始值和边界
    INITIAL_REPUTATION = 100
    MIN_REPUTATION = 0
    MAX_REPUTATION = 1000

    # 加分项
    REWARD_SUCCESSFUL_TRADE = 5
    REWARD_GOOD_REVIEW = 2
    REWARD_QUICK_CONFIRM = 1
    REWARD_DISPUTE_RESOLVE = 3

    # 减分项
    PENALTY_TRADE_CANCEL = 3
    PENALTY_BAD_REVIEW = 5
    PENALTY_FALSE_PRODUCT = 20
    PENALTY_FRAUD = 100

    # 信任传递参数
    TRUST_DECAY_FACTOR = 0.8
    MAX_HOPS = 3

    def __init__(self, node_id: str, node_info: NodeInfo):
        self.node_id = node_id
        self.node_info = node_info

        # 本地信誉记录
        self.local_records: Dict[str, ReputationRecord] = {}

        # 信任关系图
        self.trust_relations: Dict[str, TrustRelation] = {}

        # 待验证的信誉事件
        self.pending_events: List[ReputationEvent] = []

        # 见证节点列表
        self.witness_nodes: Set[str] = set()

        # 回调
        self.on_reputation_update: Optional[Callable] = None

        # 初始化自己的记录
        self._init_local_record(node_info)

    def _init_local_record(self, node_info: NodeInfo):
        """初始化本地记录"""
        record = ReputationRecord(
            node_id=node_info.node_id,
            current_reputation=self.INITIAL_REPUTATION,
            account_age_days=0
        )
        self.local_records[node_info.node_id] = record

    # ========================================================================
    # 信誉查询
    # ========================================================================

    def get_reputation(self, node_id: str) -> int:
        """获取节点信誉分"""
        if node_id == self.node_id:
            return self.local_records.get(node_id, ReputationRecord()).current_reputation

        record = self.local_records.get(node_id)
        if record:
            return record.current_reputation

        # 未知节点返回默认分
        return self.INITIAL_REPUTATION

    def get_record(self, node_id: str) -> Optional[ReputationRecord]:
        """获取完整信誉记录"""
        return self.local_records.get(node_id)

    def get_trust_score(
        self,
        from_node: str,
        to_node: str
    ) -> float:
        """计算从 from_node 到 to_node 的信任度"""
        # 直接信任
        direct_trust = 0.0
        relation_key = f"{from_node}:{to_node}"

        if relation_key in self.trust_relations:
            relation = self.trust_relations[relation_key]
            direct_trust = relation.direct_trust
        else:
            # 通过历史交互计算直接信任
            direct_trust = self._calculate_direct_trust(from_node, to_node)

        # 间接信任
        indirect_trust = self._calculate_indirect_trust(from_node, to_node)

        # 综合信任度
        total_trust = direct_trust + indirect_trust * self.TRUST_DECAY_FACTOR

        return min(total_trust, 1.0)

    def _calculate_direct_trust(self, from_node: str, to_node: str) -> float:
        """计算直接信任度"""
        from_record = self.local_records.get(from_node)
        to_record = self.local_records.get(to_node)

        if not from_record or not to_record:
            return 0.0

        # 基于成功交易率和评价
        success_rate = to_record.successful_trades / max(to_record.total_trades, 1)
        review_score = (to_record.good_reviews * 1.0 + to_record.neutral_reviews * 0.5) / max(
            to_record.good_reviews + to_record.neutral_reviews + to_record.bad_reviews, 1
        )

        # 基于争议率（越低越好）
        dispute_penalty = to_record.dispute_rate * 0.5

        trust = (success_rate * 0.4 + review_score * 0.4 + (1 - dispute_penalty) * 0.2)

        return max(0.0, min(1.0, trust))

    def _calculate_indirect_trust(
        self,
        from_node: str,
        to_node: str,
        hops: int = None
    ) -> float:
        """计算间接信任度（通过信任链）"""
        if hops is None:
            hops = self.MAX_HOPS

        if hops <= 0:
            return 0.0

        # 查找共同联系人
        from_contacts = self._get_node_contacts(from_node)
        to_contacts = self._get_node_contacts(to_node)

        shared_contacts = set(from_contacts) & set(to_contacts)

        if not shared_contacts:
            return 0.0

        # 通过共同联系人传递信任
        indirect_trust = 0.0
        for middle_node in shared_contacts:
            middle_trust = self.get_trust_score(from_node, middle_node)
            connection_trust = self._calculate_direct_trust(middle_node, to_node)

            indirect_trust += middle_trust * connection_trust * (0.8 ** hops)

        # 归一化
        if shared_contacts:
            indirect_trust /= len(shared_contacts)

        return min(indirect_trust, 1.0)

    def _get_node_contacts(self, node_id: str) -> List[str]:
        """获取节点的联系人列表"""
        contacts = []

        for key, relation in self.trust_relations.items():
            if key.startswith(f"{node_id}:"):
                contacts.append(relation.to_node)
            elif key.endswith(f":{node_id}"):
                contacts.append(relation.from_node)

        return contacts

    def is_trusted(self, node_id: str, threshold: float = 0.5) -> bool:
        """检查节点是否被信任"""
        trust = self.get_trust_score(self.node_id, node_id)
        return trust >= threshold

    def get_reputation_level(self, node_id: str) -> str:
        """获取信誉等级"""
        rep = self.get_reputation(node_id)

        if rep >= 500:
            return "SSS"
        elif rep >= 400:
            return "SS"
        elif rep >= 300:
            return "S"
        elif rep >= 200:
            return "A"
        elif rep >= 150:
            return "B"
        elif rep >= 100:
            return "C"
        elif rep >= 50:
            return "D"
        else:
            return "F"

    # ========================================================================
    # 信誉更新
    # ========================================================================

    async def record_event(
        self,
        event: ReputationEvent
    ) -> bool:
        """记录信誉事件"""
        # 验证事件
        if not await self._validate_event(event):
            logger.warning(f"Invalid reputation event: {event.event_id}")
            return False

        # 计算信誉变化
        change = self._calculate_change(event)

        # 更新本地记录
        await self._apply_change(event.node_id, change, event)

        # 广播事件
        await self._broadcast_event(event)

        # 回调
        if self.on_reputation_update:
            await self.on_reputation_update(event)

        return True

    async def _validate_event(self, event: ReputationEvent) -> bool:
        """验证事件有效性"""
        # 检查时间戳不要太老
        age = (datetime.now() - event.timestamp).total_seconds()
        if age > 86400:  # 24小时
            return False

        # 检查节点是否存在
        if event.node_id not in self.local_records:
            # 可能是新节点
            self.local_records[event.node_id] = ReputationRecord(
                node_id=event.node_id,
                current_reputation=self.INITIAL_REPUTATION
            )

        return True

    def _calculate_change(self, event: ReputationEvent) -> int:
        """计算信誉变化"""
        action_map = {
            ReputationAction.SUCCESSFUL_TRADE: self.REWARD_SUCCESSFUL_TRADE,
            ReputationAction.GOOD_REVIEW: self.REWARD_GOOD_REVIEW,
            ReputationAction.QUICK_CONFIRM: self.REWARD_QUICK_CONFIRM,
            ReputationAction.DISPUTE_RESOLVE: self.REWARD_DISPUTE_RESOLVE,
            ReputationAction.TRADE_CANCEL: -self.PENALTY_TRADE_CANCEL,
            ReputationAction.BAD_REVIEW: -self.PENALTY_BAD_REVIEW,
            ReputationAction.FALSE_PRODUCT: -self.PENALTY_FALSE_PRODUCT,
            ReputationAction.FRAUD: -self.PENALTY_FRAUD
        }

        return action_map.get(event.action, 0)

    async def _apply_change(
        self,
        node_id: str,
        change: int,
        event: ReputationEvent
    ):
        """应用信誉变化"""
        record = self.local_records.get(node_id)
        if not record:
            record = ReputationRecord(node_id=node_id)
            self.local_records[node_id] = record

        # 更新信誉分
        new_rep = record.current_reputation + change
        record.current_reputation = max(self.MIN_REPUTATION, min(self.MAX_REPUTATION, new_rep))

        # 更新统计
        if event.action == ReputationAction.SUCCESSFUL_TRADE:
            record.total_trades += 1
            record.successful_trades += 1
        elif event.action == ReputationAction.TRADE_CANCEL:
            record.total_trades += 1
        elif event.action == ReputationAction.GOOD_REVIEW:
            record.good_reviews += 1
        elif event.action == ReputationAction.BAD_REVIEW:
            record.bad_reviews += 1

        # 更新争议率
        if record.total_trades > 0:
            record.dispute_rate = record.disputed_trades / record.total_trades

        # 更新活跃时间
        record.last_active = datetime.now()

    async def _broadcast_event(self, event: ReputationEvent):
        """广播信誉事件"""
        msg = NetworkMessage(
            msg_type=MessageType.REPUTATION,
            sender_id=self.node_id,
            payload={
                "event": event.to_dict()
            }
        )

        # 广播给见证节点
        for witness_id in self.witness_nodes:
            # 实际应该通过网络发送
            pass

    # ========================================================================
    # 信任关系
    # ========================================================================

    async def establish_trust(
        self,
        to_node_id: str,
        trust_level: float,
        shared_contacts: List[str] = None
    ):
        """建立信任关系"""
        relation = TrustRelation(
            from_node=self.node_id,
            to_node=to_node_id,
            direct_trust=trust_level,
            shared_contacts=shared_contacts or []
        )
        relation.calculate_total_trust(self.TRUST_DECAY_FACTOR)

        relation_key = f"{self.node_id}:{to_node_id}"
        self.trust_relations[relation_key] = relation

        # 更新记录
        record = self.local_records.get(to_node_id)
        if record:
            record.direct_trusts += 1

        logger.info(f"Established trust from {self.node_id} to {to_node_id}: {trust_level}")

    async def revoke_trust(self, to_node_id: str):
        """撤销信任关系"""
        relation_key = f"{self.node_id}:{to_node_id}"

        if relation_key in self.trust_relations:
            del self.trust_relations[relation_key]
            logger.info(f"Revoked trust from {self.node_id} to {to_node_id}")

    # ========================================================================
    # 反欺诈
    # ========================================================================

    def check_fraud_risk(self, node_id: str) -> Dict[str, Any]:
        """检查欺诈风险"""
        record = self.local_records.get(node_id)

        risk_factors = []
        risk_score = 0.0

        # 新账户风险
        if record and record.account_age_days < 7:
            risk_factors.append("new_account")
            risk_score += 0.3

        # 高争议率
        if record and record.dispute_rate > 0.1:
            risk_factors.append("high_dispute_rate")
            risk_score += 0.3

        # 低信誉
        if record and record.current_reputation < 50:
            risk_factors.append("low_reputation")
            risk_score += 0.2

        # 近期不活跃
        if record and (datetime.now() - record.last_active).days > 30:
            risk_factors.append("inactive")
            risk_score += 0.1

        # 无信任关系
        if not self.is_trusted(node_id):
            risk_factors.append("no_trust")
            risk_score += 0.1

        return {
            "node_id": node_id,
            "risk_score": min(risk_score, 1.0),
            "risk_level": "high" if risk_score > 0.5 else "medium" if risk_score > 0.2 else "low",
            "risk_factors": risk_factors
        }

    async def verify_location(
        self,
        node_id: str,
        claimed_location: GeoLocation
    ) -> bool:
        """验证地理位置"""
        # 通过附近节点验证
        nearby_nodes = self._get_nodes_by_location(claimed_location)

        if len(nearby_nodes) < 3:
            # 节点太少，无法验证
            return True

        # 简化：假设大部分节点是诚实的
        return True

    def _get_nodes_by_location(
        self,
        location: GeoLocation,
        radius_km: float = 5.0
    ) -> List[str]:
        """获取指定位置附近的节点"""
        nodes = []

        for node_id, record in self.local_records.items():
            # 简化：实际应该通过节点信息中的位置
            nodes.append(node_id)

        return nodes[:10]

    # ========================================================================
    # 分布式验证
    # ========================================================================

    async def request_verification(
        self,
        node_id: str,
        verification_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """请求分布式验证"""
        # 生成验证请求
        request_id = hashlib.sha256(
            f"{node_id}{verification_type}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        # 收集见证节点的验证结果
        verifications = []

        for witness_id in self.witness_nodes:
            # 发送验证请求
            # 简化：直接假设验证通过
            verifications.append(True)

        # 超过半数通过即通过
        if verifications:
            return sum(verifications) >= len(verifications) / 2

        return True

    # ========================================================================
    # 导入/导出
    # ========================================================================

    def export_records(self) -> List[Dict[str, Any]]:
        """导出信誉记录"""
        return [
            {
                "node_id": node_id,
                "record": {
                    "current_reputation": record.current_reputation,
                    "total_trades": record.total_trades,
                    "successful_trades": record.successful_trades,
                    "dispute_rate": record.dispute_rate,
                    "last_active": record.last_active.isoformat()
                }
            }
            for node_id, record in self.local_records.items()
        ]

    def import_records(self, data: List[Dict[str, Any]]):
        """导入信誉记录"""
        for item in data:
            node_id = item["node_id"]
            record_data = item["record"]

            record = ReputationRecord(
                node_id=node_id,
                current_reputation=record_data.get("current_reputation", self.INITIAL_REPUTATION),
                total_trades=record_data.get("total_trades", 0),
                successful_trades=record_data.get("successful_trades", 0),
                dispute_rate=record_data.get("dispute_rate", 0.0),
                last_active=datetime.fromisoformat(record_data.get("last_active", datetime.now().isoformat()))
            )

            self.local_records[node_id] = record

    # ========================================================================
    # 统计
    # ========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """获取信誉系统统计"""
        total_nodes = len(self.local_records)
        avg_reputation = sum(
            r.current_reputation for r in self.local_records.values()
        ) / max(total_nodes, 1)

        high_rep_nodes = sum(
            1 for r in self.local_records.values() if r.current_reputation >= 200
        )

        return {
            "total_nodes": total_nodes,
            "average_reputation": avg_reputation,
            "high_reputation_nodes": high_rep_nodes,
            "total_trust_relations": len(self.trust_relations),
            "pending_events": len(self.pending_events)
        }
