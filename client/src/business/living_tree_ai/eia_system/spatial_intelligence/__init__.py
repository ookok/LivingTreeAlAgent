"""
空间智能模块
============

基于地图API的空间分析能力

Author: Hermes Desktop EIA System
"""

from .spatial_engine import (
    POICategory,
    POIPoint,
    SensitiveZone,
    TerrainData,
    SpatialAnalysisResult,
    AMapAPI,
    TiandituAPI,
    GISDataLoader,
    SpatialIntelligenceEngine,
    get_spatial_engine,
    analyze_project_location,
)

# OpenLayers 边界绘制模块
from .boundary_drawer import (
    # 枚举
    BoundaryType,
    CoordinateSystem,
    # 模型
    Vertex,
    BoundaryGeometry,
    BoundaryFeature,
    BoundaryData,
    FactoryBoundaryResult,
    AermodSourcePoint,
    CoordinatePoint,
    PolygonBoundary,
    # 函数
    calculate_factory_boundary,
    get_transformer,
    transform_coords,
    cad_to_geojson,
    # 服务
    BoundaryDrawerConfig,
    BoundaryDrawerService,
    get_boundary_drawer_service,
    create_boundary_drawer,
    parse_boundary_json,
    cad_to_wgs84,
    # PyQt6 集成
    PYQT_AVAILABLE,
)

__all__ = [
    # 原有空间分析
    "POICategory",
    "POIPoint",
    "SensitiveZone",
    "TerrainData",
    "SpatialAnalysisResult",
    "AMapAPI",
    "TiandituAPI",
    "GISDataLoader",
    "SpatialIntelligenceEngine",
    "get_spatial_engine",
    "analyze_project_location",

    # OpenLayers 边界绘制
    "BoundaryType",
    "CoordinateSystem",
    "Vertex",
    "BoundaryGeometry",
    "BoundaryFeature",
    "BoundaryData",
    "FactoryBoundaryResult",
    "AermodSourcePoint",
    "CoordinatePoint",
    "PolygonBoundary",
    "calculate_factory_boundary",
    "get_transformer",
    "transform_coords",
    "cad_to_geojson",
    "BoundaryDrawerConfig",
    "BoundaryDrawerService",
    "get_boundary_drawer_service",
    "create_boundary_drawer",
    "parse_boundary_json",
    "cad_to_wgs84",
    "PYQT_AVAILABLE",
]
