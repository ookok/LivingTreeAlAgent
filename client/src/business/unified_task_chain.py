"""统一任务链管理器 - 整合完整任务链"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import asyncio

@dataclass
class TaskChainResult:
    """任务链执行结果"""
    success: bool
    response: str
    steps: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0

@dataclass
class TaskChainContext:
    """任务链上下文"""
    user_id: str = "default"
    conversation_id: str = ""
    history: List[Dict[str, Any]] = field(default_factory=list)
    session_data: Dict[str, Any] = field(default_factory=dict)

class UnifiedTaskChain:
    """统一任务链管理器"""
    
    def __init__(self):
        self._intent_engine = None
        self._task_decomposer = None
        self._search_engine = None
        self._executor = None
        self._fusion_engine = None
        self._initialized = False
    
    async def initialize(self):
        """初始化任务链"""
        if self._initialized:
            return
        
        from .multi_modal_intent_engine import get_multi_modal_intent_engine, InputData, InputType
        from .adaptive_task_decomposer import get_adaptive_task_decomposer
        from .unified_search_engine import get_unified_search_engine
        from .parallel_execution_scheduler import get_parallel_execution_scheduler
        from .multi_source_fusion_engine import get_multi_source_fusion_engine
        
        self._intent_engine = get_multi_modal_intent_engine()
        self._task_decomposer = get_adaptive_task_decomposer()
        self._search_engine = get_unified_search_engine()
        self._executor = get_parallel_execution_scheduler()
        self._fusion_engine = get_multi_source_fusion_engine()
        
        await asyncio.gather(
            self._intent_engine.initialize(),
            self._task_decomposer.initialize(),
            self._search_engine.initialize(),
            self._fusion_engine.initialize()
        )
        
        self._initialized = True
    
    async def execute(self, input_text: str, context: Optional[TaskChainContext] = None) -> TaskChainResult:
        """执行完整任务链"""
        if not self._initialized:
            await self.initialize()
        
        start_time = asyncio.get_event_loop().time()
        steps = []
        
        try:
            from .multi_modal_intent_engine import InputData, InputType
            
            inputs = [InputData(
                type=InputType.TEXT,
                content=input_text,
                timestamp=start_time
            )]
            
            user_id = context.user_id if context else "default"
            
            steps.append({"step": "intent_understanding", "status": "started"})
            intent = await self._intent_engine.understand(inputs, user_id)
            steps[-1]["status"] = "completed"
            steps[-1]["result"] = {"intent_type": intent.type, "confidence": intent.confidence}
            
            steps.append({"step": "task_decomposition", "status": "started"})
            plan = await self._task_decomposer.decompose(intent, {})
            steps[-1]["status"] = "completed"
            steps[-1]["result"] = {"task_count": len(plan.tasks)}
            
            search_task = next((t for t in plan.tasks if t.type.value == "search"), None)
            
            if search_task:
                steps.append({"step": "search", "status": "started"})
                search_results = await self._search_engine.search(input_text)
                steps[-1]["status"] = "completed"
                steps[-1]["result"] = {"result_count": len(search_results)}
                
                steps.append({"step": "fusion", "status": "started"})
                fused_result = await self._fusion_engine.fuse(search_results)
                steps[-1]["status"] = "completed"
                steps[-1]["result"] = {"confidence": fused_result.confidence, "conflicts": len(fused_result.conflicts)}
                
                response = fused_result.content
            else:
                steps.append({"step": "execution", "status": "started"})
                execution_results = await self._executor.execute(plan)
                steps[-1]["status"] = "completed"
                steps[-1]["result"] = {"completed": sum(1 for r in execution_results.values() if r.success)}
                
                response = f"任务执行完成，共 {len(execution_results)} 个任务"
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            return TaskChainResult(
                success=True,
                response=response,
                steps=steps,
                metadata={
                    "intent_type": intent.type,
                    "task_count": len(plan.tasks),
                    "confidence": intent.confidence
                },
                execution_time=execution_time
            )
        
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            steps.append({"step": "error", "error": str(e)})
            
            return TaskChainResult(
                success=False,
                response=f"任务执行失败: {str(e)}",
                steps=steps,
                execution_time=execution_time
            )
    
    async def stream_execute(self, input_text: str, context: Optional[TaskChainContext] = None):
        """流式执行任务链"""
        if not self._initialized:
            await self.initialize()
        
        from .multi_modal_intent_engine import InputData, InputType
        
        inputs = [InputData(
            type=InputType.TEXT,
            content=input_text,
            timestamp=asyncio.get_event_loop().time()
        )]
        
        user_id = context.user_id if context else "default"
        
        yield {"step": "intent_understanding", "status": "started"}
        intent = await self._intent_engine.understand(inputs, user_id)
        yield {"step": "intent_understanding", "status": "completed", "result": intent.type}
        
        yield {"step": "task_decomposition", "status": "started"}
        plan = await self._task_decomposer.decompose(intent, {})
        yield {"step": "task_decomposition", "status": "completed", "result": len(plan.tasks)}
        
        yield {"step": "execution", "status": "started"}
        
        for i, task in enumerate(plan.tasks):
            yield {"step": "task", "task_id": task.id, "type": task.type.value, "status": "running"}
            
            await asyncio.sleep(0.2)
            
            yield {"step": "task", "task_id": task.id, "type": task.type.value, "status": "completed"}
        
        yield {"step": "execution", "status": "completed"}

_task_chain_instance = None

def get_unified_task_chain() -> UnifiedTaskChain:
    """获取统一任务链实例"""
    global _task_chain_instance
    if _task_chain_instance is None:
        _task_chain_instance = UnifiedTaskChain()
    return _task_chain_instance

async def execute_task_chain(input_text: str, context: Optional[TaskChainContext] = None) -> TaskChainResult:
    """执行任务链"""
    chain = get_unified_task_chain()
    return await chain.execute(input_text, context)