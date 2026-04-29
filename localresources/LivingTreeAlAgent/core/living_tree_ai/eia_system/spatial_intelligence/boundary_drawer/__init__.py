"""
边界绘制模块
============

OpenLayers 专业边界绘制工具：
1. HTML 模板 - OpenLayers 7+ 地图引擎
2. 坐标转换 - CGCS2000 / WGS84 / CAD 坐标互转
3. 数据模型 - BoundaryFeature / BoundaryData
4. 服务层 - BoundaryDrawerService
5. PyQt6 集成 - BoundaryDrawerPanel

核心功能：
- 多边形绘制（支持孔洞）
- 坐标系转换（CGCS2000 3度带）
- 面积/周长实时计算
- GeoJSON / DXF / SHP 导入导出
- 中心点计算（用于大气预测）

Author: Hermes Desktop EIA System
"""

from .models import (
    BoundaryType,
    Vertex,
    BoundaryGeometry,
    BoundaryFeature,
    BoundaryData,
    FactoryBoundaryResult,
    AermodSourcePoint,
    calculate_factory_boundary,
)

from .coord_transform import (
    CoordinateSystem,
    CoordinatePoint,
    PolygonBoundary,
    CoordTransformer,
    get_transformer,
    transform_coords,
    cad_to_geojson,
)

from .boundary_drawer_service import (
    BoundaryDrawerConfig,
    BoundaryDrawerService,
    get_boundary_drawer_service,
    create_boundary_drawer,
    parse_boundary_json,
    cad_to_wgs84,
)

# PyQt6 集成（可选）
try:
    from .boundary_panel import (
        WebBridge,
        BoundaryDrawerPanel,
        BoundaryReviewDialog,
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


__all__ = [
    # 枚举
    "BoundaryType",
    "CoordinateSystem",

    # 模型
    "Vertex",
    "BoundaryGeometry",
    "BoundaryFeature",
    "BoundaryData",
    "FactoryBoundaryResult",
    "AermodSourcePoint",
    "CoordinatePoint",
    "PolygonBoundary",

    # 函数
    "calculate_factory_boundary",
    "get_transformer",
    "transform_coords",
    "cad_to_geojson",

    # 服务
    "BoundaryDrawerConfig",
    "BoundaryDrawerService",
    "get_boundary_drawer_service",
    "create_boundary_drawer",
    "parse_boundary_json",
    "cad_to_wgs84",

    # PyQt6 集成
    "PYQT_AVAILABLE",
]
