# -*- coding: utf-8 -*-
"""
错误恢复机制 - Error Recovery System
=====================================

功能：
1. 自动重试策略（指数退避、抖动、固定间隔）
2. 检查点保存与恢复
3. 优雅降级（降级策略、备选方案）
4. 错误分类与处理（临时/永久/未知）
5. 熔断器模式（防止雪崩）
6. 状态回滚机制

Author: Hermes Desktop Team
"""

from core.logger import get_logger
logger = get_logger('smart_writing.error_recovery')

import time
import json
import threading
import traceback
import hashlib
from typing import Optional, Callable, Dict, Any, List, Type, Union, TypeVar
from dataclasses import dataclass, field, asdict
from enum import Enum
from abc import ABC, abstractmethod
from functools import wraps
import logging
import random

try:
    from core.config.unified_config import get_config as _get_unified_config
    _uconfig_er = _get_unified_config()
except Exception:
    _uconfig_er = None

def _er_get(key: str, default):
    return _uconfig_er.get(key, default) if _uconfig_er else default

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# 错误类型枚举
# =============================================================================

class ErrorType(Enum):
    """错误类型"""
    TEMPORARY = "temporary"
    NETWORK = "network"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVICE_UNAVAILABLE = "unavailable"
    PERMANENT = "permanent"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    BAD_REQUEST = "bad_request"
    VALIDATION = "validation"
    UNKNOWN = "unknown"
    SYSTEM = "system"


class RecoveryAction(Enum):
    """恢复动作"""
    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    FALLBACK = "fallback"
    SKIP = "skip"
    ABORT = "abort"
    CHECKPOINT_RECOVERY = "checkpoint_recovery"


# =============================================================================
# 错误定义
# =============================================================================

@dataclass
class RecoverableError(Exception):
    """可恢复错误基类"""
    message: str
    error_type: ErrorType = ErrorType.UNKNOWN
    is_retryable: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_exception: Optional[Exception] = None
    
    def __str__(self) -> str:
        return self.message
    
    def to_dict(self) -> Dict:
        return {
            "message": self.message,
            "error_type": self.error_type.value,
            "is_retryable": self.is_retryable,
            "metadata": self.metadata,
        }


class NetworkError(RecoverableError):
    """网络错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message, error_type=ErrorType.NETWORK,
            is_retryable=True, **kwargs
        )


class TimeoutError(RecoverableError):
    """超时错误"""
    def __init__(self, message: str, timeout: float = 0, **kwargs):
        super().__init__(
            message=message, error_type=ErrorType.TIMEOUT,
            is_retryable=True, metadata={"timeout": timeout}, **kwargs
        )


class RateLimitError(RecoverableError):
    """限流错误"""
    def __init__(self, message: str, retry_after: float = 60, **kwargs):
        super().__init__(
            message=message, error_type=ErrorType.RATE_LIMIT,
            is_retryable=True, metadata={"retry_after": retry_after}, **kwargs
        )


class ValidationError(RecoverableError):
    """验证错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message, error_type=ErrorType.VALIDATION,
            is_retryable=False, **kwargs
        )


# =============================================================================
# 重试策略
# =============================================================================

@dataclass
class RetryPolicy:
    """重试策略配置"""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: float = 0.1
    retryable_errors: List[ErrorType] = field(default_factory=lambda: [
        ErrorType.TEMPORARY, ErrorType.NETWORK, ErrorType.TIMEOUT,
        ErrorType.RATE_LIMIT, ErrorType.SERVICE_UNAVAILABLE,
    ])
    total_timeout: float = 300.0
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False
        
        if isinstance(error, RecoverableError):
            return error.is_retryable and error.error_type in self.retryable_errors
        return True
    
    def get_delay(self, attempt: int, error: Optional[Exception] = None) -> float:
        delay = self.initial_delay * (self.exponential_base ** attempt)
        
        if isinstance(error, RateLimitError):
            retry_after = error.metadata.get("retry_after", self.initial_delay)
            delay = max(delay, retry_after)
        
        delay = min(delay, self.max_delay)
        
        if self.jitter > 0:
            jitter_range = delay * self.jitter
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


# =============================================================================
# 检查点系统
# =============================================================================

@dataclass
class Checkpoint:
    """检查点"""
    checkpoint_id: str
    task_id: str
    step_index: int
    step_name: str
    data: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    version: str = "1.0"
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Checkpoint":
        return cls(**data)


