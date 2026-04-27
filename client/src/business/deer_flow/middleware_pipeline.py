"""
中间件管道系统

参考 DeerFlow 的 Middleware Pipeline 设计，实现标准化的中间件管道：
1. ThreadDataMiddleware - 线程数据管理
2. MemoryMiddleware - 记忆提取和注入
3. GuardrailMiddleware - 安全鉴权
4. ToolErrorHandlingMiddleware - 工具错误处理
5. SummarizationMiddleware - 上下文缩减
6. TodoListMiddleware - 任务跟踪
7. SubagentLimitMiddleware - 子智能体限制
8. ClarificationMiddleware - 澄清拦截
"""

import time
import asyncio
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


# ============ 中间件基类 ============

class MiddlewareType(Enum):
    """中间件类型"""
    DATA = "data"           # 数据处理
    MEMORY = "memory"       # 记忆处理
    SECURITY = "security"   # 安全鉴权
    TOOL = "tool"          # 工具处理
    CONTEXT = "context"    # 上下文处理
    SUBAGENT = "subagent"  # 子智能体
    CLARIFICATION = "clarification"  # 澄清


@dataclass
class MiddlewareResult:
    """中间件处理结果"""
    success: bool = True
    state: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseMiddleware(ABC):
    """
    中间件基类
    
    所有中间件都继承自此类，实现特定的处理逻辑
    """
    
    def __init__(self, middleware_type: MiddlewareType):
        self.middleware_type = middleware_type
        self.enabled = True
        self.order = 0
    
    @abstractmethod
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        """
        处理状态
        
        Args:
            state: 当前状态
            
        Returns:
            MiddlewareResult: 处理结果
        """
        raise NotImplementedError
    
    def get_name(self) -> str:
        """获取中间件名称"""
        return self.__class__.__name__
    
    def get_type(self) -> MiddlewareType:
        """获取中间件类型"""
        return self.middleware_type


# ============ 具体中间件实现 ============

class ThreadDataMiddleware(BaseMiddleware):
    """
    线程数据中间件
    
    管理线程级别的数据存储和访问
    """
    
    def __init__(self):
        super().__init__(MiddlewareType.DATA)
        self.order = 1
        self.thread_data = {}
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        """处理线程数据"""
        thread_id = state.get("thread_id", "default")
        
        # 获取或创建线程数据
        if thread_id not in self.thread_data:
            self.thread_data[thread_id] = {
                "created_at": time.time(),
                "messages": [],
                "artifacts": [],
                "context": {},
            }
        
        thread_data = self.thread_data[thread_id]
        
        # 注入线程数据到状态
        state["thread_data"] = thread_data
        
        # 更新消息历史
        if "message" in state:
            thread_data["messages"].append(state["message"])
        
        return MiddlewareResult(success=True, state=state)


