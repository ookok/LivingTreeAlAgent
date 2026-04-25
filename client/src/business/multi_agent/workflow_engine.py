#!/usr/bin/env python3
"""
LivingTreeAI Phase 2 - Multi-Agent 协作工作流引擎
核心模块：多智能体协作、动态任务分解、代理生命周期管理
"""

import sys
import os
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
import asyncio
import uuid

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRole(Enum):
    """代理角色"""
    COORDINATOR = "coordinator"    # 协调者
    EXECUTOR = "executor"         # 执行者
    REVIEWER = "reviewer"         # 审核者
    PLANNER = "planner"           # 规划者
    MONITOR = "monitor"           # 监控者


@dataclass
class Task:
    """任务定义"""
    id: str
    description: str
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    priority: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=datetime.now().timestamp)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def duration(self) -> Optional[float]:
        """计算任务耗时"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class Agent:
    """代理定义"""
    id: str
    name: str
    role: AgentRole
    capabilities: List[str] = field(default_factory=list)
    status: str = "idle"  # idle, busy, offline
    current_task: Optional[str] = None
    tasks_completed: int = 0
    created_at: float = field(default_factory=datetime.now().timestamp)


@dataclass
class WorkflowStep:
    """工作流步骤"""
    step_id: str
    agent_id: str
    task: Task
    action: str
    condition: Optional[Callable] = None
    retry_count: int = 0
    max_retries: int = 3


class MultiAgentWorkflow:
    """
    多代理协作工作流引擎
    支持复杂的多智能体任务协作
    """
    
    def __init__(self, workflow_id: str, name: str):
        self.workflow_id = workflow_id
        self.name = name
        self.tasks: Dict[str, Task] = {}
        self.agents: Dict[str, Agent] = {}
        self.steps: List[WorkflowStep] = []
        self.status = "initialized"
        self.created_at = datetime.now().timestamp
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        
        logger.info(f"创建工作流: {workflow_id} - {name}")
    
    # ==================== 代理管理 ====================
    
    def register_agent(self, agent_id: str, name: str, role: AgentRole,
                      capabilities: List[str]) -> bool:
        """注册代理"""
        if agent_id in self.agents:
            logger.warning(f"代理 {agent_id} 已存在")
            return False
        
        agent = Agent(
            id=agent_id,
            name=name,
            role=role,
            capabilities=capabilities
        )
        self.agents[agent_id] = agent
        logger.info(f"注册代理: {name} ({role.value})")
        return True
    
    def get_available_agent(self, required_capabilities: List[str]) -> Optional[Agent]:
        """获取可用代理"""
        for agent in self.agents.values():
            if agent.status == "idle":
                if all(cap in agent.capabilities for cap in required_capabilities):
                    return agent
        return None
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """分配任务给代理"""
        if task_id not in self.tasks:
            logger.error(f"任务 {task_id} 不存在")
            return False
        
        if agent_id not in self.agents:
            logger.error(f"代理 {agent_id} 不存在")
            return False
        
        task = self.tasks[task_id]
        agent = self.agents[agent_id]
        
        task.assigned_agent = agent_id
        task.status = TaskStatus.PENDING
        agent.current_task = task_id
        agent.status = "busy"
        
        logger.info(f"任务 {task_id} 分配给代理 {agent_id}")
        return True
    
    # ==================== 任务管理 ====================
    
    def create_task(self, description: str, dependencies: List[str] = None,
                    priority: int = 0) -> Task:
        """创建任务"""
        task_id = str(uuid.uuid4())[:8]
        task = Task(
            id=task_id,
            description=description,
            dependencies=dependencies or [],
            priority=priority
        )
        self.tasks[task_id] = task
        logger.info(f"创建任务: {task_id} - {description}")
        return task
    
    def add_step(self, agent_id: str, task: Task, action: str,
                condition: Callable = None) -> WorkflowStep:
        """添加工作流步骤"""
        step = WorkflowStep(
            step_id=f"{self.workflow_id}_step_{len(self.steps)}",
            agent_id=agent_id,
            task=task,
            action=action,
            condition=condition
        )
        self.steps.append(step)
        return step
    
    def can_start_task(self, task_id: str) -> bool:
        """检查任务是否可以开始"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status != TaskStatus.PENDING:
            return False
        
        # 检查依赖是否完成
        for dep_id in task.dependencies:
            if dep_id not in self.tasks:
                continue
            dep_task = self.tasks[dep_id]
            if dep_task.status != TaskStatus.COMPLETED:
                return False
        
        return True
    
    def start_task(self, task_id: str) -> bool:
        """启动任务"""
        if not self.can_start_task(task_id):
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now().timestamp
        
        if task.assigned_agent:
            self.agents[task.assigned_agent].status = "busy"
        
        logger.info(f"启动任务: {task_id}")
        return True
    
    def complete_task(self, task_id: str, result: Any) -> bool:
        """完成任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = datetime.now().timestamp
        
        if task.assigned_agent:
            agent = self.agents[task.assigned_agent]
            agent.status = "idle"
            agent.current_task = None
            agent.tasks_completed += 1
        
        logger.info(f"完成任务: {task_id}, 耗时: {task.duration():.2f}s")
        return True
    
    def fail_task(self, task_id: str, error: str) -> bool:
        """任务失败"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.FAILED
        task.error = error
        task.completed_at = datetime.now().timestamp
        
        if task.assigned_agent:
            self.agents[task.assigned_agent].status = "idle"
        
        logger.error(f"任务失败: {task_id} - {error}")
        return True
    
    # ==================== 工作流执行 ====================
    
    async def execute_async(self) -> Dict[str, Any]:
        """异步执行工作流"""
        self.status = "running"
        self.started_at = datetime.now().timestamp
        
        logger.info(f"开始执行工作流: {self.workflow_id}")
        
        # 执行所有可执行的任务
        progress = True
        while progress:
            progress = False
            
            for task in self.tasks.values():
                if self.can_start_task(task.id):
                    self.start_task(task.id)
                    progress = True
        
        # 等待所有任务完成
        all_done = False
        while not all_done:
            all_done = all(
                t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                for t in self.tasks.values()
            )
            await asyncio.sleep(0.1)
        
        self.status = "completed"
        self.completed_at = datetime.now().timestamp
        
        return self.get_results()
    
    def execute_sync(self) -> Dict[str, Any]:
        """同步执行工作流"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.execute_async())
        finally:
            loop.close()
    
    def get_results(self) -> Dict[str, Any]:
        """获取工作流结果"""
        completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)
        
        return {
            'workflow_id': self.workflow_id,
            'name': self.name,
            'status': self.status,
            'total_tasks': len(self.tasks),
            'completed': completed,
            'failed': failed,
            'duration': self.duration(),
            'tasks': [
                {
                    'id': t.id,
                    'description': t.description,
                    'status': t.status.value,
                    'result': t.result,
                    'error': t.error,
                    'duration': t.duration()
                }
                for t in self.tasks.values()
            ]
        }
    
    def duration(self) -> Optional[float]:
        """计算工作流耗时"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


