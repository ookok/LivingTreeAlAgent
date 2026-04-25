"""
意图执行器 - 执行解析后的意图
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"          # 待执行
    RUNNING = "running"          # 执行中
    SUCCESS = "success"          # 成功
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"      # 已取消
    TIMEOUT = "timeout"          # 超时


@dataclass
class ExecutionResult:
    """执行结果"""
    status: ExecutionStatus = ExecutionStatus.PENDING
    output: Any = None                       # 执行输出
    error: Optional[str] = None               # 错误信息
    execution_time: float = 0.0                # 执行时间(秒)
    tokens_used: int = 0                      # 使用的Token
    steps: List[Dict[str, Any]] = field(default_factory=list)  # 执行步骤


class IntentExecutor:
    """
    意图执行器
    
    功能：
    1. 意图执行流程管理
    2. 多步骤任务执行
    3. 错误处理和重试
    4. 执行状态追踪
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._init_executors()
        self._init_handlers()
        
    def _init_executors(self):
        """初始化执行器配置"""
        self.max_retries = self.config.get('max_retries', 3)
        self.timeout = self.config.get('timeout', 300)  # 5分钟超时
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    def _init_handlers(self):
        """初始化意图处理器"""
        self.handlers: Dict[str, Callable] = {}
        
    def register_handler(self, intent_type: str, handler: Callable):
        """注册意图处理器"""
        self.handlers[intent_type] = handler
        
    async def execute(self, intent: 'ParsedIntent', category: 'IntentCategory') -> ExecutionResult:
        """
        执行意图
        
        Args:
            intent: 解析后的意图
            category: 意图分类
            
        Returns:
            ExecutionResult: 执行结果
        """
        import time
        start_time = time.time()
        
        result = ExecutionResult()
        result.status = ExecutionStatus.RUNNING
        
        try:
            # 1. 获取处理器
            handler = self._get_handler(intent.intent_type.value)
            
            # 2. 准备执行上下文
            context = {
                'intent': intent,
                'category': category,
                'config': self.config,
            }
            
            # 3. 执行处理
            if asyncio.iscoroutinefunction(handler):
                output = await asyncio.wait_for(
                    handler(context),
                    timeout=self.timeout
                )
            else:
                output = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda: handler(context)
                )
                
            # 4. 更新结果
            result.status = ExecutionStatus.SUCCESS
            result.output = output
            result.execution_time = time.time() - start_time
            
        except asyncio.TimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error = f"Execution timeout after {self.timeout}s"
            result.execution_time = time.time() - start_time
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            result.execution_time = time.time() - start_time
            
        return result
    
    def _get_handler(self, intent_type: str) -> Callable:
        """获取意图处理器"""
        handler = self.handlers.get(intent_type)
        if handler:
            return handler
            
        # 返回默认处理器
        return self._default_handler
        
    async def _default_handler(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """默认处理器"""
        intent = context['intent']
        return {
            'message': f"Intent type: {intent.intent_type.value}",
            'entities': intent.entities,
            'parameters': intent.parameters,
        }
    
    def add_step(self, result: ExecutionResult, step_name: str, step_data: Any):
        """添加执行步骤"""
        result.steps.append({
            'name': step_name,
            'data': step_data,
        })
