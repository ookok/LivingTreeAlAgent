"""自适应任务拆解器 - LLM驱动拆解与历史学习优化"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json

class TaskType(Enum):
    SEARCH = "search"
    CREATE = "create"
    ANALYZE = "analyze"
    EXECUTE = "execute"
    SUMMARIZE = "summarize"
    LEARN = "learn"

@dataclass
class Task:
    """任务定义"""
    id: str
    type: TaskType
    description: str
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    estimated_cost: float = 0.0
    status: str = "pending"

@dataclass
class Plan:
    """计划定义"""
    tasks: List[Task]
    estimated_time: float
    total_cost: float
    strategy: str

class LearningCache:
    """学习缓存"""
    
    def __init__(self):
        self._cache: Dict[str, List[Plan]] = {}
    
    def get(self, intent_type: str) -> List[Plan]:
        """获取历史拆解经验"""
        return self._cache.get(intent_type, [])
    
    def update(self, intent_type: str, plan: Plan):
        """更新学习缓存"""
        if intent_type not in self._cache:
            self._cache[intent_type] = []
        
        self._cache[intent_type].append(plan)
        
        if len(self._cache[intent_type]) > 50:
            self._cache[intent_type] = self._cache[intent_type][-50:]
    
    def get_best_plan(self, intent_type: str) -> Optional[Plan]:
        """获取最佳历史计划"""
        plans = self._cache.get(intent_type, [])
        if not plans:
            return None
        
        plans.sort(key=lambda p: p.total_cost)
        return plans[0]

class AdaptiveTaskDecomposer:
    """自适应任务拆解器"""
    
    def __init__(self):
        self._learning_cache = LearningCache()
        self._initialized = False
    
    async def initialize(self):
        """初始化拆解器"""
        self._initialized = True
    
    async def decompose(self, intent, context: Dict[str, Any]) -> Plan:
        """拆解任务"""
        if not self._initialized:
            await self.initialize()
        
        intent_type = intent.type
        
        history = self._learning_cache.get(intent_type)
        
        plan = await self._generate_plan(intent, context, history)
        
        self._learning_cache.update(intent_type, plan)
        
        return plan
    
    async def _generate_plan(self, intent, context, history) -> Plan:
        """生成计划"""
        tasks = []
        task_id = 0
        
        if intent.type == "search":
            tasks.extend(self._create_search_tasks(intent.parameters))
        
        elif intent.type == "create":
            tasks.extend(self._create_create_tasks(intent.parameters))
        
        elif intent.type == "analyze":
            tasks.extend(self._create_analyze_tasks(intent.parameters))
        
        elif intent.type == "assist":
            tasks.extend(self._create_assist_tasks(intent.parameters))
        
        else:
            tasks.append(Task(
                id=f"task_{task_id}",
                type=TaskType.EXECUTE,
                description=f"执行任务: {intent.type}",
                parameters=intent.parameters
            ))
        
        estimated_time = len(tasks) * 0.5
        total_cost = len(tasks) * 0.1
        
        return Plan(
            tasks=tasks,
            estimated_time=estimated_time,
            total_cost=total_cost,
            strategy="adaptive"
        )
    
    def _create_search_tasks(self, parameters) -> List[Task]:
        """创建搜索任务"""
        tasks = []
        
        tasks.append(Task(
            id="task_0",
            type=TaskType.SEARCH,
            description="执行搜索查询",
            parameters=parameters,
            priority=1
        ))
        
        tasks.append(Task(
            id="task_1",
            type=TaskType.SUMMARIZE,
            description="总结搜索结果",
            dependencies=["task_0"],
            priority=2
        ))
        
        return tasks
    
    def _create_create_tasks(self, parameters) -> List[Task]:
        """创建创建任务"""
        tasks = []
        
        tasks.append(Task(
            id="task_0",
            type=TaskType.ANALYZE,
            description="分析需求",
            parameters=parameters,
            priority=1
        ))
        
        tasks.append(Task(
            id="task_1",
            type=TaskType.CREATE,
            description="执行创建",
            dependencies=["task_0"],
            priority=2
        ))
        
        tasks.append(Task(
            id="task_2",
            type=TaskType.SUMMARIZE,
            description="总结创建结果",
            dependencies=["task_1"],
            priority=3
        ))
        
        return tasks
    
    def _create_analyze_tasks(self, parameters) -> List[Task]:
        """创建分析任务"""
        tasks = []
        
        tasks.append(Task(
            id="task_0",
            type=TaskType.ANALYZE,
            description="数据收集",
            parameters=parameters,
            priority=1
        ))
        
        tasks.append(Task(
            id="task_1",
            type=TaskType.ANALYZE,
            description="深度分析",
            dependencies=["task_0"],
            priority=2
        ))
        
        tasks.append(Task(
            id="task_2",
            type=TaskType.SUMMARIZE,
            description="生成分析报告",
            dependencies=["task_1"],
            priority=3
        ))
        
        return tasks
    
    def _create_assist_tasks(self, parameters) -> List[Task]:
        """创建协助任务"""
        tasks = []
        
        tasks.append(Task(
            id="task_0",
            type=TaskType.SEARCH,
            description="搜索相关信息",
            parameters=parameters,
            priority=1
        ))
        
        tasks.append(Task(
            id="task_1",
            type=TaskType.CREATE,
            description="生成解决方案",
            dependencies=["task_0"],
            priority=2
        ))
        
        return tasks
    
    def get_history(self, intent_type: str) -> List[Plan]:
        """获取历史计划"""
        return self._learning_cache.get(intent_type)
    
    def clear_history(self):
        """清空学习缓存"""
        self._learning_cache = LearningCache()

_decomposer_instance = None

def get_adaptive_task_decomposer() -> AdaptiveTaskDecomposer:
    """获取自适应任务拆解器实例"""
    global _decomposer_instance
    if _decomposer_instance is None:
        _decomposer_instance = AdaptiveTaskDecomposer()
    return _decomposer_instance