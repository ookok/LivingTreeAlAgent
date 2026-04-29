"""
子智能体执行系统

参考 DeerFlow 的 SubagentExecutor 实现：
- 后台任务执行
- 线程池架构
- 并发限制
- 结果结构化
"""

import time
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
from abc import ABC, abstractmethod
import uuid


# ============ 子智能体类型 ============

class SubAgentType(Enum):
    """子智能体类型"""
    GENERAL = "general"          # 通用型
    BASH = "bash"               # Bash 命令执行
    RESEARCH = "research"       # 研究型
    CODING = "coding"           # 编码型
    ANALYSIS = "analysis"       # 分析型
    CUSTOM = "custom"           # 自定义


@dataclass
class SubAgentTask:
    """子智能体任务"""
    task_id: str
    agent_type: SubAgentType
    description: str
    parameters: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending, running, completed, failed, cancelled
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubAgentResult:
    """子智能体执行结果"""
    task_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============ 子智能体基类 ============

class BaseSubAgent(ABC):
    """
    子智能体基类
    
    所有子智能体都继承自此类，实现特定的任务处理逻辑
    """
    
    def __init__(self, agent_type: SubAgentType):
        self.agent_type = agent_type
        self.name = self.__class__.__name__
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务
        
        Args:
            parameters: 任务参数
            
        Returns:
            Dict: 执行结果
        """
        raise NotImplementedError
    
    def get_system_prompt(self) -> str:
        """获取系统提示"""
        return f"You are a {self.agent_type.value} subagent."


# ============ 内置子智能体 ============

class GeneralSubAgent(BaseSubAgent):
    """通用型子智能体"""
    
    def __init__(self):
        super().__init__(SubAgentType.GENERAL)
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行通用任务"""
        task_description = parameters.get("description", "")
        
        # 简单的任务执行
        return {
            "status": "completed",
            "message": f"Task completed: {task_description}",
            "output": f"Executed: {task_description}",
        }


class BashSubAgent(BaseSubAgent):
    """Bash 命令执行子智能体"""
    
    def __init__(self):
        super().__init__(SubAgentType.BASH)
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行 Bash 命令"""
        command = parameters.get("command", "")
        
        if not command:
            return {
                "status": "failed",
                "error": "No command provided",
            }
        
        try:
            # 在实际实现中，这里会调用 shell 执行命令
            # 这里简化为模拟执行
            return {
                "status": "completed",
                "command": command,
                "output": f"Simulated output for: {command}",
                "exit_code": 0,
            }
        except Exception as e:
            return {
                "status": "failed",
                "command": command,
                "error": str(e),
                "exit_code": 1,
            }


class ResearchSubAgent(BaseSubAgent):
    """研究型子智能体"""
    
    def __init__(self):
        super().__init__(SubAgentType.RESEARCH)
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行研究任务"""
        query = parameters.get("query", "")
        sources = parameters.get("sources", [])
        
        # 模拟研究任务
        findings = []
        for source in sources[:3]:
            findings.append({
                "source": source,
                "relevant_info": f"Information about {query} from {source}",
            })
        
        return {
            "status": "completed",
            "query": query,
            "findings": findings,
            "summary": f"Research completed for query: {query}",
        }


class CodingSubAgent(BaseSubAgent):
    """编码型子智能体"""
    
    def __init__(self):
        super().__init__(SubAgentType.CODING)
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行编码任务"""
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        task = parameters.get("task", "review")
        
        # 模拟编码任务
        if task == "review":
            return {
                "status": "completed",
                "language": language,
                "issues": [],
                "suggestions": ["Code looks good"],
            }
        elif task == "refactor":
            return {
                "status": "completed",
                "language": language,
                "refactored_code": f"# Refactored {code[:50]}...",
            }
        else:
            return {
                "status": "completed",
                "language": language,
                "output": f"Task '{task}' completed",
            }


class AnalysisSubAgent(BaseSubAgent):
    """分析型子智能体"""
    
    def __init__(self):
        super().__init__(SubAgentType.ANALYSIS)
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行分析任务"""
        data = parameters.get("data", "")
        analysis_type = parameters.get("type", "general")
        
        # 模拟分析任务
        return {
            "status": "completed",
            "type": analysis_type,
            "insights": [f"Insight {i+1}" for i in range(3)],
            "conclusion": f"Analysis of {data[:50]}...",
        }


# ============ 子智能体注册表 ============

