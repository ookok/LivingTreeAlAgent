"""
优化钩子管理器 (Optimization Hook Manager)
=========================================

实现系统级优化钩子，自动拦截所有模型调用：
1. 模型调用拦截 - 自动注入优化逻辑
2. 上下文自动收集 - 透明收集调用上下文
3. 优化效果追踪 - 实时监控优化效果
4. 动态开关控制 - 随时开启/关闭优化

核心特性：
- 透明拦截，无需修改现有代码
- 自动收集上下文信息
- 实时优化效果追踪
- 支持动态开关

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import asyncio
import functools
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class HookPoint(Enum):
    """钩子点"""
    MODEL_CALL = "model_call"
    PROMPT_GENERATION = "prompt_generation"
    RESPONSE_RECEIVED = "response_received"
    CONTEXT_BUILD = "context_build"


class HookPriority(Enum):
    """钩子优先级"""
    LOW = 10
    NORMAL = 50
    HIGH = 100


@dataclass
class HookContext:
    """钩子上下文"""
    hook_point: HookPoint
    timestamp: float
    prompt: Optional[str] = None
    response: Optional[str] = None
    model_type: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    """钩子执行结果"""
    success: bool
    modified_prompt: Optional[str] = None
    modified_response: Optional[str] = None
    optimization_metadata: Dict[str, Any] = field(default_factory=dict)


class OptimizationHookManager:
    """
    优化钩子管理器
    
    功能：
    1. 注册优化钩子
    2. 拦截模型调用
    3. 自动收集上下文
    4. 执行优化逻辑
    5. 追踪优化效果
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 钩子注册表
        self._hooks: Dict[HookPoint, List[Tuple[HookPriority, Callable]]] = {
            hook: [] for hook in HookPoint
        }
        
        # 优化引擎（延迟加载）
        self._optimization_engine = None
        
        # 全局开关
        self._enabled = False
        
        # 统计信息
        self._stats = {
            "hooks_executed": 0,
            "optimizations_applied": 0,
            "tokens_saved": 0,
            "cost_saved": 0.0,
        }
        
        # 已注册的模型包装器
        self._wrapped_models = {}
        
        self._initialized = True
        logger.info("[OptimizationHookManager] 优化钩子管理器初始化完成")
    
    def enable(self):
        """启用优化钩子"""
        self._enabled = True
        logger.info("[OptimizationHookManager] 优化钩子已启用")
    
    def disable(self):
        """禁用优化钩子"""
        self._enabled = False
        logger.info("[OptimizationHookManager] 优化钩子已禁用")
    
    def is_enabled(self) -> bool:
        """检查是否启用"""
        return self._enabled
    
    def register_hook(self, hook_point: HookPoint, callback: Callable, priority: HookPriority = HookPriority.NORMAL):
        """
        注册钩子
        
        Args:
            hook_point: 钩子点
            callback: 回调函数
            priority: 优先级
        """
        self._hooks[hook_point].append((priority, callback))
        # 按优先级排序
        self._hooks[hook_point].sort(key=lambda x: x[0].value, reverse=True)
        logger.info(f"[OptimizationHookManager] 注册钩子: {hook_point.value}, 优先级: {priority.value}")
    
    def unregister_hook(self, hook_point: HookPoint, callback: Callable):
        """
        注销钩子
        
        Args:
            hook_point: 钩子点
            callback: 回调函数
        """
        self._hooks[hook_point] = [
            (p, c) for p, c in self._hooks[hook_point]
            if c != callback
        ]
    
    async def execute_hooks(self, hook_point: HookPoint, context: HookContext) -> HookResult:
        """
        执行指定钩子点的所有钩子
        
        Args:
            hook_point: 钩子点
            context: 钩子上下文
            
        Returns:
            钩子执行结果
        """
        if not self._enabled:
            return HookResult(success=True)
        
        self._stats["hooks_executed"] += 1
        
        result = HookResult(success=True)
        current_context = context
        
        for priority, callback in self._hooks[hook_point]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    hook_result = await callback(current_context)
                else:
                    hook_result = callback(current_context)
                
                if hook_result.success:
                    # 更新上下文
                    if hook_result.modified_prompt is not None:
                        current_context.prompt = hook_result.modified_prompt
                        result.modified_prompt = hook_result.modified_prompt
                    
                    if hook_result.modified_response is not None:
                        current_context.response = hook_result.modified_response
                        result.modified_response = hook_result.modified_response
                    
                    if hook_result.optimization_metadata:
                        result.optimization_metadata.update(hook_result.optimization_metadata)
                        self._stats["optimizations_applied"] += 1
                        self._stats["tokens_saved"] += hook_result.optimization_metadata.get("tokens_saved", 0)
                        self._stats["cost_saved"] += hook_result.optimization_metadata.get("cost_saved", 0.0)
                
            except Exception as e:
                logger.error(f"[OptimizationHookManager] 钩子执行失败: {e}")
        
        return result
    
    def wrap_model_call(self, model_callable: Callable, model_type: str = "claude-3-sonnet") -> Callable:
        """
        包装模型调用函数，自动注入优化逻辑
        
        Args:
            model_callable: 原始模型调用函数
            model_type: 模型类型
            
        Returns:
            包装后的函数
        """
        @functools.wraps(model_callable)
        async def async_wrapper(prompt: str, **kwargs) -> Tuple[str, Dict[str, Any]]:
            return await self._execute_model_call(model_callable, prompt, model_type, kwargs)
        
        @functools.wraps(model_callable)
        def sync_wrapper(prompt: str, **kwargs) -> Tuple[str, Dict[str, Any]]:
            result = model_callable(prompt, **kwargs)
            # 如果返回的是协程，需要特殊处理
            if asyncio.iscoroutine(result):
                return asyncio.run(self._execute_model_call(model_callable, prompt, model_type, kwargs))
            return result, {}
        
        # 检查是否是异步函数
        if asyncio.iscoroutinefunction(model_callable):
            return async_wrapper
        else:
            return sync_wrapper
    
    async def _execute_model_call(self, model_callable: Callable, prompt: str, model_type: str, kwargs: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        执行带优化的模型调用
        
        Args:
            model_callable: 模型调用函数
            prompt: 提示词
            model_type: 模型类型
            kwargs: 额外参数
            
        Returns:
            (响应, 元数据)
        """
        # 1. 执行上下文构建钩子
        context = HookContext(
            hook_point=HookPoint.CONTEXT_BUILD,
            timestamp=asyncio.get_event_loop().time(),
            prompt=prompt,
            model_type=model_type,
            context=kwargs.get("context", {}),
        )
        await self.execute_hooks(HookPoint.CONTEXT_BUILD, context)
        
        # 2. 执行提示词生成钩子
        context.hook_point = HookPoint.PROMPT_GENERATION
        prompt_result = await self.execute_hooks(HookPoint.PROMPT_GENERATION, context)
        
        optimized_prompt = prompt_result.modified_prompt or prompt
        
        # 3. 使用智能优化引擎执行优化调用
        if self._optimization_engine is None:
            self._lazy_load_engine()
        
        if self._optimization_engine:
            response, optimization_metadata = await self._optimization_engine.optimize_and_call(
                optimized_prompt,
                model_callable,
                model_type=model_type,
                **kwargs
            )
        else:
            # 降级到直接调用
            response = await model_callable(optimized_prompt, **kwargs) if asyncio.iscoroutinefunction(model_callable) else model_callable(optimized_prompt, **kwargs)
            optimization_metadata = {}
        
        # 4. 执行响应接收钩子
        context.hook_point = HookPoint.RESPONSE_RECEIVED
        context.response = response
        response_result = await self.execute_hooks(HookPoint.RESPONSE_RECEIVED, context)
        
        final_response = response_result.modified_response or response
        
        # 5. 合并元数据
        metadata = {
            "optimization_metadata": optimization_metadata,
            "prompt_optimized": optimized_prompt != prompt,
            "response_modified": final_response != response,
        }
        
        return final_response, metadata
    
    def _lazy_load_engine(self):
        """延迟加载优化引擎"""
        try:
            from business.intelligent_optimization_engine import get_intelligent_optimization_engine
            self._optimization_engine = get_intelligent_optimization_engine()
            logger.info("[OptimizationHookManager] 智能优化引擎加载完成")
        except Exception as e:
            logger.error(f"[OptimizationHookManager] 加载优化引擎失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "hooks_executed": 0,
            "optimizations_applied": 0,
            "tokens_saved": 0,
            "cost_saved": 0.0,
        }
        logger.info("[OptimizationHookManager] 统计信息已重置")


# 便捷函数
def get_hook_manager() -> OptimizationHookManager:
    """获取钩子管理器单例"""
    return OptimizationHookManager()


# 装饰器：用于标记需要优化的模型调用
def optimized_model_call(model_type: str = "claude-3-sonnet"):
    """
    装饰器：标记需要优化的模型调用
    
    使用方式：
    @optimized_model_call(model_type="claude-3-sonnet")
    async def my_model_call(prompt: str, **kwargs):
        # 模型调用逻辑
        pass
    """
    def decorator(func: Callable) -> Callable:
        hook_manager = get_hook_manager()
        return hook_manager.wrap_model_call(func, model_type)
    return decorator


__all__ = [
    "HookPoint",
    "HookPriority",
    "HookContext",
    "HookResult",
    "OptimizationHookManager",
    "get_hook_manager",
    "optimized_model_call",
]
