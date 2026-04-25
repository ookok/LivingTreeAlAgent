"""
Consensus Engine
共识引擎 - 多Agent决策和共识达成
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Set
from datetime import datetime
from enum import Enum
from collections import Counter


class ConsensusStrategy(Enum):
    """共识策略"""
    UNANIMOUS = "unanimous"         # 全票通过
    MAJORITY = "majority"           # 多数同意 (超过50%)
    SUPERMAJORITY = "supermajority" # 绝对多数 (超过66%)
    WEIGHTED = "weighted"           # 加权投票
    DELAYED = "delayed"             # 延迟共识 (多轮讨论)
    DICTATOR = "dictator"           # 独裁模式 (权威决定)
    EXPERT = "expert"               # 专家决策


@dataclass
class Vote:
    """投票"""
    voter_id: str                   # 投票者ID
    option_index: int               # 选择的方案索引
    confidence: float = 1.0         # 信心程度 (0-1)
    reasoning: str = ""             # 投票理由
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConsensusResult:
    """共识结果"""
    success: bool                   # 是否达成共识
    agreed_option: Optional[int]    # 达成共识的方案索引
    votes: List[Vote]               # 所有投票
    vote_counts: Dict[int, int] = field(default_factory=dict)  # 每个方案的票数
    confidence: float = 0.0         # 共识置信度
    disagreement_agents: List[str] = field(default_factory=list)  # 不同意者
    final_reasoning: str = ""       # 最终推理
    elapsed_time: float = 0.0       # 达成共识耗时(秒)


@dataclass
class DebateRound:
    """辩论轮次"""
    round_number: int               # 轮次编号
    arguments: Dict[str, str] = field(default_factory=dict)  # agent_id -> 论点
    rebuttals: List[Dict[str, str]] = field(default_factory=list)  # 反驳列表
    updated_votes: Dict[str, int] = field(default_factory=dict)  # 更新后的投票
    timestamp: datetime = field(default_factory=datetime.now)


class ConsensusEngine:
    """共识引擎
    
    支持多种共识策略，帮助多个Agent达成决策
    """
    
    def __init__(self):
        """初始化共识引擎"""
        self._vote_validators: Dict[str, Callable] = {}  # 投票验证器
    
    def register_validator(
        self,
        name: str,
        validator: Callable[[str, int, Any], bool]
    ):
        """注册投票验证器
        
        Args:
            name: 验证器名称
            validator: 验证函数 (voter_id, option_index, context) -> bool
        """
        self._vote_validators[name] = validator
    
    async def reach_consensus(
        self,
        topic: str,
        options: List[Any],
        voters: Dict[str, float],  # voter_id -> weight
        strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY,
        max_rounds: int = 3,
        context: Any = None
    ) -> ConsensusResult:
        """达成共识
        
        Args:
            topic: 决策主题
            options: 可选方案列表
            voters: 投票者及其权重
            strategy: 共识策略
            max_rounds: 最大辩论轮次
            context: 额外上下文
            
        Returns:
            共识结果
        """
        start_time = time.time()
        votes: List[Vote] = []
        
        # 第一轮: 初始投票
        for voter_id in voters:
            vote = Vote(
                voter_id=voter_id,
                option_index=0,  # 默认第一项
                confidence=0.5,
                reasoning=""
            )
            votes.append(vote)
        
        # 多轮辩论
        debate_rounds: List[DebateRound] = []
        
        for round_num in range(max_rounds):
            round_result = await self._debate_round(
                round_num=round_num,
                options=options,
                votes=votes,
                voters=voters,
                context=context
            )
            debate_rounds.append(round_result)
            
            # 检查是否达成共识
            current_result = await self._evaluate_consensus(
                votes=votes,
                options=options,
                voters=voters,
                strategy=strategy
            )
            
            if current_result.success:
                current_result.debate_rounds = debate_rounds
                current_result.elapsed_time = time.time() - start_time
                return current_result
        
        # 最终评估
        final_result = await self._evaluate_consensus(
            votes=votes,
            options=options,
            voters=voters,
            strategy=strategy
        )
        
        final_result.debate_rounds = debate_rounds
        final_result.elapsed_time = time.time() - start_time
        
        return final_result
    
    async def _debate_round(
        self,
        round_num: int,
        options: List[Any],
        votes: List[Vote],
        voters: Dict[str, float],
        context: Any
    ) -> DebateRound:
        """执行一轮辩论
        
        在实际应用中，这里应该调用Agent的推理能力
        简化版本: 根据历史调整投票
        """
        arguments: Dict[str, str] = {}
        
        # 模拟论点生成
        for voter_id in voters:
            # 简化: 随机选择方案
            import random
            if random.random() > 0.5:
                # 支持多数意见
                vote_counts = Counter(v.option_index for v in votes)
                most_common = vote_counts.most_common(1)[0][0]
                arguments[voter_id] = f"I reconsider and now support option {most_common}"
            else:
                arguments[voter_id] = f"I maintain my position on option {votes[[v.voter_id for v in votes].index(voter_id)].option_index}"
        
        # 更新投票
        for vote in votes:
            voter_arguments = arguments.get(vote.voter_id, "")
            # 简化: 大约30%可能改变投票
            import random
            if "support option" in voter_arguments:
                for option_idx, count in Counter(v.option_index for v in votes).most_common():
                    if count > len(votes) * 0.3:
                        vote.option_index = option_idx
                        break
        
        return DebateRound(
            round_number=round_num,
            arguments=arguments,
            updated_votes={v.voter_id: v.option_index for v in votes}
        )
    
    async def _evaluate_consensus(
        self,
        votes: List[Vote],
        options: List[Any],
        voters: Dict[str, float],
        strategy: ConsensusStrategy
    ) -> ConsensusResult:
        """评估共识达成情况"""
        
        if not votes:
            return ConsensusResult(
                success=False,
                agreed_option=None,
                votes=[],
                confidence=0.0
            )
        
        # 统计票数
        vote_counts: Dict[int, int] = Counter(v.option_index for v in votes)
        total_votes = len(votes)
        total_weight = sum(voters.values())
        
        # 计算加权票数
        weighted_counts: Dict[int, float] = Counter()
        for vote in votes:
            weight = voters.get(vote.voter_id, 1.0)
            weighted_counts[vote.option_index] += weight * vote.confidence
        
        # 根据策略判断是否达成共识
        if strategy == ConsensusStrategy.UNANIMOUS:
            # 全票通过
            if len(vote_counts) == 1:
                agreed = list(vote_counts.keys())[0]
                confidence = 1.0
                success = True
            else:
                agreed = None
                confidence = 0.0
                success = False
        
        elif strategy == ConsensusStrategy.MAJORITY:
            # 多数同意 (>50%)
            max_votes = max(vote_counts.values())
            if max_votes > total_votes / 2:
                agreed = max(vote_counts, key=vote_counts.get)
                confidence = max_votes / total_votes
                success = True
            else:
                agreed = None
                confidence = max_votes / total_votes
                success = False
        
        elif strategy == ConsensusStrategy.SUPERMAJORITY:
            # 绝对多数 (>66%)
            max_votes = max(vote_counts.values())
            if max_votes > total_votes * 0.66:
                agreed = max(vote_counts, key=vote_counts.get)
                confidence = max_votes / total_votes
                success = True
            else:
                agreed = None
                confidence = max_votes / total_votes
                success = False
        
        elif strategy == ConsensusStrategy.WEIGHTED:
            # 加权投票
            max_weighted = max(weighted_counts.values())
            if max_weighted > total_weight / 2:
                agreed = max(weighted_counts, key=weighted_counts.get)
                confidence = max_weighted / total_weight
                success = True
            else:
                agreed = None
                confidence = max_weighted / total_weight
                success = False
        
        elif strategy == ConsensusStrategy.DICTATOR:
            # 独裁模式: 取权重最高的投票者
            max_weight_voter = max(voters.items(), key=lambda x: x[1])[0]
            for vote in votes:
                if vote.voter_id == max_weight_voter:
                    agreed = vote.option_index
                    confidence = voters[max_weight_voter] / total_weight
                    success = True
                    break
            else:
                agreed = None
                confidence = 0.0
                success = False
        
        else:
            # 默认多数
            max_votes = max(vote_counts.values())
            agreed = max(vote_counts, key=vote_counts.get)
            confidence = max_votes / total_votes
            success = max_votes > total_votes / 2
        
        # 找出不同意者
        disagreement_agents = []
        if agreed is not None:
            for vote in votes:
                if vote.option_index != agreed:
                    disagreement_agents.append(vote.voter_id)
        
        # 生成推理
        final_reasoning = self._generate_reasoning(
            strategy=strategy,
            agreed=agreed,
            options=options,
            vote_counts=vote_counts,
            confidence=confidence
        )
        
        return ConsensusResult(
            success=success,
            agreed_option=agreed,
            votes=votes,
            vote_counts=dict(vote_counts),
            confidence=confidence,
            disagreement_agents=disagreement_agents,
            final_reasoning=final_reasoning
        )
    
    def _generate_reasoning(
        self,
        strategy: ConsensusStrategy,
        agreed: Optional[int],
        options: List[Any],
        vote_counts: Dict[int, int],
        confidence: float
    ) -> str:
        """生成推理说明"""
        if agreed is None:
            return f"No consensus reached using {strategy.value} strategy. Highest support: {max(vote_counts.values()) if vote_counts else 0} votes."
        
        option_desc = str(options[agreed]) if agreed < len(options) else "unknown"
        return f"Consensus reached on {strategy.value}: Option {agreed} ({option_desc}) with {confidence:.1%} confidence and {vote_counts.get(agreed, 0)} votes."
    
    async def quick_decide(
        self,
        options: List[Any],
        votes: Dict[str, int]  # voter_id -> option_index
    ) -> int:
        """快速决策 (简单多数)
        
        Args:
            options: 可选方案
            votes: 投票 (voter_id -> option_index)
            
        Returns:
            胜出的方案索引
        """
        if not votes:
            return 0
        
        vote_list = list(votes.values())
        counts = Counter(vote_list)
        return counts.most_common(1)[0][0]
