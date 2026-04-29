# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 - 共识引擎

实现知识共识协议:
- 知识验证阶段: 多轮投票确认
- 价值评估阶段: 动态价值计算
- 激励分配阶段: 多方激励分配
"""

import asyncio
import logging
import json
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from .models import (
    Transaction, NodeType, KnowledgeUnit, VerificationInfo,
    ReputationScore
)

logger = logging.getLogger(__name__)


class ConsensusPhase(Enum):
    """共识阶段"""
    IDLE = "idle"
    VERIFICATION = "verification"
    VALUE_ASSESSMENT = "value_assessment"
    INCENTIVE_DISTRIBUTION = "incentive_distribution"
    FINALIZATION = "finalization"


class ConsensusResult(Enum):
    """共识结果"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class VerificationVote:
    """验证投票"""
    verifier_id: str
    knowledge_id: str
    is_valid: bool
    confidence: float  # 0.0 - 1.0
    comments: str
    timestamp: datetime
    reputation_weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verifier_id": self.verifier_id,
            "knowledge_id": self.knowledge_id,
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "comments": self.comments,
            "timestamp": self.timestamp.isoformat(),
            "reputation_weight": self.reputation_weight
        }


@dataclass
class KnowledgeProposal:
    """知识提案"""
    proposal_id: str
    knowledge: KnowledgeUnit
    proposer_id: str
    created_at: datetime
    phase: ConsensusPhase = ConsensusPhase.VERIFICATION
    votes: List[VerificationVote] = field(default_factory=list)
    current_round: int = 1
    max_rounds: int = 3
    final_value: float = 0.0
    incentive_budget: float = 0.0
    result: ConsensusResult = ConsensusResult.PENDING

    @property
    def yes_votes(self) -> int:
        return sum(1 for v in self.votes if v.is_valid)

    @property
    def no_votes(self) -> int:
        return sum(1 for v in self.votes if not v.is_valid)

    @property
    def weighted_yes_votes(self) -> float:
        return sum(v.reputation_weight for v in self.votes if v.is_valid)

    @property
    def weighted_no_votes(self) -> float:
        return sum(v.reputation_weight for v in self.votes if not v.is_valid)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "knowledge_id": self.knowledge.knowledge_id,
            "proposer_id": self.proposer_id,
            "created_at": self.created_at.isoformat(),
            "phase": self.phase.value,
            "votes": [v.to_dict() for v in self.votes],
            "current_round": self.current_round,
            "max_rounds": self.max_rounds,
            "final_value": self.final_value,
            "incentive_budget": self.incentive_budget,
            "result": self.result.value,
            "yes_votes": self.yes_votes,
            "no_votes": self.no_votes,
            "weighted_yes": self.weighted_yes_votes,
            "weighted_no": self.weighted_no_votes
        }


@dataclass
class ConsensusConfig:
    """共识配置"""
    # 验证阶段配置
    verification_threshold: int = 3  # 需要的最少验证者
    voting_round_timeout: int = 60  # 每轮投票超时(秒)
    consensus_threshold: float = 0.66  # 共识阈值(66%)
    
    # 价值评估配置
    base_value: float = 10.0  # 基础价值
    verification_bonus: float = 20.0  # 验证通过奖励
    time_decay_factor: float = 0.95  # 时间衰减因子
    learning_bonus: float = 0.3  # 学习次数奖励
    spread_bonus: float = 0.5  # 传播次数奖励
    reference_bonus: float = 2.0  # 引用次数奖励
    
    # 激励分配配置
    creator_share: float = 0.30  # 创建者份额
    verifier_share: float = 0.20  # 验证者份额
    spreader_share: float = 0.15  # 传播者份额
    learner_share: float = 0.15  # 学习者份额
    system_reserve: float = 0.10  # 系统保留
    ecosystem_share: float = 0.10  # 生态发展份额
    
    # 节点类型配置
    full_node_weight: float = 1.5  # 全节点权重
    light_node_weight: float = 1.0  # 轻节点权重
    mobile_node_weight: float = 0.7  # 移动节点权重
    validator_node_weight: float = 2.0  # 验证节点权重


