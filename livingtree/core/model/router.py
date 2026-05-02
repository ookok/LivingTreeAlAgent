"""
LivingTree 统一模型调度中心
===========================

整合 smart_ai_router 三层算力池 + model_router + model_routing +
model_election + model_switcher + model_manager + model_priority_loader

核心设计：
- 三层算力池: Local(本地小模型) / Edge(边缘Ollama) / Cloud(云端API)
- 智能分流：根据任务复杂度自动选择算力层级
- 成本控制：预算管理 + 自动降级
- 缓存优先：避免重复调用
- 熔断保护：CircuitBreaker + 健康检查
- 负载均衡：RoundRobin + LeastLatency 策略
- Thinking 模式：复杂任务自动启用深度推理
"""

import asyncio
import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from ...infrastructure.config import LTAIConfig, get_config


class ComputeTier(Enum):
    LOCAL = "local"
    EDGE = "edge"
    CLOUD = "cloud"
    OFFLINE = "offline"


class TaskCategory(Enum):
    LIGHT = auto()
    MEDIUM = auto()
    HEAVY = auto()
    SPECIAL = auto()


class RoutingStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_LATENCY = "least_latency"
    PRIORITY_FIRST = "priority_first"
    COST_OPTIMIZED = "cost_optimized"


class EndpointHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class AIResponse:
    content: str
    tier_used: ComputeTier
    model_used: str
    tokens_input: int = 0
    tokens_output: int = 0
    cost: float = 0.0
    cached: bool = False
    latency_ms: float = 0.0
    thinking_content: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CostBudget:
    monthly_limit: float = 50.0
    daily_limit: float = 5.0
    per_request_limit: float = 0.5
    current_month_spent: float = 0.0
    current_day_spent: float = 0.0
    last_reset: datetime = field(default_factory=datetime.now)

    def can_afford(self, cost: float) -> bool:
        if cost > self.per_request_limit:
            return False
        if self.current_day_spent + cost > self.daily_limit:
            return False
        if self.current_month_spent + cost > self.monthly_limit:
            return False
        return True

    def record_spend(self, cost: float):
        self.current_day_spent += cost
        self.current_month_spent += cost

    def reset_if_needed(self):
        now = datetime.now()
        if now.date() > self.last_reset.date():
            self.current_day_spent = 0.0
            self.last_reset = now
        if now.month != self.last_reset.month:
            self.current_month_spent = 0.0
            self.last_reset = now


@dataclass
class TierEndpoint:
    name: str
    tier: ComputeTier
    endpoint: str
    model_name: str = ""
    max_tokens: int = 4096
    cost_per_1k_tokens: float = 0.0
    priority: int = 0
    supports_thinking: bool = False
    health: EndpointHealth = EndpointHealth.UNKNOWN
    avg_latency_ms: float = 0.0
    error_count: int = 0
    success_count: int = 0
    last_checked: float = 0.0
    consecutive_failures: int = 0
    circuit_open: bool = False


@dataclass
class ModelInfo:
    name: str
    provider: str = ""
    size_gb: float = 0.0
    context_window: int = 4096
    quant: str = ""
    status: str = "unknown"
    loaded: bool = False
    tier: ComputeTier = ComputeTier.LOCAL
    supports_thinking: bool = False


