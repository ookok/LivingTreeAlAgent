"""
渐进去中心化AI社区与Relay Chain事件账本集成

将"进化中的AI社区"作为事件账本的一种特殊事件类型，
实现AI社区与链式账本的深度集成。

核心集成点：
1. 社区事件作为OpType
2. 进化交易类型
3. 与现有event_ext模块的互操作
"""

import json
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

from ..evolving_community import (
    EvolvingCommunity,
    AIAgent,
    StageType,
    ThoughtType,
    ContentLevel,
    FitnessScore,
)
from .event_transaction import OpType, OpCategory, EventTx, EventTxBuilder
from .event_ledger import EventLedger


# ═══════════════════════════════════════════════════════════════════════════════
# 新的操作类型：AI社区事件
# ═══════════════════════════════════════════════════════════════════════════════

class CommunityOpType(OpType):
    """
    AI社区操作类型

    扩展原有的OpType枚举，添加AI社区特有操作。
    这些操作会被记录到链式账本中。
    """

    # AI个体生命周期
    AGENT_BIRTH = "AGENT_BIRTH"             # AI个体诞生
    AGENT_DEATH = "AGENT_DEATH"             # AI个体消亡/淘汰
    AGENT_MUTATION = "AGENT_MUTATION"       # AI个体变异
    AGENT_CROSSOVER = "AGENT_CROSSOVER"     # AI个体交叉

    # 思考与认知
    THOUGHT_GENERATED = "THOUGHT_GENERATED" # 思考生成
    COGNITION_EVOLVED = "COGNITION_EVOLVED" # 认知进化

    # 交流与合作
    KNOWLEDGE_SHARED = "KNOWLEDGE_SHARED"   # 知识共享
    COLLABORATION_STARTED = "COLLABORATION_STARTED"  # 合作开始
    COLLABORATION_COMPLETED = "COLLABORATION_COMPLETED"  # 合作完成

    # 社区层面
    STAGE_TRANSITION = "STAGE_TRANSITION"   # 阶段转换
    NICHE_FORMED = "NICHE_FORMED"           # 生态位形成
    ECOSYSTEM_EVENT = "ECOSYSTEM_EVENT"     # 生态系统事件

    # 适应度评估
    FITNESS_EVALUATED = "FITNESS_EVALUATED" # 适应度评估


