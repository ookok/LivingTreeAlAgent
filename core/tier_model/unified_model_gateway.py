"""
统一模型网关 - Unified Model Gateway
====================================

核心功能：
1. 统一接口：chat() / stream_chat()
2. 硬件感知：实时检测 CPU/内存/GPU
3. 智能路由：根据资源自动选择最优模型
4. 本地/远程切换：无缝自动切换
5. L0-L4 分层处理

架构：
┌─────────────────────────────────────────────────────────────┐
│                  UnifiedModelGateway                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   用户请求                                                   │
│       │                                                      │
│       ▼                                                      │
│   ┌─────────────────────────────────────────────────┐       │
│   │  L0 健康检查 (Tier0Init)                        │       │
│   │  • Ollama 连接  • GPU 可用性                     │       │
│   │  • 内存状态    • 网络连通                       │       │
│   └─────────────────────┬───────────────────────────┘       │
│                         │                                    │
│                         ▼                                    │
│   ┌─────────────────────────────────────────────────┐       │
│   │  L1 缓存查询 (Tier1Cache)                        │       │
│   │  • 语义缓存    • 热度权重                        │       │
│   └─────────────────────┬───────────────────────────┘       │
│                         │ 缓存未命中                          │
│                         ▼                                    │
│   ┌─────────────────────────────────────────────────┐       │
│   │  硬件感知路由器 (HardwareAwareRouter)            │       │
│   │  • CPU/内存/GPU 实时检测                        │       │
│   │  • 模型-硬件匹配  • 负载评估                     │       │
│   └─────────────────────┬───────────────────────────┘       │
│                         │                                    │
│                         ▼                                    │
│   ┌─────────────────────────────────────────────────┐       │
│   │  层级选择 (TierSelector)                         │       │
│   │  L2 轻量推理 (<500ms)  qwen2.5:0.5b            │       │
│   │  L3 标准推理 (1-3s)     qwen2.5:7b              │       │
│   │  L4 深度推理 (3-10s)    qwen2.5:14b/远程         │       │
│   └─────────────────────┬───────────────────────────┘       │
│                         │                                    │
│                         ▼                                    │
│   ┌─────────────────────────────────────────────────┐       │
│   │  模型执行器 (ModelExecutor)                      │       │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │       │
│   │  │ Ollama   │ │  vLLM    │ │  Remote  │        │       │
│   │  │  本地    │ │  高性能  │ │  API     │        │       │
│   │  └──────────┘ └──────────┘ └──────────┘        │       │
│   └─────────────────────────────────────────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Author: Hermes Desktop Team
"""

import time
import asyncio
from typing import Optional, List, Dict, Any, Union, AsyncGenerator, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────────────────────

class ModelProvider(Enum):
    """模型提供者"""
    LOCAL = "local"
    REMOTE = "remote"


class TierLevel(Enum):
    """处理层级"""
    L0 = "L0"  # 系统就绪
    L1 = "L1"  # 缓存命中
    L2 = "L2"  # 轻量推理
    L3 = "L3"  # 标准推理
    L4 = "L4"  # 深度推理


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    provider: ModelProvider
    tier: TierLevel
    
    # 资源需求
    min_memory_gb: float = 2.0
    min_gpu_memory_mb: float = 0
    requires_gpu: bool = False
    
    # 性能
    context_length: int = 8192
    latency_target_ms: float = 5000
    
    # 成本 (远程)
    cost_per_million: float = 0.0
    
    # API 配置 (远程)
    api_endpoint: str = ""
    api_key_env: str = ""


@dataclass
class HardwareProfile:
    """硬件配置"""
    cpu_cores: int = 4
    cpu_available: float = 0.5  # 0-1
    
    memory_total_gb: float = 8.0
    memory_available_gb: float = 4.0
    memory_percent: float = 0.5
    
    has_gpu: bool = False
    gpu_name: str = ""
    gpu_memory_total_mb: float = 0
    gpu_memory_available_mb: float = 0
    gpu_memory_percent: float = 0
    
    network_available: bool = True
    
    def can_run(self, config: ModelConfig) -> tuple[bool, str]:
        """检查是否可运行模型"""
        if config.requires_gpu and not self.has_gpu:
            return False, "需要 GPU 但无可用 GPU"
        
        if config.min_gpu_memory_mb > 0:
            if self.gpu_memory_available_mb < config.min_gpu_memory_mb:
                return False, f"GPU内存不足: 需要 {config.min_gpu_memory_mb}MB"
        
        if self.memory_available_gb < config.min_memory_gb:
            return False, f"内存不足: 需要 {config.min_memory_gb}GB"
        
        return True, "OK"


