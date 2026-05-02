"""
DeCommerce 服务处理器
Service Handlers for different service types
"""

from .base import BaseServiceHandler, ServiceHandlerRegistry, get_handler_registry
from .live_view import RemoteLiveViewHandler
from .ai_computing import AIComputingHandler
from .remote_assist import RemoteAssistHandler
from .knowledge_consult import KnowledgeConsultHandler

__all__ = [
    "BaseServiceHandler",
    "ServiceHandlerRegistry",
    "get_handler_registry",
    "RemoteLiveViewHandler",
    "AIComputingHandler",
    "RemoteAssistHandler",
    "KnowledgeConsultHandler",
]