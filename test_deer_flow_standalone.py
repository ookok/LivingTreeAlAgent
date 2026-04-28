"""
DeerFlow 集成独立测试

完全独立测试 DeerFlow 核心功能，不依赖项目其他模块
"""

import time
import json
import asyncio
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from concurrent.futures import ThreadPoolExecutor


# ============ 复制 DeerFlow 核心组件 ============

class MiddlewareType(Enum):
    DATA = "data"
    MEMORY = "memory"
    SECURITY = "security"
    TOOL = "tool"
    CONTEXT = "context"
    SUBAGENT = "subagent"
    CLARIFICATION = "clarification"


@dataclass
class MiddlewareResult:
    success: bool = True
    state: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseMiddleware:
    def __init__(self, middleware_type: MiddlewareType):
        self.middleware_type = middleware_type
        self.enabled = True
        self.order = 0
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        raise NotImplementedError
    
    def get_type(self):
        return self.middleware_type

    def get_name(self):
        return self.__class__.__name__


class ThreadDataMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__(MiddlewareType.DATA)
        self.order = 1
        self.thread_data = {}
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        thread_id = state.get("thread_id", "default")
        
        if thread_id not in self.thread_data:
            self.thread_data[thread_id] = {
                "created_at": time.time(),
                "messages": [],
                "artifacts": [],
                "context": {},
            }
        
        thread_data = self.thread_data[thread_id]
        state["thread_data"] = thread_data
        
        if "message" in state:
            thread_data["messages"].append(state["message"])
        
        return MiddlewareResult(success=True, state=state)


class MemoryMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__(MiddlewareType.MEMORY)
        self.order = 9
        self.max_facts = 15
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        facts = []
        messages = state.get("thread_data", {}).get("messages", [])
        for msg in messages[-5:]:
            if isinstance(msg, dict) and "content" in msg:
                content = str(msg["content"])
                if len(content) > 10:
                    facts.append({
                        "content": content[:100],
                        "confidence": 0.8,
                        "timestamp": msg.get("timestamp", time.time()),
                    })
        
        state["memory_facts"] = facts[:self.max_facts]
        state["memory_updated"] = len(facts) > 0
        
        return MiddlewareResult(success=True, state=state, metadata={"facts_count": len(facts)})


class GuardrailMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__(MiddlewareType.SECURITY)
        self.order = 5
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        tool_calls = state.get("tool_calls", [])
        
        if not tool_calls:
            return MiddlewareResult(success=True, state=state)
        
        approved_calls = []
        denied_calls = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            high_risk_tools = ["delete", "exec", "system", "rm", "format"]
            if any(risk in tool_name.lower() for risk in high_risk_tools):
                if not state.get("high_risk_approved", False):
                    denied_calls.append(tool_call)
                    continue
            approved_calls.append(tool_call)
        
        state["tool_calls"] = approved_calls
        state["denied_tool_calls"] = denied_calls
        
        return MiddlewareResult(success=True, state=state, metadata={"approved": len(approved_calls), "denied": len(denied_calls)})


class SummarizationMiddleware(BaseMiddleware):
    def __init__(self, max_tokens: int = 8000):
        super().__init__(MiddlewareType.CONTEXT)
        self.order = 6
        self.max_tokens = max_tokens
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        messages = state.get("messages", [])
        current_tokens = sum(len(str(m)) for m in messages)
        
        if current_tokens > self.max_tokens:
            system_messages = [m for m in messages if isinstance(m, dict) and m.get("role") == "system"]
            recent_messages = messages[-10:]
            state["messages"] = system_messages + recent_messages
            state["was_summarized"] = True
            return MiddlewareResult(success=True, state=state, metadata={"summarized": True})
        
        state["was_summarized"] = False
        return MiddlewareResult(success=True, state=state)


class TodoListMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__(MiddlewareType.CONTEXT)
        self.order = 7
        self.todos = {}
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        thread_id = state.get("thread_id", "default")
        
        if thread_id not in self.todos:
            self.todos[thread_id] = []
        
        state["todos"] = self.todos[thread_id]
        
        new_todos = state.get("new_todos", [])
        if new_todos:
            self.todos[thread_id].extend(new_todos)
        
        completed_todos = state.get("completed_todos", [])
        for todo_id in completed_todos:
            for todo in self.todos[thread_id]:
                if todo.get("id") == todo_id:
                    todo["completed"] = True
                    todo["completed_at"] = time.time()
        
        total = len(self.todos[thread_id])
        completed = sum(1 for t in self.todos[thread_id] if t.get("completed", False))
        state["todo_progress"] = {"total": total, "completed": completed}
        
        return MiddlewareResult(success=True, state=state)


