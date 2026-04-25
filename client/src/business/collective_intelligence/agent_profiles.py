"""
Agent Profiles and Related Data Models
Agent画像和相关数据模型
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
from datetime import datetime


class AgentRole(Enum):
    """Agent角色类型"""
    COORDINATOR = "coordinator"      # 协调者 - 负责任务分配和协调
    EXPERT = "expert"               # 专家 - 提供领域知识
    LEARNER = "learner"             # 学习者 - 学习新技能
    CRITIC = "critic"               # 评论者 - 提供批评和改进建议
    EXECUTOR = "executor"           # 执行者 - 执行具体任务
    ORCHESTRATOR = "orchestrator"   # 编排者 - 编排多Agent工作流


class ExpertiseLevel(Enum):
    """专家水平"""
    NOVICE = "novice"               # 新手
    COMPETENT = "competent"         # 胜任
    PROFICIENT = "proficient"       # 熟练
    EXPERT = "expert"              # 专家
    MASTER = "master"              # 大师


@dataclass
class Expertise:
    """专业知识领域"""
    domain: str                     # 领域名称
    level: ExpertiseLevel           # 熟练度
    examples: List[str] = field(default_factory=list)  # 成功案例
    success_rate: float = 0.0      # 成功率
    total_tasks: int = 0           # 总任务数


@dataclass
class AgentProfile:
    """Agent画像
    
    描述一个Agent的能力、角色和历史表现
    """
    agent_id: str                  # Agent唯一标识
    name: str                       # Agent名称
    role: AgentRole                 # 主要角色
    description: str = ""           # 描述
    
    # 能力评估
    expertise: List[Expertise] = field(default_factory=list)  # 专业领域列表
    capabilities: List[str] = field(default_factory=list)   # 能力列表
    languages: List[str] = field(default_factory=list)       # 支持的语言
    
    # 性能指标
    total_tasks_completed: int = 0  # 已完成任务数
    successful_tasks: int = 0      # 成功任务数
    avg_response_time: float = 0.0  # 平均响应时间(秒)
    reliability_score: float = 1.0 # 可靠性评分 (0-1)
    
    # 协作历史
    collaboration_history: List[Dict[str, Any]] = field(default_factory=list)  # 协作历史
    trust_score: float = 0.5       # 信任评分 (0-1)
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    status: str = "idle"           # 状态: idle, busy, offline
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_tasks_completed == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks_completed
    
    def add_expertise(self, domain: str, level: ExpertiseLevel = ExpertiseLevel.COMPETENT):
        """添加专业领域"""
        for exp in self.expertise:
            if exp.domain == domain:
                exp.level = level
                return
        self.expertise.append(Expertise(domain=domain, level=level))
    
    def get_expertise_level(self, domain: str) -> ExpertiseLevel:
        """获取某个领域的熟练度"""
        for exp in self.expertise:
            if exp.domain == domain:
                return exp.level
        return ExpertiseLevel.NOVICE
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "description": self.description,
            "expertise": [
                {"domain": e.domain, "level": e.level.value, "success_rate": e.success_rate}
                for e in self.expertise
            ],
            "capabilities": self.capabilities,
            "languages": self.languages,
            "success_rate": self.success_rate,
            "trust_score": self.trust_score,
            "status": self.status
        }


@dataclass
class Contribution:
    """Agent贡献"""
    agent_id: str                   # Agent ID
    contribution_type: str          # 贡献类型: knowledge, solution, feedback, critique
    content: Any                    # 贡献内容
    quality_score: float = 0.0      # 质量评分 (0-1)
    impact_score: float = 0.0      # 影响评分 (0-1)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CollectiveDecision:
    """集体决策"""
    decision_id: str               # 决策ID
    topic: str                      # 决策主题
    options: List[Dict[str, Any]]  # 可选方案
    votes: Dict[str, int] = field(default_factory=dict)  # 投票: agent_id -> vote
    reasoning: Dict[str, str] = field(default_factory=dict)  # 推理: agent_id -> reasoning
    selected_option: Optional[int] = None  # 选中的方案索引
    confidence: float = 0.0        # 置信度
    consensus_level: float = 0.0   # 共识程度 (0-1)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_vote(self, agent_id: str, option_index: int, reasoning: str = ""):
        """添加投票"""
        self.votes[agent_id] = option_index
        if reasoning:
            self.reasoning[agent_id] = reasoning
        self._calculate_consensus()
    
    def _calculate_consensus(self):
        """计算共识程度"""
        if not self.votes:
            self.consensus_level = 0.0
            return
        
        vote_counts: Dict[int, int] = {}
        for option_index in self.votes.values():
            vote_counts[option_index] = vote_counts.get(option_index, 0) + 1
        
        if not vote_counts:
            self.consensus_level = 0.0
            return
        
        max_votes = max(vote_counts.values())
        total_votes = len(self.votes)
        
        # 共识程度 = 最高票数 / 总票数
        self.consensus_level = max_votes / total_votes
        
        # 找到最高票的方案
        for i, count in vote_counts.items():
            if count == max_votes:
                self.selected_option = i
                break
        
        # 计算置信度（基于共识程度和投票人数）
        self.confidence = self.consensus_level * min(total_votes / 3, 1.0)


@dataclass
class CollaborationSession:
    """协作会话"""
    session_id: str                 # 会话ID
    task: str                       # 任务描述
    participants: List[str] = field(default_factory=list)  # 参与者Agent ID列表
    contributions: List[Contribution] = field(default_factory=list)  # 贡献列表
    decisions: List[CollectiveDecision] = field(default_factory=list)  # 决策列表
    
    # 元数据
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    status: str = "active"         # active, completed, cancelled
    
    def add_contribution(self, contribution: Contribution):
        """添加贡献"""
        self.contributions.append(contribution)
    
    def add_decision(self, decision: CollectiveDecision):
        """添加决策"""
        self.decisions.append(decision)
    
    def get_agent_contributions(self, agent_id: str) -> List[Contribution]:
        """获取某个Agent的所有贡献"""
        return [c for c in self.contributions if c.agent_id == agent_id]
