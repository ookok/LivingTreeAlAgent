#!/usr/bin/env python3
"""
模型路由系统 - 参考 LinkMind 风格设计
实现企业级多模型路由、故障转移、负载均衡
"""

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ModelCapability(Enum):
    """模型能力"""
    CHAT = "chat"               # 对话
    CODE = "code"               # 代码生成
    ANALYSIS = "analysis"       # 分析
    CREATIVE = "creative"       # 创意
    REASONING = "reasoning"     # 推理
    MULTIMODAL = "multimodal"   # 多模态
    EMBEDDING = "embedding"     # 嵌入


class ModelStatus(Enum):
    """模型状态"""
    AVAILABLE = "available"     # 可用
    BUSY = "busy"              # 繁忙
    UNAVAILABLE = "unavailable" # 不可用
    MAINTENANCE = "maintenance" # 维护中


@dataclass
class ModelInfo:
    """模型信息"""
    model_id: str
    name: str
    provider: str
    capabilities: List[ModelCapability]
    cost_per_1k_tokens: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    status: ModelStatus = ModelStatus.AVAILABLE
    priority: int = 100  # 优先级，数值越高越优先
    max_concurrent: int = 10
    current_concurrent: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    health_score: float = 1.0  # 健康分数 0-1
    last_used: datetime = field(default_factory=datetime.now)
    total_requests: int = 0
    failed_requests: int = 0

    def is_available(self) -> bool:
        return (
            self.status == ModelStatus.AVAILABLE
            and self.current_concurrent < self.max_concurrent
            and self.health_score > 0.5
        )


class RouteStrategy(Enum):
    """路由策略"""
    PRIORITY = "priority"           # 优先级路由
    LATENCY = "latency"             # 延迟最优
    COST = "cost"                   # 成本最优
    LOAD_BALANCE = "load_balance"   # 负载均衡
    CAPABILITY = "capability"       # 能力匹配
    FALLBACK = "fallback"           # 故障转移


@dataclass
class RouteRequest:
    """路由请求"""
    task_type: str
    required_capabilities: List[ModelCapability]
    preferred_models: List[str] = field(default_factory=list)
    excluded_models: List[str] = field(default_factory=list)
    max_latency_ms: float = 0.0
    max_cost: float = 0.0
    priority: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteResult:
    """路由结果"""
    success: bool
    model: Optional[ModelInfo] = None
    fallback_models: List[ModelInfo] = field(default_factory=list)
    reason: str = ""
    routing_strategy: RouteStrategy = RouteStrategy.PRIORITY