@dataclass
class GatewayStatus:
    """网关状态"""
    current_tier: TierLevel = TierLevel.L2
    active_model: str = ""
    provider: ModelProvider = ModelProvider.LOCAL
    
    # 硬件
    hardware: Optional[HardwareProfile] = None
    
    # 统计
    cache_hit_rate: float = 0.0
    total_requests: int = 0
    avg_latency_ms: float = 0.0
    
    # 就绪状态
    ollama_ready: bool = False
    remote_ready: bool = False
    
    # 可用模型
    local_models: List[str] = field(default_factory=list)
    remote_models: List[str] = field(default_factory=list)


@dataclass
class ChatRequest:
    """聊天请求"""
    query: str
    tier_hint: Optional[str] = None  # 强制层级
    task_type: str = "chat"
    context: Optional[str] = None
    history: Optional[List[Dict]] = None
    stream: bool = False
    
    # 约束
    max_latency_ms: float = 5000.0
    max_cost: float = 1.0
    prefer_local: bool = True


@dataclass
class ChatResponse:
    """聊天响应"""
    content: str
    tier: TierLevel
    
    # 模型信息
    model: str = ""
    provider: ModelProvider = ModelProvider.LOCAL
    
    # 性能
    latency_ms: float = 0.0
    tokens_generated: int = 0
    
    # 来源
    cache_hit: bool = False
    reasoning: str = ""
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# 模型配置注册表
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_MODEL_REGISTRY: Dict[str, ModelConfig] = {
    # L2 轻量模型 (CPU 可运行)
    "qwen2.5:0.5b": ModelConfig(
        name="qwen2.5:0.5b",
        provider=ModelProvider.LOCAL,
        tier=TierLevel.L2,
        min_memory_gb=1.0,
        latency_target_ms=500,
    ),
    "llama3.2:1b": ModelConfig(
        name="llama3.2:1b",
        provider=ModelProvider.LOCAL,
        tier=TierLevel.L2,
        min_memory_gb=1.5,
        latency_target_ms=600,
    ),
    "phi3:3.8b": ModelConfig(
        name="phi3:3.8b",
        provider=ModelProvider.LOCAL,
        tier=TierLevel.L2,
        min_memory_gb=2.5,
        latency_target_ms=800,
    ),
    
    # L3 标准模型 (建议 GPU)
    "qwen2.5:3b": ModelConfig(
        name="qwen2.5:3b",
        provider=ModelProvider.LOCAL,
        tier=TierLevel.L3,
        min_memory_gb=2.5,
        latency_target_ms=1500,
    ),
    "qwen2.5:7b": ModelConfig(
        name="qwen2.5:7b",
        provider=ModelProvider.LOCAL,
        tier=TierLevel.L3,
        min_memory_gb=5.5,
        min_gpu_memory_mb=2048,
        latency_target_ms=3000,
    ),
    "llama3.2:7b": ModelConfig(
        name="llama3.2:7b",
        provider=ModelProvider.LOCAL,
        tier=TierLevel.L3,
        min_memory_gb=6.0,
        min_gpu_memory_mb=2048,
        latency_target_ms=3000,
    ),
    
    # L4 大模型 (需要 GPU)
    "qwen2.5:14b": ModelConfig(
        name="qwen2.5:14b",
        provider=ModelProvider.LOCAL,
        tier=TierLevel.L4,
        min_memory_gb=10.0,
        min_gpu_memory_mb=6144,
        requires_gpu=True,
        latency_target_ms=8000,
    ),
    "qwen2.5:32b": ModelConfig(
        name="qwen2.5:32b",
        provider=ModelProvider.LOCAL,
        tier=TierLevel.L4,
        min_memory_gb=20.0,
        min_gpu_memory_mb=12288,
        requires_gpu=True,
        latency_target_ms=12000,
    ),
    
    # 远程模型
    "deepseek-chat": ModelConfig(
        name="deepseek-chat",
        provider=ModelProvider.REMOTE,
        tier=TierLevel.L3,
        cost_per_million=0.14,
        api_endpoint="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        latency_target_ms=2000,
    ),
    "gpt-4o-mini": ModelConfig(
        name="gpt-4o-mini",
        provider=ModelProvider.REMOTE,
        tier=TierLevel.L3,
        cost_per_million=0.15,
        api_endpoint="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        latency_target_ms=2000,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# 硬件感知路由器
# ─────────────────────────────────────────────────────────────────────────────

class HardwareAwareRouter:
    """硬件感知路由器"""
    
    def __init__(self):
        self._profile: Optional[HardwareProfile] = None
        self._profile_time: datetime = datetime.min
    
    async def get_profile(self, force_refresh: bool = False) -> HardwareProfile:
        """获取硬件配置（带缓存）"""
        now = datetime.now()
        
        # 缓存 5 秒
        if not force_refresh and self._profile:
            if (now - self._profile_time).total_seconds() < 5:
                return self._profile
        
        profile = HardwareProfile()
        
        # CPU & Memory
        import psutil
        profile.cpu_cores = psutil.cpu_count()
        profile.cpu_available = 1.0 - psutil.cpu_percent(interval=0.1) / 100
        
        vm = psutil.virtual_memory()
        profile.memory_total_gb = vm.total / (1024 ** 3)
        profile.memory_available_gb = vm.available / (1024 ** 3)
        profile.memory_percent = vm.percent / 100
        
        # GPU
        try:
            import pynvml
            pynvml.nvmlInit()
            if pynvml.nvmlDeviceGetCount() > 0:
                profile.has_gpu = True
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                profile.gpu_memory_total_mb = mem_info.total / (1024 ** 2)
                profile.gpu_memory_available_mb = mem_info.free / (1024 ** 2)
                profile.gpu_memory_percent = mem_info.used / mem_info.total
                
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode('utf-8')
                profile.gpu_name = name
        except:
            pass
        
        # Network
        try:
            import httpx
            r = httpx.get("https://www.google.com", timeout=2)
            profile.network_available = r.status_code < 500
        except:
            profile.network_available = True  # 假设可用
        
        self._profile = profile
        self._profile_time = now
        
        return profile
    
    async def select_model(
        self,
        tier_hint: Optional[TierLevel] = None,
        prefer_local: bool = True,
    ) -> tuple[str, ModelConfig, HardwareProfile]:
        """选择最适合当前硬件的模型"""
        profile = await self.get_profile()
        
        # 候选模型
        candidates = []
        
        for name, config in DEFAULT_MODEL_REGISTRY.items():
            # 层级过滤
            if tier_hint:
                if tier_hint == TierLevel.L2 and config.tier not in [TierLevel.L2, TierLevel.L1]:
                    continue
                if tier_hint == TierLevel.L3 and config.tier not in [TierLevel.L2, TierLevel.L3]:
                    continue
                if tier_hint == TierLevel.L4 and config.tier not in [TierLevel.L2, TierLevel.L3, TierLevel.L4]:
                    continue
            
            # 偏好过滤
            if prefer_local and config.provider == ModelProvider.REMOTE:
                # 优先本地，但本地不满足时考虑远程
                can_run, _ = profile.can_run(config)
                if can_run:
                    candidates.append((name, config, 0.5))  # 降低优先级
                continue
            
            # 检查是否可运行
            can_run, reason = profile.can_run(config)
            if can_run:
                # 计算分数
                score = self._calculate_score(config, profile, prefer_local)
                candidates.append((name, config, score))
        
        if not candidates:
            # 降级到远程
            for name, config in DEFAULT_MODEL_REGISTRY.items():
                if config.provider == ModelProvider.REMOTE:
                    return name, config, profile
            # 最后兜底
            return "qwen2.5:0.5b", DEFAULT_MODEL_REGISTRY["qwen2.5:0.5b"], profile
        
        # 选择最高分
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates[0][0], candidates[0][1], profile
    
    def _calculate_score(
        self,
        config: ModelConfig,
        profile: HardwareProfile,
        prefer_local: bool,
    ) -> float:
        """计算模型选择分数"""
        score = 1.0
        
        # 本地偏好
        if prefer_local and config.provider == ModelProvider.LOCAL:
            score *= 1.5
        
        # 层级匹配
        if config.tier == TierLevel.L2:
            score *= 1.2  # 轻量优先
        
        # 资源充裕度
        memory_margin = (profile.memory_available_gb - config.min_memory_gb) / profile.memory_available_gb
        score *= (0.5 + memory_margin * 0.5)
        
        # GPU 匹配
        if config.requires_gpu and profile.has_gpu:
            gpu_margin = (profile.gpu_memory_available_mb - config.min_gpu_memory_mb) / profile.gpu_memory_available_mb
            score *= (0.5 + gpu_margin * 0.5)
        
        # 成本惩罚 (远程)
        if config.cost_per_million > 0:
            score *= (1.0 / (1 + config.cost_per_million))
        
        return score


# ─────────────────────────────────────────────────────────────────────────────
# 统一模型网关
# ─────────────────────────────────────────────────────────────────────────────

class UnifiedModelGateway:
    """
    统一模型网关
    
    用法:
        gateway = UnifiedModelGateway()
        
        # 同步
        response = await gateway.chat("你好")
        
        # 流式
        async for chunk in gateway.stream_chat("写代码"):
            print(chunk, end="")
    """
    
    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        prefer_local: bool = True,
    ):
        self.ollama_host = ollama_host
        self.prefer_local = prefer_local
        
        # 组件
        self.hardware_router = HardwareAwareRouter()
        self._ollama_client = None
        self._cache: Dict[str, str] = {}
        self._cache_hits = 0
        self._cache_total = 0
        
        # 统计
        self._total_requests = 0
        self._latencies: List[float] = []
        
        # 状态
        self._status = GatewayStatus()
        self._initialized = False
    
    async def initialize(self):
        """初始化网关"""
        if self._initialized:
            return
        
        # 初始化 Ollama 客户端
        try:
            from core.ollama_client import OllamaClient
            from core.config import OllamaConfig
            
            config = OllamaConfig(base_url=self.ollama_host)
            self._ollama_client = OllamaClient(config)
            
            # 检查 Ollama 是否可用
            if self._ollama_client.ping():
                self._status.ollama_ready = True
                
                # 获取本地模型列表
                models = self._ollama_client.list_models()
                self._status.local_models = [m.name for m in models]
        except Exception as e:
            logger.warning(f"Ollama init failed: {e}")
        
        # 检查远程能力
        try:
            import httpx
            r = httpx.get("https://api.deepseek.com", timeout=3)
            self._status.remote_ready = r.status_code < 500
        except:
            self._status.remote_ready = True  # 假设可用
        
        # 更新硬件状态
        profile = await self.hardware_router.get_profile()
        self._status.hardware = profile
        
        self._initialized = True
        logger.info(f"Gateway initialized: Ollama={self._status.ollama_ready}, "
                   f"Remote={self._status.remote_ready}")
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """统一聊天接口"""
        start = time.perf_counter()
        self._total_requests += 1
        
        # 确保初始化
        if not self._initialized:
            await self.initialize()
        
        # L1 缓存检查
        cache_key = self._hash_query(request.query)
        self._cache_total += 1
        
        if cache_key in self._cache:
            self._cache_hits += 1
            self._status.cache_hit_rate = self._cache_hits / self._cache_total
            
            return ChatResponse(
                content=self._cache[cache_key],
                tier=TierLevel.L1,
                cache_hit=True,
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        
        # L2-L4 路由选择
        tier_hint = TierLevel[request.tier_hint.upper()] if request.tier_hint else None
        model_name, model_config, profile = await self.hardware_router.select_model(
            tier_hint=tier_hint,
            prefer_local=request.prefer_local,
        )
        
        self._status.current_tier = model_config.tier
        self._status.active_model = model_name
        self._status.provider = model_config.provider
        
        # 执行推理
        try:
            if model_config.provider == ModelProvider.LOCAL:
                content = await self._chat_local(model_name, request)
            else:
                content = await self._chat_remote(model_config, request)
            
            # 缓存结果
            self._cache[cache_key] = content
            
            # 记录延迟
            latency_ms = (time.perf_counter() - start) * 1000
            self._record_latency(latency_ms)
            
            return ChatResponse(
                content=content,
                tier=model_config.tier,
                model=model_name,
                provider=model_config.provider,
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            
            # 尝试降级到远程
            if model_config.provider == ModelProvider.LOCAL:
                remote_config = DEFAULT_MODEL_REGISTRY.get("deepseek-chat")
                if remote_config:
                    try:
                        content = await self._chat_remote(remote_config, request)
                        return ChatResponse(
                            content=content,
                            tier=TierLevel.L3,
                            model="deepseek-chat",
                            provider=ModelProvider.REMOTE,
                            metadata={"fallback": True},
                        )
                    except:
                        pass
            
            raise
    
    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """流式聊天接口"""
        # 简化实现
        response = await self.chat(request)
        for char in response.content:
            yield char
            await asyncio.sleep(0)
    
    async def _chat_local(self, model_name: str, request: ChatRequest) -> str:
        """本地 Ollama 推理"""
        if not self._ollama_client:
            raise RuntimeError("Ollama client not initialized")
        
        messages = self._build_messages(request)
        
        try:
            content, _, _ = self._ollama_client.chat_sync(
                messages=messages,
                model=model_name,
            )
            return content
        except Exception as e:
            logger.error(f"Local chat failed: {e}")
            raise
    
    async def _chat_remote(self, config: ModelConfig, request: ChatRequest) -> str:
        """远程 API 推理"""
        import httpx
        import os
        
        api_key = os.environ.get(config.api_key_env, "")
        
        messages = self._build_messages(request)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{config.api_endpoint}/chat/completions",
                json={
                    "model": config.name,
                    "messages": messages,
                },
                headers={"Authorization": f"Bearer {api_key}"},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    
    def _build_messages(self, request: ChatRequest) -> List[Dict]:
        """构建消息列表"""
        messages = [{"role": "system", "content": "你是一个有帮助的AI助手。"}]
        
        if request.context:
            messages.append({"role": "system", "content": f"上下文：{request.context}"})
        
        if request.history:
            for item in request.history[-5:]:
                messages.append({
                    "role": item.get("role", "user"),
                    "content": item.get("content", ""),
                })
        
        messages.append({"role": "user", "content": request.query})
        
        return messages
    
    @staticmethod
    def _hash_query(query: str) -> str:
        """简单哈希用于缓存"""
        import hashlib
        return hashlib.md5(query.encode()).hexdigest()[:16]
    
    def _record_latency(self, latency_ms: float):
        """记录延迟"""
        self._latencies.append(latency_ms)
        if len(self._latencies) > 100:
            self._latencies = self._latencies[-100:]
        self._status.avg_latency_ms = sum(self._latencies) / len(self._latencies)
    
    def get_status(self) -> GatewayStatus:
        """获取网关状态"""
        return self._status
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_requests": self._total_requests,
            "cache_hit_rate": self._cache_hits / self._cache_total if self._cache_total > 0 else 0,
            "avg_latency_ms": self._status.avg_latency_ms,
            "current_tier": self._status.current_tier.value,
            "active_model": self._status.active_model,
            "ollama_ready": self._status.ollama_ready,
            "remote_ready": self._status.remote_ready,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 便捷函数
# ─────────────────────────────────────────────────────────────────────────────

_unified_gateway: Optional[UnifiedModelGateway] = None


def get_unified_gateway() -> UnifiedModelGateway:
    """获取统一网关单例"""
    global _unified_gateway
    if _unified_gateway is None:
        _unified_gateway = UnifiedModelGateway()
    return _unified_gateway


async def chat(message: str, tier: str = None) -> str:
    """快捷聊天接口"""
    gateway = get_unified_gateway()
    response = await gateway.chat(ChatRequest(query=message, tier_hint=tier))
    return response.content
