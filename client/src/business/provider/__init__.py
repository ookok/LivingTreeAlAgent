"""
core.provider — 三模式模型驱动系统 (向后兼容层)

⚠️ 已迁移至 livingtree.adapters.providers
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.adapters.providers import (
    DriverMode, DriverState,
    ChatRequest, ChatResponse,
    StreamChunk, CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    ModelDriver, HealthReport,
    HardLoadDriver, LocalServiceDriver, CloudDriver,
    ModelGateway,
    FaultToleranceManager, DegradationStrategy,
    ResourceMonitor, ResourceSnapshot,
    ProviderConfig, ModelSlotConfig, ABTestConfig, ProviderConfigManager,
)

__all__ = [
    "DriverMode", "DriverState", "ChatRequest", "ChatResponse",
    "StreamChunk", "CompletionRequest", "CompletionResponse",
    "EmbeddingRequest", "EmbeddingResponse", "ModelDriver", "HealthReport",
    "HardLoadDriver", "LocalServiceDriver", "CloudDriver",
    "ModelGateway",
    "FaultToleranceManager", "DegradationStrategy",
    "ResourceMonitor", "ResourceSnapshot",
    "ProviderConfig", "ModelSlotConfig", "ABTestConfig", "ProviderConfigManager",
]
