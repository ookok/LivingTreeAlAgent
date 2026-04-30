"""
熔断机制 - 分层熔断保护各层服务
"""

import asyncio
import time
from enum import Enum
from typing import Callable, Any, Dict, Optional


class BreakerState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open" # 半开状态（尝试恢复）


class CircuitBreaker:
    """单个熔断器"""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 30):
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0
        self._success_count = 0
        self._success_threshold = 3  # 连续成功次数阈值
    
    def is_open(self) -> bool:
        """检查熔断器是否打开"""
        if self._state == BreakerState.OPEN:
            # 检查是否可以尝试恢复
            if time.time() - self._last_failure_time >= self._reset_timeout:
                self._state = BreakerState.HALF_OPEN
                return False
            return True
        return False
    
    def record_success(self):
        """记录成功"""
        if self._state == BreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._success_threshold:
                self._state = BreakerState.CLOSED
                self._failure_count = 0
                self._success_count = 0
        else:
            self._failure_count = 0
    
    def record_failure(self):
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        self._success_count = 0
        
        if self._failure_count >= self._failure_threshold:
            self._state = BreakerState.OPEN
    
    def get_state(self) -> BreakerState:
        """获取当前状态"""
        return self._state


class LayeredCircuitBreaker:
    """分层熔断机制 - 保护各层服务"""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {
            "L0": CircuitBreaker(failure_threshold=5, reset_timeout=30),  # 基础设施层
            "L1": CircuitBreaker(failure_threshold=3, reset_timeout=20),  # 数据存储层
            "L2": CircuitBreaker(failure_threshold=4, reset_timeout=25),  # 服务逻辑层
            "L3": CircuitBreaker(failure_threshold=2, reset_timeout=15),  # 应用业务层
            "L4": CircuitBreaker(failure_threshold=10, reset_timeout=60)   # 表现交互层
        }
    
    async def execute_with_fallback(self, layer: str, func: Callable, fallback: Callable) -> Any:
        """执行带熔断保护的操作"""
        breaker = self._breakers.get(layer)
        if not breaker:
            return await func()
        
        if breaker.is_open():
            return fallback()
        
        try:
            result = await func()
            breaker.record_success()
            return result
        except Exception as e:
            breaker.record_failure()
            if breaker.is_open():
                return fallback()
            raise
    
    def get_layer_state(self, layer: str) -> Optional[BreakerState]:
        """获取指定层的状态"""
        breaker = self._breakers.get(layer)
        return breaker.get_state() if breaker else None
    
    def get_all_states(self) -> Dict[str, str]:
        """获取所有层的状态"""
        return {layer: breaker.get_state().value for layer, breaker in self._breakers.items()}


def get_circuit_breaker() -> LayeredCircuitBreaker:
    """获取分层熔断单例"""
    if not hasattr(get_circuit_breaker, '_instance'):
        get_circuit_breaker._instance = LayeredCircuitBreaker()
    return get_circuit_breaker._instance