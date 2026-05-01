"""
稳定性与性能优化模块自动初始化器
"""

import asyncio
from typing import Dict, Any


class StabilityManager:
    """稳定性管理器 - 统一管理所有稳定性和性能优化模块"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 延迟导入避免循环依赖
        from .circuit_breaker import get_circuit_breaker
        from .health_monitor import get_health_monitor
        from .graceful_degradation import get_degradation_manager
        from .intent_management.intelligent_cache import get_intelligent_cache_system as get_cache_manager
        from .priority_task_queue import get_task_queue
        from .distributed_tracer import get_tracer
        from .smart_profiler import get_profiler
        from .adaptive_resource_scheduler import get_resource_scheduler
        
        # 初始化所有模块
        self._circuit_breaker = get_circuit_breaker()
        self._health_monitor = get_health_monitor()
        self._degradation_manager = get_degradation_manager()
        self._cache_manager = get_cache_manager()
        self._task_queue = get_task_queue()
        self._tracer = get_tracer()
        self._profiler = get_profiler()
        self._resource_scheduler = get_resource_scheduler()
        
        self._initialized = True
    
    @property
    def circuit_breaker(self):
        return self._circuit_breaker
    
    @property
    def health_monitor(self):
        return self._health_monitor
    
    @property
    def degradation_manager(self):
        return self._degradation_manager
    
    @property
    def cache_manager(self):
        return self._cache_manager
    
    @property
    def task_queue(self):
        return self._task_queue
    
    @property
    def tracer(self):
        return self._tracer
    
    @property
    def profiler(self):
        return self._profiler
    
    @property
    def resource_scheduler(self):
        return self._resource_scheduler
    
    async def start_all(self):
        """启动所有服务"""
        # 启动健康监控
        self._health_monitor.start_monitoring()
        
        # 启动任务队列工作线程
        self._task_queue.start_workers()
        
        # 初始化缓存预热（可根据上下文调整）
        self._cache_manager.warm_up({
            "user_type": "general",
            "usage_pattern": {}
        })
        
        return {
            "circuit_breaker": "started",
            "health_monitor": "started",
            "degradation_manager": "started",
            "cache_manager": "started",
            "task_queue": "started",
            "tracer": "started",
            "profiler": "started",
            "resource_scheduler": "started"
        }
    
    async def stop_all(self):
        """停止所有服务"""
        self._health_monitor.stop_monitoring()
        self._task_queue.stop_workers()
        
        return {
            "circuit_breaker": "stopped",
            "health_monitor": "stopped",
            "degradation_manager": "stopped",
            "cache_manager": "stopped",
            "task_queue": "stopped",
            "tracer": "stopped",
            "profiler": "stopped",
            "resource_scheduler": "stopped"
        }
    
    def get_status(self) -> Dict[str, Any]:
        """获取所有模块状态"""
        return {
            "circuit_breaker": self._circuit_breaker.get_all_states(),
            "degradation_level": self._degradation_manager.get_degradation_level(),
            "cache_stats": self._cache_manager.get_stats(),
            "queue_sizes": self._task_queue.get_queue_sizes(),
            "resource_status": self._resource_scheduler.get_resource_status()
        }


# 创建全局实例
stability = StabilityManager()


# 便捷装饰器
def with_circuit_breaker(layer: str = "L2"):
    """熔断保护装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            async def execute():
                return await func(*args, **kwargs)
            
            def fallback():
                return None
            
            return await stability.circuit_breaker.execute_with_fallback(
                layer, execute, fallback
            )
        return wrapper
    return decorator


def with_profiling(operation: str):
    """性能分析装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await stability.profiler.profile(operation, func, *args, **kwargs)
        return wrapper
    return decorator


def with_tracing(operation_name: str):
    """分布式追踪装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await stability.tracer.trace_execution(operation_name, func, *args, **kwargs)
        return wrapper
    return decorator


def cached(key_prefix: str, ttl: int = 300):
    """缓存装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"
            return await stability.cache_manager.get_or_compute(key, lambda: func(*args, **kwargs), ttl)
        return wrapper
    return decorator


def submit_task(task, priority: int = 2):
    """提交任务到优先级队列"""
    stability.task_queue.submit_task(task, priority)