class DynamicTaskDecomposer:
    """
    动态任务分解器
    将复杂任务自动分解为可执行的子任务
    """
    
    def __init__(self):
        self.decomposition_patterns = {
            'parallel': self._decompose_parallel,
            'sequential': self._decompose_sequential,
            'hierarchical': self._decompose_hierarchical,
            'dag': self._decompose_dag,
        }
    
    def decompose(self, task_description: str, mode: str = 'auto') -> List[Task]:
        """分解任务"""
        # 智能选择分解模式
        if mode == 'auto':
            mode = self._detect_decomposition_mode(task_description)
        
        decomposer = self.decomposition_patterns.get(mode, self._decompose_parallel)
        return decomposer(task_description)
    
    def _detect_decomposition_mode(self, description: str) -> str:
        """检测分解模式"""
        description_lower = description.lower()
        
        if any(word in description_lower for word in ['并行', '同时', 'parallel', 'concurrent']):
            return 'parallel'
        elif any(word in description_lower for word in ['顺序', '依次', 'sequential']):
            return 'sequential'
        elif any(word in description_lower for word in ['分层', 'hierarchical']):
            return 'hierarchical'
        else:
            return 'dag'
    
    def _decompose_parallel(self, description: str) -> List[Task]:
        """并行分解"""
        subtasks = []
        keywords = ['和', '与', '及', 'and', ',', '、']
        
        parts = [description]
        for sep in keywords:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(sep))
            if len(new_parts) > 1:
                parts = new_parts
                break
        
        for i, part in enumerate(parts):
            subtask = Task(
                id=f"subtask_{i}",
                description=part.strip(),
                priority=0
            )
            subtasks.append(subtask)
        
        return subtasks
    
    def _decompose_sequential(self, description: str) -> List[Task]:
        """顺序分解"""
        subtasks = []
        keywords = ['首先', '然后', '接着', '最后', 'first', 'then', 'next', 'finally']
        
        parts = [description]
        for keyword in keywords:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(keyword))
            if len(new_parts) > 1:
                parts = [p.strip() for p in new_parts if p.strip()]
                break
        
        for i, part in enumerate(parts):
            subtask = Task(
                id=f"subtask_{i}",
                description=part.strip(),
                dependencies=[f"subtask_{i-1}"] if i > 0 else [],
                priority=i
            )
            subtasks.append(subtask)
        
        return subtasks
    
    def _decompose_hierarchical(self, description: str) -> List[Task]:
        """分层分解"""
        main_task = Task(
            id="main",
            description=description,
            priority=0
        )
        
        sub_tasks = self._decompose_parallel(description)
        main_task.dependencies = [t.id for t in sub_tasks]
        
        return [main_task] + sub_tasks
    
    def _decompose_dag(self, description: str) -> List[Task]:
        """DAG分解（依赖图）"""
        subtasks = self._decompose_parallel(description)
        
        for i, task in enumerate(subtasks):
            if i > 0:
                task.dependencies = [subtasks[i-1].id]
        
        return subtasks


