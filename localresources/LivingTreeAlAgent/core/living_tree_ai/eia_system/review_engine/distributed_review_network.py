"""
分布式审查网络 - P2P网络的"集体智慧审查"
==========================================

核心思想：将单次审查升级为网络共识，利用分布式节点的专业知识。

功能：
1. 分布式投票机制 - 分发报告给专业节点进行评价
2. 审查历史追溯 - 生成唯一哈希，记录审查轨迹
3. 争议解决 - 争议性结论的共识机制
"""

import asyncio
import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class NodeType(Enum):
    """节点类型"""
    ENGINEER = "engineer"           # 工程师节点
    EXPERT = "expert"              # 专家节点
    REGULATOR = "regulator"        # 监管节点
    VALIDATOR = "validator"        # 验证节点


class VoteStatus(Enum):
    """投票状态"""
    PENDING = "pending"            # 待投票
    AGREED = "agreed"              # 同意
    OBJECTED = "objected"          # 反对
    ABSTAINED = "abstained"        # 弃权


class ConsensusLevel(Enum):
    """共识级别"""
    UNANIMOUS = "unanimous"        # 全票同意
    STRONG_CONSENSUS = "strong"    # 强共识 (>80%)
    CONSENSUS = "consensus"        # 共识 (>60%)
    DISPUTED = "disputed"          # 争议
    REJECTED = "rejected"          # 多数反对


@dataclass
class ReviewNode:
    """审查节点"""
    node_id: str
    node_name: str
    node_type: NodeType
    expertise: List[str] = field(default_factory=list)  # 专业领域
    reputation: float = 0.0         # 信誉分 0-100
    total_reviews: int = 0          # 总审查次数
    successful_reviews: int = 0     # 成功审查次数
    token_balance: float = 0.0      # 代币余额

    # 连接信息
    address: Optional[str] = None
    is_online: bool = False

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "node_type": self.node_type.value,
            "expertise": self.expertise,
            "reputation": self.reputation,
            "total_reviews": self.total_reviews,
            "successful_reviews": self.successful_reviews,
            "token_balance": self.token_balance,
            "is_online": self.is_online,
        }


@dataclass
class ReviewTask:
    """审查任务"""
    task_id: str
    report_id: str
    report_hash: str                 # 报告的哈希值
    report_title: str
    report_summary: str              # 脱敏后的摘要

    # 争议焦点
    disputed_conclusions: List[str] = field(default_factory=list)
    uncertainty_points: List[str] = field(default_factory=list)

    # 任务分配
    assigned_nodes: List[str] = field(default_factory=list)  # 分配的节点ID列表
    required_votes: int = 3          # 需要的投票数
    deadline: Optional[datetime] = None

    # 状态
    status: str = "pending"          # pending, in_progress, completed, expired
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "report_id": self.report_id,
            "report_hash": self.report_hash,
            "report_title": self.report_title,
            "assigned_nodes": self.assigned_nodes,
            "required_votes": self.required_votes,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ReviewVote:
    """审查投票"""
    vote_id: str
    task_id: str
    node_id: str
    node_name: str

    # 投票内容
    conclusion: str                  # 被评价的结论
    verdict: VoteStatus              # 投票结果
    confidence: float                # 置信度 0-1
    comments: str = ""               # 评语

    # 评分
    technical_score: float = 0.0     # 技术评分 0-10
    compliance_score: float = 0.0    # 合规评分 0-10
    overall_score: float = 0.0       # 综合评分 0-10

    # 元数据
    voted_at: datetime = field(default_factory=datetime.now)
    token_reward: float = 0.0        # 获得的代币奖励

    def to_dict(self) -> Dict:
        return {
            "vote_id": self.vote_id,
            "task_id": self.task_id,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "conclusion": self.conclusion,
            "verdict": self.verdict.value,
            "confidence": self.confidence,
            "comments": self.comments,
            "technical_score": self.technical_score,
            "compliance_score": self.compliance_score,
            "overall_score": self.overall_score,
            "voted_at": self.voted_at.isoformat(),
            "token_reward": self.token_reward,
        }


