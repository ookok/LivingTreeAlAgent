"""
统一信誉与信任模型

合并自:
- local_market/reputation.py ReputationRecord + ReputationEvent + TrustRelation
- social_commerce/models.py CreditCredential
- flash_listing/models.py FulfillmentRecord (评价部分)
- local_market/models.py Dispute + DisputeEvidence + ArbitratorVote
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import hashlib
import json

from .enums import ReputationAction, CreditAction, DisputeCategory


# ============================================================================
# 信誉
# ============================================================================

@dataclass
class ReputationRecord:
    """节点信誉账本"""
    node_id: str = ""
    current_reputation: int = 100          # 0-1000
    total_trades: int = 0
    successful_trades: int = 0
    disputed_trades: int = 0
    good_reviews: int = 0
    neutral_reviews: int = 0
    bad_reviews: int = 0
    avg_response_time: float = 0.0
    avg_delivery_time: float = 0.0
    last_active: float = 0.0
    account_age_days: int = 0
    fraud_flags: int = 0
    dispute_rate: float = 0.0
    direct_trusts: int = 0
    indirect_trust_sum: float = 0.0

    # --- 常量 ---
    INITIAL_REPUTATION = 100
    MIN_REPUTATION = 0
    MAX_REPUTATION = 1000

    # --- 评分规则 ---
    SCORE_MAP: Dict[ReputationAction, int] = field(default_factory=lambda: {
        ReputationAction.SUCCESSFUL_TRADE: +5,
        ReputationAction.GOOD_REVIEW: +2,
        ReputationAction.QUICK_CONFIRM: +1,
        ReputationAction.DISPUTE_RESOLVE: +3,
        ReputationAction.TRADE_CANCEL: -3,
        ReputationAction.BAD_REVIEW: -5,
        ReputationAction.FALSE_PRODUCT: -20,
        ReputationAction.FRAUD: -100,
    })

    def apply_event(self, action: ReputationAction) -> int:
        """应用信誉事件，返回变化量"""
        delta = self.SCORE_MAP.get(action, 0)
        self.current_reputation = max(
            self.MIN_REPUTATION,
            min(self.MAX_REPUTATION, self.current_reputation + delta)
        )
        if action == ReputationAction.SUCCESSFUL_TRADE:
            self.successful_trades += 1
            self.total_trades += 1
        elif action == ReputationAction.FRAUD:
            self.fraud_flags += 1
        elif action == ReputationAction.BAD_REVIEW:
            self.bad_reviews += 1
        elif action == ReputationAction.GOOD_REVIEW:
            self.good_reviews += 1
        elif action == ReputationAction.DISPUTE_RESOLVE:
            self.disputed_trades += 1
        return delta

    @property
    def level(self) -> str:
        """信誉等级"""
        thresholds = [
            (900, "SSS"), (800, "SS"), (700, "S"),
            (600, "AAA"), (500, "AA"), (400, "A"),
            (300, "B"), (200, "C"), (100, "D"), (0, "F"),
        ]
        for t, level in thresholds:
            if self.current_reputation >= t:
                return level
        return "F"

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "current_reputation": self.current_reputation,
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "disputed_trades": self.disputed_trades,
            "good_reviews": self.good_reviews,
            "neutral_reviews": self.neutral_reviews,
            "bad_reviews": self.bad_reviews,
            "avg_response_time": self.avg_response_time,
            "avg_delivery_time": self.avg_delivery_time,
            "last_active": self.last_active,
            "account_age_days": self.account_age_days,
            "fraud_flags": self.fraud_flags,
            "dispute_rate": self.dispute_rate,
        }


@dataclass
class ReputationEvent:
    """信誉事件"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    node_id: str = ""
    action: ReputationAction = ReputationAction.SUCCESSFUL_TRADE
    trade_id: Optional[str] = None
    counterparty_id: Optional[str] = None
    reputation_change: int = 0
    reason: str = ""
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    evidence_hash: str = ""
    witnesses: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "node_id": self.node_id,
            "action": self.action.value,
            "trade_id": self.trade_id,
            "counterparty_id": self.counterparty_id,
            "reputation_change": self.reputation_change,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "evidence_hash": self.evidence_hash,
            "witnesses": self.witnesses,
        }


# ============================================================================
# 信任
# ============================================================================

