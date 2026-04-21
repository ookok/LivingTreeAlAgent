"""
去中心化仲裁系统

实现社区仲裁和争议解决机制
"""

import asyncio
import json
import hashlib
import random
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

from .models import (
    Dispute, DisputeEvidence, ArbitratorVote, Trade, TradeParticipant,
    TransactionStatus, NetworkMessage, MessageType, GeoLocation
)
from .reputation import ReputationManager


logger = logging.getLogger(__name__)


class ArbitrationStatus(Enum):
    """仲裁状态"""
    OPEN = "open"              # 开放（等待仲裁员）
    VOTING = "voting"          # 投票中
    DECIDED = "decided"        # 已裁决
    EXECUTED = "executed"      # 已执行


@dataclass
class ArbitratorInfo:
    """仲裁员信息"""
    node_id: str = ""
    reputation: int = 200       # 最低要求
    arbitration_count: int = 0   # 已完成的仲裁次数
    fair_rate: float = 0.8      # 公正率
    total_votes: int = 0        # 总投票数

    # 可用性
    is_available: bool = True
    current_load: int = 0       # 当前处理的案件数


class ArbitrationManager:
    """去中心化仲裁管理器"""

    # 仲裁员资格要求
    MIN_REPUTATION = 200
    MIN_FAIR_RATE = 0.8
    MIN_ARBITRATIONS = 3
    MAX_CONCURRENT = 5

    # 仲裁庭配置
    ARBITRATOR_COUNT = 5        # 每个案件选择的仲裁员数
    VOTE_DEADLINE_HOURS = 24    # 投票截止时间
    APPEAL_DEADLINE_HOURS = 48  # 上诉截止时间

    def __init__(
        self,
        node_id: str,
        reputation_manager: ReputationManager
    ):
        self.node_id = node_id
        self.reputation_manager = reputation_manager

        # 活跃争议
        self.active_disputes: Dict[str, Dispute] = {}

        # 已完成的争议
        self.closed_disputes: Dict[str, Dispute] = {}

        # 可用仲裁员池
        self.arbitrator_pool: Dict[str, ArbitratorInfo] = {}

        # 我的角色
        self.is_arbitrator: bool = False
        self.my_cases: List[str] = []  # 我正在处理的案件ID

        # 回调
        self.on_dispute_opened: Optional[Callable] = None
        self.on_dispute_decided: Optional[Callable] = None

    # ========================================================================
    # 争议创建
    # ========================================================================

    async def open_dispute(
        self,
        trade: Trade,
        reason: str,
        category: str = "quality"
    ) -> Dispute:
        """发起争议"""
        dispute_id = str(hashlib.sha256(
            f"{trade.trade_id}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12])

        dispute = Dispute(
            dispute_id=dispute_id,
            trade_id=trade.trade_id,
            complainant_id=self.node_id,  # 简化：假设发起方是 complainant
            respondent_id=trade.seller.node_id if self.node_id == trade.buyer.node_id else trade.buyer.node_id,
            reason=reason,
            category=category,
            status="open"
        )

        self.active_disputes[dispute_id] = dispute

        # 自动选择仲裁员
        await self._select_arbitrators(dispute)

        # 通知被投诉方
        await self._notify_respondent(dispute)

        # 回调
        if self.on_dispute_opened:
            await self.on_dispute_opened(dispute)

        logger.info(f"Dispute {dispute_id} opened for trade {trade.trade_id}")
        return dispute

    async def _select_arbitrators(self, dispute: Dispute):
        """选择仲裁员"""
        eligible = self._find_eligible_arbitrators()

        if len(eligible) < self.ARBITRATOR_COUNT:
            logger.warning(f"Not enough eligible arbitrators: {len(eligible)}")
            # 降低要求重试
            eligible = self._find_eligible_arbitrators(min_rep=100, min_fair=0.6)

        # 随机选择
        selected = random.sample(
            eligible,
            min(self.ARBITRATOR_COUNT, len(eligible))
        )

        dispute.arbitrators = selected

        # 更新仲裁员负载
        for arbitrator_id in selected:
            if arbitrator_id in self.arbitrator_pool:
                self.arbitrator_pool[arbitrator_id].current_load += 1

        dispute.status = "voting"

        # 通知仲裁员
        await self._notify_arbitrators(dispute)

    def _find_eligible_arbitrators(
        self,
        min_rep: int = None,
        min_fair: float = None
    ) -> List[str]:
        """查找符合条件的仲裁员"""
        if min_rep is None:
            min_rep = self.MIN_REPUTATION
        if min_fair is None:
            min_fair = self.MIN_FAIR_RATE

        eligible = []

        for node_id, info in self.arbitrator_pool.items():
            if not info.is_available:
                continue

            if info.current_load >= self.MAX_CONCURRENT:
                continue

            if node_id in [dispute.complainant_id, dispute.respondent_id]:
                continue

            record = self.reputation_manager.get_record(node_id)
            if not record:
                continue

            if record.current_reputation < min_rep:
                continue

            if info.fair_rate < min_fair:
                continue

            eligible.append(node_id)

        return eligible

    # ========================================================================
    # 证据提交
    # ========================================================================

    async def submit_evidence(
        self,
        dispute_id: str,
        evidence_type: str,
        description: str,
        content: str = ""
    ) -> DisputeEvidence:
        """提交证据"""
        if dispute_id not in self.active_disputes:
            raise ValueError(f"Dispute {dispute_id} not found")

        dispute = self.active_disputes[dispute_id]

        evidence = DisputeEvidence(
            dispute_id=dispute_id,
            evidence_type=evidence_type,
            description=description,
            content=content,
            submitted_by=self.node_id
        )

        dispute.evidence.append(evidence)

        # 广播证据给仲裁员
        await self._broadcast_evidence(dispute, evidence)

        logger.info(f"Evidence {evidence.evidence_id} submitted for dispute {dispute_id}")
        return evidence

    async def _broadcast_evidence(self, dispute: Dispute, evidence: DisputeEvidence):
        """广播证据给仲裁员"""
        msg = NetworkMessage(
            msg_type=MessageType.ARBITRATION,
            sender_id=self.node_id,
            payload={
                "action": "new_evidence",
                "dispute_id": dispute.dispute_id,
                "evidence": evidence.__dict__
            }
        )

        for arbitrator_id in dispute.arbitrators:
            if arbitrator_id != self.node_id:
                # 实际应该通过网络发送
                pass

    # ========================================================================
    # 投票
    # ========================================================================

    async def cast_vote(
        self,
        dispute_id: str,
        vote: str,  # "buyer_wins" / "seller_wins" / "reject"
        reasoning: str = ""
    ) -> bool:
        """仲裁员投票"""
        if dispute_id not in self.active_disputes:
            raise ValueError(f"Dispute {dispute_id} not found")

        dispute = self.active_disputes[dispute_id]

        if self.node_id not in dispute.arbitrators:
            raise PermissionError("You are not an arbitrator for this dispute")

        if dispute.status != "voting":
            raise ValueError(f"Dispute is not in voting status: {dispute.status}")

        # 检查是否已投票
        for existing_vote in dispute.votes:
            if existing_vote.arbitrator_id == self.node_id:
                raise ValueError("You have already voted")

        # 记录投票
        vote_obj = ArbitratorVote(
            arbitrator_id=self.node_id,
            vote=vote,
            reasoning=reasoning
        )

        dispute.votes.append(vote_obj)

        logger.info(f"Vote cast by {self.node_id} for dispute {dispute_id}: {vote}")

        # 检查是否所有人都投票了
        if len(dispute.votes) >= self.ARBITRATOR_COUNT:
            await self._finalize_voting(dispute)

        return True

    async def _finalize_voting(self, dispute: Dispute):
        """最终确定投票结果"""
        # 统计票数
        vote_counts = {}
        for vote in dispute.votes:
            vote_counts[vote.vote] = vote_counts.get(vote.vote, 0) + 1

        # 简单多数裁决
        max_votes = max(vote_counts.values())
        winners = [k for k, v in vote_counts.items() if v == max_votes]

        if len(winners) == 1:
            verdict = winners[0]
        elif "reject" in winners:
            verdict = "rejected"
        else:
            # 平票时随机决定（简化）
            verdict = random.choice(winners)

        # 更新争议状态
        dispute.verdict = verdict
        dispute.status = "decided"
        dispute.decided_at = datetime.now()

        # 决定理由
        dispute.verdict_reason = self._generate_verdict_reason(dispute, vote_counts)

        # 更新仲裁员统计
        await self._update_arbitrator_stats(dispute)

        # 通知双方
        await self._notify_parties(dispute)

        # 执行裁决
        await self._execute_verdict(dispute)

        # 移动到已关闭
        self.closed_disputes[dispute.dispute_id] = dispute
        del self.active_disputes[dispute.dispute_id]

        logger.info(f"Dispute {dispute.dispute_id} decided: {verdict}")

    def _generate_verdict_reason(
        self,
        dispute: Dispute,
        vote_counts: Dict[str, int]
    ) -> str:
        """生成裁决理由"""
        reasons = []

        for vote in dispute.votes:
            if vote.reasoning:
                reasons.append(vote.reasoning[:100])

        if reasons:
            return f"多数裁决 ({vote_counts})。仲裁员意见：{' '.join(reasons[:2])}"

        return f"多数裁决：{vote_counts}"

    async def _update_arbitrator_stats(self, dispute: Dispute):
        """更新仲裁员统计"""
        for vote in dispute.votes:
            if vote.arbitrator_id in self.arbitrator_pool:
                info = self.arbitrator_pool[vote.arbitrator_id]

                info.total_votes += 1
                info.current_load = max(0, info.current_load - 1)

                # 如果裁决与最终结果一致，增加公正率
                if vote.vote == dispute.verdict:
                    info.arbitration_count += 1

                info.fair_rate = info.arbitration_count / info.total_votes

    # ========================================================================
    # 裁决执行
    # ========================================================================

    async def _execute_verdict(self, dispute: Dispute):
        """执行裁决"""
        execution_details = {}

        if dispute.verdict == "buyer_wins":
            # 退款给买家
            execution_details = {
                "action": "refund_buyer",
                "beneficiary": dispute.complainant_id
            }

        elif dispute.verdict == "seller_wins":
            # 款项给卖家
            execution_details = {
                "action": "release_to_seller",
                "beneficiary": dispute.respondent_id
            }

        elif dispute.verdict == "rejected":
            # 驳回争议，维持原状
            execution_details = {
                "action": "dismiss",
                "reason": "Evidence insufficient"
            }

        dispute.execution_details = execution_details
        dispute.executed = True

        # 回调
        if self.on_dispute_decided:
            await self.on_dispute_decided(dispute)

    # ========================================================================
    # 通知
    # ========================================================================

    async def _notify_respondent(self, dispute: Dispute):
        """通知被投诉方"""
        msg = NetworkMessage(
            msg_type=MessageType.ARBITRATION,
            sender_id=self.node_id,
            receiver_id=dispute.respondent_id,
            payload={
                "action": "dispute_opened",
                "dispute": dispute.to_dict()
            }
        )

        logger.info(f"Respondent {dispute.respondent_id} notified of dispute")

    async def _notify_arbitrators(self, dispute: Dispute):
        """通知仲裁员"""
        msg = NetworkMessage(
            msg_type=MessageType.ARBITRATION,
            sender_id=self.node_id,
            payload={
                "action": "new_case",
                "dispute": dispute.to_dict()
            }
        )

        for arbitrator_id in dispute.arbitrators:
            if arbitrator_id == self.node_id:
                self.is_arbitrator = True
                self.my_cases.append(dispute.dispute_id)
            else:
                logger.info(f"Arbitrator {arbitrator_id} notified of case {dispute.dispute_id}")

    async def _notify_parties(self, dispute: Dispute):
        """通知双方裁决结果"""
        msg = NetworkMessage(
            msg_type=MessageType.ARBITRATION,
            sender_id=self.node_id,
            payload={
                "action": "verdict",
                "dispute_id": dispute.dispute_id,
                "verdict": dispute.verdict,
                "reason": dispute.verdict_reason
            }
        )

        logger.info(f"Parties notified of verdict for dispute {dispute.dispute_id}")

    # ========================================================================
    # 仲裁员管理
    # ========================================================================

    def register_as_arbitrator(self) -> bool:
        """注册为仲裁员"""
        record = self.reputation_manager.get_record(self.node_id)

        if not record:
            logger.warning("No reputation record found")
            return False

        if record.current_reputation < self.MIN_REPUTATION:
            logger.warning(f"Reputation {record.current_reputation} below minimum {self.MIN_REPUTATION}")
            return False

        self.arbitrator_pool[self.node_id] = ArbitratorInfo(
            node_id=self.node_id,
            reputation=record.current_reputation
        )

        self.is_arbitrator = True
        logger.info(f"Node {self.node_id} registered as arbitrator")
        return True

    def unregister_arbitrator(self):
        """注销仲裁员资格"""
        if self.node_id in self.arbitrator_pool:
            del self.arbitrator_pool[self.node_id]

        self.is_arbitrator = False
        self.my_cases.clear()

        logger.info(f"Node {self.node_id} unregistered as arbitrator")

    def get_arbitrator_stats(self, node_id: str = None) -> Dict[str, Any]:
        """获取仲裁员统计"""
        if node_id:
            info = self.arbitrator_pool.get(node_id)
            if info:
                return {
                    "node_id": info.node_id,
                    "reputation": info.reputation,
                    "arbitration_count": info.arbitration_count,
                    "fair_rate": info.fair_rate,
                    "total_votes": info.total_votes,
                    "current_load": info.current_load,
                    "is_available": info.is_available
                }
            return {}

        # 返回所有仲裁员的统计
        return {
            node_id: {
                "reputation": info.reputation,
                "fair_rate": info.fair_rate,
                "current_load": info.current_load
            }
            for node_id, info in self.arbitrator_pool.items()
        }

    # ========================================================================
    # 查询
    # ========================================================================

    def get_dispute(self, dispute_id: str) -> Optional[Dispute]:
        """获取争议"""
        return self.active_disputes.get(dispute_id) or self.closed_disputes.get(dispute_id)

    def get_my_cases(self) -> List[Dispute]:
        """获取我作为仲裁员处理的案件"""
        return [
            self.active_disputes.get(did) or self.closed_disputes.get(did)
            for did in self.my_cases
            if did in self.active_disputes or did in self.closed_disputes
        ]

    def get_disputes_by_status(self, status: str) -> List[Dispute]:
        """按状态获取争议"""
        if status == "open" or status == "voting":
            return [d for d in self.active_disputes.values() if d.status == status]
        elif status == "decided" or status == "executed":
            return [d for d in self.closed_disputes.values() if d.status == status]
        return []

    # ========================================================================
    # 统计
    # ========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """获取仲裁系统统计"""
        active = len(self.active_disputes)
        decided = len([d for d in self.closed_disputes.values() if d.status == "decided"])

        verdict_stats = {}
        for dispute in self.closed_disputes.values():
            verdict_stats[dispute.verdict] = verdict_stats.get(dispute.verdict, 0) + 1

        return {
            "active_disputes": active,
            "decided_disputes": decided,
            "total_arbitrators": len(self.arbitrator_pool),
            "available_arbitrators": sum(
                1 for a in self.arbitrator_pool.values() if a.is_available
            ),
            "verdict_distribution": verdict_stats
        }
