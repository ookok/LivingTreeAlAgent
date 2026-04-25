"""
智能代理编排引擎
Agent Orchestration Engine

负责任务分解、多智能体协作调度、结果聚合

架构：
┌─────────────────────────────────────────────────────────┐
│              🤖 智能代理编排引擎 (AgentOrchestrator)      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐   │
│  │            📋 任务管理器 (TaskManager)            │   │
│  │  - 任务队列  - 优先级调度  - 依赖管理  - 状态跟踪   │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │         🔧 智能体工厂 (AgentFactory)              │   │
│  │  - AgentType  - Capability  - Config           │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │         📡 协作调度器 (CollaborationScheduler)   │   │
│  │  - 任务分配  - 通信路由  - 结果聚合  - 冲突解决   │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │         🔄 工作流引擎 (WorkflowEngine)           │   │
│  │  - DAG执行  - 并行/串行  - 回滚机制  - 超时控制   │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

Author: LivingTreeAI Team
"""

import asyncio
import uuid
import time
import json
import logging
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from collections import defaultdict
import heapq

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """智能体类型"""
    CODER = "coder"                       # 代码生成
    REVIEWER = "reviewer"                 # 代码审查
    TESTER = "tester"                     # 测试
    PLANNER = "planner"                   # 任务规划
    RESEARCHER = "researcher"             # 研究
    DEPLOYER = "deployer"                 # 部署
    ORCHESTRATOR = "orchestrator"         # 编排器
    ANALYZER = "analyzer"                 # 分析


class AgentCapability(Enum):
    """智能体能力"""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    UNIT_TESTING = "unit_testing"
    INTEGRATION_TESTING = "integration_testing"
    CODE_DEBUGGING = "code_debugging"
    REFACTORING = "refactoring"
    TASK_PLANNING = "task_planning"
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    DATA_ANALYSIS = "data_analysis"
    DOCUMENTATION = "documentation"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"                   # 等待中
    READY = "ready"                      # 就绪
    RUNNING = "running"                   # 运行中
    WAITING = "waiting"                   # 等待依赖
    COMPLETED = "completed"              # 已完成
    FAILED = "failed"                    # 失败
    CANCELLED = "cancelled"               # 已取消


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 5
    HIGH = 7
    CRITICAL = 9


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str
    description: str
    params: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: int = 300  # 秒
    retries: int = 3
    tags: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    
    # 执行信息
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: float = 0.0
    
    # 时间戳
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # 依赖
    dependencies: Set[str] = field(default_factory=set)  # task_ids
    dependents: Set[str] = field(default_factory=set)   # task_ids
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "params": self.params,
            "priority": self.priority.value,
            "timeout": self.timeout,
            "retries": self.retries,
            "tags": self.tags,
            "parent_id": self.parent_id,
            "assigned_agent": self.assigned_agent,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "progress": self.progress,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "dependencies": list(self.dependencies),
            "dependents": list(self.dependents),
            "metadata": self.metadata
        }


@dataclass
class Agent:
    """智能体"""
    agent_id: str
    name: str
    agent_type: AgentType
    capabilities: List[AgentCapability]
    status: str = "idle"  # idle, busy, offline
    max_concurrent_tasks: int = 1
    
    # 性能指标
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_execution_time: float = 0.0
    
    # 负载
    current_load: int = 0
    config: Dict[str, Any] = field(default_factory=dict)

    def can_handle(self, capability: AgentCapability) -> bool:
        """检查是否能处理特定能力"""
        return capability in self.capabilities
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self.status == "idle" and self.current_load < self.max_concurrent_tasks
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "agent_type": self.agent_type.value,
            "capabilities": [c.value for c in self.capabilities],
            "status": self.status,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "avg_execution_time": self.avg_execution_time,
            "current_load": self.current_load
        }