# ═══════════════════════════════════════════════════════════════════════════════
# 社区事件账本
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CommunityEventLedger:
    """
    社区事件账本

    将AI社区的关键事件记录到链式账本中，
    实现可追溯和不可篡改的进化历史。
    """

    community: EvolvingCommunity
    base_ledger: EventLedger

    # 事件计数器
    event_counters: Dict[str, int] = field(default_factory=dict)

    def _get_nonce(self, user_id: str) -> int:
        """获取用户的下一个nonce"""
        if user_id not in self.event_counters:
            self.event_counters[user_id] = 0
        nonce = self.event_counters[user_id]
        self.event_counters[user_id] += 1
        return nonce

    def record_agent_birth(
        self,
        agent: AIAgent,
        parent_ids: Optional[List[str]] = None,
    ) -> EventTx:
        """记录AI个体诞生"""
        metadata = {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "personality_gene": agent.personality.to_gene_sequence(),
            "stage_at_creation": agent.stage_at_creation.value,
            "parent_ids": parent_ids or [],
            "created_at": agent.created_at,
        }

        tx = EventTx(
            user_id=agent.agent_id,
            op_type=CommunityOpType.AGENT_BIRTH,
            amount=1,
            prev_tx_hash=self.base_ledger._get_account_state(agent.agent_id).last_tx_hash or self.base_ledger.genesis_hash,
            nonce=self._get_nonce(agent.agent_id),
            biz_id=agent.agent_id,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        tx.tx_hash = tx.compute_hash()

        self.base_ledger.add_tx(tx)
        return tx

    def record_thought(
        self,
        agent_id: str,
        thought_id: str,
        thought_type: ThoughtType,
        topic: str,
        quality_scores: Dict[str, float],
    ) -> EventTx:
        """记录思考生成"""
        metadata = {
            "thought_id": thought_id,
            "agent_id": agent_id,
            "thought_type": thought_type.value,
            "topic": topic,
            "quality_scores": quality_scores,
            "timestamp": time.time(),
        }

        tx = EventTx(
            user_id=agent_id,
            op_type=CommunityOpType.THOUGHT_GENERATED,
            amount=1,
            prev_tx_hash=self.base_ledger._get_account_state(agent_id).last_tx_hash or self.base_ledger.genesis_hash,
            nonce=self._get_nonce(agent_id),
            biz_id=thought_id,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        tx.tx_hash = tx.compute_hash()

        self.base_ledger.add_tx(tx)
        return tx

    def record_knowledge_share(
        self,
        sender_id: str,
        receiver_id: str,
        content_id: str,
        content_preview: str,
        level: ContentLevel,
    ) -> EventTx:
        """记录知识共享"""
        metadata = {
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "content_id": content_id,
            "content_preview": content_preview[:200],  # 截断
            "level": level.value,
            "timestamp": time.time(),
        }

        tx = EventTx(
            user_id=sender_id,
            op_type=CommunityOpType.KNOWLEDGE_SHARED,
            amount=1,
            prev_tx_hash=self.base_ledger._get_account_state(sender_id).last_tx_hash or self.base_ledger.genesis_hash,
            nonce=self._get_nonce(sender_id),
            to_user_id=receiver_id,
            biz_id=content_id,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        tx.tx_hash = tx.compute_hash()

        self.base_ledger.add_tx(tx)
        return tx

    def record_fitness_evaluation(
        self,
        agent_id: str,
        fitness_scores: FitnessScore,
    ) -> EventTx:
        """记录适应度评估"""
        metadata = {
            "agent_id": agent_id,
            "thinking_quality": fitness_scores.thinking_quality,
            "communication_ability": fitness_scores.communication_ability,
            "niche_adaptation": fitness_scores.niche_adaptation,
            "cooperation_score": fitness_scores.cooperation_score,
            "innovation_score": fitness_scores.innovation_score,
            "overall_fitness": fitness_scores.overall_fitness,
            "timestamp": time.time(),
        }

        tx = EventTx(
            user_id=agent_id,
            op_type=CommunityOpType.FITNESS_EVALUATED,
            amount=1,
            prev_tx_hash=self.base_ledger._get_account_state(agent_id).last_tx_hash or self.base_ledger.genesis_hash,
            nonce=self._get_nonce(agent_id),
            biz_id=f"fitness_{agent_id}_{time.time()}",
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        tx.tx_hash = tx.compute_hash()

        self.base_ledger.add_tx(tx)
        return tx

    def record_stage_transition(
        self,
        community_name: str,
        from_stage: StageType,
        to_stage: StageType,
        trigger_reason: str,
    ) -> EventTx:
        """记录阶段转换"""
        tx_id = f"stage_trans_{time.time()}"

        metadata = {
            "community_name": community_name,
            "from_stage": from_stage.value,
            "to_stage": to_stage.value,
            "trigger_reason": trigger_reason,
            "timestamp": time.time(),
        }

        tx = EventTx(
            user_id=f"system_{community_name}",
            op_type=CommunityOpType.STAGE_TRANSITION,
            amount=1,
            prev_tx_hash=self.base_ledger.genesis_hash,
            nonce=0,
            biz_id=tx_id,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        tx.tx_hash = tx.compute_hash()

        self.base_ledger.add_tx(tx)
        return tx

    def record_niche_formation(
        self,
        niche_id: str,
        members: List[str],
        niche_type: str,
    ) -> EventTx:
        """记录生态位形成"""
        tx_id = f"niche_{niche_id}_{time.time()}"

        metadata = {
            "niche_id": niche_id,
            "members": members,
            "niche_type": niche_type,
            "timestamp": time.time(),
        }

        # 使用第一个成员作为交易发起者
        tx = EventTx(
            user_id=members[0] if members else "system",
            op_type=CommunityOpType.NICHE_FORMED,
            amount=1,
            prev_tx_hash=self.base_ledger.genesis_hash,
            nonce=0,
            biz_id=tx_id,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        tx.tx_hash = tx.compute_hash()

        self.base_ledger.add_tx(tx)
        return tx

    def get_agent_chain(self, agent_id: str) -> List[EventTx]:
        """获取某个AI个体的完整事件链"""
        chain = []

        for tx_hash, tx in self.base_ledger.txs.items():
            if tx.user_id == agent_id:
                chain.append(tx)

        return sorted(chain, key=lambda x: x.created_at)

    def get_evolution_timeline(self) -> List[Dict]:
        """获取进化时间线"""
        timeline = []

        for tx_hash, tx in self.base_ledger.txs.items():
            if tx.op_type in (
                CommunityOpType.AGENT_BIRTH,
                CommunityOpType.AGENT_DEATH,
                CommunityOpType.STAGE_TRANSITION,
                CommunityOpType.NICHE_FORMED,
            ):
                metadata = tx.get_metadata()
                timeline.append({
                    "tx_hash": tx_hash,
                    "event_type": tx.op_type.value,
                    "timestamp": tx.created_at,
                    "details": metadata,
                })

        return sorted(timeline, key=lambda x: x["timestamp"])


# ═══════════════════════════════════════════════════════════════════════════════
# 集成管理器
# ═══════════════════════════════════════════════════════════════════════════════

class CommunityLedgerIntegration:
    """
    社区账本集成管理器

    协调AI社区与事件账本的交互，
    确保关键事件被正确记录。
    """

    def __init__(
        self,
        community: EvolvingCommunity,
        ledger: EventLedger,
    ):
        self.community = community
        self.ledger = ledger
        self.community_ledger = CommunityEventLedger(community, ledger)

        # 设置回调
        self._setup_callbacks()

    def _setup_callbacks(self):
        """设置社区回调"""
        def on_agent_created(agent: AIAgent):
            self.community_ledger.record_agent_birth(agent)

        def on_thought_generated(agent_id: str, thought):
            self.community_ledger.record_thought(
                agent_id=agent_id,
                thought_id=thought.thought_id,
                thought_type=thought.thought_type,
                topic=thought.topic,
                quality_scores={
                    "depth": thought.depth_score,
                    "creativity": thought.creativity_score,
                    "logical": thought.logical_score,
                }
            )

        def on_stage_transition(from_stage: StageType, to_stage: StageType):
            self.community_ledger.record_stage_transition(
                community_name=self.community.name,
                from_stage=from_stage,
                to_stage=to_stage,
                trigger_reason="自动阶段转换",
            )

        self.community.on_agent_created = on_agent_created
        self.community.on_thought_generated = on_thought_generated
        self.community.on_stage_transition = on_stage_transition

    def sync_all_agents(self):
        """同步所有AI个体到账本"""
        for agent in self.community.get_all_agents():
            if agent.agent_id not in self.ledger._account_states:
                # 新个体，创建birth事件
                self.community_ledger.record_agent_birth(agent)

    def export_evolution_report(self) -> Dict[str, Any]:
        """导出发育报告"""
        return {
            "community_name": self.community.name,
            "current_stage": self.community.stage_manager.get_current_stage().value,
            "agent_count": len(self.community.agents),
            "total_events": len(self.ledger.txs),
            "timeline": self.community_ledger.get_evolution_timeline(),
            "diversity_report": self.community.get_diversity_report(),
        }

    def verify_ledger_integrity(self) -> Dict[str, Any]:
        """验证账本完整性"""
        issues = []
        verified_count = 0

        for tx_hash, tx in self.ledger.txs.items():
            # 验证哈希
            if not tx.verify_hash():
                issues.append(f"TX {tx_hash[:12]} 哈希验证失败")

            # 验证链式结构
            if tx.prev_tx_hash:
                if tx.prev_tx_hash not in self.ledger.txs:
                    # 可能是创世交易，跳过
                    if tx.prev_tx_hash != self.ledger.genesis_hash:
                        issues.append(f"TX {tx_hash[:12]} 前置哈希不存在")

            verified_count += 1

        return {
            "verified_count": verified_count,
            "issue_count": len(issues),
            "issues": issues[:10],  # 最多显示10个问题
            "integrity_score": 1.0 - len(issues) / max(verified_count, 1),
        }