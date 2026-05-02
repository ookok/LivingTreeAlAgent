"""
Model Providers — 三模式模型驱动系统 + Provider 目录

三模式:
  - HardLoad: 进程内直接加载 GGUF/Safetensors 模型
  - LocalService: 连接本地 OpenAI 兼容 API (Ollama/LMStudio/vLLM)
  - CloudService: 调用云端 API (OpenAI/Anthropic/Google/DeepSeek)

Provider 目录:
  - 统一模型列表与发现
"""

from .base import (
    DriverMode, DriverState,
    ChatMessage, ChatRequest, ChatResponse,
    CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    StreamChunk, ModelDriver, HealthReport, UsageInfo,
)
from .hardload_driver import HardLoadDriver
from .local_service_driver import LocalServiceDriver
from .cloud_driver import CloudDriver
from .gateway import ModelGateway, RouteStrategy, RouteResult
from .fault_tolerance import FaultToleranceManager, DegradationStrategy
from .monitor import (
    ResourceMonitor, ResourceSnapshot, AppMetrics,
    GPUMetrics, CPUMetrics, MemoryMetrics,
)
from .config_manager import (
    ProviderConfig, ModelSlotConfig, ABTestConfig, ProviderConfigManager,
)

from .cloud import OpenAICompatibleDriver as CloudOpenAICompatibleDriver
from .hard_load import (
    register_hard_backend, get_hard_backend,
    list_backends, create_hard_driver,
)
from .local_service import OpenAICompatibleDriver as LocalServiceOpenAICompatibleDriver

__all__ = [
    "DriverMode", "DriverState",
    "ChatMessage", "ChatRequest", "ChatResponse",
    "CompletionRequest", "CompletionResponse",
    "EmbeddingRequest", "EmbeddingResponse",
    "StreamChunk", "ModelDriver", "HealthReport", "UsageInfo",
    "HardLoadDriver", "LocalServiceDriver", "CloudDriver",
    "ModelGateway", "RouteStrategy", "RouteResult",
    "FaultToleranceManager", "DegradationStrategy",
    "ResourceMonitor", "ResourceSnapshot", "AppMetrics",
    "GPUMetrics", "CPUMetrics", "MemoryMetrics",
    "ProviderConfig", "ModelSlotConfig", "ABTestConfig", "ProviderConfigManager",
    "CloudOpenAICompatibleDriver", "LocalServiceOpenAICompatibleDriver",
    "register_hard_backend", "get_hard_backend",
    "list_backends", "create_hard_driver",
]