class SubagentLimitMiddleware(BaseMiddleware):
    def __init__(self, max_concurrent: int = 3):
        super().__init__(MiddlewareType.SUBAGENT)
        self.order = 10
        self.max_concurrent = max_concurrent
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        subagent_calls = state.get("subagent_calls", [])
        
        if not subagent_calls:
            return MiddlewareResult(success=True, state=state)
        
        if len(subagent_calls) > self.max_concurrent:
            limited_calls = subagent_calls[:self.max_concurrent]
            truncated_calls = subagent_calls[self.max_concurrent:]
            state["subagent_calls"] = limited_calls
            state["truncated_subagent_calls"] = truncated_calls
            state["subagent_limit_warning"] = f"{len(truncated_calls)} subagent call(s) truncated"
        
        return MiddlewareResult(success=True, state=state, metadata={"max_concurrent": self.max_concurrent})


class MiddlewarePipeline:
    def __init__(self):
        self.middlewares = []
    
    def add(self, middleware):
        self.middlewares.append(middleware)
        self.middlewares.sort(key=lambda m: m.order)
        return self
    
    def get(self, middleware_name):
        for m in self.middlewares:
            if m.get_name() == middleware_name:
                return m
        return None
    
    def enable(self, middleware_name):
        middleware = self.get(middleware_name)
        if middleware:
            middleware.enabled = True
            return True
        return False
    
    def disable(self, middleware_name):
        middleware = self.get(middleware_name)
        if middleware:
            middleware.enabled = False
            return True
        return False
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        current_state = state.copy()
        
        for middleware in self.middlewares:
            if not middleware.enabled:
                continue
            try:
                result = await middleware.process(current_state)
                current_state.update(result.state)
            except Exception as e:
                current_state["middleware_errors"] = current_state.get("middleware_errors", [])
                current_state["middleware_errors"].append({"middleware": middleware.get_name(), "exception": str(e)})
        
        return current_state
    
    def get_pipeline_info(self):
        return [
            {"name": m.get_name(), "type": m.get_type().value, "order": m.order, "enabled": m.enabled}
            for m in self.middlewares
        ]


# ============ 子智能体系统 ============

class SubAgentType(Enum):
    GENERAL = "general"
    BASH = "bash"
    RESEARCH = "research"
    CODING = "coding"
    ANALYSIS = "analysis"


@dataclass
class SubAgentTask:
    task_id: str
    agent_type: SubAgentType
    description: str
    parameters: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class SubAgentResult:
    task_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float = 0


class BaseSubAgent:
    def __init__(self, agent_type: SubAgentType):
        self.agent_type = agent_type
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class GeneralSubAgent(BaseSubAgent):
    def __init__(self):
        super().__init__(SubAgentType.GENERAL)
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "completed", "message": f"Task: {parameters.get('description', '')}"}


class ResearchSubAgent(BaseSubAgent):
    def __init__(self):
        super().__init__(SubAgentType.RESEARCH)
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        query = parameters.get("query", "")
        sources = parameters.get("sources", [])
        findings = [{"source": s, "info": f"Info about {query}"} for s in sources[:3]]
        return {"status": "completed", "query": query, "findings": findings}


class CodingSubAgent(BaseSubAgent):
    def __init__(self):
        super().__init__(SubAgentType.CODING)
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        code = parameters.get("code", "")
        task = parameters.get("task", "review")
        return {"status": "completed", "task": task, "suggestions": ["Code looks good"]}


class SubAgentRegistry:
    def __init__(self):
        self._agents = {}
        self._register_builtins()
    
    def _register_builtins(self):
        self._agents[SubAgentType.GENERAL] = GeneralSubAgent()
        self._agents[SubAgentType.RESEARCH] = ResearchSubAgent()
        self._agents[SubAgentType.CODING] = CodingSubAgent()
    
    def get(self, agent_type: SubAgentType):
        return self._agents.get(agent_type)


class SubAgentExecutor:
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self.registry = SubAgentRegistry()
        self.tasks = {}
        self.task_lock = threading.Lock()
    
    async def execute(self, agent_type: SubAgentType, parameters: Dict[str, Any], description: str = "", task_id: str = None) -> SubAgentResult:
        import uuid
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        agent = self.registry.get(agent_type)
        if not agent:
            return SubAgentResult(task_id=task_id, success=False, result=None, error=f"Unknown agent type")
        
        with self.task_lock:
            self.tasks[task_id] = SubAgentTask(task_id=task_id, agent_type=agent_type, description=description, parameters=parameters)
            self.tasks[task_id].status = "running"
            self.tasks[task_id].started_at = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self.executor, lambda: asyncio.run(agent.execute(parameters)))
            
            with self.task_lock:
                self.tasks[task_id].status = "completed"
                self.tasks[task_id].result = result
                self.tasks[task_id].completed_at = time.time()
            
            execution_time = self.tasks[task_id].completed_at - self.tasks[task_id].started_at
            return SubAgentResult(task_id=task_id, success=True, result=result, execution_time=execution_time)
        
        except Exception as e:
            with self.task_lock:
                self.tasks[task_id].status = "failed"
                self.tasks[task_id].error = str(e)
                self.tasks[task_id].completed_at = time.time()
            
            execution_time = time.time() - self.tasks[task_id].started_at
            return SubAgentResult(task_id=task_id, success=False, result=None, error=str(e), execution_time=execution_time)
    
    async def execute_parallel(self, tasks: List[Dict[str, Any]], max_parallel: int = None) -> List[SubAgentResult]:
        max_parallel = max_parallel or self.max_concurrent
        semaphore = asyncio.Semaphore(max_parallel)
        
        async def execute_with_semaphore(task):
            async with semaphore:
                agent_type = SubAgentType(task.get("agent_type", "general"))
                return await self.execute(agent_type=agent_type, parameters=task.get("parameters", {}), description=task.get("description", ""))
        
        return await asyncio.gather(*[execute_with_semaphore(t) for t in tasks])
    
    def get_stats(self):
        with self.task_lock:
            tasks = list(self.tasks.values())
            status_counts = {}
            for task in tasks:
                status_counts[task.status] = status_counts.get(task.status, 0) + 1
            
            return {
                "total_tasks": len(tasks),
                "status_counts": status_counts,
                "active_tasks": status_counts.get("running", 0),
            }
    
    def shutdown(self):
        self.executor.shutdown(wait=True)


