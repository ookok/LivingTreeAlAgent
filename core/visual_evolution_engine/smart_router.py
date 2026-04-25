"""
智能模型路由器 - Smart Model Router
=====================================

核心功能：
1. 评估本地硬件资源是否满足模型需求
2. 模型资源需求知识库
3. 本地/远程自动切换
4. 负载均衡和故障转移

Author: Hermes Desktop Team
"""

import time
import asyncio
from typing import Optional, List, Callable, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    """模型提供者"""
    LOCAL_OLLAMA = "local_ollama"
    REMOTE_OPENAI = "remote_openai"
    REMOTE_DEEPSEEK = "remote_deepseek"
    REMOTE_OLLAMA = "remote_ollama"
    REMOTE_GROQ = "remote_groq"


@dataclass
class ModelRequirements:
    """模型资源需求"""
    name: str
    provider: ModelProvider
    
    # 内存需求 (GB)
    min_memory_gb: float = 4.0
    recommended_memory_gb: float = 8.0
    
    # GPU需求
    min_gpu_memory_mb: float = 0  # 0 = CPU only
    recommended_gpu_memory_mb: float = 0
    
    # 计算能力 (相对值，1.0 = 最低要求)
    min_compute_score: float = 1.0
    
    # 上下文长度
    context_length: int = 4096
    
    # 其他要求
    requires_gpu: bool = False
    quantization: str = "q4_0"  # 量化级别
    
    # 优先级 (数字越小优先级越高)
    priority: int = 100
    
    # 成本 (美元/1M tokens)
    cost_per_million: float = 0.0
    
    # API端点 (远程模型)
    api_endpoint: str = ""
    api_key_env: str = ""  # 环境变量名


@dataclass
class HardwareProfile:
    """硬件配置"""
    # CPU
    cpu_cores: int = 4
    cpu_score: float = 1.0  # 相对计算能力
    
    # 内存
    total_memory_gb: float = 8.0
    available_memory_gb: float = 4.0
    
    # GPU
    has_gpu: bool = False
    gpu_name: str = ""
    total_gpu_memory_mb: float = 0
    available_gpu_memory_mb: float = 0
    
    # 网络
    network_available: bool = True
    network_latency_ms: float = 50.0
    network_bandwidth_mbps: float = 10.0


