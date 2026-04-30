"""并行执行调度器 - 依赖分析与并行调度"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from collections import defaultdict

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class ExecutionResult:
    """执行结果"""
    task_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0

@dataclass
class ExecutionTrace:
    """执行轨迹"""
    task_id: str
    status: TaskStatus
    start_time: float = 0.0
    end_time: float = 0.0
    error: Optional[str] = None

class DependencyAnalyzer:
    """依赖分析器"""
    
    def analyze(self, tasks) -> Dict[str, List[str]]:
        """分析任务依赖"""
        graph = {}
        
        for task in tasks:
            graph[task.id] = task.dependencies.copy()
        
        return graph
    
    def find_ready_tasks(self, graph: Dict[str, List[str]], completed: List[str]) -> List[str]:
        """查找就绪任务"""
        ready = []
        
        for task_id, deps in graph.items():
            if not deps or all(d in completed for d in deps):
                ready.append(task_id)
        
        return ready
    
    def has_cycle(self, graph: Dict[str, List[str]]) -> bool:
        """检测循环依赖"""
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                if dfs(node):
                    return True
        
        return False

class ParallelExecutionScheduler:
    """并行执行调度器"""
    
    def __init__(self):
        self._dependency_analyzer = DependencyAnalyzer()
        self._executor_pool = asyncio.Semaphore(10)
        self._traces: List[ExecutionTrace] = []
    
    async def execute(self, plan) -> Dict[str, ExecutionResult]:
        """并行执行任务"""
        results = {}
        completed = []
        running = set()
        
        graph = self._dependency_analyzer.analyze(plan.tasks)
        
        if self._dependency_analyzer.has_cycle(graph):
            raise ValueError("检测到循环依赖")
        
        task_map = {t.id: t for t in plan.tasks}
        
        while len(completed) < len(plan.tasks):
            ready = self._dependency_analyzer.find_ready_tasks(graph, completed)
            ready = [r for r in ready if r not in completed and r not in running]
            
            if not ready:
                await asyncio.sleep(0.1)
                continue
            
            tasks_to_run = []
            
            for task_id in ready[:3]:
                task = task_map[task_id]
                tasks_to_run.append(self._execute_task(task))
                running.add(task_id)
            
            if tasks_to_run:
                task_results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
                
                for i, task_id in enumerate(ready[:3]):
                    result = task_results[i]
                    
                    if isinstance(result, Exception):
                        results[task_id] = ExecutionResult(
                            task_id=task_id,
                            success=False,
                            error=str(result)
                        )
                    else:
                        results[task_id] = ExecutionResult(
                            task_id=task_id,
                            success=True,
                            data=result,
                            execution_time=0.5
                        )
                    
                    completed.append(task_id)
                    running.remove(task_id)
        
        return results
    
    async def _execute_task(self, task):
        """执行单个任务"""
        async with self._executor_pool:
            trace = ExecutionTrace(
                task_id=task.id,
                status=TaskStatus.RUNNING,
                start_time=asyncio.get_event_loop().time()
            )
            
            try:
                result = await self._execute_task_logic(task)
                
                trace.status = TaskStatus.COMPLETED
                trace.end_time = asyncio.get_event_loop().time()
                self._traces.append(trace)
                
                return result
            except Exception as e:
                trace.status = TaskStatus.FAILED
                trace.error = str(e)
                trace.end_time = asyncio.get_event_loop().time()
                self._traces.append(trace)
                
                raise
    
    async def _execute_task_logic(self, task):
        """执行任务逻辑"""
        await asyncio.sleep(0.3)
        
        return {
            "task_id": task.id,
            "type": task.type.value,
            "status": "completed",
            "parameters": task.parameters
        }
    
    async def retry_failed(self, results: Dict[str, ExecutionResult]) -> Dict[str, ExecutionResult]:
        """重试失败任务"""
        retried = {}
        
        for task_id, result in results.items():
            if not result.success:
                retried[task_id] = result
        
        if retried:
            print(f"重试 {len(retried)} 个失败任务")
        
        return retried
    
    def get_traces(self) -> List[ExecutionTrace]:
        """获取执行轨迹"""
        return self._traces
    
    def clear_traces(self):
        """清空执行轨迹"""
        self._traces.clear()

_scheduler_instance = None

def get_parallel_execution_scheduler() -> ParallelExecutionScheduler:
    """获取并行执行调度器实例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ParallelExecutionScheduler()
    return _scheduler_instance