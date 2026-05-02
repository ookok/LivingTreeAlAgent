"""
基础设施共享模块 (Shared Infrastructure)

提供系统级的基础设施支持:
1. 依赖注入容器
2. 统一术语模型
3. 缓存层
4. 统一异常体系

注意: 事件总线(event_bus)和配置中心(config_center)已迁移至 livingtree/infrastructure/
"""

from .dependency_injection import (
    Container,
    ServiceDefinition,
    get_container,
    register_service,
    resolve_service,
)

from .term_model import (
    Term,
    TermConflict,
    TermStatistics,
    TermNormalizer,
)

from .cache_layer import (
    CacheLayer,
    MultiLevelCache,
    CacheEntry,
    get_cache,
    cache_get,
    cache_set,
    cache_invalidate,
)

from .exceptions import (
    LTAException,
    ConfigError,
    ValidationError,
    ServiceNotFoundError,
    CircularDependencyError,
    DocumentValidationError,
    TermConflictError,
    TrainingError,
    RetrievalError,
    ModelNotFoundError,
    PermissionError,
    ResourceNotFoundError,
    ExternalServiceError,
    RateLimitError,
    InvalidArgumentError,
    ERROR_CODES,
    get_http_status,
    handle_exception,
)

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
