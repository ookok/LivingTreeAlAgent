"""
边界绘制服务
============

OpenLayers 边界绘制器服务：
1. HTML 模板生成
2. 边界数据解析
3. 坐标转换集成
4. 与 PyQt QWebEngineView 集成

Author: Hermes Desktop EIA System
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

from .html_template import get_html_template, BOUNDARY_DRAWER_HTML
from .models import (
    BoundaryFeature,
    BoundaryData,
    BoundaryType,
    BoundaryGeometry,
    FactoryBoundaryResult,
    calculate_factory_boundary,
)
from .coord_transform import (
    CoordTransformer,
    get_transformer,
    transform_coords,
    cad_to_geojson,
)


@dataclass
class BoundaryDrawerConfig:
    """边界绘制器配置"""
    # 地图配置
    default_center: tuple = (118.78, 32.07)  # (lon, lat)
    default_zoom: int = 14
    map_provider: str = "osm"  # osm/amap/google

    # 坐标系配置
    default_crs: str = "EPSG:4326"
    supported_crs: List[str] = None

    # 样式配置
    factory_fill_color: str = "rgba(25, 118, 210, 0.2)"
    factory_stroke_color: str = "#1976D2"
    factory_stroke_width: int = 2

    # 文件配置
    export_dir: str = ""

    def __post_init__(self):
        if self.supported_crs is None:
            self.supported_crs = [
                "EPSG:4326",  # WGS84
                "EPSG:4490",  # CGCS2000 经纬度
                "EPSG:4547",  # CGCS2000 3度带 117E
                "EPSG:4548",  # CGCS2000 3度带 120E
                "EPSG:4549",  # CGCS2000 3度带 123E
            ]


class BoundaryDrawerService:
    """
    边界绘制服务

    用法:
        # 1. 创建服务
        service = BoundaryDrawerService()

        # 2. 生成 HTML 文件
        html_path = service.generate_html()

        # 3. 在 PyQt QWebEngineView 中加载
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        view = QWebEngineView()
        view.load(QtCore.QUrl.fromLocalFile(html_path))

        # 4. 获取绘制结果
        data = service.parse_boundary_data(js_data)
    """

    def __init__(self, config: Optional[BoundaryDrawerConfig] = None):
        """
        Args:
            config: 边界绘制器配置
        """
        self.config = config or BoundaryDrawerConfig()
        self._temp_dir: Optional[Path] = None

    def _get_temp_dir(self) -> Path:
        """获取临时目录"""
        if self._temp_dir is None:
            self._temp_dir = Path(tempfile.mkdtemp(prefix="boundary_drawer_"))
        return self._temp_dir

    def generate_html(self, output_path: Optional[str] = None) -> str:
        """
        生成边界绘制 HTML 文件

        Args:
            output_path: 输出路径（可选）

        Returns:
            HTML 文件路径
        """
        html_content = get_html_template()

        if output_path:
            html_path = Path(output_path)
        else:
            html_path = self._get_temp_dir() / "boundary_drawer.html"

        html_path.write_text(html_content, encoding="utf-8")
        return str(html_path)

    def parse_boundary_data(self, geojson: Dict) -> BoundaryData:
        """
        解析边界数据

        Args:
            geojson: GeoJSON 数据

        Returns:
            BoundaryData 对象
        """
        return BoundaryData.from_geojson(geojson)

    def load_boundary_file(self, file_path: str) -> BoundaryData:
        """
        从文件加载边界数据

        Args:
            file_path: 文件路径（GeoJSON）

        Returns:
            BoundaryData 对象
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("type") == "FeatureCollection":
            return BoundaryData.from_geojson(data)
        elif data.get("type") == "BoundaryData":
            return BoundaryData.from_dict(data)
        else:
            raise ValueError(f"不支持的文件格式: {data.get('type')}")

    def save_boundary_data(self, data: BoundaryData, file_path: str):
        """
        保存边界数据到文件

        Args:
            data: BoundaryData 对象
            file_path: 输出文件路径
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)

    def export_to_geojson(self, data: BoundaryData, file_path: str):
        """
        导出为 GeoJSON

        Args:
            data: BoundaryData 对象
            file_path: 输出文件路径
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data.to_geojson(), f, ensure_ascii=False, indent=2)

    def calculate_boundary_info(
        self,
        boundary: BoundaryFeature
    ) -> FactoryBoundaryResult:
        """
        计算边界几何信息

        Args:
            boundary: 边界要素

        Returns:
            FactoryBoundaryResult
        """
        return calculate_factory_boundary(boundary)

    def convert_cad_coords(
        self,
        cad_coords: List[List[float]],
        src_crs: str = "EPSG:4547"
    ) -> List[List[float]]:
        """
        转换 CAD 坐标到 WGS84

        Args:
            cad_coords: CAD 坐标 [[x, y], ...]
            src_crs: 源坐标系

        Returns:
            WGS84 坐标 [[lon, lat], ...]
        """
        transformer = get_transformer()
        result = []

        for x, y in cad_coords:
            lon, lat = transformer.transform(x, y, src_crs, "EPSG:4326")
            result.append([lon, lat])

        return result

    def create_boundary_from_coords(
        self,
        coords: List[List[float]],
        name: str = "",
        boundary_type: BoundaryType = BoundaryType.FACTORY,
        src_crs: str = "EPSG:4326"
    ) -> BoundaryFeature:
        """
        从坐标创建边界

        Args:
            coords: 坐标列表 [[x, y], ...]
            name: 边界名称
            boundary_type: 边界类型
            src_crs: 源坐标系

        Returns:
            BoundaryFeature
        """
        # 坐标转换
        if src_crs != "EPSG:4326":
            transformer = get_transformer()
            transformed = []
            for x, y in coords:
                lon, lat = transformer.transform(x, y, src_crs, "EPSG:4326")
                transformed.append([lon, lat])
            coords = transformed

        # 闭合多边形
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])

        return BoundaryFeature(
            id=f"boundary_{len(coords)}",
            name=name,
            boundary_type=boundary_type,
            geometry=BoundaryGeometry(
                type="Polygon",
                coordinates=coords,
                crs="EPSG:4326"
            )
        )


