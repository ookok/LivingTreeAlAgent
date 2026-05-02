"""
地图空间智能中枢 (Map Agent)

核心功能：
1. 统一地图网关 (Map Gateway) - 智能路由、多层缓存、配额管理、坐标系转换
2. 空间感知工具 - 获取坐标的"空间身份证"
3. 几何操作工具 - 画多边形、缓冲区、测距
4. 叠加分析工具 - 判断图层关系
5. 路径与可达性分析 - 交通影响评价
6. 截图与导出工具 - 高清图片导出

支持的地图服务商：
- 高德地图 (AMAP)
- 百度地图 (BAIDU)
- 腾讯地图 (TENCENT)
- 天地图 (TDITU) - 国家测绘局主导的"国家队"

支持的坐标系：
- WGS84: GPS原始坐标系
- GCJ02: 高德/谷歌加密坐标系
- BD09: 百度加密坐标系
- CGCS2000: 天地图国家标准坐标系

交互模式：
- Auto-Pilot: 全自动批处理
- Co-Pilot: AI建议 + 人工修正
- Sketch-to-Data: 手绘驱动生成

统一地图网关特性：
- 智能路由：根据配额、特长、成本自动选择服务商
- 多层缓存：内存→文件→分布式，减少重复请求
- 配额熔断：实时监控用量，接近耗尽自动切换
- 批量聚合：优化调用次数
- 坐标系转换：自动处理CGCS2000/GCJ-02/BD-09/WGS84互转

愿景：构建一个懂地理、懂空间、能画图、能算距离的"全能型工程咨询师"。

配置方法：
    from business.map_agent import MAP_CONFIG, update_config, validate_config
    
    # 更新API Key
    update_config(api_key='your_key')
    
    # 验证配置
    validate_config()

使用网关：
    from business.map_agent import get_map_gateway
    
    gateway = get_map_gateway()
    result = gateway.geocode("北京市朝阳区望京SOHO")
    
    # 坐标系转换
    lon, lat = gateway.convert_coordinates(116.4, 39.9, 
                                          CoordinateSystem.CGCS2000, 
                                          CoordinateSystem.GCJ02)
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