class SubAgentRegistry:
    """
    子智能体注册表
    
    管理所有可用的子智能体
    """
    
    def __init__(self):
        self._agents: Dict[SubAgentType, BaseSubAgent] = {}
        self._lock = threading.Lock()
        self._register_builtins()
    
    def _register_builtins(self):
        """注册内置子智能体"""
        self.register(SubAgentType.GENERAL, GeneralSubAgent())
        self.register(SubAgentType.BASH, BashSubAgent())
        self.register(SubAgentType.RESEARCH, ResearchSubAgent())
        self.register(SubAgentType.CODING, CodingSubAgent())
        self.register(SubAgentType.ANALYSIS, AnalysisSubAgent())
    
    def register(self, agent_type: SubAgentType, agent: BaseSubAgent) -> bool:
        """
        注册子智能体
        
        Args:
            agent_type: 子智能体类型
            agent: 子智能体实例
            
        Returns:
            bool: 是否成功注册
        """
        with self._lock:
            self._agents[agent_type] = agent
            return True
    
    def get(self, agent_type: SubAgentType) -> Optional[BaseSubAgent]:
        """
        获取子智能体
        
        Args:
            agent_type: 子智能体类型
            
        Returns:
            Optional[BaseSubAgent]: 子智能体实例
        """
        return self._agents.get(agent_type)
    
    def list_types(self) -> List[SubAgentType]:
        """列出所有注册的子智能体类型"""
        return list(self._agents.keys())


# ============ 子智能体执行器 ============

