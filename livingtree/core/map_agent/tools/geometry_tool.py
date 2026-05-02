"""
几何操作工具 (Geometry Tool)

功能：在地图上创建和操作几何图形。

子工具：
- draw_polygon（画多边形，用于厂界）
- draw_buffer（画缓冲区，用于卫生防护距离）
- measure_distance（测距）
- calculate_area（计算面积）
- calculate_perimeter（计算周长）

自动化逻辑：Agent计算出"卫生防护距离为300米"，自动调用draw_buffer(center, 300)，
            并在图上画出圆圈。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
import math


class GeometryOperation(Enum):
    """几何操作类型"""
    DRAW_POLYGON = "draw_polygon"
    DRAW_BUFFER = "draw_buffer"
    MEASURE_DISTANCE = "measure_distance"
    CALCULATE_AREA = "calculate_area"
    CALCULATE_PERIMETER = "calculate_perimeter"
    INTERSECT = "intersect"
    UNION = "union"
    DIFFERENCE = "difference"


@dataclass
class Point:
    """点坐标"""
    longitude: float
    latitude: float


@dataclass
class Polygon:
    """多边形"""
    points: List[Point] = field(default_factory=list)
    name: str = ""
    color: str = "#FF0000"
    opacity: float = 0.3


@dataclass
class Buffer:
    """缓冲区"""
    center: Point
    radius: float  # 米
    name: str = ""
    color: str = "#00FF00"
    opacity: float = 0.2


@dataclass
class GeometryResult:
    """几何操作结果"""
    operation: GeometryOperation
    success: bool = True
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


class GeometryTool:
    """
    几何操作工具
    
    核心能力：
    1. 创建多边形（厂界）
    2. 创建缓冲区（卫生防护距离）
    3. 测量距离
    4. 计算面积和周长
    5. 几何运算（交集、并集、差集）
    """
    
    def __init__(self):
        self.polygons: Dict[str, Polygon] = {}
        self.buffers: Dict[str, Buffer] = {}
        self.next_id = 1
    
    def draw_polygon(self, points: List[Tuple[float, float]], name: str = "") -> GeometryResult:
        """
        画多边形
        
        Args:
            points: 坐标点列表 [(lon1, lat1), (lon2, lat2), ...]
            name: 多边形名称
        
        Returns:
            GeometryResult
        """
        try:
            polygon_points = [Point(lon, lat) for lon, lat in points]
            
            # 确保多边形闭合
            if polygon_points:
                first = polygon_points[0]
                last = polygon_points[-1]
                if first.longitude != last.longitude or first.latitude != last.latitude:
                    polygon_points.append(first)
            
            polygon = Polygon(
                points=polygon_points,
                name=name or f"多边形{self.next_id}",
                color="#FF0000",
                opacity=0.3
            )
            
            poly_id = f"poly_{self.next_id}"
            self.polygons[poly_id] = polygon
            self.next_id += 1
            
            area = self.calculate_polygon_area(polygon_points)
            perimeter = self.calculate_polygon_perimeter(polygon_points)
            
            return GeometryResult(
                operation=GeometryOperation.DRAW_POLYGON,
                success=True,
                message=f"多边形创建成功",
                data={
                    "id": poly_id,
                    "name": polygon.name,
                    "point_count": len(polygon.points),
                    "area": round(area, 2),
                    "perimeter": round(perimeter, 2),
                    "area_unit": "平方米"
                }
            )
        
        except Exception as e:
            return GeometryResult(
                operation=GeometryOperation.DRAW_POLYGON,
                success=False,
                message=f"创建多边形失败: {str(e)}"
            )
    
    def draw_buffer(self, center: Tuple[float, float], radius: float, name: str = "") -> GeometryResult:
        """
        画缓冲区
        
        Args:
            center: 中心点坐标 (lon, lat)
            radius: 半径（米）
            name: 缓冲区名称
        
        Returns:
            GeometryResult
        """
        try:
            buffer = Buffer(
                center=Point(*center),
                radius=radius,
                name=name or f"缓冲区{self.next_id}",
                color="#00FF00",
                opacity=0.2
            )
            
            buffer_id = f"buffer_{self.next_id}"
            self.buffers[buffer_id] = buffer
            self.next_id += 1
            
            area = math.pi * radius * radius
            
            return GeometryResult(
                operation=GeometryOperation.DRAW_BUFFER,
                success=True,
                message=f"缓冲区创建成功，半径{radius}米",
                data={
                    "id": buffer_id,
                    "name": buffer.name,
                    "center": center,
                    "radius": radius,
                    "area": round(area, 2),
                    "area_unit": "平方米"
                }
            )
        
        except Exception as e:
            return GeometryResult(
                operation=GeometryOperation.DRAW_BUFFER,
                success=False,
                message=f"创建缓冲区失败: {str(e)}"
            )
    
    def measure_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> GeometryResult:
        """
        测量两点之间的距离
        
        Args:
            point1: 点1坐标 (lon, lat)
            point2: 点2坐标 (lon, lat)
        
        Returns:
            GeometryResult
        """
        try:
            distance = self._calculate_distance(point1, point2)
            
            return GeometryResult(
                operation=GeometryOperation.MEASURE_DISTANCE,
                success=True,
                message=f"距离测量完成",
                data={
                    "point1": point1,
                    "point2": point2,
                    "distance": round(distance, 2),
                    "unit": "米"
                }
            )
        
        except Exception as e:
            return GeometryResult(
                operation=GeometryOperation.MEASURE_DISTANCE,
                success=False,
                message=f"测量距离失败: {str(e)}"
            )
    
    def calculate_area(self, polygon_id: str) -> GeometryResult:
        """
        计算多边形面积
        
        Args:
            polygon_id: 多边形ID
        
        Returns:
            GeometryResult
        """
        try:
            if polygon_id not in self.polygons:
                return GeometryResult(
                    operation=GeometryOperation.CALCULATE_AREA,
                    success=False,
                    message=f"多边形{polygon_id}不存在"
                )
            
            polygon = self.polygons[polygon_id]
            area = self.calculate_polygon_area([p for p in polygon.points])
            
            return GeometryResult(
                operation=GeometryOperation.CALCULATE_AREA,
                success=True,
                message=f"面积计算完成",
                data={
                    "polygon_id": polygon_id,
                    "name": polygon.name,
                    "area": round(area, 2),
                    "unit": "平方米"
                }
            )
        
        except Exception as e:
            return GeometryResult(
                operation=GeometryOperation.CALCULATE_AREA,
                success=False,
                message=f"计算面积失败: {str(e)}"
            )
    
    def calculate_perimeter(self, polygon_id: str) -> GeometryResult:
        """
        计算多边形周长
        
        Args:
            polygon_id: 多边形ID
        
        Returns:
            GeometryResult
        """
        try:
            if polygon_id not in self.polygons:
                return GeometryResult(
                    operation=GeometryOperation.CALCULATE_PERIMETER,
                    success=False,
                    message=f"多边形{polygon_id}不存在"
                )
            
            polygon = self.polygons[polygon_id]
            perimeter = self.calculate_polygon_perimeter([p for p in polygon.points])
            
            return GeometryResult(
                operation=GeometryOperation.CALCULATE_PERIMETER,
                success=True,
                message=f"周长计算完成",
                data={
                    "polygon_id": polygon_id,
                    "name": polygon.name,
                    "perimeter": round(perimeter, 2),
                    "unit": "米"
                }
            )
        
        except Exception as e:
            return GeometryResult(
                operation=GeometryOperation.CALCULATE_PERIMETER,
                success=False,
                message=f"计算周长失败: {str(e)}"
            )
    
    def calculate_polygon_area(self, points: List[Point]) -> float:
        """
        计算多边形面积（使用 shoelace 公式）
        
        Args:
            points: 点列表
        
        Returns:
            面积（平方米）
        """
        if len(points) < 3:
            return 0.0
        
        # 将经纬度转换为平面坐标（简化计算）
        # 实际应使用UTM投影或其他投影方式
        area = 0.0
        n = len(points)
        
        for i in range(n):
            j = (i + 1) % n
            area += points[i].longitude * points[j].latitude
            area -= points[j].longitude * points[i].latitude
        
        area = abs(area) / 2.0
        
        # 转换为平方米（粗略估算）
        # 1度经度 ≈ 111320米（赤道）
        # 1度纬度 ≈ 110574米
        area_m2 = area * 111320 * 110574
        
        return area_m2
    
    def calculate_polygon_perimeter(self, points: List[Point]) -> float:
        """
        计算多边形周长
        
        Args:
            points: 点列表
        
        Returns:
            周长（米）
        """
        if len(points) < 2:
            return 0.0
        
        perimeter = 0.0
        n = len(points)
        
        for i in range(n):
            j = (i + 1) % n
            perimeter += self._calculate_distance(
                (points[i].longitude, points[i].latitude),
                (points[j].longitude, points[j].latitude)
            )
        
        return perimeter
    
    def _calculate_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """
        计算两点之间的距离（米）
        
        使用 Haversine 公式计算球面距离
        """
        lon1, lat1 = point1
        lon2, lat2 = point2
        
        # 转换为弧度
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine公式
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        # 地球半径（米）
        radius = 6371000
        
        return radius * c
    
    def get_polygon(self, polygon_id: str) -> Optional[Polygon]:
        """获取多边形"""
        return self.polygons.get(polygon_id)
    
    def get_buffer(self, buffer_id: str) -> Optional[Buffer]:
        """获取缓冲区"""
        return self.buffers.get(buffer_id)
    
    def list_polygons(self) -> List[Dict[str, Any]]:
        """列出所有多边形"""
        result = []
        for poly_id, polygon in self.polygons.items():
            result.append({
                "id": poly_id,
                "name": polygon.name,
                "point_count": len(polygon.points),
                "color": polygon.color
            })
        return result
    
    def list_buffers(self) -> List[Dict[str, Any]]:
        """列出所有缓冲区"""
        result = []
        for buf_id, buffer in self.buffers.items():
            result.append({
                "id": buf_id,
                "name": buffer.name,
                "center": (buffer.center.longitude, buffer.center.latitude),
                "radius": buffer.radius
            })
        return result
    
    def clear_all(self):
        """清除所有几何图形"""
        self.polygons.clear()
        self.buffers.clear()
        self.next_id = 1