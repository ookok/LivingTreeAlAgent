"""
坐标转换工具
============

支持 CGCS2000 / WGS84 / CAD 坐标的相互转换：
- CGCS2000 经纬度 (EPSG:4490)
- CGCS2000 3度带 (EPSG:4547~EPSG:4571)
- WGS84 经纬度 (EPSG:4326)
- UTM 坐标转换

Author: Hermes Desktop EIA System
"""

import math
from typing import Tuple, List, Optional
from dataclasses import dataclass
from enum import Enum


class CoordinateSystem(Enum):
    """坐标系枚举"""
    WGS84 = "EPSG:4326"           # WGS84 经纬度
    CGCS2000_LL = "EPSG:4490"     # CGCS2000 经纬度
    CGCS2000_3N_117 = "EPSG:4547" # CGCS2000 3度带 117E
    CGCS2000_3N_120 = "EPSG:4548" # CGCS2000 3度带 120E
    CGCS2000_3N_123 = "EPSG:4549" # CGCS2000 3度带 123E


@dataclass
class CoordinatePoint:
    """坐标点"""
    x: float
    y: float
    z: float = 0.0  # 高程
    crs: str = "EPSG:4326"

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class PolygonBoundary:
    """多边形边界"""
    vertices: List[CoordinatePoint]
    crs: str = "EPSG:4326"

    def to_geojson(self) -> dict:
        """转换为 GeoJSON 格式"""
        coordinates = [[pt.x, pt.y] for pt in self.vertices]
        # 闭合多边形
        if coordinates and coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])

        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates]
            },
            "properties": {
                "crs": self.crs,
                "vertex_count": len(self.vertices)
            }
        }


# CGCS2000 椭球参数
CGCS2000_A = 6378137.0  # 长半轴
CGCS2000_F = 1 / 298.257222101  # 扁率
CGCS2000_B = CGCS2000_A * (1 - CGCS2000_F)  # 短半轴
CGCS2000_E2 = (CGCS2000_A**2 - CGCS2000_B**2) / CGCS2000_A**2  # 第一偏心率的平方