class SubAgentExecutor:
    """
    子智能体执行器
    
    参考 DeerFlow 的 SubagentExecutor 实现
    """
    
    def __init__(
        self,
        max_concurrent: int = 3,
        max_queue_size: int = 100,
        thread_name_prefix: str = "SubAgent"
    ):
        """
        初始化执行器
        
        Args:
            max_concurrent: 最大并发数
            max_queue_size: 最大队列大小
            thread_name_prefix: 线程名前缀
        """
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        
        # 线程池
        self.executor = ThreadPoolExecutor(
            max_workers=max_concurrent,
            thread_name_prefix=thread_name_prefix
        )
        
        # 注册表
        self.registry = SubAgentRegistry()
        
        # 任务管理
        self.tasks: Dict[str, SubAgentTask] = {}
        self.task_lock = threading.Lock()
        
        # 回调
        self.on_task_start: Optional[Callable[[SubAgentTask], None]] = None
        self.on_task_complete: Optional[Callable[[SubAgentResult], None]] = None
        self.on_task_error: Optional[Callable[[SubAgentTask, Exception], None]] = None
    
    async def execute(
        self,
        agent_type: SubAgentType,
        parameters: Dict[str, Any],
        description: str = "",
        task_id: Optional[str] = None,
    ) -> SubAgentResult:
        """
        执行子智能体任务
        
        Args:
            agent_type: 子智能体类型
            parameters: 任务参数
            description: 任务描述
            task_id: 任务 ID（可选）
            
        Returns:
            SubAgentResult: 执行结果
        """
        # 生成任务 ID
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # 创建任务
        task = SubAgentTask(
            task_id=task_id,
            agent_type=agent_type,
            description=description,
            parameters=parameters,
        )
        
        # 获取子智能体
        agent = self.registry.get(agent_type)
        if not agent:
            return SubAgentResult(
                task_id=task_id,
                success=False,
                result=None,
                error=f"Unknown agent type: {agent_type}",
            )
        
        # 检查并发限制
        with self.task_lock:
            running_tasks = [t for t in self.tasks.values() if t.status == "running"]
            if len(running_tasks) >= self.max_concurrent:
                # 队列已满
                return SubAgentResult(
                    task_id=task_id,
                    success=False,
                    result=None,
                    error="Concurrent limit reached, queue is full",
                )
            
            # 添加到任务列表
            self.tasks[task_id] = task
            task.status = "running"
            task.started_at = time.time()
        
        # 触发开始回调
        if self.on_task_start:
            self.on_task_start(task)
        
        try:
            # 执行任务
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._sync_execute,
                agent,
                parameters,
            )
            
            # 更新任务状态
            with self.task_lock:
                task.status = "completed"
                task.result = result
                task.completed_at = time.time()
            
            # 构建结果
            subagent_result = SubAgentResult(
                task_id=task_id,
                success=True,
                result=result,
                execution_time=task.completed_at - task.started_at,
            )
            
            # 触发完成回调
            if self.on_task_complete:
                self.on_task_complete(subagent_result)
            
            return subagent_result
            
        except Exception as e:
            # 更新任务状态
            with self.task_lock:
                task.status = "failed"
                task.error = str(e)
                task.completed_at = time.time()
            
            # 触发错误回调
            if self.on_task_error:
                self.on_task_error(task, e)
            
            return SubAgentResult(
                task_id=task_id,
                success=False,
                result=None,
                error=str(e),
                execution_time=time.time() - task.started_at,
            )
    
    def _sync_execute(self, agent: BaseSubAgent, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        同步执行任务
        
        Args:
            agent: 子智能体实例
            parameters: 任务参数
            
        Returns:
            Dict: 执行结果
        """
        # 在同步上下文中执行异步方法
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(agent.execute(parameters))
        finally:
            loop.close()
    
    async def execute_batch(
        self,
        tasks: List[Dict[str, Any]],
    ) -> List[SubAgentResult]:
        """
        批量执行任务
        
        Args:
            tasks: 任务列表
            
        Returns:
            List[SubAgentResult]: 执行结果列表
        """
        results = []
        
        for task in tasks:
            agent_type = SubAgentType(task.get("agent_type", "general"))
            parameters = task.get("parameters", {})
            description = task.get("description", "")
            
            result = await self.execute(
                agent_type=agent_type,
                parameters=parameters,
                description=description,
            )
            results.append(result)
        
        return results
    
    async def execute_parallel(
        self,
        tasks: List[Dict[str, Any]],
        max_parallel: Optional[int] = None,
    ) -> List[SubAgentResult]:
        """
        并行执行任务
        
        Args:
            tasks: 任务列表
            max_parallel: 最大并行数（可选）
            
        Returns:
            List[SubAgentResult]: 执行结果列表
        """
        max_parallel = max_parallel or self.max_concurrent
        
        # 创建信号量
        semaphore = asyncio.Semaphore(max_parallel)
        
        async def execute_with_semaphore(task: Dict[str, Any]) -> SubAgentResult:
            async with semaphore:
                agent_type = SubAgentType(task.get("agent_type", "general"))
                parameters = task.get("parameters", {})
                description = task.get("description", "")
                
                return await self.execute(
                    agent_type=agent_type,
                    parameters=parameters,
                    description=description,
                )
        
        # 并行执行
        return await asyncio.gather(*[execute_with_semaphore(t) for t in tasks])
    
    def get_task(self, task_id: str) -> Optional[SubAgentTask]:
        """获取任务"""
        with self.task_lock:
            return self.tasks.get(task_id)
    
    def list_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[SubAgentTask]:
        """
        列出任务
        
        Args:
            status: 任务状态过滤（可选）
            limit: 返回数量限制
            
        Returns:
            List[SubAgentTask]: 任务列表
        """
        with self.task_lock:
            tasks = list(self.tasks.values())
            
            if status:
                tasks = [t for t in tasks if t.status == status]
            
            # 按创建时间倒序
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            
            return tasks[:limit]
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            bool: 是否成功取消
        """
        with self.task_lock:
            task = self.tasks.get(task_id)
            if task and task.status == "pending":
                task.status = "cancelled"
                task.completed_at = time.time()
                return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            Dict: 统计信息
        """
        with self.task_lock:
            tasks = list(self.tasks.values())
            
            status_counts = {}
            for task in tasks:
                status_counts[task.status] = status_counts.get(task.status, 0) + 1
            
            total_execution_time = sum(
                (t.completed_at - t.started_at)
                for t in tasks
                if t.started_at and t.completed_at
            )
            
            return {
                "total_tasks": len(tasks),
                "status_counts": status_counts,
                "active_tasks": status_counts.get("running", 0),
                "completed_tasks": status_counts.get("completed", 0),
                "failed_tasks": status_counts.get("failed", 0),
                "average_execution_time": (
                    total_execution_time / len(tasks)
                    if tasks else 0
                ),
                "max_concurrent": self.max_concurrent,
            }
    
    def shutdown(self, wait: bool = True):
        """
        关闭执行器
        
        Args:
            wait: 是否等待任务完成
        """
        self.executor.shutdown(wait=wait)


# ============ 子智能体任务工具 ============

class TaskTool:
    """
    任务工具
    
    提供给 LLM 调用的任务委托工具
    """
    
    def __init__(self, executor: SubAgentExecutor):
        self.executor = executor
    
    def get_schema(self) -> Dict[str, Any]:
        """
        获取工具 schema
        
        Returns:
            Dict: 工具定义
        """
        return {
            "name": "task",
            "description": "Delegate a subtask to a subagent for parallel execution",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_type": {
                        "type": "string",
                        "enum": [t.value for t in SubAgentType],
                        "description": "Type of subagent to use",
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the task",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Task parameters",
                    },
                },
                "required": ["agent_type", "description"],
            },
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务委托
        
        Args:
            arguments: 工具参数
            
        Returns:
            Dict: 执行结果
        """
        agent_type_str = arguments.get("agent_type", "general")
        agent_type = SubAgentType(agent_type_str)
        description = arguments.get("description", "")
        parameters = arguments.get("parameters", {})
        
        result = await self.executor.execute(
            agent_type=agent_type,
            parameters=parameters,
            description=description,
        )
        
        return {
            "task_id": result.task_id,
            "success": result.success,
            "result": result.result,
            "error": result.error,
            "execution_time": result.execution_time,
        }


# ============ 导出 ============

__all__ = [
    "SubAgentType",
    "SubAgentTask",
    "SubAgentResult",
    "BaseSubAgent",
    "GeneralSubAgent",
    "BashSubAgent",
    "ResearchSubAgent",
    "CodingSubAgent",
    "AnalysisSubAgent",
    "SubAgentRegistry",
    "SubAgentExecutor",
    "TaskTool",
]