class CircuitBreaker:
    """熔断器 — fail-fast pattern for endpoint protection."""

    def __init__(self, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0,
                 half_open_max: int = 2):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self._state: Dict[str, str] = {}
        self._failures: Dict[str, int] = {}
        self._last_failure: Dict[str, float] = {}
        self._half_open_attempts: Dict[str, int] = {}
        self._lock = Lock()

    def allow_request(self, endpoint_key: str) -> bool:
        with self._lock:
            state = self._state.get(endpoint_key, "closed")
            if state == "closed":
                return True
            if state == "open":
                elapsed = time.time() - self._last_failure.get(endpoint_key, 0)
                if elapsed > self.recovery_timeout:
                    self._state[endpoint_key] = "half_open"
                    self._half_open_attempts[endpoint_key] = 0
                    return True
                return False
            if state == "half_open":
                attempts = self._half_open_attempts.get(endpoint_key, 0)
                return attempts < self.half_open_max
            return True

    def record_success(self, endpoint_key: str):
        with self._lock:
            self._state[endpoint_key] = "closed"
            self._failures[endpoint_key] = 0
            self._half_open_attempts.pop(endpoint_key, None)

    def record_failure(self, endpoint_key: str):
        with self._lock:
            self._failures[endpoint_key] = self._failures.get(endpoint_key, 0) + 1
            self._last_failure[endpoint_key] = time.time()
            if self._state.get(endpoint_key) == "half_open":
                self._half_open_attempts[endpoint_key] = (
                    self._half_open_attempts.get(endpoint_key, 0) + 1
                )
                if self._half_open_attempts[endpoint_key] >= self.half_open_max:
                    self._state[endpoint_key] = "open"
            elif self._failures[endpoint_key] >= self.failure_threshold:
                self._state[endpoint_key] = "open"

    def get_state(self, endpoint_key: str) -> str:
        return self._state.get(endpoint_key, "closed")


class LoadBalancer:
    """负载均衡器 — RoundRobin + LeastLatency strategies."""

    def __init__(self, strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN):
        self.strategy = strategy
        self._round_robin_index: Dict[ComputeTier, int] = {}
        self._lock = Lock()

    def select(self, endpoints: List[TierEndpoint]) -> Optional[TierEndpoint]:
        if not endpoints:
            return None
        healthy = [e for e in endpoints if not e.circuit_open]
        if not healthy:
            healthy = endpoints
        with self._lock:
            if self.strategy == RoutingStrategy.LEAST_LATENCY:
                return min(healthy, key=lambda e: e.avg_latency_ms if e.avg_latency_ms > 0 else 99999)
            elif self.strategy == RoutingStrategy.PRIORITY_FIRST:
                return max(healthy, key=lambda e: e.priority)
            elif self.strategy == RoutingStrategy.COST_OPTIMIZED:
                return min(healthy, key=lambda e: e.cost_per_1k_tokens)
            else:
                return self._round_robin_select(healthy)

    def _round_robin_select(self, endpoints: List[TierEndpoint]) -> TierEndpoint:
        if not endpoints:
            raise ValueError("empty endpoint list")
        tier = endpoints[0].tier
        idx = self._round_robin_index.get(tier, 0)
        selected = endpoints[idx % len(endpoints)]
        self._round_robin_index[tier] = (idx + 1) % len(endpoints)
        return selected


class ModelHealthChecker:
    """定期健康检查各端点，更新延迟和健康状态."""

    def __init__(self, interval: float = 30.0):
        self.interval = interval
        self._registry: Optional[ModelRegistry] = None
        self._breaker: Optional[CircuitBreaker] = None
        self._task: Optional[asyncio.Task] = None

    def bind(self, registry: "ModelRegistry", breaker: CircuitBreaker):
        self._registry = registry
        self._breaker = breaker

    async def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None

    async def _loop(self):
        while True:
            await asyncio.sleep(self.interval)
            if self._registry and self._breaker:
                for tier in ComputeTier:
                    if tier == ComputeTier.OFFLINE:
                        continue
                    for ep in self._registry.get_endpoints(tier):
                        await self._check_endpoint(ep)

    async def _check_endpoint(self, ep: TierEndpoint):
        key = f"{ep.tier.value}:{ep.name}"
        start = time.time()
        try:
            if "ollama" in ep.endpoint.lower() or ep.tier == ComputeTier.EDGE:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{ep.endpoint}/api/tags",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        ok = resp.status == 200
            elif ep.tier in (ComputeTier.LOCAL, ComputeTier.CLOUD):
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        ep.endpoint, timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        ok = resp.status < 500

            latency = (time.time() - start) * 1000
            ep.last_checked = time.time()

            if ok:
                ep.avg_latency_ms = (ep.avg_latency_ms * 0.7 + latency * 0.3) if ep.avg_latency_ms > 0 else latency
                ep.health = EndpointHealth.DEGRADED if latency > 2000 else EndpointHealth.HEALTHY
                ep.consecutive_failures = 0
                self._breaker.record_success(key)
            else:
                self._mark_unhealthy(ep, key)
        except Exception:
            self._mark_unhealthy(ep, key)

    def _mark_unhealthy(self, ep: TierEndpoint, key: str):
        ep.consecutive_failures += 1
        ep.health = EndpointHealth.UNHEALTHY
        ep.last_checked = time.time()
        self._breaker.record_failure(key)
        ep.circuit_open = not self._breaker.allow_request(key)