class CoordTransformer:
    """
    坐标转换器

    支持：
    - 经纬度 <-> 平面直角坐标
    - 不同坐标系之间的转换
    """

    # 3度带中央经线映射
    ZONE_CENTRAL_MERIDIANS = {
        75: 75, 78: 78, 81: 81, 84: 84, 87: 87,
        90: 90, 93: 93, 96: 96, 99: 99, 102: 102,
        105: 105, 108: 108, 111: 111, 114: 114, 117: 117,
        120: 120, 123: 123, 126: 126, 129: 129, 132: 132
    }

    def __init__(self):
        pass

    def geodetic_to_cartesian(self, lon: float, lat: float, height: float = 0) -> Tuple[float, float, float]:
        """
        大地坐标转空间直角坐标

        Args:
            lon: 经度 (度)
            lat: 纬度 (度)
            height: 大地高 (米)

        Returns:
            (X, Y, Z) 空间直角坐标
        """
        # 转换为弧度
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)

        # 计算卯酉圈半径
        N = CGCS2000_A / math.sqrt(1 - CGCS2000_E2 * math.sin(lat_rad)**2)

        # 计算空间直角坐标
        X = (N + height) * math.cos(lat_rad) * math.cos(lon_rad)
        Y = (N + height) * math.cos(lat_rad) * math.sin(lon_rad)
        Z = (N * (1 - CGCS2000_E2) + height) * math.sin(lat_rad)

        return (X, Y, Z)

    def cartesian_to_geodetic(self, X: float, Y: float, Z: float = 0) -> Tuple[float, float, float]:
        """
        空间直角坐标转大地坐标

        Args:
            X, Y, Z: 空间直角坐标

        Returns:
            (lon, lat, height) 经纬度和大地高
        """
        # 初值
        lon = math.atan2(Y, X)
        p = math.sqrt(X**2 + Y**2)

        # 迭代计算纬度
        lat = math.atan2(Z, p * (1 - CGCS2000_E2))
        for _ in range(10):
            N = CGCS2000_A / math.sqrt(1 - CGCS2000_E2 * math.sin(lat)**2)
            lat_new = math.atan2(Z + CGCS2000_E2 * N * math.sin(lat), p)
            if abs(lat_new - lat) < 1e-12:
                break
            lat = lat_new

        # 计算大地高
        N = CGCS2000_A / math.sqrt(1 - CGCS2000_E2 * math.sin(lat)**2)
        height = p / math.cos(lat) - N

        return (math.degrees(lon), math.degrees(lat), height)

    def ll_to_xy(self, lon: float, lat: float, zone: int = 120) -> Tuple[float, float]:
        """
        经纬度转平面直角坐标（高斯-克吕格投影）

        Args:
            lon: 经度 (度)
            lat: 纬度 (度)
            zone: 中央经线 (度)

        Returns:
            (x, y) 平面直角坐标
        """
        # 转换为弧度
        lat_rad = math.radians(lat)
        lon0 = math.radians(zone)  # 中央经线
        l = math.radians(lon) - lon0  # 经差

        # 辅助计算
        cos_lat = math.cos(lat_rad)
        sin_lat = math.sin(lat_rad)
        tan_lat = math.tan(lat_rad)

        # 椭球参数
        eta2 = CGCS2000_E2 / (1 - CGCS2000_E2)
        N = CGCS2000_A / math.sqrt(1 - CGCS2000_E2 * sin_lat**2)

        # 子午线弧长
        A0 = 1 - CGCS2000_E2 / 4 - 3 * CGCS2000_E2**2 / 64
        A2 = 3/8 * (CGCS2000_E2 + CGCS2000_E2**2 / 4)
        A4 = 15/256 * (CGCS2000_E2**2)
        S = CGCS2000_A * (A0 * lat_rad - A2 * math.sin(2*lat_rad) + A4 * math.sin(4*lat_rad))

        # 平面坐标
        x = S + N * sin_lat * cos_lat * l**2 / 2
        x += N * sin_lat * cos_lat**3 * (5 - tan_lat**2 + 9*eta2) * l**4 / 24

        y = N * cos_lat * l
        y += N * cos_lat**3 * (1 - tan_lat**2 + eta2) * l**3 / 6

        # 添加假东偏移
        y += zone * 1000000 + 500000

        return (x, y)

    def xy_to_ll(self, x: float, y: float, zone: int = 120) -> Tuple[float, float]:
        """
        平面直角坐标转经纬度

        Args:
            x: 平面 x 坐标
            y: 平面 y 坐标
            zone: 中央经线 (度)

        Returns:
            (lon, lat) 经纬度
        """
        # 去除假东偏移
        y -= zone * 1000000 + 500000

        # 子午线弧长反算
        A0 = 1 - CGCS2000_E2 / 4 - 3 * CGCS2000_E2**2 / 64
        Bf = x / (CGCS2000_A * A0)

        # 迭代计算纬度
        lat = Bf
        for _ in range(10):
            N = CGCS2000_A / math.sqrt(1 - CGCS2000_E2 * math.sin(lat)**2)
            S = CGCS2000_A * (A0 * lat - (3*CGCS2000_E2/4) * math.sin(2*lat) + (15*CGCS2000_E2**2/64) * math.sin(4*lat))
            lat -= (x - S) / N
            if abs(lat - Bf) < 1e-12:
                break

        # 计算经度
        lon0 = math.radians(zone)
        cos_lat = math.cos(lat)
        sin_lat = math.sin(lat)
        tan_lat = math.tan(lat)
        eta2 = CGCS2000_E2 / (1 - CGCS2000_E2)
        N = CGCS2000_A / math.sqrt(1 - CGCS2000_E2 * sin_lat**2)

        # 经度
        l = y / (N * cos_lat)
        lon = lon0 + l

        return (math.degrees(lon), math.degrees(lat))

    def transform(self, x: float, y: float, src_crs: str, dst_crs: str) -> Tuple[float, float]:
        """
        坐标系转换

        Args:
            x, y: 坐标
            src_crs: 源坐标系
            dst_crs: 目标坐标系

        Returns:
            转换后的坐标
        """
        # 如果相同，直接返回
        if src_crs == dst_crs:
            return (x, y)

        # WGS84 <-> CGCS2000 经纬度 (简化处理，实际需要七参数转换)
        if (src_crs == "EPSG:4326" and dst_crs == "EPSG:4490") or \
           (src_crs == "EPSG:4490" and dst_crs == "EPSG:4326"):
            # 简化：WGS84 和 CGCS2000 差异很小（分米级）
            # 实际项目中建议使用专业转换库
            return (x, y)

        # 经纬度 -> 3度带
        if src_crs == "EPSG:4490" and dst_crs.startswith("EPSG:454"):
            zone = int(dst_crs.replace("EPSG:454", ""))
            return self.ll_to_xy(x, y, zone)

        # 3度带 -> 经纬度
        if src_crs.startswith("EPSG:454") and dst_crs == "EPSG:4490":
            zone = int(src_crs.replace("EPSG:454", ""))
            return self.xy_to_ll(x, y, zone)

        # WGS84 -> 3度带
        if src_crs == "EPSG:4326" and dst_crs.startswith("EPSG:454"):
            zone = int(dst_crs.replace("EPSG:454", ""))
            return self.ll_to_xy(x, y, zone)

        # 3度带 -> WGS84
        if src_crs.startswith("EPSG:454") and dst_crs == "EPSG:4326":
            zone = int(src_crs.replace("EPSG:454", ""))
            return self.xy_to_ll(x, y, zone)

        raise ValueError(f"不支持的坐标系转换: {src_crs} -> {dst_crs}")

    def get_central_meridian(self, zone_code: int) -> int:
        """
        根据带号获取中央经线

        Args:
            zone_code: 带号 (如 4547 表示 117E)

        Returns:
            中央经线经度
        """
        # EPSG:4547 -> 117
        zone = int(str(zone_code)[-2:])
        return zone


