"""
高性能模型调度器 - Model Orchestrator
=====================================

核心功能：
1. 多后端统一管理 (vLLM / Ollama / TGI / 远程API)
2. 智能负载均衡
3. 故障自动转移
4. 成本优化路由
5. 热更新零停机

Author: Hermes Desktop Team
"""

import time
import asyncio
import hashlib
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
import httpx

logger = logging.getLogger(__name__)


class BackendType(Enum):
    """后端类型"""
    VLLM = "vllm"
    OLLAMA = "ollama"
    TGI = "tgi"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    GROQ = "groq"


@dataclass
class BackendConfig:
    """后端配置"""
    name: str
    backend_type: BackendType
    base_url: str
    api_key: Optional[str] = None
    timeout: float = 120.0
    
    # 性能参数
    max_concurrent: int = 10
    priority: int = 100  # 数字越小优先级越高
    
    # 成本 (本地=0)
    cost_per_token: float = 0.0
    
    # 健康检查
    health_check_interval: float = 30.0
    unhealthy_threshold: int = 3


@dataclass
class BackendStatus:
    """后端状态"""
    backend_name: str
    backend_type: BackendType
    
    # 健康状态
    healthy: bool = True
    last_check: datetime = field(default_factory=datetime.now)
    consecutive_failures: int = 0
    
    # 性能指标
    avg_latency_ms: float = 0.0
    requests_count: int = 0
    error_count: int = 0
    throughput: float = 0.0  # tokens/sec
    
    # 资源状态
    gpu_memory_used_mb: float = 0.0
    gpu_memory_total_mb: float = 0.0


@dataclass
class RoutingRequest:
    """路由请求"""
    task_type: str = "chat"
    preferred_backend: Optional[str] = None
    max_latency_ms: float = 5000.0
    max_cost: float = 1.0
    require_gpu: bool = False
    min_quality: float = 0.5


@dataclass
class RoutingResult:
    """路由结果"""
    selected_backend: str
    backend_type: BackendType
    endpoint: str
    model: str
    reason: str
    estimated_latency_ms: float
    estimated_cost: float


# ─────────────────────────────────────────────────────────────────────────────
# 后端管理器
# ─────────────────────────────────────────────────────────────────────────────

class BackendManager:
    """
    多后端统一管理器
    
    支持: vLLM, Ollama, TGI, OpenAI, DeepSeek, Groq
    """
    
    def __init__(self):
        self.backends: Dict[str, BackendConfig] = {}
        self.statuses: Dict[str, BackendStatus] = {}
        self._lock = asyncio.Lock()
    
    def register_backend(self, config: BackendConfig):
        """注册后端"""
        self.backends[config.name] = config
        self.statuses[config.name] = BackendStatus(
            backend_name=config.name,
            backend_type=config.backend_type,
        )
        logger.info(f"Registered backend: {config.name} ({config.backend_type.value})")
    
    def get_healthy_backends(self, require_gpu: bool = False) -> List[BackendConfig]:
        """获取健康的后端列表"""
        result = []
        for name, config in self.backends.items():
            status = self.statuses.get(name)
            if not status or not status.healthy:
                continue
            if require_gpu and config.backend_type not in [BackendType.VLLM, BackendType.OLLAMA, BackendType.TGI]:
                continue
            result.append(config)
        
        # 按优先级排序
        return sorted(result, key=lambda x: x.priority)
    
    async def health_check(self, backend_name: str) -> bool:
        """健康检查"""
        config = self.backends.get(backend_name)
        if not config:
            return False
        
        status = self.statuses.get(backend_name)
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                if config.backend_type == BackendType.OLLAMA:
                    r = await client.get(f"{config.base_url}/api/tags")
                elif config.backend_type == BackendType.VLLM:
                    r = await client.get(f"{config.base_url}/health")
                elif config.backend_type == BackendType.TGI:
                    r = await client.get(f"{config.base_url}/info")
                else:
                    # 远程API检查基本连通性
                    r = await client.get(config.base_url)
                
                healthy = r.status_code < 500
                
                if status:
                    status.healthy = healthy
                    status.last_check = datetime.now()
                    if healthy:
                        status.consecutive_failures = 0
                    else:
                        status.consecutive_failures += 1
                
                return healthy
                
        except Exception as e:
            logger.info(f"Health check failed for {backend_name}: {e}")
            if status:
                status.healthy = False
                status.consecutive_failures += 1
            return False
    
    async def health_check_all(self):
        """检查所有后端"""
        tasks = [self.health_check(name) for name in self.backends.keys()]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def record_latency(self, backend_name: str, latency_ms: float):
        """记录延迟"""
        status = self.statuses.get(backend_name)
        if status:
            # 滑动平均
            if status.avg_latency_ms == 0:
                status.avg_latency_ms = latency_ms
            else:
                status.avg_latency_ms = status.avg_latency_ms * 0.7 + latency_ms * 0.3
            status.requests_count += 1
    
    def record_error(self, backend_name: str):
        """记录错误"""
        status = self.statuses.get(backend_name)
        if status:
            status.error_count += 1
            if status.error_count > status.healthy_threshold:
                status.healthy = False


