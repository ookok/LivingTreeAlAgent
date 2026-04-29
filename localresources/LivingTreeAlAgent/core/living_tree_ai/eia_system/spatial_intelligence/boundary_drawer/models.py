"""
边界绘制数据模型
================

Author: Hermes Desktop EIA System
"""

import json
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum


class BoundaryType(str, Enum):
    """边界类型"""
    FACTORY = "factory"           # 厂区边界
    PROTECTION = "protection"     # 防护距离
    NOISE = "noise"              # 噪声预测边界
    AIR = "air"                  # 大气预测边界
    CUSTOM = "custom"             # 自定义


@dataclass
class Vertex:
    """顶点"""
    x: float
    y: float
    z: float = 0.0  # 高程
    order: int = 0  # 顺序

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "Vertex":
        return cls(**d)


@dataclass
class BoundaryGeometry:
    """边界几何"""
    type: str = "Polygon"        # Point/LineString/Polygon
    coordinates: List[List[float]] = field(default_factory=list)
    crs: str = "EPSG:4326"       # 坐标系

    def to_dict(self) -> Dict:
        return {
            "type": self.type,
            "coordinates": self.coordinates,
            "crs": self.crs
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "BoundaryGeometry":
        return cls(
            type=d.get("type", "Polygon"),
            coordinates=d.get("coordinates", []),
            crs=d.get("crs", "EPSG:4326")
        )

    def get_vertices(self) -> List[Vertex]:
        """获取顶点列表"""
        vertices = []
        for i, coord in enumerate(self.coordinates):
            z = coord[2] if len(coord) > 2 else 0.0
            vertices.append(Vertex(x=coord[0], y=coord[1], z=z, order=i))
        return vertices

    def get_centroid(self) -> Tuple[float, float]:
        """计算几何中心"""
        if not self.coordinates:
            return (0.0, 0.0)

        xs = [c[0] for c in self.coordinates]
        ys = [c[1] for c in self.coordinates]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    def get_area(self) -> float:
        """计算多边形面积（简化）"""
        if self.type != "Polygon" or len(self.coordinates) < 3:
            return 0.0

        coords = self.coordinates
        area = 0.0
        for i in range(len(coords) - 1):
            area += coords[i][0] * coords[i+1][1]
            area -= coords[i+1][0] * coords[i][1]
        area = abs(area) / 2.0

        # 粗略转换为平方米（假设纬度1度 ≈ 111km）
        meters_per_degree = 111000.0
        return area * meters_per_degree * meters_per_degree

    def get_perimeter(self) -> float:
        """计算多边形周长"""
        if self.type != "Polygon" or len(self.coordinates) < 2:
            return 0.0

        perimeter = 0.0
        coords = self.coordinates
        for i in range(len(coords) - 1):
            dx = coords[i+1][0] - coords[i][0]
            dy = coords[i+1][1] - coords[i][1]
            perimeter += math.sqrt(dx*dx + dy*dy)

        # 转换为米
        meters_per_degree = 111000.0
        return perimeter * meters_per_degree


@dataclass
class BoundaryFeature:
    """边界要素"""
    id: str
    name: str = ""
    boundary_type: BoundaryType = BoundaryType.FACTORY
    geometry: BoundaryGeometry = field(default_factory=BoundaryGeometry)
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "boundary_type": self.boundary_type.value,
            "geometry": self.geometry.to_dict(),
            "properties": self.properties,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "BoundaryFeature":
        d = d.copy()
        d["geometry"] = BoundaryGeometry.from_dict(d.get("geometry", {}))
        d["boundary_type"] = BoundaryType(d.get("boundary_type", "factory"))
        d["created_at"] = datetime.fromisoformat(d["created_at"]) if "created_at" in d else datetime.now()
        d["updated_at"] = datetime.fromisoformat(d["updated_at"]) if "updated_at" in d else datetime.now()
        return cls(**d)

    def to_geojson(self) -> Dict:
        """转换为 GeoJSON Feature"""
        return {
            "type": "Feature",
            "id": self.id,
            "properties": {
                "name": self.name,
                "boundary_type": self.boundary_type.value,
                **self.properties
            },
            "geometry": {
                "type": self.geometry.type,
                "coordinates": self.geometry.coordinates
            }
        }

    @classmethod
    def from_geojson(cls, geojson: Dict) -> "BoundaryFeature":
        """从 GeoJSON 创建"""
        geom = geojson.get("geometry", {})
        props = geojson.get("properties", {})

        return cls(
            id=geojson.get("id", str(datetime.now().timestamp())),
            name=props.get("name", ""),
            boundary_type=BoundaryType(props.get("boundary_type", "factory")),
            geometry=BoundaryGeometry(
                type=geom.get("type", "Polygon"),
                coordinates=geom.get("coordinates", [])
            ),
            properties=props
        )


@dataclass
class BoundaryData:
    """边界数据"""
    project_id: str
    features: List[BoundaryFeature] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    crs: str = "EPSG:4326"
    version: str = "1.0"

    def to_dict(self) -> Dict:
        return {
            "type": "BoundaryData",
            "project_id": self.project_id,
            "crs": self.crs,
            "version": self.version,
            "metadata": self.metadata,
            "features": [f.to_dict() for f in self.features]
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "BoundaryData":
        return cls(
            project_id=d["project_id"],
            crs=d.get("crs", "EPSG:4326"),
            version=d.get("version", "1.0"),
            metadata=d.get("metadata", {}),
            features=[BoundaryFeature.from_dict(f) for f in d.get("features", [])]
        )

    def to_geojson(self) -> Dict:
        """转换为 GeoJSON FeatureCollection"""
        return {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": self.crs}
            },
            "features": [f.to_geojson() for f in self.features]
        }

    @classmethod
    def from_geojson(cls, geojson: Dict, project_id: str = "") -> "BoundaryData":
        """从 GeoJSON FeatureCollection 创建"""
        features = []
        for f in geojson.get("features", []):
            features.append(BoundaryFeature.from_geojson(f))

        crs_name = "EPSG:4326"
        crs = geojson.get("crs", {})
        if crs and crs.get("type") == "name":
            crs_name = crs.get("properties", {}).get("name", "EPSG:4326")

        return cls(
            project_id=project_id,
            crs=crs_name,
            features=features
        )

    def save_to_file(self, path: str):
        """保存到文件"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_file(cls, path: str) -> "BoundaryData":
        """从文件加载"""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


@dataclass
class FactoryBoundaryResult:
    """厂区边界计算结果"""
    boundary: BoundaryFeature
    area_sqm: float                 # 面积（平方米）
    area_hectare: float            # 面积（公顷）
    perimeter_m: float             # 周长（米）
    centroid: Tuple[float, float]   # 中心点 (lon, lat)
    center_utm: Tuple[float, float] # 中心点 UTM 坐标
    vertex_count: int              # 顶点数
    bounding_box: Tuple[float, float, float, float]  # (min_x, min_y, max_x, max_y)

    def to_dict(self) -> Dict:
        return {
            "boundary_id": self.boundary.id,
            "boundary_name": self.boundary.name,
            "area_sqm": round(self.area_sqm, 2),
            "area_hectare": round(self.area_hectare, 4),
            "perimeter_m": round(self.perimeter_m, 2),
            "centroid_lon": round(self.centroid[0], 6),
            "centroid_lat": round(self.centroid[1], 6),
            "center_utm_x": round(self.center_utm[0], 2),
            "center_utm_y": round(self.center_utm[1], 2),
            "vertex_count": self.vertex_count,
            "bounding_box": self.bounding_box
        }


@dataclass
class AermodSourcePoint:
    """AERMOD 排放源位置点"""
    x: float                       # UTM X
    y: float                       # UTM Y
    height: float                  # 排放口高度 (m)
    temperature: float = 293.15   # 烟气温度 (K)
    velocity: float = 0.0         # 出口流速 (m/s)
    diameter: float = 0.0         # 出口直径 (m)

    def to_dict(self) -> Dict:
        return asdict(self)


def calculate_factory_boundary(boundary: BoundaryFeature) -> FactoryBoundaryResult:
    """
    计算厂区边界几何信息

    Args:
        boundary: 边界要素

    Returns:
        FactoryBoundaryResult: 包含面积、周长、中心点等
    """
    geom = boundary.geometry

    # 计算面积
    area_sqm = geom.get_area()
    area_hectare = area_sqm / 10000

    # 计算周长
    perimeter_m = geom.get_perimeter()

    # 计算中心点
    centroid = geom.get_centroid()

    # 估算 UTM 中心点（简化处理）
    center_utm = (centroid[0] * 111000 * math.cos(math.radians(centroid[1])),
                  centroid[1] * 111000)

    # 获取顶点数
    vertex_count = len(geom.coordinates)

    # 边界框
    if geom.coordinates:
        xs = [c[0] for c in geom.coordinates]
        ys = [c[1] for c in geom.coordinates]
        bounding_box = (min(xs), min(ys), max(xs), max(ys))
    else:
        bounding_box = (0, 0, 0, 0)

    return FactoryBoundaryResult(
        boundary=boundary,
        area_sqm=area_sqm,
        area_hectare=area_hectare,
        perimeter_m=perimeter_m,
        centroid=centroid,
        center_utm=center_utm,
        vertex_count=vertex_count,
        bounding_box=bounding_box
    )
