# -*- coding: utf-8 -*-
"""
fault_tolerance.py — 故障容错管理

提供驱动级别的故障转移、健康检查和降级策略。

核心概念：
  - 降级策略：当高优先级驱动不可用时，自动切换到备用驱动
  - 健康检查：定期探测驱动可用性
  - 熔断器：连续失败超过阈值时自动熔断
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .base import (
    ChatRequest, ChatResponse,
    CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    StreamChunk, ModelDriver, DriverMode, DriverState,
    HealthReport,
)

logger = logging.getLogger(__name__)


# ── 降级策略 ──────────────────────────────────────────────────────

class DegradationStrategy(Enum):
    """
    降级策略枚举

    定义驱动故障时的降级路径：
      - CLOUD_FIRST: 优先云端 → 本地服务 → 硬加载
      - LOCAL_FIRST: 优先本地服务 → 硬加载 → 云端
      - HARD_LOAD_FIRST: 优先硬加载 → 本地服务 → 云端
      - HARD_LOAD_ONLY: 仅硬加载（离线模式）
      - LOCAL_ONLY: 仅本地服务（无外网模式）
    """
    CLOUD_FIRST = "cloud_first"
    LOCAL_FIRST = "local_first"
    HARD_LOAD_FIRST = "hard_load_first"
    HARD_LOAD_ONLY = "hard_load_only"
    LOCAL_ONLY = "local_only"

    @property
    def fallback_order(self) -> List[DriverMode]:
        """获取降级顺序"""
        mapping = {
            self.CLOUD_FIRST: [
                DriverMode.CLOUD_SERVICE,
                DriverMode.LOCAL_SERVICE,
                DriverMode.HARD_LOAD,
            ],
            self.LOCAL_FIRST: [
                DriverMode.LOCAL_SERVICE,
                DriverMode.HARD_LOAD,
                DriverMode.CLOUD_SERVICE,
            ],
            self.HARD_LOAD_FIRST: [
                DriverMode.HARD_LOAD,
                DriverMode.LOCAL_SERVICE,
                DriverMode.CLOUD_SERVICE,
            ],
            self.HARD_LOAD_ONLY: [DriverMode.HARD_LOAD],
            self.LOCAL_ONLY: [DriverMode.LOCAL_SERVICE, DriverMode.HARD_LOAD],
        }
        return mapping[self]


# ── 熔断器 ──────────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED = "closed"       # 正常（允许请求）
    OPEN = "open"           # 熔断（拒绝请求）
    HALF_OPEN = "half_open" # 半开（允许少量探测请求）


@dataclass
class CircuitBreaker:
    """
    熔断器

    状态转换：
      CLOSED --(连续失败>=threshold)--> OPEN
      OPEN --(等待 recovery_timeout)--> HALF_OPEN
      HALF_OPEN --(探测成功)--> CLOSED
      HALF_OPEN --(探测失败)--> OPEN
    """
    name: str
    failure_threshold: int = 3          # 连续失败阈值
    recovery_timeout: float = 30.0      # 熔断恢复超时（秒）
    half_open_max_calls: int = 1        # 半开状态最大探测次数

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_open(self) -> bool:
        """是否处于熔断状态"""
        if self._state == CircuitState.OPEN:
            # 检查是否可以转为半开
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
                return False
            return True
        return False

    def allow_request(self) -> bool:
        """是否允许请求通过"""
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        return False  # OPEN

    def record_success(self) -> None:
        """记录成功"""
        if self._state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.CLOSED)
        self._failure_count = 0
        self._success_count += 1

    def record_failure(self) -> None:
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.OPEN)
        elif self._failure_count >= self.failure_threshold:
            self._transition(CircuitState.OPEN)

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
        logger.info(f"[CircuitBreaker/{self.name}] {old.value} -> {new_state.value}")

    def reset(self) -> None:
        """重置熔断器"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker name={self.name!r} "
            f"state={self._state.value} failures={self._failure_count}>"
        )