# ============ 测试函数 ============

def test_middleware_pipeline():
    print("=== 测试中间件管道 ===")
    
    pipeline = MiddlewarePipeline()
    pipeline.add(ThreadDataMiddleware())
    pipeline.add(GuardrailMiddleware())
    pipeline.add(SummarizationMiddleware())
    pipeline.add(TodoListMiddleware())
    pipeline.add(SubagentLimitMiddleware(max_concurrent=3))
    pipeline.add(MemoryMiddleware())
    
    print(f"管道创建成功，包含 {len(pipeline.middlewares)} 个中间件")
    
    info = pipeline.get_pipeline_info()
    print("\n管道中间件:")
    for item in info:
        print(f"  {item['order']}. {item['name']} ({item['type']}) - {'启用' if item['enabled'] else '禁用'}")
    
    initial_state = {
        "thread_id": "test_thread_1",
        "message": {"role": "user", "content": "测试消息"},
        "tool_calls": [{"name": "file_read", "arguments": {"path": "/test"}}],
        "messages": ["message1", "message2", "message3"] * 100,
        "todos": [{"id": "1", "title": "Task 1"}],
    }
    
    print("\n测试状态处理...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(pipeline.process(initial_state))
    finally:
        loop.close()
    
    print(f"处理后状态键: {list(result.keys())}")
    print(f"线程数据已创建: {bool(result.get('thread_data'))}")
    print(f"记忆事实数量: {len(result.get('memory_facts', []))}")
    print(f"任务进度: {result.get('todo_progress')}")
    print(f"是否被缩减: {result.get('was_summarized')}")
    
    pipeline.disable("MemoryMiddleware")
    print(f"\nMemoryMiddleware 禁用后启用状态: {pipeline.get('MemoryMiddleware').enabled}")
    pipeline.enable("MemoryMiddleware")
    print(f"MemoryMiddleware 启用后启用状态: {pipeline.get('MemoryMiddleware').enabled}")
    
    print("\n中间件管道测试完成!")


def test_subagent_executor():
    print("\n=== 测试子智能体执行器 ===")
    
    executor = SubAgentExecutor(max_concurrent=3)
    print(f"执行器创建成功，最大并发: {executor.max_concurrent}")
    
    types = executor.registry._agents.keys()
    print(f"注册的子智能体类型: {[t.value for t in types]}")
    
    print("\n测试执行通用任务...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        general_result = loop.run_until_complete(executor.execute(SubAgentType.GENERAL, {"description": "测试任务"}, "通用任务测试"))
    finally:
        loop.close()
    print(f"成功: {general_result.success}, 结果: {general_result.result}")
    
    print("\n测试执行研究任务...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        research_result = loop.run_until_complete(executor.execute(SubAgentType.RESEARCH, {"query": "AI", "sources": ["a", "b"]}, "研究任务"))
    finally:
        loop.close()
    print(f"成功: {research_result.success}, 发现: {len(research_result.result.get('findings', []))}")
    
    print("\n测试并行执行...")
    tasks = [{"agent_type": "general", "parameters": {"description": f"任务{i}"}, "description": f"并行任务{i}"} for i in range(5)]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        parallel_results = loop.run_until_complete(executor.execute_parallel(tasks, max_parallel=3))
    finally:
        loop.close()
    success_count = sum(1 for r in parallel_results if r.success)
    print(f"并行执行: {len(parallel_results)} 个任务, 成功: {success_count}")
    
    stats = executor.get_stats()
    print(f"统计: 总任务={stats['total_tasks']}, 活跃={stats['active_tasks']}")
    
    executor.shutdown()
    print("\n子智能体执行器测试完成!")


if __name__ == "__main__":
    print("DeerFlow 独立测试开始")
    
    try:
        test_middleware_pipeline()
        test_subagent_executor()
        print("\n✅ 所有测试通过!")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n测试完成")
