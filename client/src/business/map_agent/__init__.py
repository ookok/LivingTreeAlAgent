"""
地图空间智能中枢 (Map Agent)

Full migration complete. → livingtree.core.map_agent

核心功能：统一地图网关、空间感知、几何操作、叠加分析、路径可达性、截图导出
"""
from .map_agent_controller import MapAgentController, MapInteractionMode, get_map_agent_controller
from .tools.perception_tool import PerceptionTool, SpatialIdentity
from .tools.geometry_tool import GeometryTool, GeometryOperation
from .tools.overlay_analysis_tool import OverlayAnalysisTool, OverlayResult
from .tools.mobility_tool import MobilityTool, RouteAnalysisResult
from .tools.export_tool import ExportTool, ExportFormat
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
from .map_gateway import MapGateway, get_map_gateway, MapProvider, ServiceType, CoordinateSystem

__all__ = [
    # 网关
    "MapGateway",
    "get_map_gateway",
    "MapProvider",
    "ServiceType",
    "CoordinateSystem",
    
    # 控制器
    "MapAgentController",
    "MapInteractionMode",
    "get_map_agent_controller",
    
    # 工具
    "PerceptionTool",
    "GeometryTool",
    "OverlayAnalysisTool",
    "MobilityTool",
    "ExportTool",
    
    # 数据结构
    "SpatialIdentity",
    "GeometryOperation",
    "OverlayResult",
    "RouteAnalysisResult",
    "ExportFormat",
    
    # 配置
    "MAP_CONFIG",
    "get_api_key",
    "get_secret_key",
    "get_base_url",
    "get_timeout",
    "is_debug_enabled",
    "update_config",
    "validate_config",
    "print_config_summary",
]