# 全局实例
_transformer: Optional[CoordTransformer] = None


def get_transformer() -> CoordTransformer:
    """获取全局坐标转换器"""
    global _transformer
    if _transformer is None:
        _transformer = CoordTransformer()
    return _transformer


def transform_coords(
    coords: List[Tuple[float, float]],
    src_crs: str,
    dst_crs: str
) -> List[Tuple[float, float]]:
    """
    批量转换坐标

    Args:
        coords: 坐标列表 [(x1,y1), (x2,y2), ...]
        src_crs: 源坐标系
        dst_crs: 目标坐标系

    Returns:
        转换后的坐标列表
    """
    transformer = get_transformer()
    return [transformer.transform(x, y, src_crs, dst_crs) for x, y in coords]


def cad_to_geojson(
    cad_coords: List[Tuple[float, float]],
    src_epsg: str = "EPSG:4547"
) -> dict:
    """
    CAD 坐标转 GeoJSON

    Args:
        cad_coords: CAD 坐标列表
        src_epsg: 源坐标系 EPSG 代码

    Returns:
        GeoJSON FeatureCollection
    """
    transformer = get_transformer()

    # 转换为经纬度
    wgs84_coords = []
    for x, y in cad_coords:
        lon, lat = transformer.transform(x, y, src_epsg, "EPSG:4326")
        wgs84_coords.append([lon, lat])

    # 闭合多边形
    if wgs84_coords and wgs84_coords[0] != wgs84_coords[-1]:
        wgs84_coords.append(wgs84_coords[0])

    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [wgs84_coords]
            },
            "properties": {
                "source_crs": src_epsg,
                "original_coords": cad_coords
            }
        }]
    }