# ── 故障容错管理器 ──────────────────────────────────────────────

class FaultToleranceManager:
    """
    故障容错管理器

    集成熔断器和降级策略，为 Gateway 提供故障转移能力。
    """

    def __init__(
        self,
        strategy: DegradationStrategy = DegradationStrategy.LOCAL_FIRST,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        health_check_interval: float = 60.0,
    ):
        self.strategy = strategy
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._drivers: Dict[str, ModelDriver] = {}  # name -> driver
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._health_check_interval = health_check_interval
        self._health_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._on_degradation: Optional[Callable] = None

    @property
    def fallback_order(self) -> List[DriverMode]:
        return self.strategy.fallback_order

    # ── 驱动管理 ─────────────────────────────────────────────

    def register_driver(self, driver: ModelDriver) -> None:
        """注册驱动并创建熔断器"""
        self._drivers[driver.name] = driver
        self._breakers[driver.name] = CircuitBreaker(
            name=driver.name,
            failure_threshold=self._failure_threshold,
            recovery_timeout=self._recovery_timeout,
        )
        logger.info(f"[FTM] registered driver: {driver.name}")

    def unregister_driver(self, name: str) -> None:
        """注销驱动"""
        self._drivers.pop(name, None)
        self._breakers.pop(name, None)

    def get_breaker(self, name: str) -> Optional[CircuitBreaker]:
        return self._breakers.get(name)

    # ── 故障转移调用 ─────────────────────────────────────────

    def safe_chat(
        self,
        request: ChatRequest,
        drivers: List[ModelDriver],
    ) -> ChatResponse:
        """
        带故障转移的对话

        按降级策略依次尝试驱动，跳过熔断/不健康的驱动。
        """
        errors = []

        # 按降级策略排序驱动
        sorted_drivers = self._sort_by_strategy(drivers)

        for driver in sorted_drivers:
            breaker = self._breakers.get(driver.name)
            if breaker and breaker.is_open:
                errors.append(f"{driver.name}: circuit open")
                continue

            if driver.state != DriverState.READY:
                errors.append(f"{driver.name}: state={driver.state.value}")
                continue

            # 执行请求
            try:
                resp = driver.chat(request)
                if resp.error:
                    if breaker:
                        breaker.record_failure()
                    errors.append(f"{driver.name}: {resp.error}")
                    continue
                # 成功
                if breaker:
                    breaker.record_success()
                return resp
            except Exception as e:
                if breaker:
                    breaker.record_failure()
                errors.append(f"{driver.name}: {e}")
                continue

        # 所有驱动失败
        error_msg = f"All drivers failed: {'; '.join(errors)}"
        logger.warning(f"[FTM] {error_msg}")
        return ChatResponse(error=error_msg)

    def safe_chat_stream(
        self,
        request: ChatRequest,
        drivers: List[ModelDriver],
    ):
        """带故障转移的流式对话"""
        sorted_drivers = self._sort_by_strategy(drivers)

        for driver in sorted_drivers:
            breaker = self._breakers.get(driver.name)
            if breaker and breaker.is_open:
                continue
            if driver.state != DriverState.READY:
                continue

            has_content = False
            try:
                for chunk in driver.chat_stream(request):
                    if chunk.error:
                        if breaker:
                            breaker.record_failure()
                        break
                    has_content = True
                    yield chunk
                    if chunk.done:
                        if breaker:
                            breaker.record_success()
                        return
                if has_content and not chunk.done:
                    yield StreamChunk(done=True)
                    if breaker:
                        breaker.record_success()
                    return
            except Exception as e:
                if breaker:
                    breaker.record_failure()
                continue

        yield StreamChunk(error="All drivers failed", done=True)

    def safe_complete(
        self,
        request: CompletionRequest,
        drivers: List[ModelDriver],
    ) -> CompletionResponse:
        """带故障转移的补全"""
        sorted_drivers = self._sort_by_strategy(drivers)
        for driver in sorted_drivers:
            breaker = self._breakers.get(driver.name)
            if breaker and breaker.is_open:
                continue
            if driver.state != DriverState.READY:
                continue
            try:
                resp = driver.complete(request)
                if not resp.error:
                    if breaker:
                        breaker.record_success()
                    return resp
                if breaker:
                    breaker.record_failure()
            except Exception:
                if breaker:
                    breaker.record_failure()
        return CompletionResponse(error="All drivers failed")

    def safe_embed(
        self,
        request: EmbeddingRequest,
        drivers: List[ModelDriver],
    ) -> EmbeddingResponse:
        """带故障转移的嵌入"""
        sorted_drivers = self._sort_by_strategy(drivers)
        for driver in sorted_drivers:
            breaker = self._breakers.get(driver.name)
            if breaker and breaker.is_open:
                continue
            if driver.state != DriverState.READY:
                continue
            try:
                resp = driver.embed(request)
                if not resp.error:
                    if breaker:
                        breaker.record_success()
                    return resp
                if breaker:
                    breaker.record_failure()
            except Exception:
                if breaker:
                    breaker.record_failure()
        return EmbeddingResponse(error="All drivers failed")

    # ── 内部工具 ─────────────────────────────────────────────

    def _sort_by_strategy(self, drivers: List[ModelDriver]) -> List[ModelDriver]:
        """按降级策略排序驱动"""
        order = self.strategy.fallback_order
        mode_priority = {m: i for i, m in enumerate(order)}
        return sorted(
            drivers,
            key=lambda d: mode_priority.get(d.mode, 999),
        )

    # ── 健康检查 ─────────────────────────────────────────────

    def check_all_health(self) -> Dict[str, HealthReport]:
        """检查所有驱动健康状态"""
        results = {}
        for name, driver in self._drivers.items():
            try:
                report = driver.health_check()
                results[name] = report

                # 根据健康状态更新熔断器
                breaker = self._breakers.get(name)
                if breaker:
                    if report.healthy:
                        if breaker.state in (CircuitState.OPEN, CircuitState.HALF_OPEN):
                            # 健康检查通过，尝试恢复
                            breaker.record_success()
                    elif report.error_count > 0:
                        breaker.record_failure()
            except Exception as e:
                results[name] = HealthReport(healthy=False, details={"error": str(e)})
        return results

    def start_health_check_loop(self) -> None:
        """启动后台健康检查线程"""
        if self._health_thread and self._health_thread.is_alive():
            return
        self._stop_event.clear()
        self._health_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="ftm-health-check",
        )
        self._health_thread.start()
        logger.info("[FTM] health check loop started")

    def stop_health_check_loop(self) -> None:
        """停止后台健康检查"""
        self._stop_event.set()
        if self._health_thread:
            self._health_thread.join(timeout=5.0)
        logger.info("[FTM] health check loop stopped")

    def _health_check_loop(self) -> None:
        """健康检查循环"""
        while not self._stop_event.wait(self._health_check_interval):
            try:
                self.check_all_health()
            except Exception as e:
                logger.error(f"[FTM] health check error: {e}")

    # ── 降级回调 ─────────────────────────────────────────────

    def set_on_degradation(self, callback: Callable) -> None:
        """设置降级回调（当所有高级驱动不可用时触发）"""
        self._on_degradation = callback

    # ── 状态报告 ─────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """获取容错状态报告"""
        return {
            "strategy": self.strategy.value,
            "fallback_order": [m.value for m in self.fallback_order],
            "drivers": {
                name: {
                    "mode": driver.mode.value,
                    "state": driver.state.value,
                    "breaker": {
                        "state": self._breakers[name].state.value,
                        "failures": self._breakers[name]._failure_count,
                    } if name in self._breakers else None,
                }
                for name, driver in self._drivers.items()
            },
        }
