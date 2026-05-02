# -*- coding: utf-8 -*-
"""
争议解决模块
============

社区仲裁流程：
1. 争议发生
2. 提交仲裁
3. 随机选择5个仲裁员
4. 证据提交
5. 投票裁决
6. 执行结果

仲裁员资格：
- 信誉分 > 200
- 历史仲裁公正率 > 80%
"""

import uuid
import time
import random
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable, Set


class DisputeStatus(Enum):
    """争议状态"""
    CREATED = "created"                    # 创建
    VOTING = "voting"                      # 投票中
    RESOLVED = "resolved"                  # 已解决
    APPEALED = "appealed"                  # 已上诉
    CLOSED = "closed"                      # 关闭


class VoteResult(Enum):
    """投票结果"""
    BUYER_WINS = "buyer_wins"             # 买家胜
    SELLER_WINS = "seller_wins"            # 卖家胜
    SPLIT = "split"                        # 平分
    NO_CONSENSUS = "no_consensus"         # 无共识


@dataclass
class Evidence:
    """证据"""
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    evidence_type: str = ""               # chat_log/photo/location/payment/timestamp
    description: str = ""
    file_urls: List[str] = field(default_factory=list)  # IPFS URLs
    submitted_by: str = ""                 # 提交者ID
    submitted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Evidence':
        return cls(**data)


@dataclass
class ArbitratorVote:
    """仲裁员投票"""
    arbitrator_id: str = ""
    decision: str = ""                    # buyer/seller/split
    reason: str = ""
    voted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'ArbitratorVote':
        return cls(**data)


@dataclass
class Dispute:
    """争议"""
    dispute_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str = ""

    # 争议方
    initiator_id: str = ""                 # 发起方
    respondent_id: str = ""                # 被诉方

    # 争议类型
    dispute_type: str = ""                 # not_delivered/not_as_described/fraud/other
    description: str = ""                  # 争议描述

    # 状态
    status: DisputeStatus = DisputeStatus.CREATED

    # 证据
    initiator_evidence: List[Evidence] = field(default_factory=list)
    respondent_evidence: List[Evidence] = field(default_factory=list)

    # 仲裁员
    arbitrator_ids: List[str] = field(default_factory=list)  # 选中的仲裁员
    arbitrator_votes: Dict[str, ArbitratorVote] = field(default_factory=dict)  # arbitrator_id -> vote

    # 结果
    vote_result: Optional[VoteResult] = None
    resolution: str = ""                    # 裁决说明
    winner_id: str = ""                    # 胜方
    resolved_at: float = 0

    # 评分
    fairness_scores: Dict[str, int] = field(default_factory=dict)  # 争议方对仲裁的评价

    # 时间
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    voting_deadline: float = 0             # 投票截止时间
    appeal_deadline: float = 0             # 上诉截止时间

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['status'] = self.status.value
        if self.vote_result:
            data['vote_result'] = self.vote_result.value
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'Dispute':
        data = data.copy()
        data['status'] = DisputeStatus(data.get('status', 'created'))
        if data.get('vote_result'):
            data['vote_result'] = VoteResult(data['vote_result'])
        return cls(**data)

    def update_timestamp(self):
        self.updated_at = time.time()

    def add_evidence(self, evidence: Evidence, is_initiator: bool):
        """添加证据"""
        if is_initiator:
            self.initiator_evidence.append(evidence)
        else:
            self.respondent_evidence.append(evidence)
        self.update_timestamp()

    def calculate_vote_result(self) -> VoteResult:
        """计算投票结果"""
        votes = list(self.arbitrator_votes.values())
        if len(votes) < 3:  # 需要至少3票
            return VoteResult.NO_CONSENSUS

        buyer_votes = sum(1 for v in votes if v.decision == "buyer")
        seller_votes = sum(1 for v in votes if v.decision == "seller")
        split_votes = sum(1 for v in votes if v.decision == "split")

        if buyer_votes > seller_votes and buyer_votes > split_votes:
            return VoteResult.BUYER_WINS
        elif seller_votes > buyer_votes and seller_votes > split_votes:
            return VoteResult.SELLER_WINS
        elif split_votes > buyer_votes and split_votes > seller_votes:
            return VoteResult.SPLIT
        else:
            return VoteResult.SPLIT