class CheckpointManager:
    """检查点管理器"""
    
    def __init__(self, storage_path: Optional[str] = None):
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._lock = threading.Lock()
        self._storage_path = storage_path
        if storage_path:
            self._load_from_disk()
    
    def save(self, checkpoint: Checkpoint) -> str:
        with self._lock:
            self._checkpoints[checkpoint.checkpoint_id] = checkpoint
            if self._storage_path:
                self._save_to_disk(checkpoint)
            logger.info(f"保存检查点: {checkpoint.checkpoint_id}")
            return checkpoint.checkpoint_id
    
    def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        with self._lock:
            return self._checkpoints.get(checkpoint_id)
    
    def get_latest(self, task_id: str) -> Optional[Checkpoint]:
        with self._lock:
            task_checkpoints = [cp for cp in self._checkpoints.values() if cp.task_id == task_id]
            if not task_checkpoints:
                return None
            return max(task_checkpoints, key=lambda cp: cp.created_at)
    
    def list_task_checkpoints(self, task_id: str) -> List[Checkpoint]:
        with self._lock:
            checkpoints = [cp for cp in self._checkpoints.values() if cp.task_id == task_id]
            return sorted(checkpoints, key=lambda cp: cp.created_at)
    
    def delete(self, checkpoint_id: str) -> bool:
        with self._lock:
            if checkpoint_id in self._checkpoints:
                del self._checkpoints[checkpoint_id]
                return True
            return False
    
    def delete_task_checkpoints(self, task_id: str) -> int:
        with self._lock:
            to_delete = [cp.checkpoint_id for cp in self._checkpoints.values() if cp.task_id == task_id]
            for cid in to_delete:
                del self._checkpoints[cid]
            return len(to_delete)
    
    def cleanup(self, max_age: float = 86400) -> int:
        with self._lock:
            now = time.time()
            to_delete = [cp.checkpoint_id for cp in self._checkpoints.values() if now - cp.created_at > max_age]
            for cid in to_delete:
                del self._checkpoints[cid]
            return len(to_delete)
    
    def _save_to_disk(self, checkpoint: Checkpoint):
        import os
        try:
            os.makedirs(self._storage_path, exist_ok=True)
            path = os.path.join(self._storage_path, f"{checkpoint.checkpoint_id}.json")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存检查点失败: {e}")
    
    def _load_from_disk(self):
        import os
        try:
            os.makedirs(self._storage_path, exist_ok=True)
            for filename in os.listdir(self._storage_path):
                if filename.endswith('.json'):
                    path = os.path.join(self._storage_path, filename)
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        cp = Checkpoint.from_dict(data)
                        self._checkpoints[cp.checkpoint_id] = cp
        except Exception as e:
            logger.error(f"加载检查点失败: {e}")


# =============================================================================
# 熔断器
# =============================================================================

@dataclass
class CircuitBreakerState:
    """熔断器状态"""
    is_open: bool = False
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0
    last_success_time: float = 0
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0


class CircuitBreaker:
    """熔断器"""
    
    def __init__(self, name: str, failure_threshold: int = 5, success_threshold: int = 2, timeout: float = 60.0):
        self.name = name
        self.state = CircuitBreakerState(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout,
        )
        self._lock = threading.Lock()
    
    @property
    def is_open(self) -> bool:
        with self._lock:
            if not self.state.is_open:
                return False
            if time.time() - self.state.last_failure_time >= self.state.timeout:
                self.state.is_open = False
                self.state.success_count = 0
                logger.info(f"CircuitBreaker [{self.name}] 进入半开状态")
                return False
            return True
    
    def record_success(self):
        with self._lock:
            self.state.success_count += 1
            self.state.last_success_time = time.time()
            if self.state.success_count >= self.state.success_threshold:
                self.state.is_open = False
                self.state.failure_count = 0
                self.state.success_count = 0
                logger.info(f"CircuitBreaker [{self.name}] 关闭")
    
    def record_failure(self):
        with self._lock:
            self.state.failure_count += 1
            self.state.last_failure_time = time.time()
            if self.state.failure_count >= self.state.failure_threshold:
                self.state.is_open = True
                logger.warning(f"CircuitBreaker [{self.name}] 打开")
    
    def reset(self):
        with self._lock:
            self.state = CircuitBreakerState(
                failure_threshold=self.state.failure_threshold,
                success_threshold=self.state.success_threshold,
                timeout=self.state.timeout,
            )


# =============================================================================
# 降级策略
# =============================================================================

class FallbackStrategy(ABC):
    """降级策略基类"""
    @abstractmethod
    def execute(self, error: Exception, context: Dict) -> Any:
        pass


class ReturnNoneFallback(FallbackStrategy):
    def execute(self, error: Exception, context: Dict) -> Any:
        return None


class ReturnDefaultFallback(FallbackStrategy):
    def __init__(self, default_value: Any):
        self.default_value = default_value
    def execute(self, error: Exception, context: Dict) -> Any:
        return self.default_value


class FallbackChain:
    """降级策略链"""
    def __init__(self):
        self._strategies: List[FallbackStrategy] = []
    
    def add(self, strategy: FallbackStrategy) -> "FallbackChain":
        self._strategies.append(strategy)
        return self
    
    def execute(self, error: Exception, context: Dict) -> Any:
        for strategy in self._strategies:
            try:
                result = strategy.execute(error, context)
                if result is not None:
                    return result
            except Exception as e:
                logger.warning(f"降级策略执行失败: {e}")
        return None


# =============================================================================
# 恢复上下文
# =============================================================================