class ModelRegistry:
    """模型注册表 + 健康感知 + 负载均衡."""

    def __init__(self):
        self._models: Dict[str, ModelInfo] = {}
        self._tier_endpoints: Dict[ComputeTier, List[TierEndpoint]] = {
            ComputeTier.LOCAL: [],
            ComputeTier.EDGE: [],
            ComputeTier.CLOUD: [],
        }
        self._lock = Lock()
        self.circuit_breaker = CircuitBreaker()
        self.load_balancer = LoadBalancer(RoutingStrategy.LEAST_LATENCY)
        self.health_checker = ModelHealthChecker()
        self.health_checker.bind(self, self.circuit_breaker)

    def register_model(self, info: ModelInfo):
        with self._lock:
            self._models[info.name] = info

    def register_endpoint(self, endpoint: TierEndpoint):
        with self._lock:
            eps = self._tier_endpoints[endpoint.tier]
            eps.append(endpoint)
            eps.sort(key=lambda e: -e.priority)

    def get_model(self, name: str) -> Optional[ModelInfo]:
        return self._models.get(name)

    def list_models(self) -> List[ModelInfo]:
        return list(self._models.values())

    def get_endpoints(self, tier: ComputeTier) -> List[TierEndpoint]:
        return self._tier_endpoints.get(tier, [])

    def get_healthy_endpoints(self, tier: ComputeTier) -> List[TierEndpoint]:
        all_eps = self._tier_endpoints.get(tier, [])
        return [e for e in all_eps if not e.circuit_open]

    def get_fallback(self, tier: ComputeTier) -> Optional[TierEndpoint]:
        fallback_order = [ComputeTier.EDGE, ComputeTier.LOCAL, ComputeTier.CLOUD]
        for fallback_tier in fallback_order:
            if fallback_tier == tier:
                continue
            healthy = self.get_healthy_endpoints(fallback_tier)
            if healthy:
                return self.load_balancer.select(healthy)
            eps = self._tier_endpoints.get(fallback_tier, [])
            if eps:
                return eps[0]
        return None

    def select_endpoint(self, tier: ComputeTier) -> Optional[TierEndpoint]:
        healthy = self.get_healthy_endpoints(tier)
        if healthy:
            return self.load_balancer.select(healthy)
        return self.get_fallback(tier)

    async def start_health_checks(self):
        await self.health_checker.start()

    async def stop_health_checks(self):
        await self.health_checker.stop()


