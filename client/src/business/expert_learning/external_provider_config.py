"""
外部模型提供者配置系统 (ExternalProviderConfig)
================================================
可配置的外部AI模型API管理模块

功能:
1. 支持无限添加外部API配置
2. 支持免费/收费模式设置
3. 优先使用免费模型
4. 支持自定义定价
5. 支持API密钥管理
6. 支持多提供商优先级配置

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from business.logger import get_logger
logger = get_logger('expert_learning.external_provider_config')

import json
import os
import uuid
from typing import Dict, Optional, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
from pathlib import Path


# ── 枚举定义 ────────────────────────────────────────────────────────────────

class ProviderType(str, Enum):
    """提供者类型"""
    # 免费提供者
    OLLAMA = "ollama"           # 本地 Ollama
    LOCAL = "local"             # 本地模型
    GROQ = "groq"               # Groq (免费层)
    PERPLEXITY = "perplexity"   # Perplexity (免费层)
    LLAMAFILE = "llamafile"     # 本地 llamafile
    
    # 收费提供者
    OPENAI = "openai"           # OpenAI
    DEEPSEEK = "deepseek"       # 深度求索
    ANTHROPIC = "anthropic"     # Anthropic (Claude)
    OPENROUTER = "openrouter"   # OpenRouter
    AZURE = "azure"             # Azure OpenAI
    GEMINI = "gemini"           # Google Gemini
    MISTRAL = "mistral"         # Mistral AI
    TONGYI = "tongyi"           # 阿里通义千问
    ZHIPU = "zhipu"             # 智谱AI
    SPARK = "spark"             # 讯飞星火
    WENXIN = "wenxin"           # 百度文心
    TIANGONG = "tiangong"       # 科大讯飞天工
    
    # 自定义
    CUSTOM = "custom"           # 自定义API


class CostType(str, Enum):
    """费用类型"""
    FREE = "free"               # 完全免费
    FREEMIUM = "freemium"       # 有免费额度
    PAID = "paid"               # 收费


class ProviderStatus(str, Enum):
    """提供者状态"""
    ACTIVE = "active"           # 正常
    INACTIVE = "inactive"       # 停用
    ERROR = "error"             # 错误
    RATE_LIMITED = "rate_limited"  # 限流


# ── 数据模型 ────────────────────────────────────────────────────────────────

@dataclass
class ModelPricing:
    """模型定价配置"""
    model_name: str                    # 模型名称
    input_cost_per_million: float = 0.0  # 输入价格 (USD/1M tokens)
    output_cost_per_million: float = 0.0 # 输出价格 (USD/1M tokens)
    per_call_cost: float = 0.0          # 每次调用费用
    max_tokens: int = 0                 # 最大输出token (0=无限)
    supports_streaming: bool = True     # 是否支持流式


@dataclass
class ProviderEndpoint:
    """API端点配置"""
    base_url: str                      # API基础URL
    api_path: str = "/v1/chat/completions"  # API路径
    key_env_var: str = ""               # API Key环境变量名
    key_value: str = ""                 # 直接存储的API Key (不推荐)


@dataclass
class ProviderConfig:
    """外部提供者配置"""
    id: str                             # 唯一ID
    name: str                            # 显示名称
    provider_type: ProviderType          # 提供者类型
    cost_type: CostType                  # 费用类型
    
    # 基础配置
    endpoint: Optional[ProviderEndpoint] = None
    api_key: str = ""                    # API Key (加密存储)
    enabled: bool = True                 # 是否启用
    
    # 优先级 (数字越小优先级越高)
    priority: int = 100                 # 默认优先级
    preferred_for_types: List[str] = field(default_factory=list)  # 偏好用途
    
    # 配额配置
    daily_limit: int = 1000             # 日调用限制 (0=无限制)
    monthly_limit: int = 10000          # 月调用限制
    rate_limit_rpm: int = 60             # 每分钟请求限制
    
    # 模型配置
    models: List[ModelPricing] = field(default_factory=list)
    default_model: str = ""              # 默认模型
    
    # 状态
    status: ProviderStatus = ProviderStatus.ACTIVE
    last_used: float = 0                 # 上次使用时间戳
    use_count: int = 0                   # 累计使用次数
    error_count: int = 0                # 错误次数
    last_error: str = ""                 # 最近错误信息
    
    # 元数据
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    def is_free(self) -> bool:
        """是否为免费提供者"""
        return self.cost_type in [CostType.FREE, CostType.FREEMIUM]
    
    def get_default_pricing(self) -> ModelPricing:
        """获取默认定价"""
        if self.models and self.default_model:
            for m in self.models:
                if m.model_name == self.default_model:
                    return m
            return self.models[0]
        return ModelPricing(model_name=self.default_model or "default")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "provider_type": self.provider_type.value,
            "cost_type": self.cost_type.value,
            "endpoint": {
                "base_url": self.endpoint.base_url if self.endpoint else "",
                "api_path": self.endpoint.api_path if self.endpoint else "/v1/chat/completions",
                "key_env_var": self.endpoint.key_env_var if self.endpoint else "",
            } if self.endpoint else None,
            "api_key": self._mask_key(self.api_key),
            "enabled": self.enabled,
            "priority": self.priority,
            "preferred_for_types": self.preferred_for_types,
            "daily_limit": self.daily_limit,
            "monthly_limit": self.monthly_limit,
            "rate_limit_rpm": self.rate_limit_rpm,
            "models": [
                {
                    "model_name": m.model_name,
                    "input_cost": m.input_cost_per_million,
                    "output_cost": m.output_cost_per_million,
                    "max_tokens": m.max_tokens,
                }
                for m in self.models
            ],
            "default_model": self.default_model,
            "status": self.status.value,
            "use_count": self.use_count,
            "error_count": self.error_count,
            "description": self.description,
            "tags": self.tags,
        }
    
    @staticmethod
    def _mask_key(key: str) -> str:
        """掩码API Key"""
        if not key or len(key) < 8:
            return "***"
        return key[:4] + "***" + key[-4:]


# ── 默认提供者模板 ────────────────────────────────────────────────────────────

DEFAULT_PROVIDER_TEMPLATES: Dict[ProviderType, ProviderConfig] = {
    ProviderType.OLLAMA: ProviderConfig(
        id="builtin_ollama",
        name="本地 Ollama",
        provider_type=ProviderType.OLLAMA,
        cost_type=CostType.FREE,
        endpoint=ProviderEndpoint(
            base_url="http://localhost:11434",
            api_path="/v1/chat/completions",
        ),
        priority=1,
        models=[
            ModelPricing("qwen2.5:0.5b", 0, 0, 0, 4096),
            ModelPricing("qwen2.5:1.5b", 0, 0, 0, 8192),
            ModelPricing("qwen3.5:4b", 0, 0, 0, 8192),
            ModelPricing("qwen3.5:9b", 0, 0, 0, 16384),
        ],
        default_model="qwen2.5:1.5b",
        description="本地 Ollama 模型服务",
        tags=["local", "free", "fast"],
    ),
    
    ProviderType.GROQ: ProviderConfig(
        id="builtin_groq",
        name="Groq (免费高速)",
        provider_type=ProviderType.GROQ,
        cost_type=CostType.FREEMIUM,
        endpoint=ProviderEndpoint(
            base_url="https://api.groq.com",
            api_path="/openai/v1/chat/completions",
            key_env_var="GROQ_API_KEY",
        ),
        priority=2,
        models=[
            ModelPricing("llama-3.3-70b-versatile", 0, 0, 0, 8192),
            ModelPricing("mixtral-8x7b-32768", 0, 0, 0, 32768),
            ModelPricing("gemma2-9b-it", 0, 0, 0, 8192),
        ],
        default_model="llama-3.3-70b-versatile",
        description="Groq 高速免费API (Llama/Mixtral/Gemma)",
        tags=["free", "fast", "llama"],
    ),
    
    ProviderType.DEEPSEEK: ProviderConfig(
        id="builtin_deepseek",
        name="DeepSeek (便宜)",
        provider_type=ProviderType.DEEPSEEK,
        cost_type=CostType.PAID,
        endpoint=ProviderEndpoint(
            base_url="https://api.deepseek.com",
            api_path="/v1/chat/completions",
            key_env_var="DEEPSEEK_API_KEY",
        ),
        priority=10,
        models=[
            ModelPricing("deepseek-chat", 0.14, 0.28, 0, 16384),
            ModelPricing("deepseek-coder", 0.14, 0.28, 0, 16384),
            ModelPricing("deepseek-reasoner", 0.27, 2.19, 0, 8192),
        ],
        default_model="deepseek-chat",
        description="DeepSeek 深度求索 (性价比高)",
        tags=["paid", "coder", "reasoning"],
    ),
    
    ProviderType.OPENAI: ProviderConfig(
        id="builtin_openai",
        name="OpenAI GPT",
        provider_type=ProviderType.OPENAI,
        cost_type=CostType.PAID,
        endpoint=ProviderEndpoint(
            base_url="https://api.openai.com",
            api_path="/v1/chat/completions",
            key_env_var="OPENAI_API_KEY",
        ),
        priority=50,
        models=[
            ModelPricing("gpt-4o", 2.5, 10.0, 0, 128000),
            ModelPricing("gpt-4o-mini", 0.15, 0.6, 0, 128000),
            ModelPricing("gpt-4-turbo", 10.0, 30.0, 0, 128000),
            ModelPricing("gpt-3.5-turbo", 0.5, 1.5, 0, 16385),
        ],
        default_model="gpt-4o-mini",
        description="OpenAI GPT 系列",
        tags=["paid", "gpt", "high-quality"],
    ),
    
    ProviderType.ANTHROPIC: ProviderConfig(
        id="builtin_anthropic",
        name="Anthropic Claude",
        provider_type=ProviderType.ANTHROPIC,
        cost_type=CostType.PAID,
        endpoint=ProviderEndpoint(
            base_url="https://api.anthropic.com",
            api_path="/v1/messages",
            key_env_var="ANTHROPIC_API_KEY",
        ),
        priority=40,
        models=[
            ModelPricing("claude-sonnet-4-20250514", 3.0, 15.0, 0, 200000),
            ModelPricing("claude-3-5-sonnet-20241022", 3.0, 15.0, 0, 200000),
            ModelPricing("claude-3-5-haiku-20241022", 0.8, 4.0, 0, 4096),
        ],
        default_model="claude-sonnet-4-20250514",
        description="Anthropic Claude 系列",
        tags=["paid", "claude", "high-quality"],
    ),
    
    ProviderType.OPENROUTER: ProviderConfig(
        id="builtin_openrouter",
        name="OpenRouter (聚合)",
        provider_type=ProviderType.OPENROUTER,
        cost_type=CostType.PAID,
        endpoint=ProviderEndpoint(
            base_url="https://openrouter.ai",
            api_path="/api/v1/chat/completions",
            key_env_var="OPENROUTER_API_KEY",
        ),
        priority=30,
        models=[
            ModelPricing("anthropic/claude-sonnet-4", 3.0, 15.0, 0, 200000),
            ModelPricing("google/gemini-pro-1.5", 1.25, 5.0, 0, 65536),
            ModelPricing("meta-llama/llama-3-70b-instruct", 0.65, 2.75, 0, 8192),
        ],
        default_model="anthropic/claude-sonnet-4",
        description="OpenRouter 模型聚合平台",
        tags=["paid", "aggregated"],
    ),
}


# ── 外部提供者配置管理器 ─────────────────────────────────────────────────────

class ExternalProviderManager:
    """
    外部模型提供者配置管理器
    
    功能:
    - 添加/编辑/删除外部API配置
    - 支持免费/收费模式
    - 优先使用免费模型
    - 支持自定义定价
    - 智能选择最优提供者
    
    使用示例:
    ```python
    from business.expert_learning.external_provider_config import (
        ExternalProviderManager, ProviderType, CostType
    )
    
    # 创建管理器
    manager = ExternalProviderManager()
    
    # 添加自定义提供者
    manager.add_provider(
        name="我的DeepSeek",
        provider_type=ProviderType.DEEPSEEK,
        api_key="sk-xxx",
        cost_type=CostType.PAID,
        priority=5,
    )
    
    # 获取最优免费提供者
    provider = manager.get_best_free_provider()
    if provider:
        logger.info(f"使用: {provider.name}")
    
    # 获取所有可用提供者 (按优先级排序)
    providers = manager.get_available_providers(include_free_first=True)
    
    # 检查是否可以使用
    if manager.can_use("builtin_deepseek", estimated_calls=100):
        logger.info("可以使用 DeepSeek")
    ```
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, storage_path: Optional[str] = None):
        if self._initialized:
            return
        
        self._initialized = True
        self._lock = threading.RLock()
        
        # 存储路径
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path(__file__).parent / "providers.json"
        
        # 提供者配置
        self._providers: Dict[str, ProviderConfig] = {}
        self._builtin_templates: Dict[ProviderType, ProviderConfig] = DEFAULT_PROVIDER_TEMPLATES.copy()
        
        # 回调函数
        self._on_provider_added: Optional[Callable[[ProviderConfig], None]] = None
        self._on_provider_removed: Optional[Callable[[str], None]] = None
        self._on_provider_updated: Optional[Callable[[ProviderConfig], None]] = None
        
        # 加载配置
        self._load_config()
        
        logger.info(f"[ExternalProviderManager] 加载了 {len(self._providers)} 个提供者配置")
    
    # ── 基础操作 ─────────────────────────────────────────────────────────────
    
    def add_provider(
        self,
        name: str,
        provider_type: ProviderType,
        api_key: str = "",
        cost_type: CostType = CostType.PAID,
        endpoint_base_url: str = "",
        api_path: str = "/v1/chat/completions",
        priority: int = 100,
        enabled: bool = True,
        daily_limit: int = 1000,
        monthly_limit: int = 10000,
        default_model: str = "",
        models: Optional[List[ModelPricing]] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        添加新的提供者配置
        
        Args:
            name: 显示名称
            provider_type: 提供者类型
            api_key: API Key
            cost_type: 费用类型
            endpoint_base_url: API基础URL
            api_path: API路径
            priority: 优先级 (数字越小越高)
            enabled: 是否启用
            daily_limit: 日调用限制
            monthly_limit: 月调用限制
            default_model: 默认模型
            models: 模型定价列表
            description: 描述
            tags: 标签
            
        Returns:
            str: 提供者ID
        """
        with self._lock:
            # 生成唯一ID
            provider_id = f"provider_{uuid.uuid4().hex[:8]}"
            
            # 构建端点
            endpoint = None
            if endpoint_base_url:
                endpoint = ProviderEndpoint(
                    base_url=endpoint_base_url,
                    api_path=api_path,
                )
            elif provider_type in self._builtin_templates:
                # 使用模板端点
                template = self._builtin_templates[provider_type]
                if template.endpoint:
                    endpoint = ProviderEndpoint(
                        base_url=template.endpoint.base_url,
                        api_path=template.endpoint.api_path,
                    )
            
            # 获取模板默认值
            template = self._builtin_templates.get(provider_type)
            
            # 构建配置
            config = ProviderConfig(
                id=provider_id,
                name=name,
                provider_type=provider_type,
                cost_type=cost_type,
                endpoint=endpoint,
                api_key=api_key,
                priority=priority if priority != 100 else (template.priority if template else 100),
                enabled=enabled,
                daily_limit=daily_limit,
                monthly_limit=monthly_limit,
                models=models or (template.models if template else []),
                default_model=default_model or (template.default_model if template else ""),
                description=description or (template.description if template else ""),
                tags=tags or (template.tags if template else []),
            )
            
            self._providers[provider_id] = config
            self._save_config()
            
            if self._on_provider_added:
                self._on_provider_added(config)
            
            return provider_id
    
    def update_provider(self, provider_id: str, **kwargs) -> bool:
        """
        更新提供者配置
        
        Args:
            provider_id: 提供者ID
            **kwargs: 要更新的字段
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            if provider_id not in self._providers:
                return False
            
            config = self._providers[provider_id]
            
            # 可更新的字段
            updatable_fields = [
                "name", "cost_type", "enabled", "priority", 
                "preferred_for_types", "daily_limit", "monthly_limit",
                "rate_limit_rpm", "default_model", "description", "tags"
            ]
            
            for key, value in kwargs.items():
                if key in updatable_fields and hasattr(config, key):
                    setattr(config, key, value)
            
            # 特殊处理 API Key
            if "api_key" in kwargs and kwargs["api_key"]:
                config.api_key = kwargs["api_key"]
            
            # 特殊处理端点
            if "endpoint_base_url" in kwargs:
                if not config.endpoint:
                    config.endpoint = ProviderEndpoint(base_url="")
                config.endpoint.base_url = kwargs["endpoint_base_url"]
            
            if "api_path" in kwargs:
                if not config.endpoint:
                    config.endpoint = ProviderEndpoint(base_url="")
                config.endpoint.api_path = kwargs["api_path"]
            
            self._save_config()
            
            if self._on_provider_updated:
                self._on_provider_updated(config)
            
            return True
    
    def remove_provider(self, provider_id: str) -> bool:
        """删除提供者"""
        with self._lock:
            if provider_id in self._providers:
                del self._providers[provider_id]
                self._save_config()
                
                if self._on_provider_removed:
                    self._on_provider_removed(provider_id)
                
                return True
            return False
    
    def get_provider(self, provider_id: str) -> Optional[ProviderConfig]:
        """获取提供者配置"""
        with self._lock:
            return self._providers.get(provider_id)
    
    def get_all_providers(self) -> List[ProviderConfig]:
        """获取所有提供者"""
        with self._lock:
            return list(self._providers.values())
    
    # ── 查询方法 ─────────────────────────────────────────────────────────────
    
    def get_available_providers(
        self,
        include_free_first: bool = True,
        cost_type: Optional[CostType] = None,
        provider_type: Optional[ProviderType] = None,
        enabled_only: bool = True,
    ) -> List[ProviderConfig]:
        """
        获取可用提供者列表
        
        Args:
            include_free_first: 是否优先返回免费的
            cost_type: 按费用类型过滤
            provider_type: 按提供者类型过滤
            enabled_only: 只返回启用的
            
        Returns:
            List[ProviderConfig]: 排序后的提供者列表
        """
        with self._lock:
            providers = list(self._providers.values())
            
            # 过滤
            if enabled_only:
                providers = [p for p in providers if p.enabled]
            
            if cost_type:
                providers = [p for p in providers if p.cost_type == cost_type]
            
            if provider_type:
                providers = [p for p in providers if p.provider_type == provider_type]
            
            # 排序
            if include_free_first:
                # 先按费用类型，再按优先级
                providers.sort(key=lambda p: (
                    not p.is_free(),  # 免费优先
                    p.priority,
                ))
            else:
                providers.sort(key=lambda p: p.priority)
            
            return providers
    
    def get_best_free_provider(self, required_model: str = "") -> Optional[ProviderConfig]:
        """
        获取最优的免费提供者
        
        Args:
            required_model: 需要的模型名称 (可选)
            
        Returns:
            Optional[ProviderConfig]: 最优免费提供者
        """
        with self._lock:
            free_providers = self.get_available_providers(
                include_free_first=True,
                cost_type=CostType.FREE,
            )
            
            # 如果指定了模型，过滤支持该模型的提供者
            if required_model:
                for p in free_providers:
                    for m in p.models:
                        if required_model.lower() in m.model_name.lower():
                            return p
            
            return free_providers[0] if free_providers else None
    
    def get_best_provider(
        self,
        estimated_tokens: int = 1000,
        prefer_free: bool = True,
        required_model: str = "",
    ) -> Optional[ProviderConfig]:
        """
        获取最优提供者
        
        策略:
        1. 如果 prefer_free=True，优先选择免费提供者
        2. 按优先级排序
        3. 考虑每日调用限制
        
        Args:
            estimated_tokens: 预估token数
            prefer_free: 是否优先免费
            required_model: 需要的模型
            
        Returns:
            Optional[ProviderConfig]: 最优提供者
        """
        with self._lock:
            # 获取所有可用提供者
            providers = self.get_available_providers(include_free_first=prefer_free)
            
            for p in providers:
                # 检查是否有需要的模型
                if required_model:
                    has_model = any(
                        required_model.lower() in m.model_name.lower()
                        for m in p.models
                    )
                    if not has_model:
                        continue
                
                # 检查调用限制
                if p.daily_limit > 0 and p.use_count >= p.daily_limit:
                    continue
                
                return p
            
            return None
    
    def can_use(self, provider_id: str, estimated_calls: int = 1) -> bool:
        """检查是否可以使用提供者"""
        with self._lock:
            config = self._providers.get(provider_id)
            if not config or not config.enabled:
                return False
            
            if config.daily_limit > 0:
                if config.use_count + estimated_calls > config.daily_limit:
                    return False
            
            return True
    
    # ── 使用追踪 ─────────────────────────────────────────────────────────────
    
    def record_usage(self, provider_id: str, success: bool = True, error: str = "") -> None:
        """记录提供者使用"""
        with self._lock:
            config = self._providers.get(provider_id)
            if not config:
                return
            
            import time
            config.last_used = time.time()
            config.use_count += 1
            
            if not success:
                config.error_count += 1
                config.last_error = error
                
                # 错误过多标记为错误状态
                if config.error_count >= 10:
                    config.status = ProviderStatus.ERROR
            else:
                config.error_count = 0
                config.status = ProviderStatus.ACTIVE
            
            self._save_config()
    
    def reset_usage(self, provider_id: Optional[str] = None) -> None:
        """重置使用统计"""
        with self._lock:
            if provider_id:
                config = self._providers.get(provider_id)
                if config:
                    config.use_count = 0
                    config.error_count = 0
                    config.last_error = ""
                    config.status = ProviderStatus.ACTIVE
            else:
                for config in self._providers.values():
                    config.use_count = 0
                    config.error_count = 0
                    config.last_error = ""
                    config.status = ProviderStatus.ACTIVE
            
            self._save_config()
    
    # ── 状态管理 ─────────────────────────────────────────────────────────────
    
    def set_enabled(self, provider_id: str, enabled: bool) -> bool:
        """启用/禁用提供者"""
        return self.update_provider(provider_id, enabled=enabled)
    
    def set_status(self, provider_id: str, status: ProviderStatus) -> bool:
        """设置提供者状态"""
        return self.update_provider(provider_id, **{"status": status})
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = len(self._providers)
            enabled = sum(1 for p in self._providers.values() if p.enabled)
            free = sum(1 for p in self._providers.values() if p.is_free())
            active = sum(1 for p in self._providers.values() if p.status == ProviderStatus.ACTIVE)
            error = sum(1 for p in self._providers.values() if p.status == ProviderStatus.ERROR)
            
            return {
                "total": total,
                "enabled": enabled,
                "free": free,
                "paid": total - free,
                "active": active,
                "error": error,
            }
    
    # ── 模板管理 ─────────────────────────────────────────────────────────────
    
    def get_templates(self) -> List[ProviderConfig]:
        """获取内置模板列表"""
        return list(self._builtin_templates.values())
    
    def add_from_template(
        self,
        template_type: ProviderType,
        name: str = "",
        api_key: str = "",
        priority: Optional[int] = None,
    ) -> str:
        """
        从模板添加提供者
        
        Args:
            template_type: 模板类型
            name: 显示名称 (空则使用模板名称)
            api_key: API Key
            priority: 优先级 (空则使用模板默认值)
            
        Returns:
            str: 提供者ID
        """
        template = self._builtin_templates.get(template_type)
        if not template:
            raise ValueError(f"未知的模板类型: {template_type}")
        
        return self.add_provider(
            name=name or template.name,
            provider_type=template_type,
            api_key=api_key,
            cost_type=template.cost_type,
            endpoint_base_url=template.endpoint.base_url if template.endpoint else "",
            api_path=template.endpoint.api_path if template.endpoint else "/v1/chat/completions",
            priority=priority if priority is not None else template.priority,
            models=template.models.copy(),
            default_model=template.default_model,
            description=template.description,
            tags=template.tags.copy(),
        )
    
    # ── 回调设置 ─────────────────────────────────────────────────────────────
    
    def set_callbacks(
        self,
        on_added: Callable[[ProviderConfig], None] = None,
        on_removed: Callable[[str], None] = None,
        on_updated: Callable[[ProviderConfig], None] = None,
    ) -> None:
        """设置回调函数"""
        self._on_provider_added = on_added
        self._on_provider_removed = on_removed
        self._on_provider_updated = on_updated
    
    # ── 持久化 ───────────────────────────────────────────────────────────────
    
    def _load_config(self) -> None:
        """加载配置"""
        if not self.storage_path.exists():
            # 初始化默认内置提供者
            self._init_default_providers()
            return
        
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._providers.clear()
            
            for p_data in data.get("providers", []):
                endpoint = None
                if p_data.get("endpoint"):
                    ep_data = p_data["endpoint"]
                    endpoint = ProviderEndpoint(
                        base_url=ep_data.get("base_url", ""),
                        api_path=ep_data.get("api_path", "/v1/chat/completions"),
                        key_env_var=ep_data.get("key_env_var", ""),
                    )
                
                models = []
                for m_data in p_data.get("models", []):
                    models.append(ModelPricing(
                        model_name=m_data.get("model_name", ""),
                        input_cost_per_million=m_data.get("input_cost", 0),
                        output_cost_per_million=m_data.get("output_cost", 0),
                        per_call_cost=m_data.get("per_call_cost", 0),
                        max_tokens=m_data.get("max_tokens", 0),
                    ))
                
                self._providers[p_data["id"]] = ProviderConfig(
                    id=p_data["id"],
                    name=p_data["name"],
                    provider_type=ProviderType(p_data.get("provider_type", "custom")),
                    cost_type=CostType(p_data.get("cost_type", "paid")),
                    endpoint=endpoint,
                    api_key=p_data.get("api_key", ""),
                    enabled=p_data.get("enabled", True),
                    priority=p_data.get("priority", 100),
                    preferred_for_types=p_data.get("preferred_for_types", []),
                    daily_limit=p_data.get("daily_limit", 1000),
                    monthly_limit=p_data.get("monthly_limit", 10000),
                    rate_limit_rpm=p_data.get("rate_limit_rpm", 60),
                    models=models,
                    default_model=p_data.get("default_model", ""),
                    status=ProviderStatus(p_data.get("status", "active")),
                    use_count=p_data.get("use_count", 0),
                    error_count=p_data.get("error_count", 0),
                    description=p_data.get("description", ""),
                    tags=p_data.get("tags", []),
                )
                
        except Exception as e:
            logger.info(f"[ExternalProviderManager] 加载配置失败: {e}")
            self._init_default_providers()
    
    def _save_config(self) -> None:
        """保存配置"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "version": "1.0",
                "providers": [p.to_dict() for p in self._providers.values()],
            }
            
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.info(f"[ExternalProviderManager] 保存配置失败: {e}")
    
    def _init_default_providers(self) -> None:
        """初始化默认提供者"""
        self._providers.clear()
        
        # 添加内置免费提供者 (需要用户配置API Key)
        for p_type in [ProviderType.OLLAMA, ProviderType.GROQ]:
            if p_type in self._builtin_templates:
                template = self._builtin_templates[p_type]
                self._providers[template.id] = ProviderConfig(
                    id=template.id,
                    name=template.name,
                    provider_type=template.provider_type,
                    cost_type=template.cost_type,
                    endpoint=template.endpoint,
                    priority=template.priority,
                    models=template.models.copy(),
                    default_model=template.default_model,
                    description=template.description,
                    tags=template.tags.copy(),
                )
        
        self._save_config()
    
    # ── 便捷方法 ─────────────────────────────────────────────────────────────
    
    def list_providers(
        self,
        show_api_keys: bool = False,
        include_disabled: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        列出所有提供者 (用于UI显示)
        
        Args:
            show_api_keys: 是否显示完整API Key
            include_disabled: 是否包含禁用的
            
        Returns:
            List[Dict]: 提供者信息列表
        """
        providers = []
        for config in self.get_available_providers(enabled_only=not include_disabled):
            p_dict = config.to_dict()
            if show_api_keys:
                # 尝试从环境变量获取完整Key
                if config.endpoint and config.endpoint.key_env_var:
                    import os

                    full_key = os.environ.get(config.endpoint.key_env_var, "")
                    if full_key:
                        p_dict["api_key"] = full_key
            providers.append(p_dict)
        return providers
    
    def export_config(self) -> str:
        """导出配置为JSON字符串"""
        return json.dumps(
            {"providers": [p.to_dict() for p in self._providers.values()]},
            ensure_ascii=False,
            indent=2,
        )
    
    def import_config(self, json_str: str) -> int:
        """
        从JSON导入配置
        
        Returns:
            int: 导入的提供者数量
        """
        try:
            data = json.loads(json_str)
            count = 0
            for p_data in data.get("providers", []):
                self.add_provider(
                    name=p_data["name"],
                    provider_type=ProviderType(p_data.get("provider_type", "custom")),
                    cost_type=CostType(p_data.get("cost_type", "paid")),
                    api_key=p_data.get("api_key", ""),
                    endpoint_base_url=p_data.get("endpoint", {}).get("base_url", ""),
                    priority=p_data.get("priority", 100),
                    default_model=p_data.get("default_model", ""),
                    description=p_data.get("description", ""),
                )
                count += 1
            return count
        except Exception as e:
            raise ValueError(f"导入配置失败: {e}")


# ── 单例访问函数 ─────────────────────────────────────────────────────────────

_provider_manager: Optional[ExternalProviderManager] = None


def get_provider_manager() -> ExternalProviderManager:
    """获取全局提供者管理器实例"""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = ExternalProviderManager()
    return _provider_manager


# ── 测试 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("外部模型提供者配置系统测试")
    logger.info("=" * 60)
    
    manager = ExternalProviderManager()
    
    # 列出模板
    logger.info("\n[内置模板]")
    for template in manager.get_templates():
        logger.info(f"  - {template.name} ({template.provider_type.value})")
        logger.info(f"    费用类型: {template.cost_type.value}")
        logger.info(f"    模型: {[m.model_name for m in template.models[:2]]}")
    
    # 添加自定义提供者
    logger.info("\n[添加自定义提供者]")
    provider_id = manager.add_provider(
        name="我的天工AI",
        provider_type=ProviderType.TIANGONG,
        cost_type=CostType.PAID,
        endpoint_base_url="https://api.tiangong.cn",
        api_key="sk-xxx",
        priority=15,
        description="天工AI大模型",
    )
    logger.info(f"  添加成功: {provider_id}")
    
    # 获取最优免费提供者
    logger.info("\n[最优免费提供者]")
    free_provider = manager.get_best_free_provider()
    if free_provider:
        logger.info(f"  {free_provider.name}")
    else:
        logger.info("  没有可用的免费提供者")
    
    # 获取所有可用提供者
    logger.info("\n[所有可用提供者 (优先免费)]")
    for p in manager.get_available_providers(include_free_first=True):
        status = "✓" if p.enabled else "✗"
        cost = "FREE" if p.is_free() else "PAID"
        logger.info(f"  {status} [{cost}] {p.name} (优先级: {p.priority})")
    
    # 统计信息
    logger.info("\n[统计信息]")
    stats = manager.get_stats()
    logger.info(f"  总计: {stats['total']}")
    logger.info(f"  启用: {stats['enabled']}")
    logger.info(f"  免费: {stats['free']}")
    logger.info(f"  活跃: {stats['active']}")
    
    # 清理测试数据
    manager.remove_provider(provider_id)
    logger.info(f"\n[清理测试数据] 已删除 {provider_id}")
    
    logger.info("\n" + "=" * 60)