@dataclass
class ConsensusResult:
    """共识结果"""
    task_id: str
    report_id: str

    # 投票统计
    total_votes: int
    agreed: int
    objected: int
    abstained: int

    # 共识级别
    consensus_level: ConsensusLevel
    consensus_score: float           # 共识程度 0-1

    # 评分统计
    avg_technical_score: float
    avg_compliance_score: float
    avg_overall_score: float

    # 结论评价
    conclusion_reviews: List[Dict] = field(default_factory=list)

    # 最终建议
    final_recommendation: str        # ACCEPT, REVISE, REJECT
    recommendation_reason: str

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "report_id": self.report_id,
            "total_votes": self.total_votes,
            "agreed": self.agreed,
            "objected": self.objected,
            "abstained": self.abstained,
            "consensus_level": self.consensus_level.value,
            "consensus_score": self.consensus_score,
            "avg_technical_score": self.avg_technical_score,
            "avg_compliance_score": self.avg_compliance_score,
            "avg_overall_score": self.avg_overall_score,
            "conclusion_reviews": self.conclusion_reviews,
            "final_recommendation": self.final_recommendation,
            "recommendation_reason": self.recommendation_reason,
        }


@dataclass
class ReviewRecord:
    """审查记录（用于追溯）"""
    record_id: str
    report_id: str
    report_hash: str                 # 报告哈希

    # 审查信息
    review_time: datetime
    reviewer_nodes: List[Dict]       # 参与审查的节点信息
    consensus_result: Optional[Dict]

    # 审查结论
    disputed_points: List[str]       # 争议点
    resolution: str                  # 解决方案

    # 元数据
    review_hash: str                 # 本次审查的哈希
    previous_record_hash: Optional[str] = None  # 前序记录哈希（链式追溯）

    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "report_id": self.report_id,
            "report_hash": self.report_hash,
            "review_time": self.review_time.isoformat(),
            "reviewer_nodes": self.reviewer_nodes,
            "consensus_result": self.consensus_result,
            "disputed_points": self.disputed_points,
            "resolution": self.resolution,
            "review_hash": self.review_hash,
            "previous_record_hash": self.previous_record_hash,
        }


