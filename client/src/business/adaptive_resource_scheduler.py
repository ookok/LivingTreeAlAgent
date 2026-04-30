"""
自适应资源调度器 - 根据负载动态分配资源
"""

import asyncio
import time
from typing import Dict, Callable, Any, Optional


class LoadMonitor:
    """负载监控器"""
    
    def __init__(self):
        self._cpu_usage: float = 0.0
        self._memory_usage: float = 0.0
        self._task_queue_size: int = 0
        self._response_times: list = []
    
    def update_load(self, cpu: float, memory: float, queue_size: int, response_time: float):
        """更新负载数据"""
        self._cpu_usage = cpu
        self._memory_usage = memory
        self._task_queue_size = queue_size
        
        self._response_times.append(response_time)
        if len(self._response_times) > 100:
            self._response_times.pop(0)
    
    def get_current_load(self) -> float:
        """获取综合负载值"""
        # 综合考虑CPU、内存和队列长度
        cpu_factor = min(self._cpu_usage, 1.0)
        memory_factor = min(self._memory_usage, 1.0)
        queue_factor = min(self._task_queue_size / 100, 1.0)
        
        return (cpu_factor * 0.4 + memory_factor * 0.3 + queue_factor * 0.3)
    
    def get_average_response_time(self) -> float:
        """获取平均响应时间"""
        if not self._response_times:
            return 0.0
        return sum(self._response_times) / len(self._response_times)


class AdaptiveResourceScheduler:
    """自适应资源调度器 - 根据负载动态分配资源"""
    
    def __init__(self):
        self._resource_pools: Dict[str, int] = {
            "cpu": 4,
            "memory": 8,
            "threads": 16
        }
        self._load_monitor = LoadMonitor()
        self._backoff_counter = 0
        self._last_adjust_time = 0
    
    async def schedule_task(self, task_type: str, task: Callable) -> Any:
        """智能调度任务"""
        load = self._load_monitor.get_current_load()
        
        # 根据负载调整执行策略
        if load > 0.9:
            return await self._throttle_and_queue(task)
        elif load > 0.7:
            return await self._prioritize_critical(task_type, task)
        else:
            return await self._execute_normal(task)
    
    async def _throttle_and_queue(self, task: Callable) -> Any:
        """高负载时限流排队"""
        self._backoff_counter += 1
        backoff_time = min(self._backoff_counter * 0.1, 2.0)
        await asyncio.sleep(backoff_time)
        
        try:
            result = await task()
            self._backoff_counter = max(0, self._backoff_counter - 1)
            return result
        except Exception:
            self._backoff_counter = min(self._backoff_counter + 2, 20)
            raise
    
    async def _prioritize_critical(self, task_type: str, task: Callable) -> Any:
        """中高负载时优先处理关键任务"""
        critical_tasks = ["system_health", "emergency", "security"]
        
        if task_type in critical_tasks:
            return await task()
        else:
            # 非关键任务添加轻微延迟
            await asyncio.sleep(0.05)
            return await task()
    
    async def _execute_normal(self, task: Callable) -> Any:
        """正常负载时直接执行"""
        return await task()
    
    def adjust_resources(self):
        """根据负载调整资源分配"""
        now = time.time()
        if now - self._last_adjust_time < 60:
            return
        
        self._last_adjust_time = now
        load = self._load_monitor.get_current_load()
        
        if load > 0.8:
            self._increase_resources()
        elif load < 0.3:
            self._decrease_resources()
    
    def _increase_resources(self):
        """增加资源分配"""
        self._resource_pools["threads"] = min(self._resource_pools["threads"] * 1.5, 64)
    
    def _decrease_resources(self):
        """减少资源分配"""
        self._resource_pools["threads"] = max(self._resource_pools["threads"] / 1.5, 4)
    
    def get_resource_status(self) -> Dict[str, Any]:
        """获取资源状态"""
        return {
            "resources": self._resource_pools,
            "current_load": self._load_monitor.get_current_load(),
            "avg_response_time": self._load_monitor.get_average_response_time()
        }
    
    def update_load_data(self, cpu: float, memory: float, queue_size: int, response_time: float):
        """更新负载数据"""
        self._load_monitor.update_load(cpu, memory, queue_size, response_time)


def get_resource_scheduler() -> AdaptiveResourceScheduler:
    """获取自适应资源调度器单例"""
    if not hasattr(get_resource_scheduler, '_instance'):
        get_resource_scheduler._instance = AdaptiveResourceScheduler()
    return get_resource_scheduler._instance