class DisputeManager:
    """争议管理器"""

    # 仲裁员资格要求
    MIN_REPUTATION_SCORE = 200
    MIN_FAIRNESS_RATE = 0.80
    ARBITRATOR_COUNT = 5                   # 每次争议选择的仲裁员数量
    VOTING_PERIOD_HOURS = 48               # 投票期限
    APPEAL_PERIOD_HOURS = 24               # 上诉期限

    def __init__(self, node_id: str, reputation_manager=None):
        self.node_id = node_id
        self.disputes: Dict[str, Dispute] = {}  # dispute_id -> dispute
        self.transaction_disputes: Dict[str, str] = {}  # tx_id -> dispute_id

        # 仲裁员注册
        self.registered_arbitrators: Set[str] = set()
        self.arbitrator_fairness: Dict[str, Dict] = {}  # arbitrator_id -> {"total": x, "fair": y}

        # 信誉管理器（用于验证资格）
        self.reputation_manager = reputation_manager

        # 回调
        self.on_dispute_update: Optional[Callable] = None
        self.on_arbitrator_assigned: Optional[Callable] = None

    def create_dispute(
        self,
        transaction_id: str,
        initiator_id: str,
        respondent_id: str,
        dispute_type: str,
        description: str,
        evidence: List[Evidence] = None,
    ) -> Dispute:
        """创建争议"""
        # 检查是否已有争议
        if transaction_id in self.transaction_disputes:
            raise ValueError("Dispute already exists for this transaction")

        dispute = Dispute(
            transaction_id=transaction_id,
            initiator_id=initiator_id,
            respondent_id=respondent_id,
            dispute_type=dispute_type,
            description=description,
            voting_deadline=time.time() + self.VOTING_PERIOD_HOURS * 3600,
        )

        # 添加初始证据
        if evidence:
            for ev in evidence:
                dispute.add_evidence(ev, is_initiator=True)

        self.disputes[dispute.dispute_id] = dispute
        self.transaction_disputes[transaction_id] = dispute.dispute_id

        # 选择仲裁员
        self._select_arbitrators(dispute)

        dispute.status = DisputeStatus.VOTING
        dispute.update_timestamp()

        return dispute

    def add_evidence(self, dispute_id: str, evidence: Evidence, is_initiator: bool) -> bool:
        """添加证据"""
        dispute = self.disputes.get(dispute_id)
        if not dispute:
            return False

        if dispute.status not in [DisputeStatus.CREATED, DisputeStatus.VOTING]:
            return False

        # 验证提交者身份
        if is_initiator and evidence.submitted_by != dispute.initiator_id:
            return False
        if not is_initiator and evidence.submitted_by != dispute.respondent_id:
            return False

        dispute.add_evidence(evidence, is_initiator)
        self._notify_update(dispute)

        return True

    def submit_vote(
        self,
        dispute_id: str,
        arbitrator_id: str,
        decision: str,
        reason: str = "",
    ) -> bool:
        """提交投票"""
        dispute = self.disputes.get(dispute_id)
        if not dispute:
            return False

        if dispute.status != DisputeStatus.VOTING:
            return False

        # 验证仲裁员资格
        if arbitrator_id not in dispute.arbitrator_ids:
            return False

        # 检查是否已投票
        if arbitrator_id in dispute.arbitrator_votes:
            return False

        # 检查是否过期
        if time.time() > dispute.voting_deadline:
            return False

        vote = ArbitratorVote(
            arbitrator_id=arbitrator_id,
            decision=decision,
            reason=reason,
        )

        dispute.arbitrator_votes[arbitrator_id] = vote
        dispute.update_timestamp()

        # 检查是否所有人都投票了
        if len(dispute.arbitrator_votes) >= self.ARBITRATOR_COUNT:
            self._resolve_dispute(dispute)

        self._notify_update(dispute)

        return True

    def rate_arbitration(self, dispute_id: str, user_id: str, score: int) -> bool:
        """评价仲裁结果"""
        dispute = self.disputes.get(dispute_id)
        if not dispute:
            return False

        if dispute.status != DisputeStatus.RESOLVED:
            return False

        # 只有争议方可以评价
        if user_id not in [dispute.initiator_id, dispute.respondent_id]:
            return False

        # 只有在申诉期内可以评价
        if time.time() > dispute.appeal_deadline:
            return False

        dispute.fairness_scores[user_id] = score
        return True

    def appeal(self, dispute_id: str, user_id: str, reason: str) -> bool:
        """上诉"""
        dispute = self.disputes.get(dispute_id)
        if not dispute:
            return False

        if dispute.status != DisputeStatus.RESOLVED:
            return False

        if user_id not in [dispute.initiator_id, dispute.respondent_id]:
            return False

        if time.time() > dispute.appeal_deadline:
            return False

        dispute.status = DisputeStatus.APPEALED
        dispute.update_timestamp()

        # 重新选择仲裁员
        self._select_arbitrators(dispute)

        return True

    def close_dispute(self, dispute_id: str) -> bool:
        """关闭争议"""
        dispute = self.disputes.get(dispute_id)
        if not dispute:
            return False

        if dispute.status not in [DisputeStatus.RESOLVED, DisputeStatus.APPEALED]:
            return False

        dispute.status = DisputeStatus.CLOSED
        dispute.update_timestamp()

        # 更新仲裁员统计
        self._update_arbitrator_stats(dispute)

        return True

    def register_as_arbitrator(self, user_id: str) -> bool:
        """注册为仲裁员"""
        if user_id in self.registered_arbitrators:
            return True

        # 检查资格
        if self.reputation_manager:
            rep = self.reputation_manager.get_reputation(user_id)
            if rep.score < self.MIN_REPUTATION_SCORE:
                return False

        self.registered_arbitrators.add(user_id)
        self.arbitrator_fairness[user_id] = {"total": 0, "fair": 0}
        return True

    def unregister_arbitrator(self, user_id: str) -> bool:
        """注销仲裁员"""
        if user_id in self.registered_arbitrators:
            self.registered_arbitrators.discard(user_id)
            return True
        return False

    def get_eligible_arbitrators(self) -> List[str]:
        """获取符合条件的仲裁员"""
        eligible = []

        for arbitrator_id in self.registered_arbitrators:
            if self.reputation_manager:
                rep = self.reputation_manager.get_reputation(arbitrator_id)
                if rep.score < self.MIN_REPUTATION_SCORE:
                    continue

            fairness = self.arbitrator_fairness.get(arbitrator_id, {"total": 0, "fair": 0})
            if fairness["total"] > 0:
                rate = fairness["fair"] / fairness["total"]
                if rate < self.MIN_FAIRNESS_RATE:
                    continue

            eligible.append(arbitrator_id)

        return eligible

    def get_my_disputes(self) -> List[Dispute]:
        """获取我的争议"""
        return [
            d for d in self.disputes.values()
            if d.initiator_id == self.node_id or d.respondent_id == self.node_id
        ]

    def get_pending_arbitrations(self) -> List[Dispute]:
        """获取待仲裁的争议"""
        return [
            d for d in self.disputes.values()
            if d.status == DisputeStatus.VOTING
            and self.node_id in d.arbitrator_ids
            and self.node_id not in d.arbitrator_votes
        ]

    def _select_arbitrators(self, dispute: Dispute):
        """选择仲裁员"""
        eligible = self.get_eligible_arbitrators()

        # 排除争议双方
        eligible = [
            aid for aid in eligible
            if aid not in [dispute.initiator_id, dispute.respondent_id]
        ]

        # 随机选择
        count = min(self.ARBITRATOR_COUNT, len(eligible))
        selected = random.sample(eligible, count) if eligible else []

        dispute.arbitrator_ids = selected

        if self.on_arbitrator_assigned:
            for arbitrator_id in selected:
                self.on_arbitrator_assigned(dispute, arbitrator_id)

    def _resolve_dispute(self, dispute: Dispute):
        """解决争议"""
        dispute.vote_result = dispute.calculate_vote_result()
        dispute.status = DisputeStatus.RESOLVED
        dispute.resolved_at = time.time()
        dispute.appeal_deadline = time.time() + self.APPEAL_PERIOD_HOURS * 3600

        # 确定胜方
        if dispute.vote_result == VoteResult.BUYER_WINS:
            dispute.winner_id = dispute.initiator_id
            dispute.resolution = "Buyer wins: payment will be refunded"
        elif dispute.vote_result == VoteResult.SELLER_WINS:
            dispute.winner_id = dispute.respondent_id
            dispute.resolution = "Seller wins: payment will be released"
        else:
            dispute.winner_id = ""
            dispute.resolution = "Split decision: payment will be split equally"

        dispute.update_timestamp()

    def _update_arbitrator_stats(self, dispute: Dispute):
        """更新仲裁员统计"""
        # 简化实现：争议方评价的加权平均
        for arbitrator_id in dispute.arbitrator_ids:
            if arbitrator_id not in self.arbitrator_fairness:
                self.arbitrator_fairness[arbitrator_id] = {"total": 0, "fair": 0}

            stats = self.arbitrator_fairness[arbitrator_id]
            stats["total"] += 1

            # 如果胜方给高分，认为仲裁公正
            if dispute.winner_id:
                winner_score = dispute.fairness_scores.get(dispute.winner_id, 0)
                if winner_score >= 4:
                    stats["fair"] += 1

    def _notify_update(self, dispute: Dispute):
        """通知更新"""
        if self.on_dispute_update:
            self.on_dispute_update(dispute)


if __name__ == "__main__":
    # 简单测试
    manager = DisputeManager("buyer_123")

    # 注册仲裁员
    manager.register_as_arbitrator("arb_001")
    manager.register_as_arbitrator("arb_002")
    manager.register_as_arbitrator("arb_003")

    # 创建争议
    evidence = [
        Evidence(
            evidence_type="chat_log",
            description="聊天记录显示卖家承诺当天发货",
            submitted_by="buyer_123",
        )
    ]

    dispute = manager.create_dispute(
        transaction_id="tx_001",
        initiator_id="buyer_123",
        respondent_id="seller_456",
        dispute_type="not_delivered",
        description="已付款3天未收到货",
        evidence=evidence,
    )

    print(f"Dispute created: {dispute.dispute_id}")
    print(f"Selected arbitrators: {dispute.arbitrator_ids}")