class UnifiedModelRouter:
    """
    统一模型路由器

    整合三层算力池分流策略：
    1. 轻量任务 (complexity < 0.3) → LOCAL
    2. 中量任务 (0.3 <= complexity < 0.6) → EDGE
    3. 重量任务 (complexity >= 0.6) → CLOUD

    附加策略：
    - Thinking 模式：复杂性 >= 0.5 或显式启用时优先使用支持 Thinking 的端点
    - 熔断保护：连续失败达到阈值后自动切换端点
    - 负载均衡：LeastLatency 策略选择最优端点
    - 指数退避重试：失败后自动重试备用端点
    """

    def __init__(self, config: Optional[LTAIConfig] = None):
        self.config = config or get_config()
        self.registry = ModelRegistry()
        self.budget = CostBudget()
        self._cache: Dict[str, Tuple[float, AIResponse]] = {}
        self._cache_ttl: float = 3600
        self._lock = Lock()
        self._thinking_threshold: float = 0.5
        self._max_retries: int = 2
        self._init_default_endpoints()

    def _init_default_endpoints(self):
        for tier in ComputeTier:
            eps = self.registry.get_endpoints(tier)
            if not eps:
                if tier == ComputeTier.LOCAL:
                    self.registry.register_endpoint(TierEndpoint(
                        name="local_default", tier=ComputeTier.LOCAL,
                        endpoint="ollama", model_name="qwen2.5:1.5b",
                        priority=0, supports_thinking=False))
                elif tier == ComputeTier.EDGE:
                    default_model = self.config.ollama.default_model or "qwen2.5:7b"
                    self.registry.register_endpoint(TierEndpoint(
                        name="edge_default", tier=ComputeTier.EDGE,
                        endpoint=self.config.ollama.base_url,
                        model_name=default_model, priority=10,
                        supports_thinking=True))

    @property
    def thinking_threshold(self) -> float:
        return self._thinking_threshold

    @thinking_threshold.setter
    def thinking_threshold(self, value: float):
        self._thinking_threshold = max(0.0, min(1.0, value))

    def classify_complexity(self, complexity: float) -> ComputeTier:
        if complexity < 0.3:
            return ComputeTier.LOCAL
        elif complexity < 0.6:
            return ComputeTier.EDGE
        else:
            return ComputeTier.CLOUD

    def _needs_thinking(self, complexity: float, force_thinking: bool) -> bool:
        return force_thinking or complexity >= self._thinking_threshold

    def route(self, task_description: str, complexity: float,
              max_cost: float = 0.1, force_thinking: bool = False) -> TierEndpoint:
        target_tier = self.classify_complexity(complexity)
        self.budget.reset_if_needed()

        use_thinking = self._needs_thinking(complexity, force_thinking)

        candidates = self.registry.get_healthy_endpoints(target_tier)
        if not candidates:
            candidates = self.registry.get_endpoints(target_tier)

        if use_thinking:
            thinking_candidates = [e for e in candidates if e.supports_thinking]
            if thinking_candidates:
                candidates = thinking_candidates

        selected = self.registry.select_endpoint(target_tier)
        if selected is None:
            fallback = self.registry.get_fallback(target_tier)
            if fallback:
                return fallback
            return TierEndpoint(name="fallback", tier=ComputeTier.OFFLINE,
                                endpoint="offline", model_name="fallback")

        if selected.cost_per_1k_tokens > 0:
            estimated_cost = (len(task_description) / 1000.0) * selected.cost_per_1k_tokens
            if estimated_cost > max_cost:
                fallback = self.registry.get_fallback(target_tier)
                if fallback:
                    return fallback

        return selected

    def route_with_retries(self, task_description: str, complexity: float,
                           max_cost: float = 0.1,
                           force_thinking: bool = False) -> TierEndpoint:
        primary = self.route(task_description, complexity, max_cost, force_thinking)
        if primary.tier != ComputeTier.OFFLINE:
            return primary
        for _ in range(self._max_retries):
            alternate = self.registry.get_fallback(
                self.classify_complexity(complexity))
            if alternate and alternate.tier != ComputeTier.OFFLINE:
                return alternate
        return primary

    def record_result(self, endpoint: TierEndpoint, success: bool,
                      latency_ms: float = 0.0):
        key = f"{endpoint.tier.value}:{endpoint.name}"
        endpoint.success_count += 1 if success else 0
        endpoint.error_count += 0 if success else 1
        if success:
            endpoint.avg_latency_ms = (
                (endpoint.avg_latency_ms * 0.8 + latency_ms * 0.2)
                if endpoint.avg_latency_ms > 0 else latency_ms
            )
            self.registry.circuit_breaker.record_success(key)
            endpoint.consecutive_failures = 0
            endpoint.circuit_open = False
        else:
            self.registry.circuit_breaker.record_failure(key)
            endpoint.consecutive_failures += 1
            state = self.registry.circuit_breaker.get_state(key)
            endpoint.circuit_open = state == "open"

    def _cache_key(self, prompt: str, model: str) -> str:
        raw = f"{prompt}:{model}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get_cached(self, prompt: str, model: str) -> Optional[AIResponse]:
        key = self._cache_key(prompt, model)
        with self._lock:
            if key in self._cache:
                ts, resp = self._cache[key]
                if time.time() - ts < self._cache_ttl:
                    resp.cached = True
                    return resp
                else:
                    del self._cache[key]
        return None

    def set_cache(self, prompt: str, model: str, response: AIResponse):
        key = self._cache_key(prompt, model)
        with self._lock:
            self._cache[key] = (time.time(), response)

    def clear_cache(self):
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        stats = {"budget": {
            "monthly_limit": self.budget.monthly_limit,
            "daily_limit": self.budget.daily_limit,
            "month_spent": self.budget.current_month_spent,
            "day_spent": self.budget.current_day_spent,
        }, "endpoints": {}}
        for tier in ComputeTier:
            if tier == ComputeTier.OFFLINE:
                continue
            for ep in self.registry.get_endpoints(tier):
                stats["endpoints"][ep.name] = {
                    "tier": ep.tier.value,
                    "health": ep.health.value,
                    "avg_latency_ms": ep.avg_latency_ms,
                    "success_count": ep.success_count,
                    "error_count": ep.error_count,
                    "circuit_open": ep.circuit_open,
                }
        return stats