# ─────────────────────────────────────────────────────────────────────────────
# 负载均衡器
# ─────────────────────────────────────────────────────────────────────────────

class LoadBalancer:
    """负载均衡器"""
    
    @staticmethod
    def weighted_round_robin(backends: List[BackendConfig], statuses: Dict[str, BackendStatus]) -> BackendConfig:
        """加权轮询"""
        weights = []
        for config in backends:
            status = statuses.get(config.name)
            if status and status.avg_latency_ms > 0:
                # 延迟越高，权重越低
                weight = 1000 / status.avg_latency_ms
            else:
                weight = config.priority
            weights.append(weight)
        
        total = sum(weights)
        r = total * (time.time() % 1.0)
        
        cumulative = 0
        for i, w in enumerate(weights):
            cumulative += w
            if cumulative >= r:
                return backends[i]
        
        return backends[0]
    
    @staticmethod
    def least_connections(backends: List[BackendConfig], statuses: Dict[str, BackendStatus]) -> BackendConfig:
        """最小连接数"""
        best = None
        min_connections = float('inf')
        
        for config in backends:
            status = statuses.get(config.name)
            connections = status.requests_count if status else 0
            if connections < min_connections:
                min_connections = connections
                best = config
        
        return best or backends[0]
    
    @staticmethod
    def fastest_response(backends: List[BackendConfig], statuses: Dict[str, BackendStatus]) -> BackendConfig:
        """最快响应"""
        best = None
        min_latency = float('inf')
        
        for config in backends:
            status = statuses.get(config.name)
            latency = status.avg_latency_ms if status and status.avg_latency_ms > 0 else 500
            if latency < min_latency:
                min_latency = latency
                best = config
        
        return best or backends[0]


# ─────────────────────────────────────────────────────────────────────────────
# 智能调度器
# ─────────────────────────────────────────────────────────────────────────────

