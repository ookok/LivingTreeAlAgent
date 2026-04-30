"""
企业任务调度器
Enterprise Task Scheduler

管理企业内的任务调度和编排，支持分组任务
from __future__ import annotations
"""


import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from business.enterprise.node_manager import EnterpriseNodeManager, get_enterprise_manager, EnterpriseNode
from business.task_queue import TaskQueue, get_task_queue, QueuedTask, QueuePriority
from .intelligent_router import get_intelligent_router, get_cost_optimizer

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型"""
    STORAGE = "storage"  # 存储任务
    COMPUTING = "computing"  # 计算任务
    NETWORK = "network"  # 网络任务
    MAINTENANCE = "maintenance"  # 维护任务
    CUSTOM = "custom"  # 自定义任务


class TaskState(Enum):
    """任务状态"""
    PENDING = "pending"  # 等待中
    ASSIGNED = "assigned"  # 已分配
    RUNNING = "running"  # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class EnterpriseTask:
    """企业任务"""
    task_id: str
    enterprise_id: str
    title: str
    description: str = ""
    task_type: TaskType = TaskType.CUSTOM
    priority: int = 1  # 1-5，5最高
    state: TaskState = TaskState.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    assigned_node_id: Optional[str] = None
    progress: float = 0.0
    result: Optional[Any] = None
    error: Optional[str] = None
    
    # 分组信息
    group_id: Optional[str] = None  # 任务组ID
    group_order: int = 0  # 组内执行顺序
    depends_on: List[str] = field(default_factory=list)  # 依赖的任务ID
    
    # 资源需求
    required_storage: int = 0  # 所需存储空间（MB）
    required_memory: int = 0  # 所需内存（MB）
    required_cpu: float = 0.0  # 所需CPU核心数
    required_bandwidth: int = 0  # 所需带宽（Mbps）
    
    # 执行配置
    handler: Optional[Callable] = None
    args: tuple = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "enterprise_id": self.enterprise_id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type.value,
            "priority": self.priority,
            "state": self.state.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "assigned_node_id": self.assigned_node_id,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "group_id": self.group_id,
            "group_order": self.group_order,
            "depends_on": self.depends_on,
            "required_storage": self.required_storage,
            "required_memory": self.required_memory,
            "required_cpu": self.required_cpu,
            "required_bandwidth": self.required_bandwidth,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EnterpriseTask:
        """从字典创建"""
        return cls(
            task_id=data.get("task_id"),
            enterprise_id=data.get("enterprise_id"),
            title=data.get("title"),
            description=data.get("description", ""),
            task_type=TaskType(data.get("task_type", "custom")),
            priority=data.get("priority", 1),
            state=TaskState(data.get("state", "pending")),
            created_at=data.get("created_at", time.time()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            assigned_node_id=data.get("assigned_node_id"),
            progress=data.get("progress", 0.0),
            result=data.get("result"),
            error=data.get("error"),
            group_id=data.get("group_id"),
            group_order=data.get("group_order", 0),
            depends_on=data.get("depends_on", []),
            required_storage=data.get("required_storage", 0),
            required_memory=data.get("required_memory", 0),
            required_cpu=data.get("required_cpu", 0.0),
            required_bandwidth=data.get("required_bandwidth", 0),
            metadata=data.get("metadata", {})
        )


@dataclass
class TaskGroup:
    """任务组"""
    group_id: str
    enterprise_id: str
    name: str
    description: str = ""
    created_at: float = field(default_factory=time.time)
    tasks: List[str] = field(default_factory=list)  # 任务ID列表
    state: str = "pending"  # pending, running, completed, failed
    progress: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "group_id": self.group_id,
            "enterprise_id": self.enterprise_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "tasks": self.tasks,
            "state": self.state,
            "progress": self.progress
        }


class EnterpriseTaskScheduler:
    """企业任务调度器"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.node_manager = get_enterprise_manager(enterprise_id)
        self.task_queue = get_task_queue(f"enterprise_{enterprise_id}")
        self.tasks: Dict[str, EnterpriseTask] = {}
        self.task_groups: Dict[str, TaskGroup] = {}
        self._scheduling_task: Optional[asyncio.Task] = None
        self.is_running = False
        self.scheduling_interval = 5  # 调度间隔（秒）

    async def start(self):
        """启动调度器"""
        logger.info(f"Starting Enterprise Task Scheduler for {self.enterprise_id}...")
        self.is_running = True
        self._scheduling_task = asyncio.create_task(self._scheduling_loop())
        logger.info(f"Enterprise Task Scheduler started")

    async def stop(self):
        """停止调度器"""
        logger.info(f"Stopping Enterprise Task Scheduler for {self.enterprise_id}...")
        self.is_running = False
        if self._scheduling_task:
            self._scheduling_task.cancel()
            try:
                await self._scheduling_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Enterprise Task Scheduler stopped")

    async def _scheduling_loop(self):
        """调度循环"""
        while self.is_running:
            try:
                await self._schedule_tasks()
                await self._update_group_status()
                await asyncio.sleep(self.scheduling_interval)
            except Exception as e:
                logger.error(f"Scheduling loop error: {e}")
                await asyncio.sleep(self.scheduling_interval)

    async def _schedule_tasks(self):
        """调度任务"""
        # 获取待分配的任务
        pending_tasks = [task for task in self.tasks.values() 
                       if task.state == TaskState.PENDING]
        
        # 按优先级排序
        pending_tasks.sort(key=lambda x: (-x.priority, x.created_at))
        
        # 获取可用节点
        available_nodes = self.node_manager.get_nodes(status="online")
        
        for task in pending_tasks:
            # 检查任务依赖
            if not self._check_dependencies(task):
                continue
            
            # 选择合适的节点
            node = self._select_node(task, available_nodes)
            if node:
                await self._assign_task(task, node)

    def _check_dependencies(self, task: EnterpriseTask) -> bool:
        """检查任务依赖"""
        if not task.depends_on:
            return True
        
        for dep_task_id in task.depends_on:
            dep_task = self.tasks.get(dep_task_id)
            if not dep_task or dep_task.state != TaskState.COMPLETED:
                return False
        return True

    def _select_node(self, task: EnterpriseTask, nodes: List[EnterpriseNode]) -> Optional[EnterpriseNode]:
        """选择合适的节点"""
        # 过滤出满足资源需求的节点
        suitable_nodes = []
        for node in nodes:
            if (node.capability.storage_available >= task.required_storage and
                node.capability.memory_available >= task.required_memory and
                node.capability.cpu_available >= task.required_cpu and
                node.capability.bandwidth >= task.required_bandwidth):
                suitable_nodes.append(node)
        
        if not suitable_nodes:
            return None
        
        # 使用智能任务路由器选择最佳节点
        router = get_intelligent_router()
        selected_node_id = router.route_task(task, suitable_nodes)
        
        if selected_node_id:
            # 查找对应的节点对象
            for node in suitable_nodes:
                if node.node_id == selected_node_id:
                    return node
        
        #  fallback: 如果智能路由失败，使用原有的排序逻辑
        suitable_nodes.sort(key=lambda x: (
            # 优先选择资源利用率低的节点
            x.storage_used / (x.storage_allocated + x.capability.storage_available) if x.storage_allocated + x.capability.storage_available > 0 else 0,
            # 其次选择同类型任务历史表现好的节点
            -x.capability.uptime
        ))
        
        return suitable_nodes[0]

    async def _assign_task(self, task: EnterpriseTask, node: EnterpriseNode):
        """分配任务给节点"""
        task.state = TaskState.ASSIGNED
        task.assigned_node_id = node.node_id
        
        # 创建任务队列中的任务
        def task_handler():
            try:
                # 执行任务
                if task.handler:
                    result = task.handler(*task.args, **task.kwargs)
                    self._complete_task(task, result)
                else:
                    # 模拟任务执行
                    asyncio.create_task(self._simulate_task_execution(task))
            except Exception as e:
                self._fail_task(task, str(e))
        
        # 添加到任务队列
        self.task_queue.add(
            title=task.title,
            handler=task_handler,
            priority=QueuePriority.HIGH if task.priority >= 4 else 
                     QueuePriority.NORMAL if task.priority >= 2 else 
                     QueuePriority.LOW
        )
        
        logger.info(f"Task {task.task_id} assigned to node {node.node_id}")

    async def _simulate_task_execution(self, task: EnterpriseTask):
        """模拟任务执行"""
        task.state = TaskState.RUNNING
        task.started_at = time.time()
        
        # 模拟执行过程
        for i in range(11):
            progress = i * 10
            task.progress = progress
            await asyncio.sleep(0.5)
        
        # 完成任务
        self._complete_task(task, {"status": "success"})

    def _complete_task(self, task: EnterpriseTask, result: Any):
        """完成任务"""
        task.state = TaskState.COMPLETED
        task.completed_at = time.time()
        task.progress = 100.0
        task.result = result
        
        # 计算任务执行时间
        execution_time = task.completed_at - task.started_at if task.started_at else 0
        
        # 计算性能评分（基于执行时间和任务复杂度）
        performance = self._calculate_performance_score(task, execution_time)
        
        # 更新智能路由器的历史数据
        router = get_intelligent_router()
        if task.assigned_node_id:
            router.update_task_performance(task.assigned_node_id, task, performance)
        
        # 记录成本数据
        optimizer = get_cost_optimizer()
        if task.assigned_node_id:
            # 计算实际成本（基于资源使用和执行时间）
            actual_cost = self._calculate_actual_cost(task, execution_time)
            optimizer.update_cost_history(task.assigned_node_id, task, actual_cost, performance)
        
        logger.info(f"Task {task.task_id} completed in {execution_time:.2f}s")

    def _fail_task(self, task: EnterpriseTask, error: str):
        """任务失败"""
        task.state = TaskState.FAILED
        task.completed_at = time.time()
        task.error = error
        
        # 计算任务执行时间
        execution_time = task.completed_at - task.started_at if task.started_at else 0
        
        # 记录失败的任务数据
        optimizer = get_cost_optimizer()
        if task.assigned_node_id:
            # 失败任务的成本和性能
            actual_cost = self._calculate_actual_cost(task, execution_time)
            optimizer.update_cost_history(task.assigned_node_id, task, actual_cost, 0.0)  # 性能为0
        
        logger.error(f"Task {task.task_id} failed: {error}")
    
    def _calculate_performance_score(self, task: EnterpriseTask, execution_time: float) -> float:
        """计算任务性能评分"""
        # 基于执行时间和任务复杂度计算性能评分
        # 执行时间越短，性能越高
        base_score = 100.0
        
        # 根据任务复杂度设置基准执行时间
        complexity_baseline = {
            1: 600,  # 低复杂度: 10分钟
            2: 300,  # 中等复杂度: 5分钟
            3: 180,  # 高复杂度: 3分钟
            4: 60    # 极高复杂度: 1分钟
        }
        
        baseline = complexity_baseline.get(task.priority, 300)
        
        # 计算性能得分（执行时间越接近基准越好）
        if execution_time > 0:
            # 性能得分 = 基准时间 / 实际时间 * 100
            score = min(100.0, (baseline / max(1, execution_time)) * 100)
        else:
            score = 50.0  # 默认得分
        
        return score
    
    def _calculate_actual_cost(self, task: EnterpriseTask, execution_time: float) -> float:
        """计算实际成本"""
        # 基于资源使用和执行时间计算成本
        cost = 0.0
        
        # CPU成本
        if task.required_cpu > 0:
            cpu_hours = (task.required_cpu * execution_time) / 3600
            cost += cpu_hours * 0.05  # 每CPU小时0.05单位
        
        # 内存成本
        if task.required_memory > 0:
            memory_hours = (task.required_memory * execution_time) / (3600 * 1024)  # 转换为GB小时
            cost += memory_hours * 0.01  # 每GB小时0.01单位
        
        # 存储成本
        if task.required_storage > 0:
            storage_gb = task.required_storage / 1024  # 转换为GB
            cost += storage_gb * 0.001  # 每GB0.001单位
        
        # 带宽成本
        if task.required_bandwidth > 0:
            bandwidth_hours = (task.required_bandwidth * execution_time) / 3600
            cost += bandwidth_hours * 0.01  # 每Mbps小时0.01单位
        
        return cost

    async def _update_group_status(self):
        """更新任务组状态"""
        for group in self.task_groups.values():
            if group.state in ["completed", "failed"]:
                continue
            
            # 获取组内所有任务
            group_tasks = [self.tasks.get(task_id) for task_id in group.tasks if self.tasks.get(task_id)]
            
            if not group_tasks:
                continue
            
            # 计算组进度
            completed_tasks = [t for t in group_tasks if t.state == TaskState.COMPLETED]
            failed_tasks = [t for t in group_tasks if t.state == TaskState.FAILED]
            
            group.progress = (len(completed_tasks) / len(group_tasks)) * 100
            
            # 更新组状态
            if failed_tasks:
                group.state = "failed"
            elif len(completed_tasks) == len(group_tasks):
                group.state = "completed"
            elif any(t.state in [TaskState.RUNNING, TaskState.ASSIGNED] for t in group_tasks):
                group.state = "running"

    def create_task(self, task: EnterpriseTask) -> str:
        """创建任务"""
        self.tasks[task.task_id] = task
        logger.info(f"Task created: {task.task_id} - {task.title}")
        return task.task_id

    def create_task_group(self, group: TaskGroup) -> str:
        """创建任务组"""
        self.task_groups[group.group_id] = group
        logger.info(f"Task group created: {group.group_id} - {group.name}")
        return group.group_id

    def add_task_to_group(self, group_id: str, task_id: str):
        """将任务添加到组"""
        if group_id in self.task_groups and task_id in self.tasks:
            self.task_groups[group_id].tasks.append(task_id)
            self.tasks[task_id].group_id = group_id
            logger.info(f"Task {task_id} added to group {group_id}")

    def get_task(self, task_id: str) -> Optional[EnterpriseTask]:
        """获取任务"""
        return self.tasks.get(task_id)

    def get_tasks(self, state: Optional[TaskState] = None, task_type: Optional[TaskType] = None) -> List[EnterpriseTask]:
        """获取任务列表"""
        tasks = list(self.tasks.values())
        
        if state:
            tasks = [task for task in tasks if task.state == state]
        
        if task_type:
            tasks = [task for task in tasks if task.task_type == task_type]
        
        return tasks

    def get_task_group(self, group_id: str) -> Optional[TaskGroup]:
        """获取任务组"""
        return self.task_groups.get(group_id)

    def get_task_groups(self, state: Optional[str] = None) -> List[TaskGroup]:
        """获取任务组列表"""
        groups = list(self.task_groups.values())
        
        if state:
            groups = [group for group in groups if group.state == state]
        
        return groups

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
            return False
        
        task.state = TaskState.CANCELLED
        task.completed_at = time.time()
        logger.info(f"Task {task_id} cancelled")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_tasks = len(self.tasks)
        pending_tasks = len([t for t in self.tasks.values() if t.state == TaskState.PENDING])
        running_tasks = len([t for t in self.tasks.values() if t.state in [TaskState.ASSIGNED, TaskState.RUNNING]])
        completed_tasks = len([t for t in self.tasks.values() if t.state == TaskState.COMPLETED])
        failed_tasks = len([t for t in self.tasks.values() if t.state == TaskState.FAILED])
        
        total_groups = len(self.task_groups)
        completed_groups = len([g for g in self.task_groups.values() if g.state == "completed"])
        
        return {
            "enterprise_id": self.enterprise_id,
            "total_tasks": total_tasks,
            "pending_tasks": pending_tasks,
            "running_tasks": running_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "total_groups": total_groups,
            "completed_groups": completed_groups
        }


# 单例管理
task_schedulers: Dict[str, EnterpriseTaskScheduler] = {}


def get_enterprise_task_scheduler(enterprise_id: str) -> EnterpriseTaskScheduler:
    """获取企业任务调度器"""
    if enterprise_id not in task_schedulers:
        task_schedulers[enterprise_id] = EnterpriseTaskScheduler(enterprise_id)
        # 启动调度器
        import asyncio
        asyncio.create_task(task_schedulers[enterprise_id].start())
    return task_schedulers[enterprise_id]


def list_enterprise_schedulers() -> List[str]:
    """列出所有企业调度器"""
    return list(task_schedulers.keys())
