"""
LLM 提供商模块

借鉴 pi-mono 的极简设计哲学，提供统一的 LLM 调用抽象层。

模块结构：
- base_provider.py: 抽象基类
- provider_registry.py: 提供商注册中心 (40+ providers)
- ollama_provider.py: Ollama 提供商
- openai_provider.py: OpenAI 提供商
- anthropic_provider.py: Anthropic 提供商
- google_provider.py: Google 提供商

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from .base_provider import (
    BaseProvider,
    ProviderType,
    ModelCapability,
    ModelInfo,
    ChatMessage,
    UsageInfo,
    ProviderResponse
)
from .provider_registry import (
    ProviderConfig,
    ProviderRegistry,
    ModelConfig,
    TransportType,
    ProviderCategory,
    PROVIDER_CATALOG,
    get_provider_registry
)

__all__ = [
    # base_provider
    "BaseProvider",
    "ProviderType",
    "ModelCapability",
    "ModelInfo",
    "ChatMessage",
    "UsageInfo",
    "ProviderResponse",
    # provider_registry
    "ProviderConfig",
    "ProviderRegistry",
    "ModelConfig",
    "TransportType",
    "ProviderCategory",
    "PROVIDER_CATALOG",
    "get_provider_registry",
]
