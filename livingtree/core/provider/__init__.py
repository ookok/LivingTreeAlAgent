"""
Provider - 模型驱动层
桥接层: 委托到 client.src.business.provider
TODO: 逐步迁移到 livingtree/core/provider/
"""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_biz = os.path.join(_root, 'client', 'src')
if _biz not in sys.path:
    sys.path.insert(0, _biz)

from client.src.business.provider import *

from client.src.business.provider.base import (
    DriverMode, DriverState,
    ChatMessage, ChatRequest, ChatResponse,
    CompletionRequest, CompletionResponse,
    EmbeddingRequest, EmbeddingResponse,
    StreamChunk, UsageInfo,
    HealthReport, ModelDriver,
)
from client.src.business.provider.gateway import ModelGateway, RouteStrategy
from client.src.business.provider.fault_tolerance import (
    FaultToleranceManager, DegradationStrategy,
    CircuitBreaker, CircuitState,
)
from client.src.business.provider.monitor import ResourceMonitor, ResourceSnapshot, AppMetrics
from client.src.business.provider.config_manager import (
    ProviderConfigManager, ProviderConfig,
    ModelSlotConfig, ABTestConfig,
)