# 全局实例
_global_service: Optional[BoundaryDrawerService] = None


def get_boundary_drawer_service(
    config: Optional[BoundaryDrawerConfig] = None
) -> BoundaryDrawerService:
    """获取全局边界绘制服务"""
    global _global_service
    if _global_service is None:
        _global_service = BoundaryDrawerService(config)
    return _global_service


def create_boundary_drawer() -> str:
    """
    快捷函数：创建边界绘制器 HTML

    Returns:
        HTML 文件路径
    """
    service = get_boundary_drawer_service()
    return service.generate_html()


def parse_boundary_json(geojson_str: str) -> BoundaryData:
    """
    快捷函数：解析边界 JSON

    Args:
        geojson_str: GeoJSON 字符串

    Returns:
        BoundaryData 对象
    """
    geojson = json.loads(geojson_str)
    return BoundaryData.from_geojson(geojson)


def cad_to_wgs84(
    cad_coords: List[List[float]],
    zone: int = 120
) -> List[List[float]]:
    """
    快捷函数：CAD 坐标转 WGS84

    Args:
        cad_coords: CAD 坐标 [[x, y], ...]
        zone: 中央经线 (默认 120E)

    Returns:
        WGS84 坐标 [[lon, lat], ...]
    """
    transformer = get_transformer()
    src_crs = f"EPSG:454{7 + (zone - 117)}" if zone >= 117 else f"EPSG:4547"

    result = []
    for x, y in cad_coords:
        lon, lat = transformer.transform(x, y, src_crs, "EPSG:4326")
        result.append([lon, lat])

    return result