@dataclass
class TrustRelation:
    """信任关系"""
    from_node: str = ""
    to_node: str = ""
    direct_trust: float = 0.0         # 直接信任度 0-1
    indirect_trust: float = 0.0       # 间接信任度 0-1
    total_trust: float = 0.0          # 总信任度
    shared_contacts: List[str] = field(default_factory=list)
    successful_trades: int = 0
    last_interaction: float = field(default_factory=lambda: datetime.now().timestamp())

    def calculate_total_trust(self, decay_factor: float = 0.8) -> float:
        """总信任度 = 直接信任 + 间接信任 × 衰减因子"""
        self.total_trust = self.direct_trust + self.indirect_trust * decay_factor
        return self.total_trust


# ============================================================================
# 信用凭证（链式）
# ============================================================================

@dataclass
class CreditCredential:
    """信用凭证 — 链式评价"""
    credential_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    from_node: str = ""
    to_node: str = ""
    deal_id: Optional[str] = None
    deal_category: Optional[str] = None
    deal_amount: float = 0.0
    rating: float = 0.0                 # 1-5
    comment: str = ""
    tags: List[str] = field(default_factory=list)
    previous_credential: Optional[str] = None
    credential_hash: str = ""
    is_verified: bool = False
    verified_by: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())

    def compute_hash(self) -> str:
        data = {
            "from": self.from_node,
            "to": self.to_node,
            "deal_id": self.deal_id or "",
            "rating": self.rating,
            "previous": self.previous_credential or "",
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "credential_id": self.credential_id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "deal_id": self.deal_id,
            "deal_category": self.deal_category,
            "deal_amount": self.deal_amount,
            "rating": self.rating,
            "comment": self.comment,
            "tags": self.tags,
            "previous_credential": self.previous_credential,
            "credential_hash": self.credential_hash,
            "is_verified": self.is_verified,
            "verified_by": self.verified_by,
            "created_at": self.created_at,
        }


# ============================================================================
# 争议与仲裁
# ============================================================================

@dataclass
class DisputeEvidence:
    """争议证据"""
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    dispute_id: str = ""
    evidence_type: str = ""            # "chat"/"photo"/"location"/"payment"/"timestamp"
    description: str = ""
    content: str = ""                   # 证据内容或IPFS哈希
    submitted_by: str = ""
    submitted_at: float = field(default_factory=lambda: datetime.now().timestamp())
    verified: bool = False
    verified_by: List[str] = field(default_factory=list)


@dataclass
class ArbitratorVote:
    """仲裁员投票"""
    arbitrator_id: str = ""
    vote: str = ""                      # "buyer"/"seller"/"reject"
    reasoning: str = ""
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class Dispute:
    """争议记录"""
    dispute_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    order_id: str = ""
    complainant_id: str = ""
    respondent_id: str = ""
    reason: str = ""
    category: DisputeCategory = DisputeCategory.OTHER
    arbitrators: List[str] = field(default_factory=list)    # 5个仲裁员
    votes: List[ArbitratorVote] = field(default_factory=list)
    evidence: List[DisputeEvidence] = field(default_factory=list)
    verdict: str = ""                   # "buyer_wins"/"seller_wins"/"rejected"
    verdict_reason: str = ""
    decided_at: Optional[float] = None
    executed: bool = False
    execution_details: Dict[str, Any] = field(default_factory=dict)
    status: str = "open"               # "open"/"voting"/"decided"/"executed"
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())

    @property
    def quorum_reached(self) -> bool:
        """仲裁员 >= 3 人投票"""
        return len(self.votes) >= 3

    @property
    def majority_verdict(self) -> Optional[str]:
        """多数裁决"""
        if not self.quorum_reached:
            return None
        counts: Dict[str, int] = {}
        for v in self.votes:
            counts[v.vote] = counts.get(v.vote, 0) + 1
        best = max(counts, key=counts.get)
        return best if counts[best] > len(self.votes) / 2 else None

    def to_dict(self) -> dict:
        return {
            "dispute_id": self.dispute_id,
            "order_id": self.order_id,
            "complainant_id": self.complainant_id,
            "respondent_id": self.respondent_id,
            "reason": self.reason,
            "category": self.category.value,
            "arbitrators": self.arbitrators,
            "votes": [{"arbitrator_id": v.arbitrator_id, "vote": v.vote,
                        "reasoning": v.reasoning, "timestamp": v.timestamp}
                       for v in self.votes],
            "evidence": [{"evidence_id": e.evidence_id, "evidence_type": e.evidence_type,
                           "description": e.description, "content": e.content,
                           "submitted_by": e.submitted_by}
                          for e in self.evidence],
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
            "decided_at": self.decided_at,
            "executed": self.executed,
            "execution_details": self.execution_details,
            "status": self.status,
            "created_at": self.created_at,
        }