class TaskQueue:
    """任务队列"""
    
    def __init__(self):
        self._heap: List[Tuple[int, TaskContext]] = []  # (priority, task)
        self._task_map: Dict[str, TaskContext] = {}
        self._counter = 0  # 用于相同优先级的FIFO
    
    def enqueue(self, task: TaskContext) -> str:
        """入队"""
        # 优先级取负数，Python heapq 是最小堆
        entry = (-task.priority.value, self._counter, task)
        heapq.heappush(self._heap, entry)
        self._task_map[task.task_id] = task
        self._counter += 1
        logger.debug(f"Task enqueued: {task.task_id} (priority: {task.priority.value})")
        return task.task_id
    
    def dequeue(self) -> Optional[TaskContext]:
        """出队"""
        if not self._heap:
            return None
        _, _, task = heapq.heappop(self._heap)
        del self._task_map[task.task_id]
        return task
    
    def peek(self) -> Optional[TaskContext]:
        """查看队首"""
        if not self._heap:
            return None
        _, _, task = self._heap[0]
        return task
    
    def get(self, task_id: str) -> Optional[TaskContext]:
        """获取任务"""
        return self._task_map.get(task_id)
    
    def remove(self, task_id: str) -> bool:
        """移除任务（仅从未执行的任务中）"""
        if task_id not in self._task_map:
            return False
        task = self._task_map[task_id]
        if task.status != TaskStatus.PENDING:
            return False
        del self._task_map[task_id]
        # 注意：heap 中的任务不会真正删除，只能标记
        task.status = TaskStatus.CANCELLED
        return True
    
    def size(self) -> int:
        """队列大小"""
        return len(self._task_map)
    
    def is_empty(self) -> bool:
        """是否为空"""
        return len(self._heap) == 0
    
    def get_ready_tasks(self) -> List[TaskContext]:
        """获取所有就绪的任务"""
        return [
            t for t in self._task_map.values()
            if t.status == TaskStatus.READY
        ]


class WorkflowDefinition:
    """工作流定义"""
    
    def __init__(self, name: str, workflow_id: str = None):
        self.workflow_id = workflow_id or str(uuid.uuid4())
        self.name = name
        self.tasks: Dict[str, TaskContext] = {}
        self.edges: List[Tuple[str, str]] = []  # (from_id, to_id)
        self.metadata: Dict[str, Any] = {}
    
    def add_task(self, description: str, task_id: str = None,
                priority: TaskPriority = TaskPriority.NORMAL,
                timeout: int = 300, **kwargs) -> str:
        """添加任务"""
        task_id = task_id or str(uuid.uuid4())
        task = TaskContext(
            task_id=task_id,
            description=description,
            priority=priority,
            timeout=timeout,
            **kwargs
        )
        self.tasks[task_id] = task
        return task_id
    
    def add_dependency(self, from_task_id: str, to_task_id: str):
        """添加依赖关系"""
        if from_task_id not in self.tasks:
            raise ValueError(f"Task {from_task_id} not found")
        if to_task_id not in self.tasks:
            raise ValueError(f"Task {to_task_id} not found")
        
        self.edges.append((from_task_id, to_task_id))
        self.tasks[to_task_id].dependencies.add(from_task_id)
        self.tasks[from_task_id].dependents.add(to_task_id)
    
    def build_dag(self) -> Dict[str, List[str]]:
        """构建 DAG（邻接表）"""
        dag = defaultdict(list)
        for from_id, to_id in self.edges:
            dag[from_id].append(to_id)
        return dict(dag)
    
    def get_execution_order(self) -> List[List[str]]:
        """获取执行顺序（层级）"""
        in_degree = {tid: 0 for tid in self.tasks}
        for from_id, to_id in self.edges:
            in_degree[to_id] += 1
        
        layers = []
        current = [tid for tid, deg in in_degree.items() if deg == 0]
        
        while current:
            layers.append(current)
            next_layer = []
            for tid in current:
                for neighbor in self.tasks[tid].dependents:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_layer.append(neighbor)
            current = next_layer
        
        return layers


