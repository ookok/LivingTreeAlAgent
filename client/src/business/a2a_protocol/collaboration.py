"""
A2A Agent 协作模块
Multi-Agent Collaboration via A2A Protocol

功能：
- Agent 团队管理
- 协作任务编排
- 消息广播与收集
"""

import json
import time
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from core.logger import get_logger

logger = get_logger('a2a_collab')


class TeamRole(str, Enum):
    """团队角色"""
    LEADER = "leader"           # 领导者
    COORDINATOR = "coordinator"  # 协调者
    SPECIALIST = "specialist"   # 专家
    WORKER = "worker"          # 工作者


@dataclass
class TeamMember:
    """团队成员"""
    agent_id: str
    agent_name: str
    role: TeamRole
    capabilities: List[str]
    is_active: bool = True
    current_task: Optional[str] = None
    performance_score: float = 1.0


@dataclass
class CollaborationTask:
    """协作任务"""
    task_id: str
    description: str
    subtasks: List[str]  # 子任务 ID 列表
    assignee: str  # 分配给谁
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    created_at: int = field(default_factory=lambda: int(time.time() * 1000))
    completed_at: Optional[int] = None


class AgentTeam:
    """
    Agent 团队管理器
    管理多 Agent 协作工作流
    """
    
    def __init__(self, team_id: str, team_name: str, task_manager: 'A2ATaskManager'):
        """
        Args:
            team_id: 团队 ID
            team_name: 团队名称
            task_manager: A2A 任务管理器
        """
        self._team_id = team_id
        self._team_name = team_name
        self._task_manager = task_manager
        
        # 团队成员
        self._members: Dict[str, TeamMember] = {}
        
        # 协作任务
        self._tasks: Dict[str, CollaborationTask] = {}
        
        # 任务依赖图
        self._dependencies: Dict[str, List[str]] = defaultdict(list)  # task_id -> depends_on
        
        # 消息队列
        self._messages: Dict[str, List[Dict]] = defaultdict(list)
        
        # 回调
        self._on_task_complete: Optional[Callable] = None
        self._on_member_update: Optional[Callable] = None
        
        # 锁
        self._lock = threading.RLock()
        
        logger.info(f"Agent team created: {team_id} ({team_name})")
    
    # ========== 成员管理 ==========
    
    def add_member(
        self,
        agent_id: str,
        agent_name: str,
        role: TeamRole = TeamRole.WORKER,
        capabilities: Optional[List[str]] = None
    ) -> bool:
        """添加团队成员"""
        with self._lock:
            if agent_id in self._members:
                logger.warning(f"Member already exists: {agent_id}")
                return False
            
            member = TeamMember(
                agent_id=agent_id,
                agent_name=agent_name,
                role=role,
                capabilities=capabilities or [],
            )
            
            self._members[agent_id] = member
            
            # 注册到任务管理器
            self._task_manager.register_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_type=self._role_to_agent_type(role),
                capabilities=capabilities or [],
                handler=self._create_member_handler(agent_id),
            )
            
            logger.info(f"Member added: {agent_id} as {role.value}")
            return True
    
    def remove_member(self, agent_id: str) -> bool:
        """移除团队成员"""
        with self._lock:
            if agent_id in self._members:
                del self._members[agent_id]
                self._task_manager.unregister_agent(agent_id)
                logger.info(f"Member removed: {agent_id}")
                return True
            return False
    
    def get_member(self, agent_id: str) -> Optional[TeamMember]:
        """获取成员"""
        with self._lock:
            return self._members.get(agent_id)
    
    def list_members(self, role: Optional[TeamRole] = None, active_only: bool = True) -> List[TeamMember]:
        """列出成员"""
        with self._lock:
            members = self._members.values()
            if role:
                members = [m for m in members if m.role == role]
            if active_only:
                members = [m for m in members if m.is_active]
            return list(members)
    
    def _role_to_agent_type(self, role: TeamRole) -> 'AgentType':
        """角色转换为 Agent 类型"""
        from .task_integration import AgentType
        
        mapping = {
            TeamRole.LEADER: AgentType.ORCHESTRATOR,
            TeamRole.COORDINATOR: AgentType.ORCHESTRATOR,
            TeamRole.SPECIALIST: AgentType.CODER,
            TeamRole.WORKER: AgentType.GENERAL,
        }
        return mapping.get(role, AgentType.GENERAL)
    
    def _create_member_handler(self, agent_id: str) -> Callable:
        """创建成员任务处理器"""
        async def handler(task):
            # 更新成员状态
            self.update_member_status(agent_id, current_task=task.task_id)
            
            # 处理任务
            result = await self._process_member_task(agent_id, task)
            
            # 清理状态
            self.update_member_status(agent_id, current_task=None)
            
            return result
        
        return handler
    
    async def _process_member_task(self, agent_id: str, task) -> Dict[str, Any]:
        """处理成员任务"""
        logger.info(f"Member {agent_id} processing task: {task.task_id}")
        
        # 实际处理逻辑由子模块实现
        return {
            "agent_id": agent_id,
            "task_id": task.task_id,
            "status": "completed",
            "output": {}
        }
    
    def update_member_status(self, agent_id: str, **kwargs):
        """更新成员状态"""
        with self._lock:
            if agent_id in self._members:
                member = self._members[agent_id]
                for key, value in kwargs.items():
                    if hasattr(member, key):
                        setattr(member, key, value)
                
                if self._on_member_update:
                    self._on_member_update(agent_id, kwargs)
    
    # ========== 协作任务 ==========
    
    def create_task(
        self,
        task_id: str,
        description: str,
        assignee: str,
        depends_on: Optional[List[str]] = None
    ) -> CollaborationTask:
        """创建协作任务"""
        with self._lock:
            task = CollaborationTask(
                task_id=task_id,
                description=description,
                subtasks=[],
                assignee=assignee,
            )
            
            self._tasks[task_id] = task
            
            # 设置依赖
            if depends_on:
                self._dependencies[task_id] = depends_on
            
            logger.info(f"Task created: {task_id} -> {assignee}")
            return task
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """分配任务"""
        with self._lock:
            if task_id not in self._tasks:
                logger.warning(f"Task not found: {task_id}")
                return False
            
            if agent_id not in self._members:
                logger.warning(f"Agent not found: {agent_id}")
                return False
            
            self._tasks[task_id].assignee = agent_id
            self._members[agent_id].current_task = task_id
            
            logger.info(f"Task assigned: {task_id} -> {agent_id}")
            return True
    
    def complete_task(self, task_id: str, result: Dict[str, Any]) -> List[str]:
        """
        完成任务
        
        Returns:
            等待此任务完成的依赖任务 ID 列表
        """
        with self._lock:
            if task_id not in self._tasks:
                return []
            
            task = self._tasks[task_id]
            task.status = "completed"
            task.result = result
            task.completed_at = int(time.time() * 1000)
            
            # 释放成员
            member = self._members.get(task.assignee)
            if member:
                member.current_task = None
            
            # 查找依赖此任务的任务
            ready_tasks = [
                tid for tid, deps in self._dependencies.items()
                if task_id in deps and self._are_dependencies_met(tid)
            ]
            
            if self._on_task_complete:
                self._on_task_complete(task_id, result)
            
            logger.info(f"Task completed: {task_id}")
            return ready_tasks
    
    def _are_dependencies_met(self, task_id: str) -> bool:
        """检查任务依赖是否满足"""
        deps = self._dependencies.get(task_id, [])
        return all(
            self._tasks.get(dep_id, CollaborationTask("", "", [], "")).status == "completed"
            for dep_id in deps
        )
    
    def get_ready_tasks(self) -> List[CollaborationTask]:
        """获取就绪的任务"""
        with self._lock:
            return [
                task for task in self._tasks.values()
                if task.status == "pending" and self._are_dependencies_met(task.task_id)
            ]
    
    # ========== 消息传递 ==========
    
    def send_message(self, from_id: str, to_id: str, message: Dict[str, Any]) -> bool:
        """发送消息"""
        with self._lock:
            if from_id not in self._members or to_id not in self._members:
                return False
            
            msg = {
                "from": from_id,
                "to": to_id,
                "content": message,
                "timestamp": int(time.time() * 1000),
            }
            
            self._messages[to_id].append(msg)
            
            logger.debug(f"Message: {from_id} -> {to_id}")
            return True
    
    def broadcast(self, from_id: str, message: Dict[str, Any]) -> int:
        """广播消息"""
        count = 0
        with self._lock:
            for agent_id in self._members:
                if agent_id != from_id:
                    if self.send_message(from_id, agent_id, message):
                        count += 1
        return count
    
    def get_messages(self, agent_id: str, clear: bool = False) -> List[Dict]:
        """获取消息"""
        with self._lock:
            messages = self._messages.get(agent_id, [])
            if clear:
                self._messages[agent_id] = []
            return messages
    
    # ========== 协作工作流 ==========
    
    async def execute_workflow(self, workflow: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        执行协作工作流
        
        workflow 格式:
        [
            {"task": "plan", "assign_to": "planner", "depends_on": []},
            {"task": "implement", "assign_to": "coder", "depends_on": ["plan"]},
            {"task": "review", "assign_to": "reviewer", "depends_on": ["implement"]},
        ]
        """
        results = {}
        
        for step in workflow:
            task_id = step["task"]
            assignee = step["assign_to"]
            depends_on = step.get("depends_on", [])
            
            # 等待依赖完成
            for dep_id in depends_on:
                if dep_id not in results:
                    logger.warning(f"Dependency not met: {dep_id}")
            
            # 创建任务
            task = self.create_task(
                task_id=task_id,
                description=step.get("description", task_id),
                assignee=assignee,
                depends_on=depends_on,
            )
            
            # 分发任务
            await self._dispatch_collaboration_task(task)
            
            # 等待完成（简化版，实际应使用异步队列）
            while task.status != "completed":
                await asyncio.sleep(0.1)
            
            results[task_id] = task.result
        
        return results
    
    async def _dispatch_collaboration_task(self, task: CollaborationTask):
        """分发协作任务到 A2A 网络"""
        from client.src.business.a2a_protocol import Task
        
        a2a_task = Task(
            task_id=task.task_id,
            task_type=task.description[:50],
            description=task.description,
            input_data={"team_id": self._team_id},
        )
        
        await self._task_manager.dispatch_task(
            node=None,
            task_context=None,
            preferred_agents=[task.assignee],
        )
    
    # ========== 统计 ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """获取团队统计"""
        with self._lock:
            return {
                "team_id": self._team_id,
                "team_name": self._team_name,
                "member_count": len(self._members),
                "active_members": sum(1 for m in self._members.values() if m.is_active),
                "busy_members": sum(1 for m in self._members.values() if m.current_task),
                "task_count": len(self._tasks),
                "completed_tasks": sum(1 for t in self._tasks.values() if t.status == "completed"),
                "pending_tasks": sum(1 for t in self._tasks.values() if t.status == "pending"),
                "by_role": {
                    role.value: len([m for m in self._members.values() if m.role == role])
                    for role in TeamRole
                }
            }


# ========== 便捷工厂函数 ==========

def create_agent_team(
    team_id: str,
    team_name: str,
    task_manager: 'A2ATaskManager'
) -> AgentTeam:
    """创建 Agent 团队"""
    return AgentTeam(team_id, team_name, task_manager)