class ConsensusEngine:
    """共识引擎"""

    def __init__(
        self,
        blockchain: 'KnowledgeBlockchain',
        node_id: str,
        node_type: NodeType = NodeType.LIGHT,
        config: Optional[ConsensusConfig] = None
    ):
        """
        初始化共识引擎
        
        Args:
            blockchain: 区块链实例
            node_id: 节点ID
            node_type: 节点类型
            config: 共识配置
        """
        self.blockchain = blockchain
        self.node_id = node_id
        self.node_type = node_type
        self.config = config or ConsensusConfig()
        
        # 活跃提案
        self.active_proposals: Dict[str, KnowledgeProposal] = {}
        
        # 验证者池
        self.validator_pool: Dict[str, Dict[str, Any]] = {}  # node_id -> info
        
        # 共识历史
        self.consensus_history: List[Dict[str, Any]] = []
        
        # 统计
        self.stats = {
            "total_proposals": 0,
            "accepted": 0,
            "rejected": 0,
            "timeout": 0,
            "avg_consensus_time": 0.0
        }
        
        logger.info(f"初始化共识引擎: {node_id} ({node_type.value})")

    # ==================== 提案管理 ====================

    async def propose_knowledge(
        self,
        knowledge: KnowledgeUnit,
        proposer_id: Optional[str] = None
    ) -> str:
        """
        提交知识提案
        
        Args:
            knowledge: 知识单元
            proposer_id: 提案者ID
            
        Returns:
            提案ID
        """
        import hashlib
        
        proposal_id = hashlib.sha256(
            f"{knowledge.knowledge_id}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:24]
        
        proposal = KnowledgeProposal(
            proposal_id=proposal_id,
            knowledge=knowledge,
            proposer_id=proposer_id or self.node_id,
            created_at=datetime.now()
        )
        
        self.active_proposals[proposal_id] = proposal
        self.stats["total_proposals"] += 1
        
        logger.info(f"📝 新提案: {proposal_id}")
        
        # 启动验证流程
        asyncio.create_task(self._run_verification_phase(proposal_id))
        
        return proposal_id

    async def propose_and_wait(
        self,
        transaction: Transaction,
        timeout: int = 30
    ) -> Tuple[bool, str]:
        """
        提交提案并等待结果
        
        Args:
            transaction: 交易
            timeout: 超时时间(秒)
            
        Returns:
            (是否接受, 原因)
        """
        if transaction.tx_type == "knowledge_create":
            from .models import KnowledgeMetadata, KnowledgeContent
            
            knowledge = KnowledgeUnit(
                metadata=KnowledgeMetadata(
                    knowledge_id=transaction.tx_id,
                    creator_id=transaction.sender_id,
                    created_at=transaction.timestamp,
                    knowledge_type=transaction.data.get("knowledge_type", "concept"),
                    domain_tags=transaction.data.get("domain_tags", [])
                ),
                content=KnowledgeContent(
                    title=transaction.data.get("title", ""),
                    summary=transaction.data.get("summary", ""),
                    content=transaction.data.get("content", ""),
                    references=transaction.data.get("references", []),
                    keywords=transaction.data.get("keywords", [])
                )
            )
            
            proposal_id = await self.propose_knowledge(knowledge)
            
            # 等待共识完成
            start_time = datetime.now()
            while (datetime.now() - start_time).seconds < timeout:
                proposal = self.active_proposals.get(proposal_id)
                if proposal and proposal.result != ConsensusResult.PENDING:
                    return (
                        proposal.result == ConsensusResult.ACCEPTED,
                        proposal.result.value
                    )
                await asyncio.sleep(0.5)
            
            return False, "timeout"
        
        # 其他交易类型直接接受
        return True, "auto_accepted"

    # ==================== 验证阶段 ====================

    async def _run_verification_phase(self, proposal_id: str):
        """运行验证阶段"""
        proposal = self.active_proposals.get(proposal_id)
        if not proposal:
            return
        
        logger.info(f"🔍 验证阶段开始: {proposal_id}")
        
        for round_num in range(1, proposal.max_rounds + 1):
            proposal.current_round = round_num
            proposal.phase = ConsensusPhase.VERIFICATION
            
            # 选择验证者
            verifiers = await self._select_verifiers(proposal, round_num)
            
            # 收集投票
            await self._collect_votes(proposal, verifiers, round_num)
            
            # 检查共识
            if self._check_consensus(proposal):
                proposal.phase = ConsensusPhase.VALUE_ASSESSMENT
                await self._run_value_assessment_phase(proposal)
                return
            
            # 检查是否应该拒绝
            if proposal.current_round >= proposal.max_rounds:
                proposal.result = ConsensusResult.REJECTED
                proposal.phase = ConsensusPhase.FINALIZATION
                logger.info(f"❌ 提案被拒绝: {proposal_id}")
                return
        
        proposal.result = ConsensusResult.TIMEOUT
        logger.warning(f"⏰ 提案超时: {proposal_id}")

    async def _select_verifiers(
        self,
        proposal: KnowledgeProposal,
        round_num: int
    ) -> List[str]:
        """选择验证者"""
        # 基于信誉和可用性选择
        candidate_count = self.config.verification_threshold + round_num
        
        candidates = []
        for node_id, info in self.validator_pool.items():
            if node_id == proposal.proposer_id:
                continue
            
            reputation = info.get("reputation", 50.0)
            availability = info.get("availability", 0.8)
            node_type = NodeType(info.get("node_type", "light"))
            
            # 计算权重
            type_weight = getattr(self.config, f"{node_type.value}_node_weight", 1.0)
            score = reputation * availability * type_weight
            
            candidates.append((score, node_id))
        
        # 选择得分最高的
        candidates.sort(reverse=True)
        return [node_id for _, node_id in candidates[:candidate_count]]

    async def _collect_votes(
        self,
        proposal: KnowledgeProposal,
        verifiers: List[str],
        round_num: int
    ):
        """收集投票"""
        # 模拟验证者投票（实际实现中需要等待真实投票）
        vote_tasks = []
        
        for verifier_id in verifiers:
            # 如果是本地节点，直接投票
            if verifier_id == self.node_id:
                vote = await self._create_verification_vote(proposal, verifier_id)
                proposal.votes.append(vote)
            else:
                # 模拟远程投票
                vote_tasks.append(
                    self._simulate_remote_vote(proposal, verifier_id)
                )
        
        # 等待投票
        if vote_tasks:
            remote_votes = await asyncio.gather(*vote_tasks, return_exceptions=True)
            for vote in remote_votes:
                if isinstance(vote, VerificationVote):
                    proposal.votes.append(vote)

    async def _create_verification_vote(
        self,
        proposal: KnowledgeProposal,
        verifier_id: str
    ) -> VerificationVote:
        """创建验证投票"""
        knowledge = proposal.knowledge
        
        # 基础验证逻辑
        is_valid = True
        confidence = 0.8
        comments = ""
        
        # 检查内容完整性
        if not knowledge.content.title or not knowledge.content.content:
            is_valid = False
            comments = "内容不完整"
            confidence = 0.3
        
        # 检查知识类型
        if not knowledge.metadata.knowledge_type:
            is_valid = False
            comments = "未指定知识类型"
            confidence = 0.2
        
        # 获取验证者信誉
        rep_weight = await self._get_verifier_weight(verifier_id)
        
        return VerificationVote(
            verifier_id=verifier_id,
            knowledge_id=knowledge.knowledge_id,
            is_valid=is_valid,
            confidence=confidence,
            comments=comments,
            timestamp=datetime.now(),
            reputation_weight=rep_weight
        )

    async def _simulate_remote_vote(
        self,
        proposal: KnowledgeProposal,
        verifier_id: str
    ) -> Optional[VerificationVote]:
        """模拟远程验证投票"""
        import random
        
        is_valid = random.random() > 0.2  # 80%概率有效
        confidence = random.uniform(0.6, 1.0)
        
        return VerificationVote(
            verifier_id=verifier_id,
            knowledge_id=proposal.knowledge.knowledge_id,
            is_valid=is_valid,
            confidence=confidence,
            comments="自动验证" if is_valid else "需要更多验证",
            timestamp=datetime.now(),
            reputation_weight=1.0
        )

    async def _get_verifier_weight(self, verifier_id: str) -> float:
        """获取验证者权重"""
        info = self.validator_pool.get(verifier_id, {})
        node_type = NodeType(info.get("node_type", "light"))
        reputation = info.get("reputation", 50.0)
        
        type_weight = getattr(self.config, f"{node_type.value}_node_weight", 1.0)
        rep_factor = min(reputation / 100.0, 1.0)  # 归一化到0-1
        
        return type_weight * (0.5 + 0.5 * rep_factor)

    def _check_consensus(self, proposal: KnowledgeProposal) -> bool:
        """检查是否达成共识"""
        total_votes = len(proposal.votes)
        if total_votes < self.config.verification_threshold:
            return False
        
        threshold = self.config.consensus_threshold
        total_weight = proposal.weighted_yes_votes + proposal.weighted_no_votes
        
        if total_weight == 0:
            return False
        
        yes_ratio = proposal.weighted_yes_votes / total_weight
        
        # 高置信度共识
        if yes_ratio >= threshold and proposal.yes_votes >= self.config.verification_threshold:
            return True
        
        # 强拒绝共识
        no_ratio = proposal.weighted_no_votes / total_weight
        if no_ratio >= threshold:
            return True
        
        return False

    # ==================== 价值评估阶段 ====================

    async def _run_value_assessment_phase(self, proposal: KnowledgeProposal):
        """运行价值评估阶段"""
        logger.info(f"💰 价值评估阶段: {proposal.proposal_id}")
        proposal.phase = ConsensusPhase.VALUE_ASSESSMENT
        
        # 计算初始价值
        base_value = self.config.base_value
        
        # 验证通过奖励
        verification = proposal.knowledge.verification_info
        verification_bonus = (
            self.config.verification_bonus * verification.pass_rate
            if verification.verification_count > 0 else 0
        )
        
        # 基础价值
        initial_value = base_value + verification_bonus
        
        # 时间衰减（基于提案年龄）
        age_hours = (datetime.now() - proposal.created_at).total_seconds() / 3600
        time_decay = self.config.time_decay_factor ** (age_hours / 24)  # 每日衰减
        
        final_value = initial_value * time_decay
        
        # 动态调整（基于引用和传播潜力）
        content = proposal.knowledge.content
        if content.references:
            final_value += len(content.references) * self.config.reference_bonus
        
        # 设置激励预算
        proposal.final_value = final_value
        proposal.incentive_budget = final_value
        
        logger.info(f"💎 知识价值评估: {final_value:.2f}")

    # ==================== 激励分配 ====================

    async def distribute_incentives(self, proposal: KnowledgeProposal) -> Dict[str, float]:
        """
        分配激励
        
        Args:
            proposal: 提案
            
        Returns:
            激励分配映射
        """
        logger.info(f"🎁 激励分配阶段: {proposal.proposal_id}")
        proposal.phase = ConsensusPhase.INCENTIVE_DISTRIBUTION
        
        budget = proposal.incentive_budget
        config = self.config
        
        # 计算各方份额
        creator_amount = budget * config.creator_share
        
        # 验证者份额分配
        verifier_budget = budget * config.verifier_share
        verifiers = [v for v in proposal.votes if v.is_valid]
        verifier_shares = {}
        
        if verifiers:
            total_weight = sum(v.reputation_weight for v in verifiers)
            for v in verifiers:
                share = verifier_budget * (v.reputation_weight / total_weight)
                verifier_shares[v.verifier_id] = share
        
        # 传播者份额（预留，由实际传播者领取）
        spreader_budget = budget * config.spreader_share
        
        # 学习者份额（预留，由实际学习者领取）
        learner_budget = budget * config.learner_share
        
        # 系统保留
        system_reserve = budget * config.system_reserve
        
        # 生态发展
        ecosystem = budget * config.ecosystem_share
        
        # 构建分配结果
        distribution = {
            "creator": {
                proposal.proposer_id: creator_amount
            },
            "verifiers": verifier_shares,
            "spreader_budget": spreader_budget,
            "learner_budget": learner_budget,
            "system_reserve": system_reserve,
            "ecosystem": ecosystem,
            "total": budget
        }
        
        # 记录到历史
        self.consensus_history.append({
            "proposal_id": proposal.proposal_id,
            "proposer_id": proposal.proposer_id,
            "final_value": proposal.final_value,
            "distribution": distribution,
            "completed_at": datetime.now().isoformat()
        })
        
        proposal.phase = ConsensusPhase.FINALIZATION
        proposal.result = ConsensusResult.ACCEPTED
        
        logger.info(f"✅ 提案通过，激励分配完成")
        
        return distribution

    # ==================== 验证提交 ====================

    async def submit_verification(
        self,
        verifier_id: str,
        knowledge_id: str,
        is_valid: bool,
        comments: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        提交验证结果
        
        Args:
            verifier_id: 验证者ID
            knowledge_id: 知识ID
            is_valid: 是否有效
            comments: 意见
            
        Returns:
            (是否接受, 原因)
        """
        # 查找相关提案
        proposal = None
        for p in self.active_proposals.values():
            if p.knowledge.knowledge_id == knowledge_id:
                proposal = p
                break
        
        if not proposal:
            return False, "proposal_not_found"
        
        # 检查是否已投票
        for vote in proposal.votes:
            if vote.verifier_id == verifier_id:
                return False, "already_voted"
        
        # 获取权重
        weight = await self._get_verifier_weight(verifier_id)
        
        # 创建投票
        vote = VerificationVote(
            verifier_id=verifier_id,
            knowledge_id=knowledge_id,
            is_valid=is_valid,
            confidence=0.8,
            comments=comments or "",
            timestamp=datetime.now(),
            reputation_weight=weight
        )
        
        proposal.votes.append(vote)
        
        # 检查是否达成共识
        if self._check_consensus(proposal):
            proposal.phase = ConsensusPhase.VALUE_ASSESSMENT
            await self._run_value_assessment_phase(proposal)
            await self.distribute_incentives(proposal)
            return True, "consensus_reached"
        
        return True, "vote_recorded"

    # ==================== 注册与查询 ====================

    def register_validator(
        self,
        node_id: str,
        node_type: NodeType,
        reputation: float = 50.0,
        availability: float = 0.8
    ):
        """注册验证者"""
        self.validator_pool[node_id] = {
            "node_type": node_type.value,
            "reputation": reputation,
            "availability": availability,
            "registered_at": datetime.now()
        }
        logger.info(f"✅ 验证者注册: {node_id}")

    def unregister_validator(self, node_id: str):
        """注销验证者"""
        if node_id in self.validator_pool:
            del self.validator_pool[node_id]
            logger.info(f"🗑️ 验证者注销: {node_id}")

    def get_consensus_stats(self) -> Dict[str, Any]:
        """获取共识统计"""
        return {
            "active_proposals": len(self.active_proposals),
            "total_proposals": self.stats["total_proposals"],
            "accepted": self.stats["accepted"],
            "rejected": self.stats["rejected"],
            "timeout": self.stats["timeout"],
            "validator_count": len(self.validator_pool),
            "avg_consensus_time": self.stats["avg_consensus_time"]
        }

    def get_pending_proposals(self) -> List[Dict[str, Any]]:
        """获取待处理提案"""
        return [
            p.to_dict() for p in self.active_proposals.values()
            if p.result == ConsensusResult.PENDING
        ]