class DistributedReviewNetwork:
    """
    分布式审查网络

    核心能力：
    1. 审查任务分发与投票
    2. 共识机制与争议解决
    3. 审查历史追溯（区块链式结构）
    4. 信誉系统与代币激励
    """

    def __init__(self, node_name: str = "LocalNode"):
        self.local_node = ReviewNode(
            node_id=self._generate_node_id(node_name),
            node_name=node_name,
            node_type=NodeType.ENGINEER,
            expertise=["环境影响评价"],
            reputation=80.0
        )

        # 网络中的其他节点
        self.peers: Dict[str, ReviewNode] = {}

        # 审查任务
        self.tasks: Dict[str, ReviewTask] = {}

        # 投票记录
        self.votes: Dict[str, List[ReviewVote]] = {}

        # 审查记录链
        self.review_records: List[ReviewRecord] = []

        # 代币系统
        self.token_reward_pool: float = 1000.0  # 初始代币池

        # P2P通信回调
        self.p2p_send_callback: Optional[Callable] = None

    def _generate_node_id(self, name: str) -> str:
        """生成节点ID"""
        timestamp = str(time.time())
        content = f"{name}_{timestamp}_{random.randint(1000, 9999)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _generate_hash(self, *args) -> str:
        """生成哈希"""
        content = "_".join(str(a) for a in args)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def set_p2p_callback(self, callback: Callable):
        """设置P2P通信回调"""
        self.p2p_send_callback = callback

    # ============ 节点管理 ============

    def register_peer(self, peer: ReviewNode):
        """注册对等节点"""
        self.peers[peer.node_id] = peer
        peer.is_online = True

    def unregister_peer(self, node_id: str):
        """注销对等节点"""
        if node_id in self.peers:
            self.peers[node_id].is_online = False

    def get_online_nodes(
        self,
        expertise: Optional[List[str]] = None,
        min_reputation: float = 0.0
    ) -> List[ReviewNode]:
        """获取在线节点列表"""
        nodes = [n for n in self.peers.values() if n.is_online]

        if expertise:
            nodes = [n for n in nodes if any(e in n.expertise for e in expertise)]

        if min_reputation > 0:
            nodes = [n for n in nodes if n.reputation >= min_reputation]

        return nodes

    # ============ 审查任务 ============

    async def create_review_task(
        self,
        report_id: str,
        report_title: str,
        report_content: Dict[str, Any],
        disputed_conclusions: List[str],
        project_context: Dict[str, Any]
    ) -> ReviewTask:
        """
        创建审查任务

        Args:
            report_id: 报告ID
            report_title: 报告标题
            report_content: 报告内容（将脱敏）
            disputed_conclusions: 争议性结论列表
            project_context: 项目上下文

        Returns:
            ReviewTask: 创建的审查任务
        """
        # 生成报告哈希
        report_hash = self._generate_hash(report_id, json.dumps(report_content, sort_keys=True))

        # 脱敏报告摘要（移除敏感信息）
        report_summary = self._anonymize_report(report_content, project_context)

        # 创建任务
        task_id = self._generate_hash("task", report_id, datetime.now().isoformat())
        task = ReviewTask(
            task_id=task_id,
            report_id=report_id,
            report_hash=report_hash,
            report_title=report_title,
            report_summary=report_summary,
            disputed_conclusions=disputed_conclusions,
            uncertainty_points=project_context.get('uncertainty_points', []),
            deadline=datetime.now() + timedelta(hours=24)  # 24小时截止
        )

        # 自动分配节点
        required_expertise = project_context.get('industry_type', '')
        assigned_nodes = await self._auto_assign_nodes(required_expertise, task.required_votes)
        task.assigned_nodes = assigned_nodes

        # 保存任务
        self.tasks[task_id] = task
        self.votes[task_id] = []

        # 分发任务给节点
        await self._dispatch_task(task)

        return task

    def _anonymize_report(
        self,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> str:
        """脱敏报告，移除敏感信息"""
        # 移除具体坐标，保留区域
        lat = project_context.get('lat', 0)
        lon = project_context.get('lon', 0)

        # 生成模糊位置（精确到县级）
        location = project_context.get('location', '')

        # 移除企业名称
        project_name = project_context.get('project_name', '某项目')

        # 生成摘要
        summary = f"{project_context.get('industry_type', '工业')}项目"
        summary += f"，位于{location}"
        summary += f"，涉及{project_context.get('main_pollutants', ['大气污染物'])}排放"

        return summary

    async def _auto_assign_nodes(
        self,
        expertise_needed: str,
        required_count: int
    ) -> List[str]:
        """自动分配审查节点"""
        # 找到有相关经验的节点
        candidates = self.get_online_nodes(
            expertise=[expertise_needed],
            min_reputation=50.0
        )

        # 如果不够，扩大范围
        if len(candidates) < required_count:
            candidates.extend(
                self.get_online_nodes(min_reputation=30.0)
            )

        # 随机选择（考虑信誉加权）
        candidates.sort(key=lambda n: n.reputation, reverse=True)
        selected = candidates[:required_count]

        return [n.node_id for n in selected]

    async def _dispatch_task(self, task: ReviewTask):
        """分发任务给节点"""
        if self.p2p_send_callback:
            for node_id in task.assigned_nodes:
                await self.p2p_send_callback(
                    node_id,
                    {
                        "type": "review_task",
                        "task": task.to_dict()
                    }
                )

    # ============ 投票系统 ============

    async def submit_vote(
        self,
        task_id: str,
        node_id: str,
        conclusion: str,
        verdict: VoteStatus,
        comments: str = "",
        technical_score: float = 0.0,
        compliance_score: float = 0.0
    ) -> ReviewVote:
        """
        提交投票

        Args:
            task_id: 任务ID
            node_id: 节点ID
            conclusion: 被评价的结论
            verdict: 投票结果
            comments: 评语
            technical_score: 技术评分
            compliance_score: 合规评分

        Returns:
            ReviewVote: 投票记录
        """
        # 验证节点
        if node_id not in self.peers:
            node = self.local_node
        else:
            node = self.peers[node_id]

        # 计算综合评分
        overall_score = (technical_score + compliance_score) / 2

        # 创建投票
        vote_id = self._generate_hash("vote", task_id, node_id, datetime.now().isoformat())
        vote = ReviewVote(
            vote_id=vote_id,
            task_id=task_id,
            node_id=node.node_id,
            node_name=node.node_name,
            conclusion=conclusion,
            verdict=verdict,
            confidence=overall_score / 10.0,
            comments=comments,
            technical_score=technical_score,
            compliance_score=compliance_score,
            overall_score=overall_score
        )

        # 保存投票
        if task_id not in self.votes:
            self.votes[task_id] = []
        self.votes[task_id].append(vote)

        # 更新节点统计
        node.total_reviews += 1

        # 计算代币奖励
        token_reward = self._calculate_token_reward(vote, node)
        vote.token_reward = token_reward
        node.token_balance += token_reward

        # 检查是否达到共识
        await self._check_consensus(task_id)

        return vote

    def _calculate_token_reward(self, vote: ReviewVote, node: ReviewNode) -> float:
        """计算代币奖励"""
        base_reward = 10.0

        # 信誉加成
        reputation_multiplier = node.reputation / 100.0

        # 评分加成
        score_multiplier = vote.overall_score / 10.0

        # 共识加成
        consensus_bonus = 5.0 if vote.verdict == VoteStatus.AGREED else 0

        reward = base_reward * reputation_multiplier * score_multiplier + consensus_bonus
        return round(reward, 2)

    async def _check_consensus(self, task_id: str):
        """检查是否达到共识"""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]
        votes = self.votes.get(task_id, [])

        # 需要达到最低投票数
        if len(votes) < task.required_votes:
            return

        # 计算共识
        result = self._calculate_consensus(task, votes)

        # 判断是否结束任务
        if result.consensus_level in [
            ConsensusLevel.UNANIMOUS,
            ConsensusLevel.STRONG_CONSENSUS,
            ConsensusLevel.CONSENSUS,
            ConsensusLevel.REJECTED
        ]:
            task.status = "completed"

            # 生成审查记录
            await self._create_review_record(task, votes, result)

    def _calculate_consensus(self, task: ReviewTask, votes: List[ReviewVote]) -> ConsensusResult:
        """计算共识结果"""
        total = len(votes)
        agreed = sum(1 for v in votes if v.verdict == VoteStatus.AGREED)
        objected = sum(1 for v in votes if v.verdict == VoteStatus.OBJECTED)
        abstained = sum(1 for v in votes if v.verdict == VoteStatus.ABSTAINED)

        # 计算共识分数
        if total > 0:
            consensus_score = agreed / total
        else:
            consensus_score = 0

        # 确定共识级别
        if agreed == total:
            consensus_level = ConsensusLevel.UNANIMOUS
        elif consensus_score >= 0.8:
            consensus_level = ConsensusLevel.STRONG_CONSENSUS
        elif consensus_score >= 0.6:
            consensus_level = ConsensusLevel.CONSENSUS
        elif objected > agreed:
            consensus_level = ConsensusLevel.REJECTED
        else:
            consensus_level = ConsensusLevel.DISPUTED

        # 计算平均分
        avg_technical = sum(v.technical_score for v in votes) / total if total > 0 else 0
        avg_compliance = sum(v.compliance_score for v in votes) / total if total > 0 else 0
        avg_overall = sum(v.overall_score for v in votes) / total if total > 0 else 0

        # 生成结论评价列表
        conclusion_reviews = []
        for conclusion in task.disputed_conclusions:
            relevant_votes = [v for v in votes if v.conclusion == conclusion]
            if relevant_votes:
                avg_score = sum(v.overall_score for v in relevant_votes) / len(relevant_votes)
                verdict_count = {
                    "agreed": sum(1 for v in relevant_votes if v.verdict == VoteStatus.AGREED),
                    "objected": sum(1 for v in relevant_votes if v.verdict == VoteStatus.OBJECTED),
                }
                conclusion_reviews.append({
                    "conclusion": conclusion,
                    "avg_score": avg_score,
                    "verdict_count": verdict_count,
                })

        # 生成最终建议
        if consensus_level == ConsensusLevel.UNANIMOUS:
            final_recommendation = "ACCEPT"
            recommendation_reason = "全票同意，报告通过审查"
        elif consensus_level == ConsensusLevel.STRONG_CONSENSUS:
            final_recommendation = "ACCEPT"
            recommendation_reason = "强共识，建议接受报告"
        elif consensus_level == ConsensusLevel.CONSENSUS:
            final_recommendation = "REVISE"
            recommendation_reason = "达成共识，建议对争议点进行修订"
        elif consensus_level == ConsensusLevel.REJECTED:
            final_recommendation = "REJECT"
            recommendation_reason = "多数反对，建议重新编写报告"
        else:
            final_recommendation = "REVISE"
            recommendation_reason = "存在争议，建议进一步澄清"

        return ConsensusResult(
            task_id=task.task_id,
            report_id=task.report_id,
            total_votes=total,
            agreed=agreed,
            objected=objected,
            abstained=abstained,
            consensus_level=consensus_level,
            consensus_score=consensus_score,
            avg_technical_score=avg_technical,
            avg_compliance_score=avg_compliance,
            avg_overall_score=avg_overall,
            conclusion_reviews=conclusion_reviews,
            final_recommendation=final_recommendation,
            recommendation_reason=recommendation_reason
        )

    # ============ 审查追溯 ============

    async def _create_review_record(
        self,
        task: ReviewTask,
        votes: List[ReviewVote],
        consensus: ConsensusResult
    ):
        """创建审查记录"""
        # 获取前序记录哈希
        previous_hash = None
        if self.review_records:
            previous_hash = self.review_records[-1].review_hash

        # 生成审查哈希
        record_content = {
            "report_id": task.report_id,
            "report_hash": task.report_hash,
            "votes": [v.to_dict() for v in votes],
            "consensus": consensus.to_dict(),
            "review_time": datetime.now().isoformat(),
        }
        record_hash = self._generate_hash(json.dumps(record_content, sort_keys=True))

        # 创建记录
        record = ReviewRecord(
            record_id=self._generate_hash("record", task.task_id, record_hash),
            report_id=task.report_id,
            report_hash=task.report_hash,
            review_time=datetime.now(),
            reviewer_nodes=[{"node_id": v.node_id, "node_name": v.node_name} for v in votes],
            consensus_result=consensus.to_dict(),
            disputed_points=task.disputed_conclusions,
            resolution=consensus.final_recommendation,
            review_hash=record_hash,
            previous_record_hash=previous_hash
        )

        self.review_records.append(record)

    def verify_review_chain(self) -> Tuple[bool, str]:
        """
        验证审查链的完整性

        Returns:
            (is_valid, message): 验证结果和消息
        """
        if not self.review_records:
            return True, "审查链为空"

        for i, record in enumerate(self.review_records):
            # 验证链式结构
            if i > 0:
                expected_previous = self.review_records[i - 1].review_hash
                if record.previous_record_hash != expected_previous:
                    return False, f"记录 {i} 的前序哈希不匹配"

            # 验证自身哈希
            computed_hash = self._generate_hash(
                record.report_id,
                record.report_hash,
                str(record.review_time),
                str(record.consensus_result)
            )
            if record.review_hash != computed_hash:
                return False, f"记录 {i} 的哈希验证失败"

        return True, "审查链完整，可追溯"

    def get_report_review_history(self, report_id: str) -> List[ReviewRecord]:
        """获取报告的审查历史"""
        return [r for r in self.review_records if r.report_id == report_id]

    # ============ 信誉系统 ============

    def update_node_reputation(self, node_id: str, success: bool):
        """更新节点信誉"""
        if node_id in self.peers:
            node = self.peers[node_id]
            if success:
                node.successful_reviews += 1

            # 计算新信誉
            if node.total_reviews > 0:
                success_rate = node.successful_reviews / node.total_reviews
                # 信誉 = 成功率 * 权重 + 当前信誉 * (1 - 权重)
                node.reputation = success_rate * 0.7 + node.reputation * 0.3
                node.reputation = min(100.0, max(0.0, node.reputation))

    # ============ 便捷方法 ============

    async def request_review(
        self,
        report_id: str,
        report_title: str,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> str:
        """
        请求审查的便捷方法

        Returns:
            task_id: 审查任务ID
        """
        # 识别争议性结论
        disputed = self._identify_disputed_conclusions(report_content, project_context)

        # 创建审查任务
        task = await self.create_review_task(
            report_id=report_id,
            report_title=report_title,
            report_content=report_content,
            disputed_conclusions=disputed,
            project_context=project_context
        )

        return task.task_id

    def _identify_disputed_conclusions(
        self,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> List[str]:
        """识别可能的争议性结论"""
        disputed = []

        # 检查不确定性高的结论
        uncertainty_keywords = [
            "预测", "估算", "假设", "模型", "可能", "或许"
        ]

        if 'conclusions' in report_content:
            for conclusion in report_content['conclusions']:
                for keyword in uncertainty_keywords:
                    if keyword in conclusion:
                        disputed.append(conclusion)
                        break

        # 如果没有明确结论，返回空
        return disputed[:3]  # 最多3个争议点

    def get_review_status(self, task_id: str) -> Optional[Dict]:
        """获取审查状态"""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        votes = self.votes.get(task_id, [])

        return {
            "task": task.to_dict(),
            "votes_received": len(votes),
            "votes": [v.to_dict() for v in votes],
            "consensus_progress": len(votes) / task.required_votes if task.required_votes > 0 else 0
        }


# 全局实例
_review_network_instance: Optional[DistributedReviewNetwork] = None


def get_review_network(node_name: str = "LocalNode") -> DistributedReviewNetwork:
    """获取分布式审查网络全局实例"""
    global _review_network_instance
    if _review_network_instance is None:
        _review_network_instance = DistributedReviewNetwork(node_name)
    return _review_network_instance


def get_review_network_instance() -> Optional[DistributedReviewNetwork]:
    """获取实例（不创建）"""
    return _review_network_instance