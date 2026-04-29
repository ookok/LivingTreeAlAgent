"""
Distributed Task Scheduler

分布式任务调度器
- 智能调度算法
- 负载均衡
- 资源匹配
- 故障转移
"""

import asyncio
import heapq
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .models import TaskInfo, NodeInfo, QoSPriority


@dataclass
class TaskScheduler:
    """
    分布式任务调度器
    
    Features:
    - Smart scheduling algorithm
    - Load balancing
    - Resource matching
    - Fault tolerance
    """
    
    node_id: str
    
    # 任务队列
    _pending_tasks: list = field(default_factory=list)
    _running_tasks: dict[str, TaskInfo] = field(default_factory=dict)
    _completed_tasks: dict[str, TaskInfo] = field(default_factory=dict)
    _failed_tasks: dict[str, TaskInfo] = field(default_factory=dict)
    
    # 调度器权重
    WEIGHT_RESOURCE = 0.4  # 资源匹配度权重
    WEIGHT_NETWORK = 0.3  # 网络状况权重
    WEIGHT_LOAD = 0.2     # 负载均衡权重
    WEIGHT_COST = 0.1      # 成本权重
    
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    
    async def schedule_task(
        self,
        task: TaskInfo,
        node_grader,
        connection_pool,
    ) -> str:
        """
        调度任务到最优节点
        
        Args:
            task: 任务信息
            node_grader: 节点分级器
            connection_pool: 连接池
            
        Returns:
            str: 任务ID
        """
        # 生成任务ID
        task.task_id = task.task_id or str(uuid.uuid4())
        task.created_at = time.time()
        
        # 选择最优节点
        optimal_nodes = await self._select_optimal_nodes(
            task=task,
            node_grader=node_grader,
            count=3,
        )
        
        # 尝试调度到最优节点
        scheduled = False
        for node in optimal_nodes:
            try:
                success = await self._dispatch_task(task, node, connection_pool)
                if success:
                    task.target_nodes = [node.node_id]
                    task.status = "scheduled"
                    scheduled = True
                    break
            except Exception:
                continue
        
        if not scheduled:
            # 加入待调度队列
            async with self._lock:
                heapq.heappush(
                    self._pending_tasks,
                    (self._get_task_priority(task), task.created_at, task)
                )
            task.status = "pending"
        
        async with self._lock:
            self._running_tasks[task.task_id] = task
        
        return task.task_id
    
    async def _select_optimal_nodes(
        self,
        task: TaskInfo,
        node_grader,
        count: int,
    ) -> list[NodeInfo]:
        """
        选择最优节点
        
        Args:
            task: 任务信息
            node_grader: 节点分级器
            count: 返回数量
            
        Returns:
            list[NodeInfo]: 最优节点列表
        """
        # 获取所有在线节点
        all_nodes = node_grader.get_optimal_nodes(
            count=100,
            prefer_super=(task.task_type == "relay"),
        )
        
        # 计算每个节点的调度分数
        scored_nodes = []
        for node in all_nodes:
            score = self._calculate_node_score(task, node)
            scored_nodes.append((score, node))
        
        # 按分数排序
        scored_nodes.sort(key=lambda x: x[0], reverse=True)
        
        return [node for _, node in scored_nodes[:count]]
    
    def _calculate_node_score(self, task: TaskInfo, node: NodeInfo) -> float:
        """
        计算节点调度分数
        
        Score = Resource*0.4 + Network*0.3 + Load*0.2 + Cost*0.1
        """
        # 资源匹配度
        resource_score = self._calculate_resource_score(task, node)
        
        # 网络状况
        network_score = min(100, 500 - node.latency_ms) / 100
        
        # 负载均衡 (负载越低分数越高)
        load_score = 1 - (node.cpu_usage + node.memory_usage) / 200
        
        # 成本 (超级节点成本高)
        cost_score = 1.0 if node.level.value != "super" else 0.8
        
        # 综合分数
        total_score = (
            resource_score * self.WEIGHT_RESOURCE +
            network_score * self.WEIGHT_NETWORK +
            load_score * self.WEIGHT_LOAD +
            cost_score * self.WEIGHT_COST
        )
        
        return total_score
    
    def _calculate_resource_score(self, task: TaskInfo, node: NodeInfo) -> float:
        """计算资源匹配度"""
        required_cpu = task.required_cpu
        required_memory = task.required_memory_mb
        
        # 可用资源
        available_cpu = 100 - node.cpu_usage
        available_memory = (100 - node.memory_usage) * 0.479 * 1024  # GB to MB
        
        # 匹配度
        cpu_match = min(1, available_cpu / required_cpu) if required_cpu > 0 else 1
        memory_match = min(1, available_memory / required_memory) if required_memory > 0 else 1
        
        return (cpu_match + memory_match) / 2
    
    def _get_task_priority(self, task: TaskInfo) -> tuple:
        """获取任务优先级元组"""
        # (deadline_score, -priority, created_at)
        deadline_score = 0
        if task.deadline_seconds:
            remaining = task.deadline_seconds - (time.time() - task.created_at)
            deadline_score = -remaining if remaining > 0 else float('inf')
        
        return (deadline_score, -task.priority.value, task.created_at)
    
    async def _dispatch_task(
        self,
        task: TaskInfo,
        node: NodeInfo,
        connection_pool,
    ) -> bool:
        """
        分发任务到节点
        
        Args:
            task: 任务信息
            node: 目标节点
            connection_pool: 连接池
            
        Returns:
            bool: 是否分发成功
        """
        conn = await connection_pool.get_connection(node.node_id)
        if not conn:
            return False
        
        try:
            # 构建任务消息
            import json
            message = json.dumps({
                "type": "task_dispatch",
                "task_id": task.task_id,
                "task_type": task.task_type,
                "payload_size": len(task.payload),
                "required_resources": {
                    "cpu": task.required_cpu,
                    "memory_mb": task.required_memory_mb,
                    "bandwidth_mbps": task.required_bandwidth_mbps,
                },
            }).encode()
            
            success = await conn.send(message)
            return success
        except Exception:
            return False
    
    async def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务状态"""
        if task_id in self._running_tasks:
            return self._running_tasks[task_id]
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id]
        if task_id in self._failed_tasks:
            return self._failed_tasks[task_id]
        return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        async with self._lock:
            # 从待调度队列移除
            new_pending = []
            for _, created, t in self._pending_tasks:
                if t.task_id != task_id:
                    new_pending.append((_, created, t))
            self._pending_tasks = new_pending
            
            # 从运行中移除
            task = self._running_tasks.pop(task_id, None)
            if task:
                task.status = "cancelled"
                return True
        
        return False
    
    async def retry_task(self, task_id: str) -> Optional[str]:
        """重试失败的任务"""
        async with self._lock:
            task = self._failed_tasks.pop(task_id, None)
            if not task:
                return None
            
            task.status = "pending"
            task.progress = 0
            heapq.heappush(
                self._pending_tasks,
                (self._get_task_priority(task), task.created_at, task)
            )
            
            self._running_tasks[task.task_id] = task
        
        return task.task_id
    
    async def _process_pending_tasks(self, node_grader, connection_pool):
        """处理待调度任务"""
        while self._pending_tasks:
            _, _, task = heapq.heappop(self._pending_tasks)
            
            # 检查是否超时
            if task.deadline_seconds:
                elapsed = time.time() - task.created_at
                if elapsed > task.deadline_seconds:
                    task.status = "expired"
                    self._failed_tasks[task.task_id] = task
                    continue
            
            # 重新调度
            await self.schedule_task(task, node_grader, connection_pool)
    
    def get_stats(self) -> dict:
        """获取调度器统计"""
        return {
            "pending": len(self._pending_tasks),
            "running": len(self._running_tasks),
            "completed": len(self._completed_tasks),
            "failed": len(self._failed_tasks),
            "node_id": self.node_id,
        }
