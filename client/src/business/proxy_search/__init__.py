# -*- coding: utf-8 -*-
"""
代理搜索服务

功能：
- 多源聚合代理获取
- 三级验证机制
- 代理池管理
- 请求中间件
- 白名单路由
- 定时监测与断网保护
- 深度搜索集成
"""

from .config import (
    ProxySearchConfig,
    ProxySource,
    ValidatorConfig,
    ProxyPoolConfig,
    WhiteListConfig,
    get_config,
    update_config,
    add_source,
    remove_source,
    enable_source,
    add_target_url,
    should_use_proxy,
    get_allowed_domains,
)

from .proxy_sources import (
    Proxy,
    ProxyFetcher,
    get_fetcher,
    fetch_proxies,
)

from .validator import (
    ValidationResult,
    ProxyValidator,
    get_validator,
    validate_proxy,
    validate_proxies,
)

from .proxy_pool import (
    PooledProxy,
    ProxyPool,
    get_proxy_pool,
    initialize_pool,
)

from .proxy_middleware import (
    ProxyMiddleware,
    get_middleware,
    proxy_get,
    proxy_post,
    proxy_request,
    with_proxy,
)

from .url_router import (
    URLRouter,
    URLRouteResult,
    URLType,
    get_router,
    route_url,
    is_blocked,
    get_access_info,
)

from .monitor import (
    ProxyMonitor,
    HealthReport,
    HealthStatus,
    NetworkStatus,
    get_monitor,
    start_monitoring,
    stop_monitoring,
    get_latest_report,
    get_status_summary,
)

from .deep_search_integration import (
    DeepSearchProxyIntegration,
    DeepSearchRequest,
    DeepSearchResponse,
    SearchMode,
    get_integration,
    initialize_integration,
    route_input,
)

from .proxy_manager_widget import (
    ProxySourceTable,
    WhiteListTable,
    ProxyManagerWidget,
)


__all__ = [
    # 配置
    'ProxySearchConfig',
    'ProxySource',
    'ValidatorConfig',
    'ProxyPoolConfig',
    'WhiteListConfig',
    'get_config',
    'update_config',
    'add_source',
    'remove_source',
    'enable_source',
    'add_target_url',
    'should_use_proxy',
    'get_allowed_domains',

    # 代理源
    'Proxy',
    'ProxyFetcher',
    'get_fetcher',
    'fetch_proxies',

    # 验证器
    'ValidationResult',
    'ProxyValidator',
    'get_validator',
    'validate_proxy',
    'validate_proxies',

    # 代理池
    'PooledProxy',
    'ProxyPool',
    'get_proxy_pool',
    'initialize_pool',

    # 中间件
    'ProxyMiddleware',
    'get_middleware',
    'proxy_get',
    'proxy_post',
    'proxy_request',
    'with_proxy',

    # URL路由
    'URLRouter',
    'URLRouteResult',
    'URLType',
    'get_router',
    'route_url',
    'is_blocked',
    'get_access_info',

    # 监测
    'ProxyMonitor',
    'HealthReport',
    'HealthStatus',
    'NetworkStatus',
    'get_monitor',
    'start_monitoring',
    'stop_monitoring',
    'get_latest_report',
    'get_status_summary',

    # 深度搜索集成
    'DeepSearchProxyIntegration',
    'DeepSearchRequest',
    'DeepSearchResponse',
    'SearchMode',
    'get_integration',
    'initialize_integration',
    'route_input',

    # UI组件
    'ProxySourceTable',
    'WhiteListTable',
    'ProxyManagerWidget',
]