class AgentLifecycleManager:
    """
    代理生命周期管理器
    管理代理的创建、激活、休眠、销毁
    """
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.agent_pools: Dict[str, List[Agent]] = {}
        self.agent_creation_factory: Dict[str, Callable] = {}
        self.lifecycle_hooks: Dict[str, List[Callable]] = {
            'on_create': [],
            'on_start': [],
            'on_stop': [],
            'on_destroy': [],
        }
        
        logger.info("AgentLifecycleManager 初始化完成")
    
    def register_factory(self, agent_type: str, factory: Callable) -> bool:
        """注册代理工厂"""
        self.agent_creation_factory[agent_type] = factory
        logger.info(f"注册代理工厂: {agent_type}")
        return True
    
    def create_agent(self, agent_type: str, name: str, **kwargs) -> Optional[Agent]:
        """创建代理"""
        if agent_type not in self.agent_creation_factory:
            logger.error(f"未知的代理类型: {agent_type}")
            return None
        
        factory = self.agent_creation_factory[agent_type]
        agent = factory(name=name, **kwargs)
        
        self.agents[agent.id] = agent
        self._trigger_hook('on_create', agent)
        
        logger.info(f"创建代理: {name} ({agent_type})")
        return agent
    
    def start_agent(self, agent_id: str) -> bool:
        """启动代理"""
        if agent_id not in self.agents:
            return False
        
        agent = self.agents[agent_id]
        if agent.status == "idle":
            agent.status = "busy"
            self._trigger_hook('on_start', agent)
            logger.info(f"启动代理: {agent.name}")
            return True
        return False
    
    def stop_agent(self, agent_id: str) -> bool:
        """停止代理"""
        if agent_id not in self.agents:
            return False
        
        agent = self.agents[agent_id]
        agent.status = "idle"
        agent.current_task = None
        self._trigger_hook('on_stop', agent)
        logger.info(f"停止代理: {agent.name}")
        return True
    
    def destroy_agent(self, agent_id: str) -> bool:
        """销毁代理"""
        if agent_id not in self.agents:
            return False
        
        agent = self.agents[agent_id]
        self._trigger_hook('on_destroy', agent)
        del self.agents[agent_id]
        logger.info(f"销毁代理: {agent.name}")
        return True
    
    def get_agent_pool(self, pool_name: str) -> List[Agent]:
        """获取代理池"""
        return self.agent_pools.get(pool_name, [])
    
    def add_to_pool(self, pool_name: str, agent: Agent) -> bool:
        """添加到代理池"""
        if pool_name not in self.agent_pools:
            self.agent_pools[pool_name] = []
        
        if agent not in self.agent_pools[pool_name]:
            self.agent_pools[pool_name].append(agent)
            logger.info(f"添加代理 {agent.name} 到池 {pool_name}")
            return True
        return False
    
    def get_from_pool(self, pool_name: str) -> Optional[Agent]:
        """从代理池获取空闲代理"""
        if pool_name not in self.agent_pools:
            return None
        
        for agent in self.agent_pools[pool_name]:
            if agent.status == "idle":
                return agent
        return None
    
    def register_hook(self, event: str, hook: Callable) -> bool:
        """注册生命周期钩子"""
        if event not in self.lifecycle_hooks:
            self.lifecycle_hooks[event] = []
        
        self.lifecycle_hooks[event].append(hook)
        logger.info(f"注册生命周期钩子: {event}")
        return True
    
    def _trigger_hook(self, event: str, agent: Agent) -> None:
        """触发生命周期钩子"""
        for hook in self.lifecycle_hooks.get(event, []):
            try:
                hook(agent)
            except Exception as e:
                logger.error(f"生命周期钩子执行失败: {event} - {e}")


