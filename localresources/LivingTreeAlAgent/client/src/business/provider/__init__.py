"""
core.provider — 三模式模型驱动系统

支持三种模型驱动方式：
  1. 硬加载 (HardLoad)  — 直接在进程内加载 GGUF/Safetensors 模型
  2. 本地服务 (LocalService) — 连接本地运行的 OpenAI 兼容 API（Ollama/LMStudio/vLLM 等）
  3. 云服务 (CloudService) — 调用云端 API（OpenAI / Anthropic / Google / 兼容服务）

上层（L0/L3/L4）通过 ModelGateway 统一接口无缝切换。
"""

from .base import (
    DriverMode,
    DriverState,
    ChatRequest,
    ChatResponse,
    StreamChunk,
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelDriver,
    HealthReport,
)
from .hardload_driver import HardLoadDriver
from .local_service_driver import LocalServiceDriver
from .cloud_driver import CloudDriver
from .gateway import ModelGateway
from .fault_tolerance import FaultToleranceManager, DegradationStrategy
from .monitor import ResourceMonitor, ResourceSnapshot
from .config_manager import ProviderConfig, ModelSlotConfig, ABTestConfig, ProviderConfigManager

__all__ = [
    # 基础类型
    "DriverMode", "DriverState", "ChatRequest", "ChatResponse",
    "StreamChunk", "CompletionRequest", "CompletionResponse",
    "EmbeddingRequest", "EmbeddingResponse", "ModelDriver", "HealthReport",
    # 三驱动
    "HardLoadDriver", "LocalServiceDriver", "CloudDriver",
    # 网关
    "ModelGateway",
    # 容错
    "FaultToleranceManager", "DegradationStrategy",
    # 监控
    "ResourceMonitor", "ResourceSnapshot",
    # 配置
    "ProviderConfig", "ModelSlotConfig", "ABTestConfig", "ProviderConfigManager",
]