class LinkMindRouter:
    """
    LinkMind 风格模型路由器

    特性:
    1. 多模型智能路由
    2. 故障自动转移
    3. 负载均衡
    4. 成本优化
    5. 延迟敏感路由
    6. 生产级过滤器和监控
    """

    def __init__(self):
        self._models: Dict[str, ModelInfo] = {}
        self._provider_models: Dict[str, List[str]] = {}  # provider -> model_ids
        self._strategy: RouteStrategy = RouteStrategy.PRIORITY
        self._filters: List[Callable[[RouteRequest, ModelInfo], bool]] = []
        self._event_handlers: Dict[str, List[Callable]] = {
            "route_success": [],
            "route_failed": [],
            "fallback_triggered": [],
            "model_unavailable": [],
        }

    def register_model(
        self,
        model_id: str,
        name: str,
        provider: str,
        capabilities: List[str],
        priority: int = 100,
        **kwargs
    ) -> bool:
        """
        注册模型

        Args:
            model_id: 模型 ID
            name: 模型名称
            provider: 提供商
            capabilities: 能力列表
            priority: 优先级
            **kwargs: 其他参数

        Returns:
            是否成功
        """
        if model_id in self._models:
            return False

        caps = []
        for cap in capabilities:
            try:
                caps.append(ModelCapability(cap))
            except ValueError:
                pass

        model = ModelInfo(
            model_id=model_id,
            name=name,
            provider=provider,
            capabilities=caps,
            priority=priority,
            **kwargs
        )

        self._models[model_id] = model

        if provider not in self._provider_models:
            self._provider_models[provider] = []
        self._provider_models[provider].append(model_id)

        return True

    def unregister_model(self, model_id: str) -> bool:
        """取消注册模型"""
        if model_id not in self._models:
            return False

        model = self._models[model_id]
        provider = model.provider

        if provider in self._provider_models:
            self._provider_models[provider].remove(model_id)

        del self._models[model_id]
        return True

    def update_model_status(self, model_id: str, status: ModelStatus) -> bool:
        """更新模型状态"""
        model = self._models.get(model_id)
        if not model:
            return False

        old_status = model.status
        model.status = status

        if status != ModelStatus.AVAILABLE:
            self._trigger_event("model_unavailable", model_id, status)

        return True

    def record_request(
        self,
        model_id: str,
        latency_ms: float,
        success: bool,
    ) -> bool:
        """记录请求结果"""
        model = self._models.get(model_id)
        if not model:
            return False

        model.total_requests += 1
        model.last_used = datetime.now()

        if success:
            model.current_concurrent = max(0, model.current_concurrent - 1)
            model.health_score = (
                model.health_score * 0.9 + 0.1
                if latency_ms < model.latency_p95_ms
                else model.health_score * 0.95
            )
        else:
            model.failed_requests += 1
            model.current_concurrent = max(0, model.current_concurrent - 1)
            model.health_score *= 0.8

        return True

    def add_filter(self, filter_func: Callable[[RouteRequest, ModelInfo], bool]):
        """添加路由过滤器"""
        self._filters.append(filter_func)

    def register_handler(self, event: str, handler: Callable):
        """注册事件处理器"""
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def _trigger_event(self, event: str, *args, **kwargs):
        """触发事件"""
        for handler in self._event_handlers.get(event, []):
            try:
                handler(*args, **kwargs)
            except Exception as e:
                print(f"Event handler error: {e}")

    def route(self, request: RouteRequest) -> RouteResult:
        """
        路由请求

        Args:
            request: 路由请求

        Returns:
            路由结果
        """
        candidates = self._get_candidates(request)

        if not candidates:
            self._trigger_event("route_failed", request, "No available models")
            return RouteResult(
                success=False,
                reason="No available models",
                routing_strategy=self._strategy,
            )

        if self._strategy == RouteStrategy.PRIORITY:
            candidates = sorted(candidates, key=lambda m: m.priority, reverse=True)
        elif self._strategy == RouteStrategy.LATENCY:
            candidates = sorted(candidates, key=lambda m: m.latency_p50_ms)
        elif self._strategy == RouteStrategy.COST:
            candidates = sorted(candidates, key=lambda m: m.cost_per_1k_tokens)
        elif self._strategy == RouteStrategy.LOAD_BALANCE:
            candidates = sorted(candidates, key=lambda m: m.current_concurrent)

        primary = candidates[0]
        fallbacks = candidates[1:3] if len(candidates) > 1 else []

        self._trigger_event("route_success", request, primary)

        return RouteResult(
            success=True,
            model=primary,
            fallback_models=fallbacks,
            reason=f"Routed to {primary.name}",
            routing_strategy=self._strategy,
        )

    def _get_candidates(self, request: RouteRequest) -> List[ModelInfo]:
        """获取候选模型"""
        candidates = []

        for model in self._models.values():
            if not model.is_available():
                continue

            if request.excluded_models and model.model_id in request.excluded_models:
                continue

            if request.required_capabilities:
                if not all(cap in model.capabilities for cap in request.required_capabilities):
                    continue

            if request.max_latency_ms > 0 and model.latency_p95_ms > request.max_latency_ms:
                continue

            if request.max_cost > 0 and model.cost_per_1k_tokens > request.max_cost:
                continue

            if request.preferred_models and model.model_id not in request.preferred_models:
                continue

            if self._filters and not all(f(request, model) for f in self._filters):
                continue

            candidates.append(model)

        return candidates

    def set_strategy(self, strategy: RouteStrategy):
        """设置路由策略"""
        self._strategy = strategy

    def get_available_models(
        self,
        capability: ModelCapability = None,
    ) -> List[ModelInfo]:
        """获取可用模型"""
        models = [m for m in self._models.values() if m.is_available()]

        if capability:
            models = [m for m in models if capability in m.capabilities]

        return sorted(models, key=lambda m: m.priority, reverse=True)

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        return self._models.get(model_id)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._models)
        available = len([m for m in self._models.values() if m.is_available()])
        busy = len([m for m in self._models.values() if m.status == ModelStatus.BUSY])

        total_requests = sum(m.total_requests for m in self._models.values())
        total_failed = sum(m.failed_requests for m in self._models.values())

        return {
            "total_models": total,
            "available_models": available,
            "busy_models": busy,
            "total_requests": total_requests,
            "failed_requests": total_failed,
            "success_rate": (
                (total_requests - total_failed) / total_requests * 100
                if total_requests > 0
                else 100.0
            ),
            "current_strategy": self._strategy.value,
        }


