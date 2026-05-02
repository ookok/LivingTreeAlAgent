"""
共享基础设施模块 - 向后兼容层

⚠️ 已迁移至 livingtree.infrastructure.shared
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.infrastructure.shared import (
    Container, ServiceDefinition, get_container, register_service, resolve_service,
    Term, TermConflict, TermStatistics, TermNormalizer,
    CacheLayer, MultiLevelCache, CacheEntry, get_cache, cache_get, cache_set, cache_invalidate,
    LTAException, ConfigError, ValidationError, ServiceNotFoundError,
    CircularDependencyError, DocumentValidationError, TermConflictError,
    TrainingError, RetrievalError, ModelNotFoundError, PermissionError,
    ResourceNotFoundError, ExternalServiceError, RateLimitError, InvalidArgumentError,
    ERROR_CODES, get_http_status, handle_exception,
)

from livingtree.infrastructure.config import config as ConfigCenter, get_config
from livingtree.infrastructure.event_bus import EventBus, get_event_bus, EVENTS

__all__ = [
    "Container", "ServiceDefinition", "get_container", "register_service", "resolve_service",
    "Term", "TermConflict", "TermStatistics", "TermNormalizer",
    "CacheLayer", "MultiLevelCache", "CacheEntry", "get_cache", "cache_get", "cache_set", "cache_invalidate",
    "LTAException", "ConfigError", "ValidationError", "ServiceNotFoundError",
    "CircularDependencyError", "DocumentValidationError", "TermConflictError",
    "TrainingError", "RetrievalError", "ModelNotFoundError", "PermissionError",
    "ResourceNotFoundError", "ExternalServiceError", "RateLimitError", "InvalidArgumentError",
    "ERROR_CODES", "get_http_status", "handle_exception",
]

__version__ = "2.0.0"
__author__ = "LivingTree AI Team"
__description__ = "Shared Infrastructure Module (migrated → livingtree.infrastructure.shared)"