class MemoryMiddleware(BaseMiddleware):
    """
    记忆中间件
    
    参考 DeerFlow 的 MemoryMiddleware，实现记忆提取和注入
    """
    
    def __init__(self, memory_extractor: Optional[Callable] = None):
        super().__init__(MiddlewareType.MEMORY)
        self.order = 9
        self.memory_queue = []
        self.memory_extractor = memory_extractor
        self.max_facts = 15  # 最多注入 15 个事实
        self.debounce_seconds = 30
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        """处理记忆"""
        thread_id = state.get("thread_id", "default")
        
        # 队列记忆更新
        if "message" in state:
            self.memory_queue.append({
                "thread_id": thread_id,
                "message": state["message"],
                "timestamp": time.time(),
            })
        
        # 提取上下文事实
        facts = await self._extract_facts(state)
        
        # 注入事实到上下文
        state["memory_facts"] = facts[:self.max_facts]
        state["memory_updated"] = len(facts) > 0
        
        return MiddlewareResult(
            success=True,
            state=state,
            metadata={"facts_count": len(facts)}
        )
    
    async def _extract_facts(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取事实"""
        if self.memory_extractor:
            return await self.memory_extractor(state)
        
        # 默认事实提取：简单地从消息中提取关键信息
        facts = []
        
        # 从消息中提取实体和关系
        messages = state.get("thread_data", {}).get("messages", [])
        for msg in messages[-5:]:  # 只看最近 5 条消息
            if isinstance(msg, dict) and "content" in msg:
                content = str(msg["content"])
                # 简单的事实提取
                if len(content) > 10:
                    facts.append({
                        "content": content[:100],
                        "confidence": 0.8,
                        "timestamp": msg.get("timestamp", time.time()),
                    })
        
        return facts


class GuardrailMiddleware(BaseMiddleware):
    """
    安全鉴权中间件
    
    参考 DeerFlow 的 GuardrailMiddleware，实现预工具调用鉴权
    """
    
    def __init__(self, guardrail_provider: Optional[Callable] = None):
        super().__init__(MiddlewareType.SECURITY)
        self.order = 5
        self.guardrail_provider = guardrail_provider
        self.deny_count = 0
        self.allow_count = 0
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        """处理安全鉴权"""
        # 检查是否有工具调用
        tool_calls = state.get("tool_calls", [])
        
        if not tool_calls:
            return MiddlewareResult(success=True, state=state)
        
        # 对每个工具调用进行鉴权
        approved_calls = []
        denied_calls = []
        
        for tool_call in tool_calls:
            if await self._authorize_tool_call(tool_call, state):
                approved_calls.append(tool_call)
            else:
                denied_calls.append(tool_call)
                self.deny_count += 1
        
        # 更新状态
        state["tool_calls"] = approved_calls
        state["denied_tool_calls"] = denied_calls
        
        # 如果有被拒绝的调用，记录警告
        if denied_calls:
            state["guardrail_warning"] = f"{len(denied_calls)} tool call(s) denied by guardrail"
        
        self.allow_count += len(approved_calls)
        
        return MiddlewareResult(
            success=True,
            state=state,
            metadata={
                "approved": len(approved_calls),
                "denied": len(denied_calls),
            }
        )
    
    async def _authorize_tool_call(self, tool_call: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """授权工具调用"""
        if self.guardrail_provider:
            return await self.guardrail_provider(tool_call, state)
        
        # 默认策略：允许所有调用
        tool_name = tool_call.get("name", "")
        
        # 高危工具需要额外鉴权
        high_risk_tools = ["delete", "exec", "system", "rm", "format"]
        if any(risk in tool_name.lower() for risk in high_risk_tools):
            # 高危工具需要确认
            return state.get("high_risk_approved", False)
        
        return True


class ToolErrorHandlingMiddleware(BaseMiddleware):
    """
    工具错误处理中间件
    
    参考 DeerFlow 的 ToolErrorHandlingMiddleware，转换工具异常为错误消息
    """
    
    def __init__(self):
        super().__init__(MiddlewareType.TOOL)
        self.order = 8
        self.error_count = 0
        self.recoverable_errors = ["timeout", "network", "resource"]
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        """处理工具错误"""
        tool_results = state.get("tool_results", [])
        
        if not tool_results:
            return MiddlewareResult(success=True, state=state)
        
        processed_results = []
        
        for result in tool_results:
            if isinstance(result, dict) and "error" in result:
                error_msg = str(result["error"])
                
                # 判断是否可恢复
                is_recoverable = any(err in error_msg.lower() for err in self.recoverable_errors)
                
                if is_recoverable:
                    # 可恢复错误：转换为错误消息
                    result = {
                        "tool": result.get("tool", "unknown"),
                        "error": f"Recoverable error: {error_msg}",
                        "recoverable": True,
                        "retry_suggested": True,
                    }
                else:
                    # 不可恢复错误：记录并继续
                    result = {
                        "tool": result.get("tool", "unknown"),
                        "error": f"Error: {error_msg}",
                        "recoverable": False,
                        "retry_suggested": False,
                    }
                    self.error_count += 1
            else:
                # 成功结果
                result["recoverable"] = False
                result["retry_suggested"] = False
            
            processed_results.append(result)
        
        state["tool_results"] = processed_results
        
        return MiddlewareResult(
            success=True,
            state=state,
            metadata={"error_count": self.error_count}
        )


class SummarizationMiddleware(BaseMiddleware):
    """
    上下文缩减中间件
    
    参考 DeerFlow 的 SummarizationMiddleware，当上下文过长时进行缩减
    """
    
    def __init__(self, max_tokens: int = 8000):
        super().__init__(MiddlewareType.CONTEXT)
        self.order = 6
        self.max_tokens = max_tokens
        self.summarization_count = 0
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        """处理上下文缩减"""
        messages = state.get("messages", [])
        
        # 计算当前 token 数（简单估算）
        current_tokens = sum(len(str(m)) for m in messages)
        
        if current_tokens > self.max_tokens:
            # 需要缩减
            summarized_messages = await self._summarize_messages(messages)
            state["messages"] = summarized_messages
            state["was_summarized"] = True
            self.summarization_count += 1
            
            return MiddlewareResult(
                success=True,
                state=state,
                metadata={"summarized": True, "original_count": len(messages)}
            )
        
        state["was_summarized"] = False
        return MiddlewareResult(success=True, state=state)
    
    async def _summarize_messages(self, messages: List[Any]) -> List[Any]:
        """缩减消息"""
        # 简单策略：保留最近的消息和系统消息
        system_messages = [m for m in messages if isinstance(m, dict) and m.get("role") == "system"]
        recent_messages = messages[-10:]  # 保留最近 10 条
        
        return system_messages + recent_messages


class TodoListMiddleware(BaseMiddleware):
    """
    任务列表中间件
    
    参考 DeerFlow 的 TodoListMiddleware，管理任务跟踪
    """
    
    def __init__(self):
        super().__init__(MiddlewareType.CONTEXT)
        self.order = 7
        self.todos = {}
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        """处理任务列表"""
        thread_id = state.get("thread_id", "default")
        
        # 获取或创建任务列表
        if thread_id not in self.todos:
            self.todos[thread_id] = []
        
        # 注入任务列表到状态
        state["todos"] = self.todos[thread_id]
        
        # 处理任务更新
        new_todos = state.get("new_todos", [])
        if new_todos:
            self.todos[thread_id].extend(new_todos)
        
        # 处理任务完成
        completed_todos = state.get("completed_todos", [])
        for todo_id in completed_todos:
            for todo in self.todos[thread_id]:
                if todo.get("id") == todo_id:
                    todo["completed"] = True
                    todo["completed_at"] = time.time()
        
        # 更新任务进度
        total = len(self.todos[thread_id])
        completed = sum(1 for t in self.todos[thread_id] if t.get("completed", False))
        state["todo_progress"] = {"total": total, "completed": completed}
        
        return MiddlewareResult(success=True, state=state)


class SubagentLimitMiddleware(BaseMiddleware):
    """
    子智能体限制中间件
    
    参考 DeerFlow 的 SubagentLimitMiddleware，限制并发子智能体数量
    """
    
    def __init__(self, max_concurrent: int = 3):
        super().__init__(MiddlewareType.SUBAGENT)
        self.order = 10
        self.max_concurrent = max_concurrent
        self.active_subagents = 0
        self.total_subagents = 0
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        """处理子智能体限制"""
        subagent_calls = state.get("subagent_calls", [])
        
        if not subagent_calls:
            return MiddlewareResult(success=True, state=state)
        
        # 限制并发数量
        if len(subagent_calls) > self.max_concurrent:
            # 截断多余的调用
            limited_calls = subagent_calls[:self.max_concurrent]
            truncated_calls = subagent_calls[self.max_concurrent:]
            
            state["subagent_calls"] = limited_calls
            state["truncated_subagent_calls"] = truncated_calls
            state["subagent_limit_warning"] = f"{len(truncated_calls)} subagent call(s) truncated due to limit"
        
        self.total_subagents += len(state.get("subagent_calls", []))
        
        return MiddlewareResult(
            success=True,
            state=state,
            metadata={
                "max_concurrent": self.max_concurrent,
                "active": len(state.get("subagent_calls", []))
            }
        )


class ClarificationMiddleware(BaseMiddleware):
    """
    澄清拦截中间件
    
    参考 DeerFlow 的 ClarificationMiddleware，拦截需要澄清的请求
    """
    
    def __init__(self):
        super().__init__(MiddlewareType.CLARIFICATION)
        self.order = 11
        self.clarifications = {}
    
    async def process(self, state: Dict[str, Any]) -> MiddlewareResult:
        """处理澄清拦截"""
        # 检查是否需要澄清
        needs_clarification = state.get("needs_clarification", False)
        
        if needs_clarification:
            clarification_question = state.get("clarification_question", "需要澄清")
            
            # 创建澄清请求
            clarification = {
                "id": f"clarify_{int(time.time())}",
                "question": clarification_question,
                "original_state": {k: v for k, v in state.items() if k not in ["clarification_question"]},
                "timestamp": time.time(),
            }
            
            thread_id = state.get("thread_id", "default")
            self.clarifications[thread_id] = clarification
            
            state["clarification_pending"] = True
            state["clarification_id"] = clarification["id"]
        
        return MiddlewareResult(success=True, state=state)


# ============ 中间件管道 ============

class MiddlewarePipeline:
    """
    中间件管道
    
    参考 DeerFlow 的 Middleware Pipeline 实现
    """
    
    def __init__(self):
        self.middlewares: List[BaseMiddleware] = []
        self._lock = False
    
    def add(self, middleware: BaseMiddleware) -> "MiddlewarePipeline":
        """
        添加中间件
        
        Args:
            middleware: 中间件实例
            
        Returns:
            MiddlewarePipeline: 管道自身，支持链式调用
        """
        self.middlewares.append(middleware)
        # 按 order 排序
        self.middlewares.sort(key=lambda m: m.order)
        return self
    
    def remove(self, middleware_name: str) -> bool:
        """
        移除中间件
        
        Args:
            middleware_name: 中间件名称
            
        Returns:
            bool: 是否成功移除
        """
        for i, m in enumerate(self.middlewares):
            if m.get_name() == middleware_name:
                del self.middlewares[i]
                return True
        return False
    
    def get(self, middleware_name: str) -> Optional[BaseMiddleware]:
        """
        获取中间件
        
        Args:
            middleware_name: 中间件名称
            
        Returns:
            Optional[BaseMiddleware]: 中间件实例
        """
        for m in self.middlewares:
            if m.get_name() == middleware_name:
                return m
        return None
    
    def enable(self, middleware_name: str) -> bool:
        """启用中间件"""
        middleware = self.get(middleware_name)
        if middleware:
            middleware.enabled = True
            return True
        return False
    
    def disable(self, middleware_name: str) -> bool:
        """禁用中间件"""
        middleware = self.get(middleware_name)
        if middleware:
            middleware.enabled = False
            return True
        return False
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理状态
        
        Args:
            state: 初始状态
            
        Returns:
            Dict[str, Any]: 处理后的状态
        """
        current_state = state.copy()
        
        for middleware in self.middlewares:
            if not middleware.enabled:
                continue
            
            try:
                result = await middleware.process(current_state)
                
                if not result.success:
                    # 中间件处理失败，记录错误但继续
                    current_state["middleware_errors"] = current_state.get("middleware_errors", [])
                    current_state["middleware_errors"].append({
                        "middleware": middleware.get_name(),
                        "error": result.error,
                    })
                
                # 更新状态
                current_state.update(result.state)
                
            except Exception as e:
                # 中间件异常，记录但继续
                current_state["middleware_errors"] = current_state.get("middleware_errors", [])
                current_state["middleware_errors"].append({
                    "middleware": middleware.get_name(),
                    "exception": str(e),
                })
        
        return current_state
    
    def get_pipeline_info(self) -> List[Dict[str, Any]]:
        """
        获取管道信息
        
        Returns:
            List: 中间件列表信息
        """
        return [
            {
                "name": m.get_name(),
                "type": m.get_type().value,
                "order": m.order,
                "enabled": m.enabled,
            }
            for m in self.middlewares
        ]


# ============ 管道构建器 ============

class PipelineBuilder:
    """
    管道构建器
    
    方便构建标准化的中间件管道
    """
    
    def __init__(self):
        self.pipeline = MiddlewarePipeline()
    
    def add_thread_data(self) -> "PipelineBuilder":
        """添加线程数据中间件"""
        self.pipeline.add(ThreadDataMiddleware())
        return self
    
    def add_memory(self, memory_extractor: Optional[Callable] = None) -> "PipelineBuilder":
        """添加记忆中间件"""
        self.pipeline.add(MemoryMiddleware(memory_extractor))
        return self
    
    def add_guardrail(self, guardrail_provider: Optional[Callable] = None) -> "PipelineBuilder":
        """添加安全鉴权中间件"""
        self.pipeline.add(GuardrailMiddleware(guardrail_provider))
        return self
    
    def add_tool_error_handling(self) -> "PipelineBuilder":
        """添加工具错误处理中间件"""
        self.pipeline.add(ToolErrorHandlingMiddleware())
        return self
    
    def add_summarization(self, max_tokens: int = 8000) -> "PipelineBuilder":
        """添加上下文缩减中间件"""
        self.pipeline.add(SummarizationMiddleware(max_tokens))
        return self
    
    def add_todo_list(self) -> "PipelineBuilder":
        """添加任务列表中间件"""
        self.pipeline.add(TodoListMiddleware())
        return self
    
    def add_subagent_limit(self, max_concurrent: int = 3) -> "PipelineBuilder":
        """添加子智能体限制中间件"""
        self.pipeline.add(SubagentLimitMiddleware(max_concurrent))
        return self
    
    def add_clarification(self) -> "PipelineBuilder":
        """添加澄清拦截中间件"""
        self.pipeline.add(ClarificationMiddleware())
        return self
    
    def build(self) -> MiddlewarePipeline:
        """构建管道"""
        return self.pipeline


# ============ 导出 ============

__all__ = [
    "MiddlewareType",
    "MiddlewareResult",
    "BaseMiddleware",
    "ThreadDataMiddleware",
    "MemoryMiddleware",
    "GuardrailMiddleware",
    "ToolErrorHandlingMiddleware",
    "SummarizationMiddleware",
    "TodoListMiddleware",
    "SubagentLimitMiddleware",
    "ClarificationMiddleware",
    "MiddlewarePipeline",
    "PipelineBuilder",
]