@dataclass
class RoutingDecision:
    """路由决策"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 决策结果
    selected_provider: ModelProvider = ModelProvider.LOCAL_OLLAMA
    selected_model: str = ""
    
    # 原因
    reason: str = ""
    confidence: float = 1.0  # 0-1
    
    # 资源评估
    hardware_profile: Optional[HardwareProfile] = None
    meets_requirements: bool = True
    
    # 备选方案
    alternatives: List[tuple[ModelProvider, str]] = field(default_factory=list)


@dataclass
class ModelRegistry:
    """模型注册表"""
    models: Dict[str, ModelRequirements] = field(default_factory=dict)
    
    def register(self, model: ModelRequirements):
        self.models[model.name] = model
    
    def get(self, name: str) -> Optional[ModelRequirements]:
        return self.models.get(name)
    
    def list_by_provider(self, provider: ModelProvider) -> List[ModelRequirements]:
        return [m for m in self.models.values() if m.provider == provider]
    
    def list_local_models(self) -> List[ModelRequirements]:
        return self.list_by_provider(ModelProvider.LOCAL_OLLAMA)
    
    def list_remote_models(self) -> List[ModelRequirements]:
        return [m for m in self.models.values() 
                if m.provider != ModelProvider.LOCAL_OLLAMA]


# ─────────────────────────────────────────────────────────────────────────────
# 默认模型注册表
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_MODEL_REGISTRY = ModelRegistry()


def _register_default_models():
    """注册默认模型"""
    
    # === 本地 Ollama 模型 ===
    local_models = [
        # 极小模型 (CPU可运行)
        ModelRequirements(
            name="llama3.2:1b",
            provider=ModelProvider.LOCAL_OLLAMA,
            min_memory_gb=1.5,
            recommended_memory_gb=2.5,
            min_gpu_memory_mb=0,
            min_compute_score=0.5,
            context_length=8192,
            requires_gpu=False,
            priority=50,
        ),
        ModelRequirements(
            name="qwen2.5:0.5b",
            provider=ModelProvider.LOCAL_OLLAMA,
            min_memory_gb=1.0,
            recommended_memory_gb=1.5,
            min_gpu_memory_mb=0,
            min_compute_score=0.5,
            context_length=8192,
            requires_gpu=False,
            priority=45,
        ),
        ModelRequirements(
            name="phi3:3.8b",
            provider=ModelProvider.LOCAL_OLLAMA,
            min_memory_gb=2.5,
            recommended_memory_gb=4.0,
            min_gpu_memory_mb=0,
            min_compute_score=0.8,
            context_length=4096,
            requires_gpu=False,
            priority=60,
        ),
        
        # 小模型 (CPU可运行，GPU更佳)
        ModelRequirements(
            name="llama3.2:3b",
            provider=ModelProvider.LOCAL_OLLAMA,
            min_memory_gb=3.0,
            recommended_memory_gb=5.0,
            min_gpu_memory_mb=0,
            recommended_gpu_memory_mb=4096,
            min_compute_score=1.0,
            context_length=8192,
            requires_gpu=False,
            priority=40,
        ),
        ModelRequirements(
            name="qwen2.5:3b",
            provider=ModelProvider.LOCAL_OLLAMA,
            min_memory_gb=2.5,
            recommended_memory_gb=4.0,
            min_gpu_memory_mb=0,
            recommended_gpu_memory_mb=4096,
            min_compute_score=1.0,
            context_length=8192,
            requires_gpu=False,
            priority=35,
        ),
        
        # 中等模型 (建议GPU)
        ModelRequirements(
            name="llama3.2:7b",
            provider=ModelProvider.LOCAL_OLLAMA,
            min_memory_gb=6.0,
            recommended_memory_gb=10.0,
            min_gpu_memory_mb=2048,
            recommended_gpu_memory_mb=8192,
            min_compute_score=1.5,
            context_length=8192,
            requires_gpu=False,
            priority=30,
        ),
        ModelRequirements(
            name="qwen2.5:7b",
            provider=ModelProvider.LOCAL_OLLAMA,
            min_memory_gb=5.5,
            recommended_memory_gb=9.0,
            min_gpu_memory_mb=2048,
            recommended_gpu_memory_mb=8192,
            min_compute_score=1.5,
            context_length=8192,
            requires_gpu=False,
            priority=25,
        ),
        
        # 大模型 (需要GPU)
        ModelRequirements(
            name="llama3.1:8b",
            provider=ModelProvider.LOCAL_OLLAMA,
            min_memory_gb=7.0,
            recommended_memory_gb=12.0,
            min_gpu_memory_mb=4096,
            recommended_gpu_memory_mb=12288,
            min_compute_score=2.0,
            context_length=128000,
            requires_gpu=True,
            priority=20,
        ),
        ModelRequirements(
            name="qwen2.5:14b",
            provider=ModelProvider.LOCAL_OLLAMA,
            min_memory_gb=10.0,
            recommended_memory_gb=16.0,
            min_gpu_memory_mb=6144,
            recommended_gpu_memory_mb=16384,
            min_compute_score=2.5,
            context_length=8192,
            requires_gpu=True,
            priority=15,
        ),
        
        # 超大模型 (需要高端GPU)
        ModelRequirements(
            name="qwen2.5:32b",
            provider=ModelProvider.LOCAL_OLLAMA,
            min_memory_gb=20.0,
            recommended_memory_gb=32.0,
            min_gpu_memory_mb=12288,
            recommended_gpu_memory_mb=24576,
            min_compute_score=3.0,
            context_length=8192,
            requires_gpu=True,
            priority=10,
        ),
        ModelRequirements(
            name="llama3.1:70b",
            provider=ModelProvider.LOCAL_OLLAMA,
            min_memory_gb=40.0,
            recommended_memory_gb=64.0,
            min_gpu_memory_mb=24576,
            recommended_gpu_memory_mb=49152,
            min_compute_score=4.0,
            context_length=128000,
            requires_gpu=True,
            priority=5,
        ),
    ]
    
    for model in local_models:
        DEFAULT_MODEL_REGISTRY.register(model)
    
    # === 远程模型 ===
    remote_models = [
        # DeepSeek 系列
        ModelRequirements(
            name="deepseek-chat",
            provider=ModelProvider.REMOTE_DEEPSEEK,
            min_memory_gb=0,
            recommended_memory_gb=0,
            min_gpu_memory_mb=0,
            min_compute_score=0,
            context_length=64000,
            requires_gpu=False,
            priority=100,
            cost_per_million=0.14,  # $0.14/M tokens
            api_endpoint="https://api.deepseek.com/v1",
            api_key_env="DEEPSEEK_API_KEY",
        ),
        ModelRequirements(
            name="deepseek-coder",
            provider=ModelProvider.REMOTE_DEEPSEEK,
            min_memory_gb=0,
            recommended_memory_gb=0,
            min_gpu_memory_mb=0,
            min_compute_score=0,
            context_length=64000,
            requires_gpu=False,
            priority=95,
            cost_per_million=0.14,
            api_endpoint="https://api.deepseek.com/v1",
            api_key_env="DEEPSEEK_API_KEY",
        ),
        
        # OpenAI GPT 系列
        ModelRequirements(
            name="gpt-4o-mini",
            provider=ModelProvider.REMOTE_OPENAI,
            min_memory_gb=0,
            recommended_memory_gb=0,
            min_gpu_memory_mb=0,
            min_compute_score=0,
            context_length=128000,
            requires_gpu=False,
            priority=90,
            cost_per_million=0.15,
            api_endpoint="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
        ),
        ModelRequirements(
            name="gpt-4o",
            provider=ModelProvider.REMOTE_OPENAI,
            min_memory_gb=0,
            recommended_memory_gb=0,
            min_gpu_memory_mb=0,
            min_compute_score=0,
            context_length=128000,
            requires_gpu=False,
            priority=85,
            cost_per_million=2.5,
            api_endpoint="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
        ),
        
        # Groq (超低延迟)
        ModelRequirements(
            name="llama-3.1-70b-versatile",
            provider=ModelProvider.REMOTE_GROQ,
            min_memory_gb=0,
            recommended_memory_gb=0,
            min_gpu_memory_mb=0,
            min_compute_score=0,
            context_length=128000,
            requires_gpu=False,
            priority=80,
            cost_per_million=0.59,
            api_endpoint="https://api.groq.com/openai/v1",
            api_key_env="GROQ_API_KEY",
        ),
        ModelRequirements(
            name="mixtral-8x7b-32768",
            provider=ModelProvider.REMOTE_GROQ,
            min_memory_gb=0,
            recommended_memory_gb=0,
            min_gpu_memory_mb=0,
            min_compute_score=0,
            context_length=32768,
            requires_gpu=False,
            priority=75,
            cost_per_million=0.24,
            api_endpoint="https://api.groq.com/openai/v1",
            api_key_env="GROQ_API_KEY",
        ),
        
        # Claude 系列 (通过 OpenAI 兼容接口)
        ModelRequirements(
            name="claude-3-haiku",
            provider=ModelProvider.REMOTE_OPENAI,
            min_memory_gb=0,
            recommended_memory_gb=0,
            min_gpu_memory_mb=0,
            min_compute_score=0,
            context_length=200000,
            requires_gpu=False,
            priority=70,
            cost_per_million=0.8,
            api_endpoint="https://api.anthropic.com/v1",
            api_key_env="ANTHROPIC_API_KEY",
        ),
    ]
    
    for model in remote_models:
        DEFAULT_MODEL_REGISTRY.register(model)


# 注册默认模型
_register_default_models()


# ─────────────────────────────────────────────────────────────────────────────
# 硬件评估器
# ─────────────────────────────────────────────────────────────────────────────

class HardwareProfiler:
    """硬件能力评估"""
    
    @staticmethod
    def get_current_profile() -> HardwareProfile:
        """获取当前硬件配置"""
        import psutil
        
        # CPU
        cpu_cores = psutil.cpu_count()
        cpu_score = cpu_cores / 4.0  # 4核为基准
        
        # 内存
        vm = psutil.virtual_memory()
        total_memory_gb = vm.total / (1024 ** 3)
        available_memory_gb = vm.available / (1024 ** 3)
        
        # GPU
        has_gpu = False
        gpu_name = ""
        total_gpu_memory_mb = 0
        available_gpu_memory_mb = 0
        
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                has_gpu = True
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode('utf-8')
                
                gpu_name = name
                total_gpu_memory_mb = mem_info.total / (1024 ** 2)
                available_gpu_memory_mb = mem_info.free / (1024 ** 2)
        except:
            pass
        
        # 网络 (简化)
        network_available = True
        network_latency_ms = 50.0
        
        return HardwareProfile(
            cpu_cores=cpu_cores,
            cpu_score=cpu_score,
            total_memory_gb=total_memory_gb,
            available_memory_gb=available_memory_gb,
            has_gpu=has_gpu,
            gpu_name=gpu_name,
            total_gpu_memory_mb=total_gpu_memory_mb,
            available_gpu_memory_mb=available_gpu_memory_mb,
            network_available=network_available,
            network_latency_ms=network_latency_ms,
        )
    
    @staticmethod
    def can_run_model(profile: HardwareProfile, requirements: ModelRequirements) -> tuple[bool, str]:
        """
        检查硬件是否能运行模型
        
        返回: (是否可运行, 原因)
        """
        reasons = []
        can_run = True
        
        # 检查内存
        if profile.available_memory_gb < requirements.min_memory_gb:
            can_run = False
            reasons.append(
                f"内存不足: 需要 {requirements.min_memory_gb}GB, "
                f"可用 {profile.available_memory_gb:.1f}GB"
            )
        
        # 检查GPU
        if requirements.requires_gpu and not profile.has_gpu:
            can_run = False
            reasons.append("需要GPU但无可用GPU")
        
        if requirements.min_gpu_memory_mb > 0:
            if profile.available_gpu_memory_mb < requirements.min_gpu_memory_mb:
                can_run = False
                reasons.append(
                    f"GPU内存不足: 需要 {requirements.min_gpu_memory_mb}MB, "
                    f"可用 {profile.available_gpu_memory_mb:.0f}MB"
                )
        
        # 检查计算能力
        if profile.cpu_score < requirements.min_compute_score:
            can_run = False
            reasons.append(
                f"CPU性能不足: 需要 {requirements.min_compute_score}, "
                f"当前 {profile.cpu_score:.1f}"
            )
        
        # 检查网络 (远程模型)
        if requirements.provider != ModelProvider.LOCAL_OLLAMA:
            if not profile.network_available:
                can_run = False
                reasons.append("网络不可用")
        
        return can_run, "; ".join(reasons) if reasons else "满足所有要求"


# ─────────────────────────────────────────────────────────────────────────────
# 智能路由器
# ─────────────────────────────────────────────────────────────────────────────

class SmartModelRouter:
    """
    智能模型路由器
    
    根据硬件能力和任务需求，自动选择最优模型（本地或远程）
    """
    
    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        prefer_local: bool = True,
        fallback_to_remote: bool = True,
    ):
        self.registry = registry or DEFAULT_MODEL_REGISTRY
        self.prefer_local = prefer_local  # 优先使用本地模型
        self.fallback_to_remote = fallback_to_remote  # 本地不足时切换到远程
        
        # 回调
        self._on_routing_callback: Optional[Callable[[RoutingDecision], None]] = None
    
    def set_routing_callback(self, callback: Callable[[RoutingDecision], None]):
        """设置路由决策回调"""
        self._on_routing_callback = callback
    
    def route(
        self,
        preferred_model: Optional[str] = None,
        task_type: Optional[str] = None,
        min_quality: float = 0.5,  # 0-1, 最低质量要求
        max_cost: float = 1.0,  # 美元/1M tokens
    ) -> RoutingDecision:
        """
        路由决策
        
        Args:
            preferred_model: 首选模型名 (如 "qwen2.5:7b")
            task_type: 任务类型 (如 "chat", "coding", "reasoning")
            min_quality: 最低质量要求 (0-1)
            max_cost: 最大成本 ($/1M tokens)
        
        Returns:
            RoutingDecision: 路由决策结果
        """
        # 获取当前硬件配置
        profile = HardwareProfiler.get_current_profile()
        
        decision = RoutingDecision(hardware_profile=profile)
        
        # 情况1: 指定了具体模型
        if preferred_model:
            return self._route_specific_model(preferred_model, profile, decision)
        
        # 情况2: 根据任务类型选择
        if task_type:
            return self._route_by_task(task_type, profile, decision, min_quality, max_cost)
        
        # 情况3: 默认策略 (优先本地，高质量)
        return self._route_default(profile, decision, min_quality, max_cost)
    
    def _route_specific_model(
        self,
        model_name: str,
        profile: HardwareProfile,
        decision: RoutingDecision,
    ) -> RoutingDecision:
        """指定模型的路由"""
        requirements = self.registry.get(model_name)
        
        if not requirements:
            # 模型未注册，假设是本地模型
            requirements = ModelRequirements(
                name=model_name,
                provider=ModelProvider.LOCAL_OLLAMA,
            )
            self.registry.register(requirements)
        
        can_run, reason = HardwareProfiler.can_run_model(profile, requirements)
        
        decision.selected_model = model_name
        decision.meets_requirements = can_run
        decision.reason = reason
        
        if can_run or requirements.provider != ModelProvider.LOCAL_OLLAMA:
            decision.selected_provider = requirements.provider
        elif self.fallback_to_remote:
            # 尝试找替代的远程模型
            alt = self._find_alternative(model_name, profile)
            if alt:
                return alt
        
        self._notify_callback(decision)
        return decision
    
    def _route_by_task(
        self,
        task_type: str,
        profile: HardwareProfile,
        decision: RoutingDecision,
        min_quality: float,
        max_cost: float,
    ) -> RoutingDecision:
        """根据任务类型路由"""
        
        # 任务类型到模型偏好映射
        task_preferences = {
            "chat": ["qwen2.5:7b", "llama3.2:7b", "deepseek-chat", "gpt-4o-mini"],
            "coding": ["qwen2.5:14b", "deepseek-coder", "gpt-4o"],
            "reasoning": ["qwen2.5:32b", "llama3.1:70b", "deepseek-chat"],
            "fast": ["qwen2.5:0.5b", "llama3.2:1b", "phi3:3.8b"],
            "writing": ["qwen2.5:7b", "deepseek-chat", "claude-3-haiku"],
            "analysis": ["qwen2.5:14b", "deepseek-chat", "gpt-4o"],
        }
        
        # 质量等级
        quality_levels = {
            "fast": (0.3, 0.5),
            "chat": (0.5, 0.7),
            "writing": (0.6, 0.8),
            "coding": (0.7, 0.9),
            "analysis": (0.8, 0.95),
            "reasoning": (0.9, 1.0),
        }
        
        min_q, max_q = quality_levels.get(task_type.lower(), (min_quality, 1.0))
        preferred_models = task_preferences.get(task_type.lower(), [])
        
        # 尝试每个首选模型
        for model_name in preferred_models:
            req = self.registry.get(model_name)
            if not req:
                continue
            
            can_run, reason = HardwareProfiler.can_run_model(profile, req)
            
            if can_run and req.provider == ModelProvider.LOCAL_OLLAMA:
                decision.selected_provider = ModelProvider.LOCAL_OLLAMA
                decision.selected_model = model_name
                decision.reason = f"任务 '{task_type}' 的本地最佳选择: {reason}"
                decision.confidence = 0.9
                self._notify_callback(decision)
                return decision
        
        # 需要使用远程模型
        if self.fallback_to_remote:
            for model_name in preferred_models:
                req = self.registry.get(model_name)
                if not req or req.provider == ModelProvider.LOCAL_OLLAMA:
                    continue
                
                if req.cost_per_million <= max_cost:
                    decision.selected_provider = req.provider
                    decision.selected_model = model_name
                    decision.reason = f"任务 '{task_type}' 的远程最佳选择 (成本 ${req.cost_per_million}/M)"
                    decision.confidence = 0.85
                    decision.alternatives = [(ModelProvider.LOCAL_OLLAMA, p) 
                                              for p in preferred_models[:2] 
                                              if self.registry.get(p)?.provider == ModelProvider.LOCAL_OLLAMA]
                    self._notify_callback(decision)
                    return decision
        
        # 兜底: 返回可用的本地最小模型
        return self._route_default(profile, decision, min_quality, max_cost)
    
    def _route_default(
        self,
        profile: HardwareProfile,
        decision: RoutingDecision,
        min_quality: float,
        max_cost: float,
    ) -> RoutingDecision:
        """默认路由策略"""
        
        alternatives = []
        
        # 按优先级排序所有本地模型
        local_models = sorted(
            self.registry.list_local_models(),
            key=lambda m: m.priority,
        )
        
        # 找到第一个可用的本地模型
        for req in local_models:
            can_run, reason = HardwareProfiler.can_run_model(profile, req)
            
            if can_run:
                decision.selected_provider = ModelProvider.LOCAL_OLLAMA
                decision.selected_model = req.name
                decision.reason = f"本地模型推荐 (满足硬件要求)"
                decision.confidence = 0.8 if req.priority > 30 else 0.9
                decision.alternatives = alternatives[:3]
                self._notify_callback(decision)
                return decision
            
            alternatives.append((ModelProvider.LOCAL_OLLAMA, req.name))
        
        # 尝试远程模型
        remote_models = sorted(
            self.registry.list_remote_models(),
            key=lambda m: m.cost_per_million,
        )
        
        for req in remote_models:
            if req.cost_per_million <= max_cost:
                decision.selected_provider = req.provider
                decision.selected_model = req.name
                decision.reason = f"本地资源不足，使用远程模型 (${req.cost_per_million}/M)"
                decision.confidence = 0.7
                self._notify_callback(decision)
                return decision
        
        # 兜底: 返回最便宜的远程模型
        if remote_models:
            req = remote_models[0]
            decision.selected_provider = req.provider
            decision.selected_model = req.name
            decision.reason = "兜底选择: 最便宜的远程模型"
            decision.confidence = 0.5
            self._notify_callback(decision)
        
        return decision
    
    def _find_alternative(
        self,
        original_model: str,
        profile: HardwareProfile,
    ) -> Optional[RoutingDecision]:
        """为指定模型找到替代方案"""
        
        # 获取原始模型信息
        original_req = self.registry.get(original_model)
        if not original_req:
            return None
        
        decision = RoutingDecision(hardware_profile=profile)
        
        # 1. 尝试找同类但更小的本地模型
        local_models = sorted(
            [m for m in self.registry.list_local_models() 
             if m.priority > original_req.priority],  # 更小 = 优先级数字更大
            key=lambda m: m.priority,
        )
        
        for req in local_models:
            can_run, reason = HardwareProfiler.can_run_model(profile, req)
            if can_run:
                decision.selected_provider = ModelProvider.LOCAL_OLLAMA
                decision.selected_model = req.name
                decision.reason = f"原模型不可用，切换到 {req.name} ({reason})"
                decision.confidence = 0.7
                self._notify_callback(decision)
                return decision
        
        # 2. 使用远程等价模型
        remote_models = [
            m for m in self.registry.list_remote_models()
            if original_req.provider == ModelProvider.REMOTE_DEEPSEEK or
               original_req.provider == ModelProvider.REMOTE_OPENAI
        ]
        
        for req in remote_models:
            decision.selected_provider = req.provider
            decision.selected_model = req.name
            decision.reason = f"本地资源不足，切换到远程模型 {req.name}"
            decision.confidence = 0.6
            self._notify_callback(decision)
            return decision
        
        return None
    
    def _notify_callback(self, decision: RoutingDecision):
        """通知回调"""
        if self._on_routing_callback:
            try:
                self._on_routing_callback(decision)
            except Exception as e:
                logger.error(f"路由回调错误: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 动态切换器
# ─────────────────────────────────────────────────────────────────────────────

class DynamicModelSwitcher:
    """
    动态模型切换器
    
    监控本地资源，动态切换本地/远程模型
    """
    
    def __init__(
        self,
        router: Optional[SmartModelRouter] = None,
        monitor_interval: float = 10.0,  # 秒
        memory_threshold: float = 0.85,  # 内存使用率阈值
    ):
        self.router = router or SmartModelRouter()
        self.monitor_interval = monitor_interval
        self.memory_threshold = memory_threshold
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # 当前状态
        self.current_model: str = ""
        self.current_provider: ModelProvider = ModelProvider.LOCAL_OLLAMA
        self.is_switching: bool = False
        
        # 切换回调
        self._on_switch_callback: Optional[Callable[[str, str, str], None]] = None
    
    def set_switch_callback(self, callback: Callable[[str, str, str], None]):
        """设置切换回调 (from_model, to_model, reason)"""
        self._on_switch_callback = callback
    
    async def start(self, preferred_model: Optional[str] = None):
        """启动动态切换"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(preferred_model))
        logger.info("动态模型切换器已启动")
    
    async def stop(self):
        """停止动态切换"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("动态模型切换器已停止")
    
    async def _monitor_loop(self, preferred_model: Optional[str]):
        """监控循环"""
        while self._running:
            try:
                # 检查是否需要切换
                should_switch, reason = await self._check_switch_needed(preferred_model)
                
                if should_switch and not self.is_switching:
                    await self._perform_switch(preferred_model, reason)
                
                await asyncio.sleep(self.monitor_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(self.monitor_interval)
    
    async def _check_switch_needed(self, preferred_model: Optional[str]) -> tuple[bool, str]:
        """检查是否需要切换模型"""
        import psutil
        
        # 检查内存使用率
        vm = psutil.virtual_memory()
        memory_percent = vm.percent / 100.0
        
        if memory_percent > self.memory_threshold:
            # 内存紧张，检查是否可切换
            if self.current_provider == ModelProvider.LOCAL_OLLAMA:
                return True, f"内存使用率 {memory_percent*100:.0f}% 超过阈值 {self.memory_threshold*100:.0f}%"
        
        # 检查GPU可用性变化
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            
            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_percent = mem_info.used / mem_info.total
                
                if gpu_percent > 0.95 and self.current_provider == ModelProvider.LOCAL_OLLAMA:
                    return True, f"GPU内存使用率 {gpu_percent*100:.0f}% 过高"
        except:
            pass
        
        return False, ""
    
    async def _perform_switch(self, preferred_model: Optional[str], reason: str):
        """执行模型切换"""
        self.is_switching = True
        old_model = self.current_model
        old_provider = self.current_provider
        
        try:
            # 做出路由决策
            decision = self.router.route(
                preferred_model=preferred_model,
                task_type=None,
            )
            
            self.current_model = decision.selected_model
            self.current_provider = decision.selected_provider
            
            # 触发回调
            if self._on_switch_callback:
                self._on_switch_callback(old_model, self.current_model, reason)
            
            logger.info(
                f"模型切换: {old_provider.value}/{old_model} -> "
                f"{self.current_provider.value}/{self.current_model} ({reason})"
            )
            
        finally:
            self.is_switching = False


# ─────────────────────────────────────────────────────────────────────────────
# 统一接口
# ─────────────────────────────────────────────────────────────────────────────

def get_smart_router() -> SmartModelRouter:
    """获取智能路由器单例"""
    return SmartModelRouter()


def route_model(
    preferred_model: Optional[str] = None,
    task_type: Optional[str] = None,
) -> RoutingDecision:
    """快捷路由函数"""
    router = get_smart_router()
    return router.route(preferred_model=preferred_model, task_type=task_type)
