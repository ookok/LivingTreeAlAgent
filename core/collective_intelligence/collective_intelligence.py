"""
Collective Intelligence Core
集体智能核心系统 - 多Agent协作 orchestration
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Set
from datetime import datetime
from enum import Enum

from .agent_profiles import (
    AgentProfile, AgentRole, ExpertiseLevel, Expertise,
    Contribution, CollectiveDecision, CollaborationSession
)
from .knowledge_base import SharedKnowledgeBase, KnowledgeEntry, KnowledgeQuery
from .consensus_engine import ConsensusEngine, ConsensusStrategy, ConsensusResult
from .collective_memory import CollectiveMemory, MemoryEntry


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"             # 待处理
    ASSIGNED = "assigned"           # 已分配
    IN_PROGRESS = "in_progress"    # 进行中
    COMPLETED = "completed"         # 已完成
    FAILED = "failed"               # 失败
    CANCELLED = "cancelled"         # 取消


@dataclass
class Task:
    """协作任务"""
    task_id: str                   # 任务ID
    description: str               # 任务描述
    required_expertise: List[str] = field(default_factory=list)  # 需要的专业领域
    status: TaskStatus = TaskStatus.PENDING
    assigned_agents: List[str] = field(default_factory=list)  # 分配的Agent
    contributions: List[Contribution] = field(default_factory=list)
    result: Optional[Any] = None    # 任务结果
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


@dataclass
class CollaborationResult:
    """协作结果"""
    success: bool                   # 是否成功
    task: Task                      # 相关任务
    contributions: List[Contribution]  # 贡献列表
    final_result: Any               # 最终结果
    consensus_result: Optional[ConsensusResult] = None  # 共识结果
    total_time: float = 0.0         # 总耗时
    agent_participation: Dict[str, int] = field(default_factory=dict)  # agent_id -> contribution_count


class CollectiveIntelligence:
    """集体智能系统
    
    协调多个Agent协作的系统，支持任务分配、知识共享、共识达成
    """
    
    def __init__(
        self,
        knowledge_base: SharedKnowledgeBase = None,
        consensus_engine: ConsensusEngine = None,
        collective_memory: CollectiveMemory = None
    ):
        """初始化集体智能系统
        
        Args:
            knowledge_base: 共享知识库
            consensus_engine: 共识引擎
            collective_memory: 集体记忆
        """
        # 子系统
        self._knowledge_base = knowledge_base or SharedKnowledgeBase()
        self._consensus_engine = consensus_engine or ConsensusEngine()
        self._collective_memory = collective_memory or CollectiveMemory()
        
        # Agent管理
        self._agents: Dict[str, AgentProfile] = {}  # agent_id -> profile
        
        # 协作会话
        self._sessions: Dict[str, CollaborationSession] = {}  # session_id -> session
        
        # 任务管理
        self._tasks: Dict[str, Task] = {}  # task_id -> task
        
        # 执行器
        self._executors: Dict[str, Callable] = {}  # action_name -> executor
        
        # 锁
        self._lock = asyncio.Lock()
    
    # ==================== Agent管理 ====================
    
    def register_agent(self, profile: AgentProfile) -> bool:
        """注册Agent
        
        Args:
            profile: Agent画像
            
        Returns:
            是否成功
        """
        self._agents[profile.agent_id] = profile
        return True
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销Agent"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False
    
    def get_agent(self, agent_id: str) -> Optional[AgentProfile]:
        """获取Agent画像"""
        return self._agents.get(agent_id)
    
    def list_agents(self, role: AgentRole = None) -> List[AgentProfile]:
        """列出Agent
        
        Args:
            role: 可选的角色过滤
            
        Returns:
            Agent列表
        """
        if role:
            return [a for a in self._agents.values() if a.role == role]
        return list(self._agents.values())
    
    def find_best_agent(
        self,
        domain: str,
        role: AgentRole = None
    ) -> Optional[AgentProfile]:
        """找到最佳Agent
        
        Args:
            domain: 需要的专业领域
            role: 可选的角色过滤
            
        Returns:
            最佳匹配的Agent
        """
        candidates = self.list_agents(role) if role else self.list_agents()
        
        if not candidates:
            return None
        
        # 按专家水平排序
        def get_level(agent: AgentProfile) -> int:
            level = agent.get_expertise_level(domain)
            return level.value if hasattr(level, 'value') else 0
        
        candidates.sort(key=get_level, reverse=True)
        return candidates[0] if candidates else None
    
    # ==================== 任务管理 ====================
    
    def create_task(
        self,
        description: str,
        required_expertise: List[str] = None
    ) -> Task:
        """创建协作任务
        
        Args:
            description: 任务描述
            required_expertise: 需要的专业领域
            
        Returns:
            创建的任务
        """
        task = Task(
            task_id=str(uuid.uuid4())[:8],
            description=description,
            required_expertise=required_expertise or []
        )
        self._tasks[task.task_id] = task
        return task
    
    async def assign_task(
        self,
        task_id: str,
        agent_ids: List[str]
    ) -> bool:
        """分配任务
        
        Args:
            task_id: 任务ID
            agent_ids: Agent ID列表
            
        Returns:
            是否成功
        """
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            task.assigned_agents = agent_ids
            task.status = TaskStatus.ASSIGNED
            
            return True
    
    # ==================== 协作执行 ====================
    
    def register_executor(self, action: str, executor: Callable):
        """注册执行器
        
        Args:
            action: 动作名称
            executor: 执行函数 async (params, context) -> result
        """
        self._executors[action] = executor
    
    async def collaborate(
        self,
        task: Task,
        options: List[Any] = None,
        strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY
    ) -> CollaborationResult:
        """执行协作
        
        Args:
            task: 任务
            options: 可选方案列表 (用于共识决策)
            strategy: 共识策略
            
        Returns:
            协作结果
        """
        start_time = time.time()
        
        # 创建会话
        session = CollaborationSession(
            session_id=str(uuid.uuid4())[:8],
            task=task.description,
            participants=task.assigned_agents
        )
        self._sessions[session.session_id] = session
        
        try:
            # 更新任务状态
            task.status = TaskStatus.IN_PROGRESS
            
            # 每个Agent执行任务
            results = []
            for agent_id in task.assigned_agents:
                # 获取Agent能力
                agent = self._agents.get(agent_id)
                
                # 模拟执行 (实际应调用注册的执行器)
                result = await self._execute_agent_task(agent_id, task)
                
                contribution = Contribution(
                    agent_id=agent_id,
                    contribution_type="solution",
                    content=result,
                    quality_score=agent.success_rate if agent else 0.5
                )
                
                task.contributions.append(contribution)
                session.add_contribution(contribution)
                results.append(result)
            
            # 共识决策 (如果有多个选项)
            consensus_result = None
            final_result = None
            
            if options and len(task.assigned_agents) > 1:
                # 加权投票
                weights = {}
                for agent_id in task.assigned_agents:
                    agent = self._agents.get(agent_id)
                    weights[agent_id] = agent.trust_score if agent else 0.5
                
                consensus_result = await self._consensus_engine.reach_consensus(
                    topic=task.description,
                    options=options,
                    voters=weights,
                    strategy=strategy
                )
                
                if consensus_result.success:
                    final_result = options[consensus_result.agreed_option]
                else:
                    final_result = results[0]  # 回退到第一个结果
            else:
                # 无需共识，选择最佳结果
                if results:
                    # 选择成功率最高的Agent的结果
                    best_idx = 0
                    best_score = 0.0
                    for i, agent_id in enumerate(task.assigned_agents):
                        agent = self._agents.get(agent_id)
                        if agent and agent.success_rate > best_score:
                            best_score = agent.success_rate
                            best_idx = i
                    final_result = results[best_idx]
            
            # 更新任务
            task.result = final_result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # 更新Agent统计
            for agent_id in task.assigned_agents:
                agent = self._agents.get(agent_id)
                if agent:
                    agent.total_tasks_completed += 1
                    agent.successful_tasks += 1
            
            # 记录到集体记忆
            await self._collective_memory.store_shared_memory(
                content=f"Task completed: {task.description}",
                event_type="success",
                agents_involved=task.assigned_agents,
                outcome="success"
            )
            
            # 记录到知识库
            await self._knowledge_base.add_knowledge(
                content=f"{task.description}: {final_result}",
                source_agent=task.assigned_agents[0] if task.assigned_agents else "system",
                domain=task.required_expertise[0] if task.required_expertise else "general"
            )
            
            return CollaborationResult(
                success=True,
                task=task,
                contributions=task.contributions,
                final_result=final_result,
                consensus_result=consensus_result,
                total_time=time.time() - start_time,
                agent_participation={
                    agent_id: len([c for c in task.contributions if c.agent_id == agent_id])
                    for agent_id in task.assigned_agents
                }
            )
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            
            # 记录失败
            await self._collective_memory.store_shared_memory(
                content=f"Task failed: {task.description}",
                event_type="failure",
                agents_involved=task.assigned_agents,
                outcome="failure"
            )
            
            return CollaborationResult(
                success=False,
                task=task,
                contributions=task.contributions,
                final_result=None,
                total_time=time.time() - start_time
            )
    
    async def _execute_agent_task(self, agent_id: str, task: Task) -> Any:
        """执行Agent任务
        
        简化版本，实际应调用具体的executor
        """
        agent = self._agents.get(agent_id)
        
        # 模拟执行
        await asyncio.sleep(0.01)
        
        return {
            "agent_id": agent_id,
            "agent_name": agent.name if agent else "Unknown",
            "result": f"Executed: {task.description}"
        }
    
    # ==================== 知识共享 ====================
    
    async def share_knowledge(
        self,
        agent_id: str,
        content: str,
        domain: str,
        tags: List[str] = None
    ) -> KnowledgeEntry:
        """共享知识
        
        Args:
            agent_id: 贡献者Agent ID
            content: 知识内容
            domain: 领域
            tags: 标签
            
        Returns:
            创建的知识条目
        """
        return await self._knowledge_base.add_knowledge(
            content=content,
            source_agent=agent_id,
            domain=domain,
            tags=tags
        )
    
    async def retrieve_knowledge(
        self,
        query: str,
        domain: str = None,
        limit: int = 5
    ) -> List[KnowledgeEntry]:
        """检索知识
        
        Args:
            query: 查询文本
            domain: 领域
            limit: 返回数量
            
        Returns:
            知识条目列表
        """
        kq = KnowledgeQuery(
            query_text=query,
            domain=domain,
            limit=limit
        )
        result = await self._knowledge_base.search(kq)
        return result.entries
    
    # ==================== 集体学习 ====================
    
    async def collective_learn(
        self,
        experience: str,
        agents_involved: List[str],
        outcome: str,
        lessons: List[str] = None
    ) -> MemoryEntry:
        """集体学习
        
        从经验中学习并记录到集体记忆
        
        Args:
            experience: 经验描述
            agents_involved: 涉及的Agent
            outcome: 结果
            lessons: 经验教训
            
        Returns:
            创建的记忆条目
        """
        event_type = "success" if outcome == "success" else "failure"
        
        return await self._collective_memory.store_shared_memory(
            content=experience,
            event_type=event_type,
            agents_involved=agents_involved,
            outcome=outcome,
            lessons=lessons
        )
    
    async def get_collective_wisdom(self, query: str) -> List[str]:
        """获取集体智慧
        
        获取与查询相关的集体洞察
        
        Args:
            query: 查询
            
        Returns:
            洞察列表
        """
        memories = await self._collective_memory.search_memories(query, limit=5)
        return [m.content for m in memories]
    
    # ==================== 统计 ====================
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取系统统计"""
        return {
            "total_agents": len(self._agents),
            "total_tasks": len(self._tasks),
            "completed_tasks": sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED),
            "total_sessions": len(self._sessions),
            "knowledge_entries": len(self._knowledge_base._entries),
            "collective_memories": len(self._collective_memory._shared_memories),
            "discovered_patterns": len(self._collective_memory._patterns),
            "active_agents": sum(1 for a in self._agents.values() if a.status == "idle")
        }