class AgentFactory:
    """智能体工厂"""
    
    _templates: Dict[AgentType, Dict] = {
        AgentType.CODER: {
            "capabilities": [
                AgentCapability.CODE_GENERATION,
                AgentCapability.REFACTORING
            ],
            "max_concurrent": 2
        },
        AgentType.REVIEWER: {
            "capabilities": [
                AgentCapability.CODE_REVIEW,
                AgentCapability.CODE_DEBUGGING
            ],
            "max_concurrent": 3
        },
        AgentType.TESTER: {
            "capabilities": [
                AgentCapability.UNIT_TESTING,
                AgentCapability.INTEGRATION_TESTING
            ],
            "max_concurrent": 2
        },
        AgentType.PLANNER: {
            "capabilities": [
                AgentCapability.TASK_PLANNING,
                AgentCapability.REQUIREMENT_ANALYSIS
            ],
            "max_concurrent": 1
        },
        AgentType.RESEARCHER: {
            "capabilities": [
                AgentCapability.DATA_ANALYSIS,
                AgentCapability.REQUIREMENT_ANALYSIS
            ],
            "max_concurrent": 2
        }
    }
    
    @classmethod
    def create_agent(cls, agent_type: AgentType, name: str = None,
                    config: Dict = None) -> Agent:
        """创建智能体"""
        template = cls._templates.get(agent_type, {})
        
        agent = Agent(
            agent_id=str(uuid.uuid4()),
            name=name or f"{agent_type.value}_{agent_id[:8]}",
            agent_type=agent_type,
            capabilities=template.get("capabilities", []),
            max_concurrent_tasks=template.get("max_concurrent", 1),
            config=config or {}
        )
        
        return agent
    
    @classmethod
    def create_team(cls, team_type: str) -> List[Agent]:
        """创建团队"""
        if team_type == "development":
            return [
                cls.create_agent(AgentType.PLANNER, "Planner"),
                cls.create_agent(AgentType.CODER, "Coder"),
                cls.create_agent(AgentType.REVIEWER, "Reviewer"),
                cls.create_agent(AgentType.TESTER, "Tester")
            ]
        elif team_type == "research":
            return [
                cls.create_agent(AgentType.PLANNER, "Planner"),
                cls.create_agent(AgentType.RESEARCHER, "Researcher"),
                cls.create_agent(AgentType.ANALYZER, "Analyzer")
            ]
        return []


class TaskExecutor(ABC):
    """任务执行器基类"""
    
    @abstractmethod
    async def execute(self, task: TaskContext, agent: Agent) -> Any:
        """执行任务"""
        pass
    
    @abstractmethod
    async def cancel(self, task_id: str) -> bool:
        """取消任务"""
        pass