class UnifiedModelClient:
    """统一模型客户端 — LLM 调用入口.

    支持同步/异步/流式三种调用模式，自动缓存和重试.
    """

    def __init__(self, router: Optional[UnifiedModelRouter] = None):
        self.router = router or UnifiedModelRouter()
        self._ollama_url: str = ""
        self._default_max_tokens: int = 4096

    def configure(self, ollama_url: str = "", max_tokens: int = 4096):
        self._ollama_url = ollama_url or get_config().ollama.base_url
        self._default_max_tokens = max_tokens

    async def chat(self, prompt: str, model: str = "",
                   temperature: float = 0.7,
                   max_tokens: int = 0,
                   force_thinking: bool = False,
                   system_prompt: str = "") -> AIResponse:
        model = model or self.router.config.ollama.default_model or "qwen2.5:7b"
        max_tokens = max_tokens or self._default_max_tokens
        start = time.time()

        cached = self.router.get_cached(prompt, model)
        if cached:
            return cached

        endpoint = self.router.route_with_retries(
            task_description=prompt,
            complexity=self._estimate_complexity(prompt),
            force_thinking=force_thinking,
        )
        if endpoint.tier == ComputeTier.OFFLINE:
            return AIResponse(
                content=f"[No available endpoint] Prompt: {prompt[:100]}",
                tier_used=ComputeTier.OFFLINE, model_used="fallback",
                latency_ms=(time.time() - start) * 1000,
            )

        response = await self._call_ollama_endpoint(
            endpoint, prompt, model, temperature, max_tokens, system_prompt, start)

        self.router.record_result(endpoint, success=response.tier_used != ComputeTier.OFFLINE,
                                  latency_ms=response.latency_ms)
        self.router.set_cache(prompt, model, response)
        return response

    async def _call_ollama_endpoint(self, endpoint: TierEndpoint, prompt: str,
                                    model: str, temperature: float,
                                    max_tokens: int, system_prompt: str,
                                    start_time: float) -> AIResponse:
        import aiohttp
        url = f"{self.router.config.ollama.base_url}/api/generate"
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                }
                if system_prompt:
                    payload["system"] = system_prompt
                async with session.post(url, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    data = await resp.json()
                    return AIResponse(
                        content=data.get("response", ""),
                        tier_used=endpoint.tier,
                        model_used=model,
                        tokens_input=data.get("prompt_eval_count", 0),
                        tokens_output=data.get("eval_count", 0),
                        latency_ms=(time.time() - start_time) * 1000,
                    )
        except Exception as e:
            return AIResponse(
                content=f"[Error: {e}]",
                tier_used=ComputeTier.OFFLINE,
                model_used="fallback",
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def chat_stream(self, prompt: str, model: str = "",
                          temperature: float = 0.7,
                          max_tokens: int = 0):
        """流式对话 — async generator yielding text chunks."""
        model = model or self.router.config.ollama.default_model or "qwen2.5:7b"
        max_tokens = max_tokens or self._default_max_tokens

        import aiohttp
        url = f"{self.router.config.ollama.base_url}/api/generate"
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                }
                async with session.post(url, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    async for line in resp.content:
                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue
                        try:
                            chunk = json.loads(line_str)
                            text = chunk.get("response", "")
                            if text:
                                yield text
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"[Stream Error: {e}]"

    async def chat_stream_raw(self, prompt: str, model: str = "",
                              temperature: float = 0.7,
                              max_tokens: int = 0):
        """Streaming that yields the raw JSON chunks for full metadata."""
        model = model or self.router.config.ollama.default_model or "qwen2.5:7b"
        max_tokens = max_tokens or self._default_max_tokens

        import aiohttp
        url = f"{self.router.config.ollama.base_url}/api/generate"
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": model, "prompt": prompt, "stream": True,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }
            async with session.post(url, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=300)) as resp:
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue
                    try:
                        yield json.loads(line_str)
                    except json.JSONDecodeError:
                        continue

    def chat_sync(self, prompt: str, model: str = "",
                  temperature: float = 0.7,
                  max_tokens: int = 0,
                  force_thinking: bool = False) -> AIResponse:
        model = model or self.router.config.ollama.default_model or "qwen2.5:7b"
        max_tokens = max_tokens or self._default_max_tokens
        start = time.time()

        cached = self.router.get_cached(prompt, model)
        if cached:
            return cached

        endpoint = self.router.route_with_retries(
            task_description=prompt,
            complexity=self._estimate_complexity(prompt),
            force_thinking=force_thinking,
        )
        if endpoint.tier == ComputeTier.OFFLINE:
            return AIResponse(
                content=f"[No available endpoint] Prompt: {prompt[:100]}",
                tier_used=ComputeTier.OFFLINE, model_used="fallback",
                latency_ms=(time.time() - start) * 1000,
            )

        import requests
        url = f"{self.router.config.ollama.base_url}/api/generate"
        try:
            payload = {
                "model": model, "prompt": prompt, "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }
            resp = requests.post(url, json=payload, timeout=120)
            data = resp.json()
            response = AIResponse(
                content=data.get("response", ""),
                tier_used=endpoint.tier, model_used=model,
                tokens_input=data.get("prompt_eval_count", 0),
                tokens_output=data.get("eval_count", 0),
                latency_ms=(time.time() - start) * 1000,
            )
            self.router.record_result(endpoint, success=True,
                                      latency_ms=response.latency_ms)
            self.router.set_cache(prompt, model, response)
            return response
        except Exception as e:
            self.router.record_result(endpoint, success=False)
            return AIResponse(
                content=f"[Error: {e}]",
                tier_used=ComputeTier.OFFLINE, model_used="fallback",
                latency_ms=(time.time() - start) * 1000,
            )

    def _estimate_complexity(self, text: str) -> float:
        if not text:
            return 0.1
        score = 0.0
        thinking_triggers = {
            "分析", "推理", "规划", "设计", "策略", "优化", "评估", "预测",
            "诊断", "架构", "重构", "调试", "审计", "建模", "逻辑",
            "analyze", "reason", "plan", "design", "strategy", "optimize",
            "evaluate", "predict", "diagnose", "architecture", "refactor",
            "debug", "audit", "model", "logic",
        }
        for keyword in thinking_triggers:
            if keyword.lower() in text.lower():
                score += 0.15
        if len(text) > 500:
            score += 0.1
        if len(text) > 2000:
            score += 0.2
        return min(1.0, score)


_default_router: Optional[UnifiedModelRouter] = None
_default_client: Optional[UnifiedModelClient] = None


def get_model_router() -> UnifiedModelRouter:
    global _default_router
    if _default_router is None:
        _default_router = UnifiedModelRouter()
    return _default_router


def get_model_client() -> UnifiedModelClient:
    global _default_client
    if _default_client is None:
        _default_client = UnifiedModelClient()
    return _default_client


__all__ = [
    "UnifiedModelRouter",
    "UnifiedModelClient",
    "ModelRegistry",
    "ModelHealthChecker",
    "CircuitBreaker",
    "LoadBalancer",
    "ModelInfo",
    "ComputeTier",
    "TaskCategory",
    "RoutingStrategy",
    "EndpointHealth",
    "AIResponse",
    "CostBudget",
    "TierEndpoint",
    "get_model_router",
    "get_model_client",
]
