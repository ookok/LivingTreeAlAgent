"""
LivingTree 地图空间智能中枢
==========================

Full migration from client/src/business/map_agent/

支持高德/百度/腾讯/天地图四大地图服务商，集成坐标系转换、
多层缓存、智能路由、配额熔断等能力。
"""

from .map_gateway import (
    MapGateway,
    get_map_gateway,
    MapProvider,
    ServiceType,
    CoordinateSystem,
    ProviderConfig,
    CacheEntry,
)
from .config import (
    MAP_CONFIG,
    get_api_key,
    get_secret_key,
    get_base_url,
    get_timeout,
    is_debug_enabled,
    update_config,
    validate_config,
    print_config_summary,
)
from .map_agent_controller import (
    MapAgentController,
    MapInteractionMode,
    get_map_agent_controller,
)
from .tools.perception_tool import PerceptionTool, SpatialIdentity
from .tools.geometry_tool import GeometryTool, GeometryOperation
from .tools.overlay_analysis_tool import OverlayAnalysisTool, OverlayResult
from .tools.mobility_tool import MobilityTool, RouteAnalysisResult
from .tools.export_tool import ExportTool, ExportFormat

__all__ = [
    "MapGateway",
    "get_map_gateway",
    "MapProvider",
    "ServiceType",
    "CoordinateSystem",
    "ProviderConfig",
    "CacheEntry",
    "MAP_CONFIG",
    "get_api_key",
    "get_secret_key",
    "get_base_url",
    "get_timeout",
    "is_debug_enabled",
    "update_config",
    "validate_config",
    "print_config_summary",
    "MapAgentController",
    "MapInteractionMode",
    "get_map_agent_controller",
    "PerceptionTool",
    "SpatialIdentity",
    "GeometryTool",
    "GeometryOperation",
    "OverlayAnalysisTool",
    "OverlayResult",
    "MobilityTool",
    "RouteAnalysisResult",
    "ExportTool",
    "ExportFormat",
]