class MockTaskExecutor(TaskExecutor):
    """模拟任务执行器（用于测试）"""
    
    def __init__(self):
        self._running_tasks: Dict[str, asyncio.Task] = {}
    
    async def execute(self, task: TaskContext, agent: Agent) -> Any:
        """模拟执行"""
        logger.info(f"Executing task {task.task_id} with agent {agent.name}")
        
        # 模拟执行
        await asyncio.sleep(min(task.timeout / 10, 5))  # 最多5秒
        
        # 模拟结果
        result = {
            "task_id": task.task_id,
            "agent_id": agent.agent_id,
            "status": "completed",
            "output": f"Mock result for: {task.description}",
            "execution_time": time.time() - (task.started_at or time.time())
        }
        
        return result
    
    async def cancel(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            del self._running_tasks[task_id]
            return True
        return False


class AgentOrchestrator:
    """
    智能代理编排引擎
    核心调度器，协调多智能体执行任务
    """
    
    def __init__(self, executor: TaskExecutor = None):
        self.executor = executor or MockTaskExecutor()
        self.agents: Dict[str, Agent] = {}
        self.task_queue = TaskQueue()
        self.active_tasks: Dict[str, TaskContext] = {}
        self.completed_tasks: Dict[str, TaskContext] = {}
        self.workflows: Dict[str, WorkflowDefinition] = {}
        
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    # ==================== 智能体管理 ====================
    
    def register_agent(self, agent: Agent) -> str:
        """注册智能体"""
        self.agents[agent.agent_id] = agent
        logger.info(f"Agent registered: {agent.name} ({agent.agent_id})")
        return agent.agent_id
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销智能体"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            if agent.current_load > 0:
                logger.warning(f"Cannot unregister busy agent: {agent_id}")
                return False
            del self.agents[agent_id]
            logger.info(f"Agent unregistered: {agent_id}")
            return True
        return False
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取智能体"""
        return self.agents.get(agent_id)
    
    def find_available_agent(self, capability: AgentCapability) -> Optional[Agent]:
        """查找可用智能体"""
        available = [
            agent for agent in self.agents.values()
            if agent.can_handle(capability) and agent.is_available()
        ]
        
        if not available:
            return None
        
        # 按负载排序，选择负载最低的
        available.sort(key=lambda a: a.current_load)
        return available[0]
    
    def get_all_agents(self) -> List[Agent]:
        """获取所有智能体"""
        return list(self.agents.values())
    
    # ==================== 任务管理 ====================
    
    def submit_task(self, description: str, priority: TaskPriority = TaskPriority.NORMAL,
                   timeout: int = 300, **kwargs) -> str:
        """提交任务"""
        task = TaskContext(
            task_id=str(uuid.uuid4()),
            description=description,
            priority=priority,
            timeout=timeout,
            **kwargs
        )
        self.task_queue.enqueue(task)
        logger.info(f"Task submitted: {task.task_id} - {description}")
        return task.task_id
    
    def submit_workflow(self, workflow: WorkflowDefinition) -> str:
        """提交工作流"""
        self.workflows[workflow.workflow_id] = workflow
        
        # 将所有任务加入队列
        for task in workflow.tasks.values():
            self.task_queue.enqueue(task)
        
        logger.info(f"Workflow submitted: {workflow.workflow_id} ({len(workflow.tasks)} tasks)")
        return workflow.workflow_id
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        async with self._lock:
            task = self.task_queue.get(task_id)
            if task:
                success = self.task_queue.remove(task_id)
                if success:
                    task.status = TaskStatus.CANCELLED
                    logger.info(f"Task cancelled: {task_id}")
                return success
            
            if task_id in self.active_tasks:
                return await self.executor.cancel(task_id)
            
            return False
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        task = self.task_queue.get(task_id)
        if task:
            return task.status
        
        task = self.active_tasks.get(task_id)
        if task:
            return task.status
        
        task = self.completed_tasks.get(task_id)
        if task:
            return task.status
        
        return None
    
    def get_task_result(self, task_id: str) -> Optional[Any]:
        """获取任务结果"""
        task = self.completed_tasks.get(task_id)
        return task.result if task else None
    
    # ==================== 调度执行 ====================
    
    async def start(self):
        """启动编排器"""
        if self._running:
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._schedule_loop())
        logger.info("AgentOrchestrator started")
    
    async def stop(self):
        """停止编排器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("AgentOrchestrator stopped")
    
    async def _schedule_loop(self):
        """调度循环"""
        while self._running:
            try:
                await self._schedule_tasks()
                await asyncio.sleep(0.5)  # 调度间隔
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Schedule error: {e}")
    
    async def _schedule_tasks(self):
        """调度任务"""
        async with self._lock:
            # 更新等待依赖的任务状态
            await self._update_waiting_tasks()
            
            # 调度就绪任务
            while True:
                task = self.task_queue.dequeue()
                if not task:
                    break
                
                if task.status != TaskStatus.PENDING:
                    continue
                
                # 查找合适的智能体
                agent = await self._find_agent_for_task(task)
                if not agent:
                    # 重新入队
                    task.status = TaskStatus.READY
                    self.task_queue.enqueue(task)
                    break
                
                # 分配任务
                await self._assign_task(task, agent)
    
    async def _update_waiting_tasks(self):
        """更新等待依赖的任务"""
        for task in list(self.task_queue.get_ready_tasks()):
            dependencies_met = all(
                self.get_task_status(dep_id) == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )
            
            if dependencies_met and task.status == TaskStatus.WAITING:
                task.status = TaskStatus.READY
    
    async def _find_agent_for_task(self, task: TaskContext) -> Optional[Agent]:
        """为任务查找智能体"""
        # 根据任务标签或类型选择能力
        required_capability = AgentCapability.CODE_GENERATION  # 默认
        
        if "test" in task.description.lower():
            required_capability = AgentCapability.UNIT_TESTING
        elif "review" in task.description.lower():
            required_capability = AgentCapability.CODE_REVIEW
        elif "plan" in task.description.lower():
            required_capability = AgentCapability.TASK_PLANNING
        
        return self.find_available_agent(required_capability)
    
    async def _assign_task(self, task: TaskContext, agent: Agent):
        """分配任务"""
        task.status = TaskStatus.RUNNING
        task.assigned_agent = agent.agent_id
        task.started_at = time.time()
        
        agent.status = "busy"
        agent.current_load += 1
        
        self.active_tasks[task.task_id] = task
        
        # 执行任务
        asyncio.create_task(self._execute_task(task, agent))
        
        logger.info(f"Task assigned: {task.task_id} -> {agent.name}")
    
    async def _execute_task(self, task: TaskContext, agent: Agent):
        """执行任务"""
        try:
            result = await asyncio.wait_for(
                self.executor.execute(task, agent),
                timeout=task.timeout
            )
            
            async with self._lock:
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = time.time()
                task.progress = 1.0
                
                # 更新智能体状态
                agent.current_load -= 1
                agent.completed_tasks += 1
                if agent.current_load == 0:
                    agent.status = "idle"
                
                # 移动到完成列表
                del self.active_tasks[task.task_id]
                self.completed_tasks[task.task_id] = task
                
                logger.info(f"Task completed: {task.task_id} ({task.completed_at - task.started_at:.2f}s)")
        
        except asyncio.TimeoutError:
            async with self._lock:
                task.status = TaskStatus.FAILED
                task.error = "Timeout"
                task.completed_at = time.time()
                
                agent.current_load -= 1
                agent.failed_tasks += 1
                if agent.current_load == 0:
                    agent.status = "idle"
                
                del self.active_tasks[task.task_id]
                self.completed_tasks[task.task_id] = task
                
                logger.error(f"Task failed (timeout): {task.task_id}")
        
        except Exception as e:
            async with self._lock:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = time.time()
                
                agent.current_load -= 1
                agent.failed_tasks += 1
                if agent.current_load == 0:
                    agent.status = "idle"
                
                del self.active_tasks[task.task_id]
                self.completed_tasks[task.task_id] = task
                
                logger.error(f"Task failed: {task.task_id} - {e}")
    
    # ==================== 统计和监控 ====================
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_tasks = (
            self.task_queue.size() +
            len(self.active_tasks) +
            len(self.completed_tasks)
        )
        
        completed = len([
            t for t in self.completed_tasks.values()
            if t.status == TaskStatus.COMPLETED
        ])
        
        failed = len([
            t for t in self.completed_tasks.values()
            if t.status == TaskStatus.FAILED
        ])
        
        return {
            "total_agents": len(self.agents),
            "total_tasks": total_tasks,
            "queue_size": self.task_queue.size(),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": completed,
            "failed_tasks": failed,
            "success_rate": completed / (completed + failed) if (completed + failed) > 0 else 0
        }
    
    def get_agent_stats(self) -> Dict[str, Dict]:
        """获取智能体统计"""
        return {
            agent_id: {
                "name": agent.name,
                "status": agent.status,
                "load": agent.current_load,
                "completed": agent.completed_tasks,
                "failed": agent.failed_tasks,
                "avg_time": agent.avg_execution_time
            }
            for agent_id, agent in self.agents.items()
        }


# 全局编排器实例
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """获取全局编排器"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


def create_development_team() -> AgentOrchestrator:
    """创建开发团队并返回编排器"""
    orchestrator = get_orchestrator()
    team = AgentFactory.create_team("development")
    for agent in team:
        orchestrator.register_agent(agent)
    return orchestrator


__all__ = [
    'AgentType',
    'AgentCapability',
    'TaskStatus',
    'TaskPriority',
    'TaskContext',
    'Agent',
    'TaskQueue',
    'WorkflowDefinition',
    'AgentFactory',
    'TaskExecutor',
    'MockTaskExecutor',
    'AgentOrchestrator',
    'get_orchestrator',
    'create_development_team'
]