@dataclass
class RecoveryContext:
    """恢复上下文"""
    task_id: str
    operation_name: str
    attempt: int = 0
    max_attempts: int = 3
    start_time: float = field(default_factory=time.time)
    checkpoint: Optional[Checkpoint] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time


# =============================================================================
# 恢复执行器
# =============================================================================

class RecoveryExecutor:
    """恢复执行器"""
    
    def __init__(self, retry_policy: Optional[RetryPolicy] = None, checkpoint_manager: Optional[CheckpointManager] = None):
        self.retry_policy = retry_policy or RetryPolicy()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
    
    def execute(
        self, func: Callable[..., T], *args,
        task_id: str = "default", operation_name: str = "operation",
        checkpoint_enabled: bool = True, fallback: Optional[FallbackStrategy] = None,
        on_retry: Optional[Callable[[Exception, int], None]] = None, **kwargs,
    ) -> T:
        context = RecoveryContext(task_id=task_id, operation_name=operation_name, max_attempts=self.retry_policy.max_retries)
        
        if checkpoint_enabled:
            latest_cp = self.checkpoint_manager.get_latest(task_id)
            if latest_cp:
                context.checkpoint = latest_cp
        
        last_error = None
        
        while context.attempt < self.retry_policy.max_retries:
            try:
                exec_kwargs = kwargs.copy()
                if context.checkpoint:
                    exec_kwargs["_checkpoint"] = context.checkpoint.data
                result = func(*args, **exec_kwargs)
                if checkpoint_enabled:
                    self._save_checkpoint(context, result)
                return result
            except Exception as e:
                last_error = e
                context.attempt += 1
                
                if not self.retry_policy.should_retry(e, context.attempt):
                    break
                
                cb = self._get_circuit_breaker(operation_name)
                if cb.is_open:
                    break
                
                if on_retry:
                    on_retry(e, context.attempt)
                
                delay = self.retry_policy.get_delay(context.attempt, e)
                logger.info(f"重试 {context.attempt}/{self.retry_policy.max_retries}, 延迟 {delay:.1f}s")
                time.sleep(delay)
                cb.record_failure()
        
        if fallback:
            try:
                return fallback.execute(last_error, {"task_id": task_id, "operation": operation_name})
            except Exception as e:
                logger.error(f"降级失败: {e}")
        
        if isinstance(last_error, RecoverableError):
            raise last_error
        raise RecoverableError(message=str(last_error), original_exception=last_error)
    
    def _save_checkpoint(self, context: RecoveryContext, result: Any):
        import hashlib

        cp_id = hashlib.md5(f"{context.task_id}:{context.operation_name}:{time.time()}".encode()).hexdigest()[:16]
        checkpoint = Checkpoint(
            checkpoint_id=cp_id, task_id=context.task_id, step_index=context.attempt,
            step_name=context.operation_name, data={"result_preview": str(result)[:1000] if result else {}},
        )
        self.checkpoint_manager.save(checkpoint)
    
    def _get_circuit_breaker(self, name: str) -> CircuitBreaker:
        with self._lock:
            if name not in self._circuit_breakers:
                self._circuit_breakers[name] = CircuitBreaker(name)
            return self._circuit_breakers[name]


# =============================================================================
# 全局实例
# =============================================================================

_recovery_executor: Optional[RecoveryExecutor] = None
_checkpoint_manager: Optional[CheckpointManager] = None


def get_recovery_executor() -> RecoveryExecutor:
    global _recovery_executor
    if _recovery_executor is None:
        _recovery_executor = RecoveryExecutor()
    return _recovery_executor


def get_checkpoint_manager() -> CheckpointManager:
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    logger.info("=== 测试错误恢复机制 ===\n")
    
    logger.info("1. 测试重试机制:")
    attempt_count = 0
    
    def unreliable_function():
        global attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise NetworkError(f"网络错误 (尝试 {attempt_count})")
        return "成功!"
    
    executor = get_recovery_executor()
    executor.retry_policy.max_retries = 5
    executor.retry_policy.initial_delay = 0.1
    
    result = executor.execute(unreliable_function, task_id="test1", operation_name="unreliable_call")
    logger.info(f"结果: {result}, 总尝试次数: {attempt_count}\n")
    
    logger.info("2. 测试检查点:")
    cp_manager = get_checkpoint_manager()
    cp = Checkpoint(checkpoint_id="test_cp_1", task_id="test_task", step_index=1, step_name="step1", data={"key": "value"})
    cp_manager.save(cp)
    loaded = cp_manager.get_latest("test_task")
    logger.info(f"加载检查点: {loaded.step_name if loaded else 'None'}\n")
    
    logger.info("3. 测试熔断器:")
    cb = CircuitBreaker("test_service", failure_threshold=3, timeout=2)
    for i in range(5):
        cb.record_failure()
        logger.info(f"  尝试 {i+1}: is_open={cb.is_open}")
    time.sleep(2.5)
    logger.info(f"  超时后: is_open={cb.is_open}")
    
    logger.info("\n完成!")