def test_linkmind_router():
    """测试 LinkMind 路由器"""
    print("=== 测试 LinkMind 模型路由系统 ===")

    router = LinkMindRouter()

    print("\n1. 测试注册模型")
    router.register_model(
        model_id="gpt-4",
        name="GPT-4",
        provider="openai",
        capabilities=["chat", "code", "analysis", "reasoning"],
        priority=100,
        cost_per_1k_tokens=0.03,
        latency_p50_ms=500,
        latency_p95_ms=2000,
    )
    router.register_model(
        model_id="gpt-3.5-turbo",
        name="GPT-3.5 Turbo",
        provider="openai",
        capabilities=["chat", "code"],
        priority=80,
        cost_per_1k_tokens=0.002,
        latency_p50_ms=200,
        latency_p95_ms=500,
    )
    router.register_model(
        model_id="claude-3",
        name="Claude 3",
        provider="anthropic",
        capabilities=["chat", "analysis", "creative"],
        priority=95,
        cost_per_1k_tokens=0.015,
        latency_p50_ms=600,
        latency_p95_ms=2500,
    )
    print(f"  已注册 {len(router._models)} 个模型")

    print("\n2. 测试路由 - 优先级策略")
    router.set_strategy(RouteStrategy.PRIORITY)
    request = RouteRequest(
        task_type="chat",
        required_capabilities=[ModelCapability.CHAT],
    )
    result = router.route(request)
    print(f"  路由结果: {result.model.name if result.model else 'None'}")
    print(f"  策略: {result.routing_strategy.value}")

    print("\n3. 测试路由 - 延迟最优策略")
    router.set_strategy(RouteStrategy.LATENCY)
    result = router.route(request)
    print(f"  路由结果: {result.model.name if result.model else 'None'}")

    print("\n4. 测试路由 - 成本最优策略")
    router.set_strategy(RouteStrategy.COST)
    result = router.route(request)
    print(f"  路由结果: {result.model.name if result.model else 'None'}")

    print("\n5. 测试能力过滤")
    request = RouteRequest(
        task_type="analysis",
        required_capabilities=[ModelCapability.ANALYSIS],
    )
    result = router.route(request)
    print(f"  分析任务路由结果: {result.model.name if result.model else 'None'}")

    print("\n6. 测试记录请求")
    router.record_request("gpt-4", 450, True)
    router.record_request("gpt-3.5-turbo", 180, True)
    print("  请求记录成功")

    print("\n7. 测试统计")
    stats = router.get_stats()
    print(f"  总模型: {stats['total_models']}")
    print(f"  可用模型: {stats['available_models']}")
    print(f"  总请求: {stats['total_requests']}")
    print(f"  成功率: {stats['success_rate']:.2f}%")

    print("\n8. 测试获取可用模型")
    models = router.get_available_models(capability=ModelCapability.CODE)
    print(f"  支持代码的模型: {[m.name for m in models]}")

    print("\nLinkMind 模型路由系统测试完成！")


if __name__ == "__main__":
    test_linkmind_router()