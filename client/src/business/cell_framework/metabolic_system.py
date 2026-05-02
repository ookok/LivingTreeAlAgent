"""
代谢系统模块 - MetabolicSystem

实现资源管理、能量效率优化和休眠机制。

代谢系统层次：
┌─────────────────────────────────────────────────────────┐
│  能量生产层                                            │
│  • 计算资源利用                                       │
│  • 效率优化                                           │
│  • 能量回收                                           │
├─────────────────────────────────────────────────────────┤
│  能量分配层                                            │
│  • 动态资源分配                                       │
│  • 优先级调度                                         │
│  • 负载均衡                                           │
├─────────────────────────────────────────────────────────┤
│  能量储存层                                            │
│  • 能量储备管理                                       │
│  • 节能模式                                           │
│  • 休眠机制                                           │
├─────────────────────────────────────────────────────────┤
│  废物处理层                                            │
│  • 垃圾回收                                           │
│  • 内存清理                                           │
│  • 状态保存                                           │
└─────────────────────────────────────────────────────────┘

资源类型：
- CPU：计算能力
- 内存：数据存储
- 网络：带宽
- 能量：综合资源指标
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from collections import defaultdict


class EnergyLevel(Enum):
    """能量级别"""
    CRITICAL = "critical"   # 危急 (< 10%)
    LOW = "low"             # 低 (10-30%)
    NORMAL = "normal"       # 正常 (30-70%)
    HIGH = "high"           # 高 (70-90%)
    OPTIMAL = "optimal"     # 最佳 (> 90%)


class ResourceType(Enum):
    """资源类型"""
    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"
    ENERGY = "energy"


class MetabolicState(Enum):
    """代谢状态"""
    ACTIVE = "active"           # 活跃
    CONSERVING = "conserving"   # 节能
    DORMANT = "dormant"         # 休眠
    RECOVERING = "recovering"   # 恢复中


class ResourcePool:
    """资源池"""
    
    def __init__(self, resource_type: ResourceType, capacity: float):
        self.type = resource_type
        self.capacity = capacity
        self.usage = 0.0
        self.allocation: Dict[str, float] = {}  # 分配记录
    
    @property
    def available(self) -> float:
        """可用资源"""
        return self.capacity - self.usage
    
    @property
    def utilization(self) -> float:
        """利用率"""
        return self.usage / self.capacity if self.capacity > 0 else 0.0
    
    def allocate(self, requester_id: str, amount: float) -> bool:
        """分配资源"""
        if self.available >= amount:
            self.allocation[requester_id] = amount
            self.usage += amount
            return True
        return False
    
    def release(self, requester_id: str):
        """释放资源"""
        if requester_id in self.allocation:
            self.usage -= self.allocation[requester_id]
            del self.allocation[requester_id]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type.value,
            'capacity': self.capacity,
            'usage': self.usage,
            'available': self.available,
            'utilization': self.utilization
        }


class MetabolicSystem:
    """
    代谢系统
    
    负责：
    1. 资源管理和分配
    2. 能量效率优化
    3. 休眠和唤醒机制
    4. 垃圾回收和内存管理
    5. 负载均衡和优先级调度
    """
    
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.state = MetabolicState.ACTIVE
        self.last_activity = datetime.now()
        
        # 资源池
        self.resource_pools: Dict[ResourceType, ResourcePool] = {
            ResourceType.CPU: ResourcePool(ResourceType.CPU, 100.0),
            ResourceType.MEMORY: ResourcePool(ResourceType.MEMORY, 1024.0),  # MB
            ResourceType.NETWORK: ResourcePool(ResourceType.NETWORK, 100.0),  # Mbps
            ResourceType.ENERGY: ResourcePool(ResourceType.ENERGY, 100.0),
        }
        
        # 能量管理
        self.energy_reserve = 20.0  # 能量储备
        self.energy_regeneration_rate = 0.5  # 每秒恢复
        self.last_regeneration = datetime.now()
        
        # 休眠配置
        self.dormancy_timeout = 300  # 5分钟无活动进入休眠
        self.min_energy_for_dormancy = 10.0
        
        # 优先级配置
        self.priorities: Dict[str, int] = {
            'critical': 10,
            'high': 7,
            'normal': 5,
            'low': 3,
            'background': 1
        }
        
        # 统计信息
        self.total_processed = 0
        self.energy_consumed = 0.0
        self.peak_usage: Dict[ResourceType, float] = {}
        
        # 调度队列
        self.task_queue: List[Dict] = []
        
        # 垃圾回收
        self.gc_threshold = 0.8
        self.last_gc = datetime.now()
    
    async def manage_resources(self) -> Dict[str, Any]:
        """
        管理资源
        
        Returns:
            资源状态报告
        """
        # 更新能量
        await self._regenerate_energy()
        
        # 检查休眠条件
        await self._check_dormancy()
        
        # 执行垃圾回收
        await self._perform_gc_if_needed()
        
        # 调度任务
        await self._schedule_tasks()
        
        return self.get_metabolic_report()
    
    async def _regenerate_energy(self):
        """能量恢复"""
        now = datetime.now()
        elapsed = (now - self.last_regeneration).total_seconds()
        
        if elapsed >= 1.0:
            energy_pool = self.resource_pools[ResourceType.ENERGY]
            max_regeneration = energy_pool.capacity - energy_pool.usage
            
            if max_regeneration > 0:
                regeneration = min(elapsed * self.energy_regeneration_rate, max_regeneration)
                energy_pool.usage -= regeneration
            
            self.last_regeneration = now
    
    async def _check_dormancy(self):
        """检查休眠条件"""
        now = datetime.now()
        elapsed_since_activity = (now - self.last_activity).total_seconds()
        
        energy_pool = self.resource_pools[ResourceType.ENERGY]
        
        # 检查是否需要进入休眠
        if (elapsed_since_activity > self.dormancy_timeout and 
            energy_pool.utilization < self.min_energy_for_dormancy and
            self.state == MetabolicState.ACTIVE):
            
            await self.enter_dormancy()
        
        # 检查是否需要唤醒
        if self.state == MetabolicState.DORMANT and energy_pool.usage > 50.0:
            await self.wake_up()
    
    async def enter_dormancy(self):
        """进入休眠模式"""
        # 保存状态
        await self._save_state()
        
        # 释放非关键资源
        for pool in self.resource_pools.values():
            pool.usage *= 0.1
        
        self.state = MetabolicState.DORMANT
        self.energy_regeneration_rate *= 2  # 休眠时恢复更快
    
    async def wake_up(self):
        """唤醒系统"""
        # 恢复状态
        await self._restore_state()
        
        self.state = MetabolicState.RECOVERING
        self.energy_regeneration_rate /= 2
        
        # 逐步恢复活跃状态
        await asyncio.sleep(5)
        self.state = MetabolicState.ACTIVE
    
    async def _save_state(self):
        """保存状态"""
        pass  # 在实际系统中保存到持久化存储
    
    async def _restore_state(self):
        """恢复状态"""
        pass  # 在实际系统中从持久化存储恢复
    
    async def _perform_gc_if_needed(self):
        """执行垃圾回收"""
        memory_pool = self.resource_pools[ResourceType.MEMORY]
        
        if memory_pool.utilization > self.gc_threshold:
            await self._perform_gc()
    
    async def _perform_gc(self):
        """执行垃圾回收"""
        memory_pool = self.resource_pools[ResourceType.MEMORY]
        
        # 释放未使用的分配
        freed = memory_pool.usage * 0.2
        memory_pool.usage -= freed
        
        # 清理任务队列中过期的任务
        now = datetime.now()
        self.task_queue = [t for t in self.task_queue if t.get('deadline', now) > now]
        
        self.last_gc = datetime.now()
    
    async def _schedule_tasks(self):
        """调度任务"""
        # 按优先级排序
        self.task_queue.sort(key=lambda t: self.priorities.get(t.get('priority', 'normal'), 5), reverse=True)
        
        # 执行高优先级任务
        high_priority = [t for t in self.task_queue if self.priorities.get(t.get('priority'), 5) >= 7]
        
        for task in high_priority[:3]:  # 最多同时执行3个高优先级任务
            await self._execute_task(task)
    
    async def _execute_task(self, task: Dict):
        """执行任务"""
        task_id = task.get('id')
        priority = task.get('priority', 'normal')
        
        # 分配资源
        if await self.allocate_resources(task_id, priority):
            # 模拟任务执行
            await asyncio.sleep(0.1)
            
            # 更新统计
            self.total_processed += 1
            self.energy_consumed += 0.5
            
            # 释放资源
            self.release_resources(task_id)
            
            # 从队列移除
            self.task_queue = [t for t in self.task_queue if t.get('id') != task_id]
    
    async def allocate_resources(self, requester_id: str, priority: str = 'normal') -> bool:
        """
        分配资源
        
        Args:
            requester_id: 请求者ID
            priority: 优先级
        
        Returns:
            是否成功分配
        """
        priority_level = self.priorities.get(priority, 5)
        
        # 根据优先级分配不同数量的资源
        allocation = {
            ResourceType.CPU: min(10.0, priority_level * 1.5),
            ResourceType.MEMORY: min(100.0, priority_level * 15.0),
            ResourceType.ENERGY: min(5.0, priority_level * 0.5)
        }
        
        # 尝试分配所有需要的资源
        allocated = []
        try:
            for resource_type, amount in allocation.items():
                pool = self.resource_pools[resource_type]
                if pool.allocate(requester_id, amount):
                    allocated.append(resource_type)
                else:
                    # 部分分配失败，回滚
                    for rt in allocated:
                        self.resource_pools[rt].release(requester_id)
                    return False
            
            return True
        except:
            # 异常时回滚
            for rt in allocated:
                self.resource_pools[rt].release(requester_id)
            return False
    
    def release_resources(self, requester_id: str):
        """释放资源"""
        for pool in self.resource_pools.values():
            pool.release(requester_id)
    
    def add_task(self, task: Dict):
        """添加任务到队列"""
        task['id'] = task.get('id', str(uuid.uuid4())[:8])
        task['added_at'] = datetime.now()
        self.task_queue.append(task)
    
    def get_metabolic_report(self) -> Dict[str, Any]:
        """获取代谢报告"""
        energy_pool = self.resource_pools[ResourceType.ENERGY]
        
        return {
            'id': self.id,
            'state': self.state.value,
            'energy_level': self._get_energy_level().value,
            'resources': {rt.value: pool.to_dict() for rt, pool in self.resource_pools.items()},
            'energy_reserve': self.energy_reserve,
            'total_processed': self.total_processed,
            'energy_consumed': self.energy_consumed,
            'active_tasks': len(self.task_queue),
            'last_activity': self.last_activity.isoformat(),
            'last_gc': self.last_gc.isoformat()
        }
    
    def _get_energy_level(self) -> EnergyLevel:
        """获取能量级别"""
        energy_pool = self.resource_pools[ResourceType.ENERGY]
        utilization = energy_pool.utilization
        
        if utilization < 0.1:
            return EnergyLevel.CRITICAL
        elif utilization < 0.3:
            return EnergyLevel.LOW
        elif utilization < 0.7:
            return EnergyLevel.NORMAL
        elif utilization < 0.9:
            return EnergyLevel.HIGH
        else:
            return EnergyLevel.OPTIMAL
    
    def update_resource_usage(self, resource_type: ResourceType, usage: float):
        """更新资源使用"""
        if resource_type in self.resource_pools:
            self.resource_pools[resource_type].usage = min(
                self.resource_pools[resource_type].capacity,
                usage
            )
            
            # 更新峰值
            if resource_type not in self.peak_usage or usage > self.peak_usage[resource_type]:
                self.peak_usage[resource_type] = usage
    
    def record_activity(self):
        """记录活动"""
        self.last_activity = datetime.now()
        
        # 如果在休眠状态，唤醒
        if self.state == MetabolicState.DORMANT:
            asyncio.create_task(self.wake_up())
    
    def optimize_efficiency(self):
        """优化效率"""
        # 识别低效的资源使用
        for rt, pool in self.resource_pools.items():
            if pool.utilization < 0.1:
                # 低使用率，可能可以减少分配
                pass
            
            if pool.utilization > 0.9:
                # 高使用率，需要优化
                self._optimize_high_utilization(rt)
    
    def _optimize_high_utilization(self, resource_type: ResourceType):
        """优化高使用率资源"""
        pool = self.resource_pools[resource_type]
        
        # 尝试释放低优先级任务的资源
        for task in sorted(self.task_queue, key=lambda t: self.priorities.get(t.get('priority'), 5)):
            if pool.utilization < 0.8:
                break
            
            task_id = task.get('id')
            if task_id in pool.allocation:
                pool.release(task_id)
                self.task_queue.remove(task)
    
    def get_energy_efficiency(self) -> float:
        """计算能量效率"""
        if self.energy_consumed == 0:
            return 0.0
        
        # 效率 = 处理任务数 / 消耗能量
        return self.total_processed / self.energy_consumed