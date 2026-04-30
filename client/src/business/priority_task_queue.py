"""
优先级任务队列 - 智能任务调度
"""

import asyncio
from typing import Any, Callable, Dict, Optional


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class PriorityTaskQueue:
    """优先级任务队列 - 智能任务调度"""
    
    def __init__(self):
        self._queues: Dict[int, asyncio.PriorityQueue] = {
            0: asyncio.PriorityQueue(maxsize=100),   # critical
            1: asyncio.PriorityQueue(maxsize=200),   # high
            2: asyncio.PriorityQueue(maxsize=500),   # normal
            3: asyncio.PriorityQueue(maxsize=1000)   # low
        }
        self._workers: Dict[int, asyncio.Task] = {}
        self._shutdown = False
    
    def submit_task(self, task: Callable, priority: int = 2):
        """提交任务到对应优先级队列"""
        priority = max(0, min(3, priority))  # 限制在有效范围内
        queue = self._queues[priority]
        
        try:
            queue.put_nowait((priority, asyncio.create_task(task())))
        except asyncio.QueueFull:
            # 队列满时降级处理
            if priority < 3:
                # 低优先级队列有空间则放入
                for p in range(3, priority, -1):
                    if not self._queues[p].full():
                        self._queues[p].put_nowait((p, asyncio.create_task(task())))
                        break
    
    def start_workers(self, workers_per_priority: int = 2):
        """启动工作线程"""
        for priority in range(4):
            for _ in range(workers_per_priority):
                worker = asyncio.create_task(self._worker_loop(priority))
                self._workers[(priority, _)] = worker
    
    async def _worker_loop(self, priority: int):
        """工作线程循环"""
        queue = self._queues[priority]
        
        while not self._shutdown:
            try:
                _, task = await asyncio.wait_for(
                    queue.get(),
                    timeout=1.0
                )
                try:
                    await task
                except Exception:
                    pass  # 任务执行失败不影响工作线程
                queue.task_done()
            except asyncio.TimeoutError:
                continue
    
    def stop_workers(self):
        """停止工作线程"""
        self._shutdown = True
        for worker in self._workers.values():
            worker.cancel()
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """获取各队列大小"""
        return {
            "critical": self._queues[0].qsize(),
            "high": self._queues[1].qsize(),
            "normal": self._queues[2].qsize(),
            "low": self._queues[3].qsize()
        }
    
    def is_empty(self) -> bool:
        """检查所有队列是否为空"""
        return all(queue.empty() for queue in self._queues.values())


def get_task_queue() -> PriorityTaskQueue:
    """获取优先级任务队列单例"""
    if not hasattr(get_task_queue, '_instance'):
        get_task_queue._instance = PriorityTaskQueue()
    return get_task_queue._instance


from enum import Enum  # noqa: E402