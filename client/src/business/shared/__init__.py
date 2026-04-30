"""
共享基础设施模块 (Shared Infrastructure)

提供系统级的基础设施支持：
1. 依赖注入容器
2. 统一术语模型
3. 配置中心
4. 事件总线
5. 缓存层
6. 统一异常体系
"""

# 依赖注入容器
from .dependency_injection import (
    Container,
    ServiceDefinition,
    get_container,
    register_service,
    resolve_service
)

# 统一术语模型
from .term_model import (
    Term,
    TermConflict,
    TermStatistics,
    TermNormalizer
)

# 配置中心
from .config_center import (
    ConfigCenter,
    ConfigEntry,
    get_config,
    load_config_file,
    get_config_value,
    set_config_value
)

# 事件总线
from .event_bus import (
    EventBus,
    Event,
    EVENTS,
    get_event_bus,
    subscribe_event,
    publish_event
)

# 缓存层
from .cache_layer import (
    CacheLayer,
    MultiLevelCache,
    CacheEntry,
    get_cache,
    cache_get,
    cache_set,
    cache_invalidate
)

# 统一异常体系
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
    handle_exception
)


__all__ = [
    # 依赖注入容器
    "Container",
    "ServiceDefinition",
    "get_container",
    "register_service",
    "resolve_service",
    
    # 统一术语模型
    "Term",
    "TermConflict",
    "TermStatistics",
    "TermNormalizer",
    
    # 配置中心
    "ConfigCenter",
    "ConfigEntry",
    "get_config",
    "load_config_file",
    "get_config_value",
    "set_config_value",
    
    # 事件总线
    "EventBus",
    "Event",
    "EVENTS",
    "get_event_bus",
    "subscribe_event",
    "publish_event",
    
    # 缓存层
    "CacheLayer",
    "MultiLevelCache",
    "CacheEntry",
    "get_cache",
    "cache_get",
    "cache_set",
    "cache_invalidate",
    
    # 统一异常体系
    "LTAException",
    "ConfigError",
    "ValidationError",
    "ServiceNotFoundError",
    "CircularDependencyError",
    "DocumentValidationError",
    "TermConflictError",
    "TrainingError",
    "RetrievalError",
    "ModelNotFoundError",
    "PermissionError",
    "ResourceNotFoundError",
    "ExternalServiceError",
    "RateLimitError",
    "InvalidArgumentError",
    "ERROR_CODES",
    "get_http_status",
    "handle_exception"
]


__version__ = "1.0.0"
__author__ = "LivingTree AI Team"
__description__ = "Shared Infrastructure Module"