class ModelOrchestrator:
    """
    智能模型调度器
    
    特性:
    - 多后端统一管理
    - 智能路由选择
    - 故障自动转移
    - 成本优化
    - 零停机热更新
    """
    
    def __init__(
        self,
        strategy: str = "fastest",  # fastest, least_connections, weighted
        enable_fallback: bool = True,
        fallback_timeout: float = 30.0,
    ):
        self.backend_manager = BackendManager()
        self.load_balancer = LoadBalancer()
        self.strategy = strategy
        self.enable_fallback = enable_fallback
        self.fallback_timeout = fallback_timeout
        
        # 路由缓存
        self._route_cache: Dict[str, RoutingResult] = {}
        self._cache_ttl = 60.0  # 秒
        
        # 健康检查任务
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
    
    # ── 后端注册 ──────────────────────────────────────────────────────────
    
    def register_vllm(
        self,
        name: str,
        base_url: str = "http://localhost:8000",
        model: str = "qwen2.5:7b",
        priority: int = 10,
    ):
        """注册 vLLM 后端 (最高性能)"""
        self.backend_manager.register_backend(BackendConfig(
            name=name,
            backend_type=BackendType.VLLM,
            base_url=base_url,
            priority=priority,
            max_concurrent=32,  # vLLM 支持高并发
        ))
    
    def register_ollama(
        self,
        name: str,
        base_url: str = "http://localhost:11434",
        priority: int = 50,
    ):
        """注册 Ollama 后端"""
        self.backend_manager.register_backend(BackendConfig(
            name=name,
            backend_type=BackendType.OLLAMA,
            base_url=base_url,
            priority=priority,
            max_concurrent=10,
        ))
    
    def register_tgi(
        self,
        name: str,
        base_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        priority: int = 20,
    ):
        """注册 TGI 后端"""
        self.backend_manager.register_backend(BackendConfig(
            name=name,
            backend_type=BackendType.TGI,
            base_url=base_url,
            api_key=api_key,
            priority=priority,
            max_concurrent=20,
        ))
    
    def register_remote(
        self,
        name: str,
        backend_type: BackendType,
        base_url: str,
        api_key: str,
        cost_per_million: float = 0.0,
        priority: int = 100,
    ):
        """注册远程后端 (OpenAI/DeepSeek/Groq)"""
        self.backend_manager.register_backend(BackendConfig(
            name=name,
            backend_type=backend_type,
            base_url=base_url,
            api_key=api_key,
            priority=priority,
            cost_per_token=cost_per_million / 1_000_000,
            max_concurrent=100,
        ))
    
    # ── 路由选择 ──────────────────────────────────────────────────────────
    
    def route(self, request: RoutingRequest) -> RoutingResult:
        """
        智能路由选择
        
        策略:
        1. 检查缓存
        2. 获取健康后端
        3. 根据策略选择
        4. 记录决策
        """
        # 检查缓存
        cache_key = self._get_cache_key(request)
        if cache_key in self._route_cache:
            cached = self._route_cache[cache_key]
            if (datetime.now() - cached).seconds < self._cache_ttl:
                return cached
        
        # 获取候选后端
        backends = self.backend_manager.get_healthy_backends(require_gpu=request.require_gpu)
        
        if not backends:
            # 无健康后端，返回默认或远程兜底
            return self._route_fallback(request)
        
        # 根据策略选择
        if self.strategy == "fastest":
            selected = self.load_balancer.fastest_response(
                backends, self.backend_manager.statuses
            )
        elif self.strategy == "least_connections":
            selected = self.load_balancer.least_connections(
                backends, self.backend_manager.statuses
            )
        else:  # weighted
            selected = self.load_balancer.weighted_round_robin(
                backends, self.backend_manager.statuses
            )
        
        # 构建结果
        result = RoutingResult(
            selected_backend=selected.name,
            backend_type=selected.backend_type,
            endpoint=selected.base_url,
            model=self._get_default_model(selected.backend_type),
            reason=f"{self.strategy} strategy, backend healthy",
            estimated_latency_ms=self._estimate_latency(selected),
            estimated_cost=selected.cost_per_token,
        )
        
        # 缓存
        self._route_cache[cache_key] = result
        
        return result
    
    def _route_fallback(self, request: RoutingRequest) -> RoutingResult:
        """兜底路由到远程"""
        # DeepSeek 最便宜
        if request.max_cost < 0.2:
            backend_type = BackendType.DEEPSEEK
            model = "deepseek-chat"
        elif request.max_cost < 1.0:
            backend_type = BackendType.GROQ
            model = "llama-3.1-70b-versatile"
        else:
            backend_type = BackendType.OPENAI
            model = "gpt-4o"
        
        return RoutingResult(
            selected_backend=f"{backend_type.value}_fallback",
            backend_type=backend_type,
            endpoint=self._get_endpoint(backend_type),
            model=model,
            reason="No healthy local backend, fallback to remote",
            estimated_latency_ms=500,
            estimated_cost=0.00000014,
        )
    
    def _get_cache_key(self, request: RoutingRequest) -> str:
        """生成缓存键"""
        key = f"{request.task_type}:{request.require_gpu}:{request.max_latency_ms}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def _estimate_latency(self, backend: BackendConfig) -> float:
        """估算延迟"""
        status = self.backend_manager.statuses.get(backend.name)
        if status and status.avg_latency_ms > 0:
            return status.avg_latency_ms
        
        # 默认估算
        defaults = {
            BackendType.VLLM: 50,
            BackendType.OLLAMA: 100,
            BackendType.TGI: 80,
            BackendType.OPENAI: 500,
            BackendType.DEEPSEEK: 600,
            BackendType.GROQ: 300,
        }
        return defaults.get(backend.backend_type, 200)
    
    def _get_default_model(self, backend_type: BackendType) -> str:
        """获取默认模型"""
        defaults = {
            BackendType.VLLM: "qwen2.5:7b",
            BackendType.OLLAMA: "qwen2.5:7b",
            BackendType.TGI: "meta-llama/Llama-3.2-7B",
            BackendType.OPENAI: "gpt-4o-mini",
            BackendType.DEEPSEEK: "deepseek-chat",
            BackendType.GROQ: "llama-3.1-70b-versatile",
        }
        return defaults.get(backend_type, "qwen2.5:7b")
    
    def _get_endpoint(self, backend_type: BackendType) -> str:
        """获取API端点"""
        endpoints = {
            BackendType.OPENAI: "https://api.openai.com/v1",
            BackendType.DEEPSEEK: "https://api.deepseek.com/v1",
            BackendType.GROQ: "https://api.groq.com/openai/v1",
        }
        return endpoints.get(backend_type, "")
    
    # ── 执行请求 ──────────────────────────────────────────────────────────
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        task_type: str = "chat",
        **kwargs,
    ) -> tuple[str, str]:
        """
        统一聊天接口
        
        自动处理:
        - 路由选择
        - 故障转移
        - 负载均衡
        """
        request = RoutingRequest(task_type=task_type, require_gpu=kwargs.get("require_gpu", False))
        result = self.route(request)
        
        # 记录开始时间
        start_time = time.time()
        
        try:
            # 根据后端类型调用
            if result.backend_type == BackendType.OLLAMA:
                content = await self._chat_ollama(result, messages, model, **kwargs)
            elif result.backend_type == BackendType.VLLM:
                content = await self._chat_vllm(result, messages, model, **kwargs)
            elif result.backend_type == BackendType.TGI:
                content = await self._chat_tgi(result, messages, model, **kwargs)
            else:
                content = await self._chat_remote(result, messages, model, **kwargs)
            
            # 记录延迟
            latency_ms = (time.time() - start_time) * 1000
            self.backend_manager.record_latency(result.selected_backend, latency_ms)
            
            return content, result.selected_backend
            
        except Exception as e:
            self.backend_manager.record_error(result.selected_backend)
            logger.error(f"Request failed: {e}")
            
            # 尝试故障转移
            if self.enable_fallback and result.backend_type != BackendType.DEEPSEEK:
                logger.info("Attempting fallback...")
                fallback_result = self._route_fallback(request)
                return await self._chat_remote(fallback_result, messages, model, **kwargs)
            
            raise
    
    async def _chat_ollama(
        self, result: RoutingResult, messages: List[Dict], model: Optional[str], **kwargs
    ) -> str:
        """Ollama 调用"""
        model = model or "qwen2.5:7b"
        async with httpx.AsyncClient(timeout=result.estimated_latency_ms / 1000 + 10) as client:
            r = await client.post(
                f"{result.endpoint}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    
    async def _chat_vllm(
        self, result: RoutingResult, messages: List[Dict], model: Optional[str], **kwargs
    ) -> str:
        """vLLM 调用"""
        model = model or "qwen2.5:7b"
        async with httpx.AsyncClient(timeout=result.estimated_latency_ms / 1000 + 10) as client:
            r = await client.post(
                f"{result.endpoint}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    
    async def _chat_tgi(
        self, result: RoutingResult, messages: List[Dict], model: Optional[str], **kwargs
    ) -> str:
        """TGI 调用"""
        model = model or "meta-llama/Llama-3.2-7B"
        async with httpx.AsyncClient(timeout=result.estimated_latency_ms / 1000 + 10) as client:
            r = await client.post(
                f"{result.endpoint}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    
    async def _chat_remote(
        self, result: RoutingResult, messages: List[Dict], model: Optional[str], **kwargs
    ) -> str:
        """远程 API 调用"""
        model = model or result.model
        
        headers = {"Authorization": f"Bearer {self.backend_manager.backends.get(result.selected_backend, BackendConfig('', BackendType.OPENAI, '')).api_key}"}
        
        async with httpx.AsyncClient(timeout=result.estimated_latency_ms / 1000 + 30) as client:
            r = await client.post(
                f"{result.endpoint}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                },
                headers=headers,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    
    # ── 健康检查 ──────────────────────────────────────────────────────────
    
    async def start_health_checks(self, interval: float = 30.0):
        """启动健康检查"""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop(interval))
    
    async def stop_health_checks(self):
        """停止健康检查"""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
    
    async def _health_check_loop(self, interval: float):
        """健康检查循环"""
        while self._running:
            try:
                await self.backend_manager.health_check_all()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            await asyncio.sleep(interval)
    
    # ── 状态获取 ──────────────────────────────────────────────────────────
    
    def get_status(self) -> Dict[str, Any]:
        """获取所有后端状态"""
        result = {}
        for name, status in self.backend_manager.statuses.items():
            config = self.backend_manager.backends[name]
            result[name] = {
                "type": config.backend_type.value,
                "healthy": status.healthy,
                "latency_ms": status.avg_latency_ms,
                "requests": status.requests_count,
                "errors": status.error_count,
                "priority": config.priority,
            }
        return result


# ─────────────────────────────────────────────────────────────────────────────
# 单例访问
# ─────────────────────────────────────────────────────────────────────────────

_orchestrator: Optional[ModelOrchestrator] = None


def get_orchestrator() -> ModelOrchestrator:
    """获取调度器单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ModelOrchestrator()
        
        # 注册默认后端
        _orchestrator.register_ollama("ollama_local", priority=50)
        
        # 远程后端
        _orchestrator.register_remote(
            "deepseek",
            BackendType.DEEPSEEK,
            "https://api.deepseek.com/v1",
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            cost_per_million=0.14,
            priority=100,
        )
        
        _orchestrator.register_remote(
            "groq",
            BackendType.GROQ,
            "https://api.groq.com/openai/v1",
            api_key=os.environ.get("GROQ_API_KEY", ""),
            cost_per_million=0.59,
            priority=80,
        )
    
    return _orchestrator