# ==================== 全局实例 ====================

_multi_agent_workflow: Optional[MultiAgentWorkflow] = None
_task_decomposer: Optional[DynamicTaskDecomposer] = None
_lifecycle_manager: Optional[AgentLifecycleManager] = None


def get_multi_agent_workflow(workflow_id: str, name: str) -> MultiAgentWorkflow:
    """获取多代理工作流"""
    global _multi_agent_workflow
    _multi_agent_workflow = MultiAgentWorkflow(workflow_id, name)
    return _multi_agent_workflow


def get_task_decomposer() -> DynamicTaskDecomposer:
    """获取任务分解器"""
    global _task_decomposer
    if _task_decomposer is None:
        _task_decomposer = DynamicTaskDecomposer()
    return _task_decomposer


def get_lifecycle_manager() -> AgentLifecycleManager:
    """获取生命周期管理器"""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = AgentLifecycleManager()
    return _lifecycle_manager


def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-Agent 协作工作流引擎')
    parser.add_argument('--workflow', '-w', help='工作流名称')
    parser.add_argument('--mode', '-m', choices=['parallel', 'sequential', 'hierarchical', 'dag'],
                       default='dag', help='分解模式')
    parser.add_argument('--task', '-t', help='任务描述')
    
    args = parser.parse_args()
    
    if args.task:
        decomposer = get_task_decomposer()
        tasks = decomposer.decompose(args.task, mode=args.mode)
        print(f"分解模式: {args.mode}")
        print(f"子任务数: {len(tasks)}")
        for i, task in enumerate(tasks):
            print(f"  {i+1}. {task.description}")
            if task.dependencies:
                print(f"     依赖: {task.dependencies}")
    
    if args.workflow:
        workflow = get_multi_agent_workflow(str(uuid.uuid4())[:8], args.workflow)
        print(f"创建工作流: {workflow.name}")


if __name__ == "__main__":
    main()
