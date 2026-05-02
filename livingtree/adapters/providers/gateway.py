# -*- coding: utf-8 -*-
"""
gateway.py — 统一 API 网关

ModelGateway 是三模式驱动系统的核心入口，负责：
  - 驱动注册与管理
  - 请求路由（按模型/模式/优先级）
  - A/B 测试分发
  - 模型预热
  - 统一调用接口

上层 (L0/L3/L4) 只需与 ModelGateway 交互。
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional

from .base import (
    ChatRequest, ChatResponse,
    CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    StreamChunk, ModelDriver, DriverMode, DriverState,
    HealthReport, UsageInfo,
)
from .hardload_driver import HardLoadDriver
from .local_service_driver import LocalServiceDriver
from .cloud_driver import CloudDriver

logger = logging.getLogger(__name__)


# ── 路由策略 ──────────────────────────────────────────────────────

class RouteStrategy:
    """路由策略"""
    PRIORITY = "priority"         # 优先级路由
    ROUND_ROBIN = "round_robin"   # 轮询
    RANDOM = "random"             # 随机
    AB_TEST = "ab_test"           # A/B 测试


@dataclass
class RouteResult:
    """路由结果"""
    driver: ModelDriver
    score: float = 1.0            # 路由分数（A/B 测试用）
    reason: str = ""


# ── 统一 API 网关 ──────────────────────────────────────────────────

class ModelGateway:
    """
    统一模型 API 网关

    管理多个驱动实例，提供统一调用入口。
    支持按模式/模型/优先级路由，A/B 测试，模型预热。
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._drivers: Dict[str, ModelDriver] = {}      # name -> driver
        self._model_routing: Dict[str, List[str]] = {}  # model -> [driver_names] 按优先级
        self._mode_drivers: Dict[DriverMode, List[str]] = {  # mode -> [driver_names]
            DriverMode.HARD_LOAD: [],
            DriverMode.LOCAL_SERVICE: [],
            DriverMode.CLOUD_SERVICE: [],
        }
        self._default_mode: DriverMode = DriverMode.LOCAL_SERVICE
        self._strategy = RouteStrategy.PRIORITY
        self._ab_config: Dict[str, Dict[str, float]] = {}  # model -> {driver_name: weight}
        self._round_robin_idx: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._warmup_tasks: List[str] = []  # 预热中的模型
        self._initialized = False

    @property
    def drivers(self) -> Dict[str, ModelDriver]:
        return dict(self._drivers)

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # ── 驱动注册 ─────────────────────────────────────────────

    def register_driver(
        self,
        driver: ModelDriver,
        models: List[str] | None = None,
        priority: int = 100,
    ) -> None:
        """
        注册驱动到网关

        Args:
            driver: 驱动实例
            models: 该驱动支持的模型列表（用于路由）
            priority: 路由优先级（数值越大越优先）
        """
        with self._lock:
            self._drivers[driver.name] = driver

            # 模式索引
            mode_list = self._mode_drivers.setdefault(driver.mode, [])
            if driver.name not in mode_list:
                mode_list.append(driver.name)

            # 模型路由
            models = models or []
            for model in models:
                route_list = self._model_routing.setdefault(model, [])
                # 按优先级插入
                route_list.append(driver.name)
                route_list.sort(key=lambda n: self._drivers.get(n) and 100 or 0)

            logger.info(
                f"[Gateway/{self.name}] registered: {driver.name} "
                f"(mode={driver.mode.value}, models={models or 'default'})"
            )

    def unregister_driver(self, name: str) -> None:
        """注销驱动"""
        with self._lock:
            if name not in self._drivers:
                return
            driver = self._drivers.pop(name)
            # 清理索引
            for mode_key in self._mode_drivers:
                if name in self._mode_drivers[mode_key]:
                    self._mode_drivers[mode_key].remove(name)
            for model_key in self._model_routing:
                if name in self._model_routing[model_key]:
                    self._model_routing[model_key].remove(name)
            logger.info(f"[Gateway/{self.name}] unregistered: {name}")

    def get_driver(self, name: str) -> Optional[ModelDriver]:
        """获取指定驱动"""
        return self._drivers.get(name)

    def get_drivers_by_mode(self, mode: DriverMode) -> List[ModelDriver]:
        """获取指定模式的所有驱动"""
        names = self._mode_drivers.get(mode, [])
        return [self._drivers[n] for n in names if n in self._drivers]

    # ── 路由 ─────────────────────────────────────────────────

    def set_route_strategy(self, strategy: str) -> None:
        """设置路由策略"""
        self._strategy = strategy
        logger.info(f"[Gateway/{self.name}] route strategy: {strategy}")

    def set_ab_config(self, model: str, weights: Dict[str, float]) -> None:
        """
        设置 A/B 测试配置

        Args:
            model: 模型名称
            weights: {driver_name: weight} 权重
        """
        self._ab_config[model] = weights
        self._strategy = RouteStrategy.AB_TEST
        logger.info(f"[Gateway/{self.name}] AB config for {model}: {weights}")

    def _route(self, model: str = "", preferred_mode: DriverMode | None = None) -> RouteResult:
        """
        路由请求到驱动

        Args:
            model: 目标模型
            preferred_mode: 优先使用的模式
        """
        # 1. 模型精确匹配
        if model and model in self._model_routing:
            candidates = self._model_routing[model]
            if candidates:
                driver_name = candidates[0]  # 优先级最高
                driver = self._drivers.get(driver_name)
                if driver and driver.state == DriverState.READY:
                    return RouteResult(driver=driver, reason=f"model_match: {model}")

        # 2. A/B 测试
        if model and model in self._ab_config and self._strategy == RouteStrategy.AB_TEST:
            weights = self._ab_config[model]
            driver_names = list(weights.keys())
            w_values = list(weights.values())
            chosen = random.choices(driver_names, weights=w_values, k=1)[0]
            driver = self._drivers.get(chosen)
            if driver and driver.state == DriverState.READY:
                return RouteResult(driver=driver, score=weights[chosen], reason=f"ab_test: {chosen}")

        # 3. 按优先模式选择
        modes_to_try = []
        if preferred_mode:
            modes_to_try.append(preferred_mode)
        modes_to_try.extend([
            self._default_mode,
            DriverMode.LOCAL_SERVICE,
            DriverMode.HARD_LOAD,
            DriverMode.CLOUD_SERVICE,
        ])
        # 去重
        seen = set()
        for m in modes_to_try:
            if m not in seen:
                seen.add(m)
                names = self._mode_drivers.get(m, [])
                for n in names:
                    if n in self._drivers:
                        driver = self._drivers[n]
                        if driver.state == DriverState.READY:
                            return RouteResult(driver=driver, reason=f"mode_fallback: {m.value}")

        # 4. 轮询
        if self._strategy == RouteStrategy.ROUND_ROBIN:
            all_ready = [d for d in self._drivers.values() if d.state == DriverState.READY]
            if all_ready:
                key = model or "__all__"
                idx = self._round_robin_idx.get(key, 0) % len(all_ready)
                self._round_robin_idx[key] = idx + 1
                return RouteResult(driver=all_ready[idx], reason="round_robin")

        # 5. 随机
        all_ready = [d for d in self._drivers.values() if d.state == DriverState.READY]
        if all_ready:
            return RouteResult(driver=random.choice(all_ready), reason="random_fallback")

        return RouteResult(
            driver=list(self._drivers.values())[0] if self._drivers else None,
            reason="no_ready_driver",
        )

    # ── 初始化与预热 ─────────────────────────────────────────

    def initialize(self) -> bool:
        """初始化网关（启动所有已注册驱动）"""
        logger.info(f"[Gateway/{self.name}] initializing {len(self._drivers)} drivers...")
        success = True
        for name, driver in self._drivers.items():
            try:
                ok = driver.initialize()
                if not ok:
                    logger.warning(f"[Gateway/{self.name}] driver {name} init failed")
                    success = False
                else:
                    logger.info(f"[Gateway/{self.name}] driver {name} ready")
            except Exception as e:
                logger.error(f"[Gateway/{self.name}] driver {name} init error: {e}")
                success = False
        self._initialized = True
        return success

    def shutdown(self) -> None:
        """关闭网关（停止所有驱动）"""
        for name, driver in self._drivers.items():
            try:
                driver.shutdown()
            except Exception as e:
                logger.error(f"[Gateway/{self.name}] driver {name} shutdown error: {e}")
        self._initialized = False
        logger.info(f"[Gateway/{self.name}] shut down")

    def warmup(self, model: str = "", prompt: str = "Hi") -> bool:
        """
        预热模型（发送一条测试请求）

        Args:
            model: 目标模型
            prompt: 测试提示词
        """
        route = self._route(model=model)
        if not route.driver:
            logger.warning(f"[Gateway/{self.name}] warmup failed: no driver for {model}")
            return False
        try:
            req = ChatRequest(
                messages=[{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt,
                model=model,
                max_tokens=1,
                stream=False,
            )
            # 修复：messages 需要 ChatMessage 列表
            from .base import ChatMessage
            req = ChatRequest(
                messages=[ChatMessage(role="user", content=prompt)],
                model=model,
                max_tokens=1,
                stream=False,
            )
            resp = route.driver.chat(req)
            ok = not resp.error
            if ok:
                logger.info(f"[Gateway/{self.name}] warmup OK: {model} via {route.driver.name}")
            else:
                logger.warning(f"[Gateway/{self.name}] warmup error: {resp.error}")
            return ok
        except Exception as e:
            logger.error(f"[Gateway/{self.name}] warmup exception: {e}")
            return False

    async def warmup_async(self, model: str = "", prompt: str = "Hi") -> bool:
        """异步预热"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.warmup, model, prompt)

    # ── 统一调用接口 ─────────────────────────────────────────

    def chat(
        self,
        request: ChatRequest,
        mode: DriverMode | None = None,
    ) -> ChatResponse:
        """
        统一对话接口

        Args:
            request: 聊天请求
            mode: 优先使用的驱动模式
        """
        route = self._route(model=request.model, preferred_mode=mode)
        if not route.driver:
            return ChatResponse(error="No available driver", finish_reason="error")
        return route.driver.chat(request)

    def chat_stream(
        self,
        request: ChatRequest,
        mode: DriverMode | None = None,
    ) -> Iterator[StreamChunk]:
        """统一流式对话接口"""
        route = self._route(model=request.model, preferred_mode=mode)
        if not route.driver:
            yield StreamChunk(error="No available driver", done=True)
            return
        for chunk in route.driver.chat_stream(request):
            yield chunk

    def complete(
        self,
        request: CompletionRequest,
        mode: DriverMode | None = None,
    ) -> CompletionResponse:
        """统一补全接口"""
        route = self._route(model=request.model, preferred_mode=mode)
        if not route.driver:
            return CompletionResponse(error="No available driver")
        return route.driver.complete(request)

    def embed(
        self,
        request: EmbeddingRequest,
        mode: DriverMode | None = None,
    ) -> EmbeddingResponse:
        """统一嵌入接口"""
        route = self._route(model=request.model, preferred_mode=mode)
        if not route.driver:
            return EmbeddingResponse(error="No available driver")
        return route.driver.embed(request)

    # ── 批量请求 ─────────────────────────────────────────────

    def chat_batch(
        self,
        requests: List[ChatRequest],
        mode: DriverMode | None = None,
    ) -> List[ChatResponse]:
        """批量对话"""
        return [self.chat(req, mode) for req in requests]

    # ── 健康检查 ─────────────────────────────────────────────

    def health_check(self) -> Dict[str, HealthReport]:
        """获取所有驱动健康状态"""
        results = {}
        for name, driver in self._drivers.items():
            try:
                results[name] = driver.health_check()
            except Exception as e:
                results[name] = HealthReport(healthy=False, details={"error": str(e)})
        return results

    def list_all_models(self) -> List[Dict[str, Any]]:
        """列出所有驱动中的可用模型"""
        all_models = []
        for name, driver in self._drivers.items():
            try:
                models = driver.list_models()
                for m in models:
                    m["driver"] = name
                    m["mode"] = driver.mode.value
                    all_models.append(m)
            except Exception:
                pass
        return all_models

    # ── 配置 ─────────────────────────────────────────────────

    def set_default_mode(self, mode: DriverMode) -> None:
        """设置默认驱动模式"""
        self._default_mode = mode
        logger.info(f"[Gateway/{self.name}] default mode: {mode.value}")

    def __repr__(self) -> str:
        ready = sum(1 for d in self._drivers.values() if d.state == DriverState.READY)
        return (
            f"<ModelGateway name={self.name!r} "
            f"drivers={len(self._drivers)} ready={ready} "
            f"strategy={self._strategy}>"
        )
