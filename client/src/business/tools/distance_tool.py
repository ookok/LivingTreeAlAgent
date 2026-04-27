"""
DistanceTool - 距离计算工具

实现 Haversine 公式和其他距离计算方法
"""

import math
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from loguru import logger


@dataclass
class DistanceResult:
    """距离计算结果"""
    distance: float
    unit: str
    from_point: Dict[str, float]
    to_point: Dict[str, float]


class DistanceTool(BaseTool):
    """
    距离计算工具
    
    支持多种距离计算方法：
    - Haversine：球面距离（基于地球椭球体）
    - Vincenty：更高精度的椭球体距离
    - Euclidean：平面欧几里得距离
    - Manhattan：曼哈顿距离
    
    功能：
    - 两点间距离计算
    - 多点路径距离计算
    - 距离矩阵生成
    - 单位转换
    """
    
    # WGS84 椭球体参数
    EARTH_RADIUS_KM = 6371.0  # 平均半径
    EARTH_SEMIMAJOR_M = 6378137.0  # 长半轴
    EARTH_SEMIMINOR_M = 6356752.314245  # 短半轴
    
    def __init__(self):
        super().__init__(
            name="distance_tool",
            description="Calculate distances between geographic coordinates. "
                       "Supports Haversine (great-circle), Vincenty (high-precision ellipsoid), "
                       "Euclidean (flat plane), and Manhattan distance methods.",
            category="geo",
            tags=["geography", "distance", "coordinates", "haversine", "gis", "navigation"]
        )
    
    def execute(self, **kwargs) -> ToolResult:
        """
        执行距离计算
        
        Args:
            method: 计算方法 ("haversine", "vincenty", "euclidean", "manhattan")
            from_lat: 起点纬度
            from_lon: 起点经度
            to_lat: 终点纬度
            to_lon: 终点经度
            unit: 输出单位 ("km", "m", "miles", "nautical_miles")
            
        Returns:
            ToolResult with DistanceResult
        """
        try:
            method = kwargs.get("method", "haversine").lower()
            from_lat = float(kwargs.get("from_lat"))
            from_lon = float(kwargs.get("from_lon"))
            to_lat = float(kwargs.get("to_lat"))
            to_lon = float(kwargs.get("to_lon"))
            unit = kwargs.get("unit", "km")
            
            # 计算距离
            if method == "haversine":
                distance = self.haversine(from_lat, from_lon, to_lat, to_lon)
            elif method == "vincenty":
                distance = self.vincenty(from_lat, from_lon, to_lat, to_lon)
            elif method == "euclidean":
                distance = self.euclidean(from_lat, from_lon, to_lat, to_lon)
            elif method == "manhattan":
                distance = self.manhattan(from_lat, from_lon, to_lat, to_lon)
            else:
                return ToolResult.fail(error=f"Unknown method: {method}")
            
            # 单位转换
            distance_m = self.to_meters(distance, "km")
            final_distance = self.convert_unit(distance_m, "m", unit)
            
            return ToolResult.ok(
                data={
                    "distance": final_distance,
                    "unit": unit,
                    "method": method,
                    "from_point": {"lat": from_lat, "lon": from_lon},
                    "to_point": {"lat": to_lat, "lon": to_lon}
                },
                message=f"Distance: {final_distance:.4f} {unit} ({method})"
            )
            
        except Exception as e:
            logger.error(f"Distance calculation failed: {e}")
            return ToolResult.fail(error=str(e))
    
    def haversine(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        Haversine 公式计算球面距离
        
        Args:
            lat1, lon1: 起点坐标（度）
            lat2, lon2: 终点坐标（度）
            
        Returns:
            距离（公里）
        """
        # 转换为弧度
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        # Haversine 公式
        a = math.sin(dlat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return self.EARTH_RADIUS_KM * c
    
    def vincenty(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
        max_iterations: int = 200,
        tolerance: float = 1e-12
    ) -> float:
        """
        Vincenty 公式计算椭球体距离（更高精度）
        
        Args:
            lat1, lon1: 起点坐标（度）
            lat2, lon2: 终点坐标（度）
            max_iterations: 最大迭代次数
            tolerance: 收敛容差
            
        Returns:
            距离（米）
        """
        # 椭球体参数
        a = self.EARTH_SEMIMAJOR_M
        b = self.EARTH_SEMIMINOR_M
        f = (a - b) / a  # 扁率
        
        # 转换为弧度
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        L = math.radians(lon2 - lon1)
        
        U1 = math.atan((1 - f) * math.tan(lat1_rad))
        U2 = math.atan((1 - f) * math.tan(lat2_rad))
        
        sin_U1 = math.sin(U1)
        cos_U1 = math.cos(U1)
        sin_U2 = math.sin(U2)
        cos_U2 = math.cos(U2)
        
        lam = L
        lam_prev = 0
        iter_count = 0
        
        for _ in range(max_iterations):
            iter_count += 1
            
            sin_lam = math.sin(lam)
            cos_lam = math.cos(lam)
            
            sin_sigma = math.sqrt(
                (cos_U2 * sin_lam) ** 2 +
                (cos_U1 * sin_U2 - sin_U1 * cos_U2 * cos_lam) ** 2
            )
            cos_sigma = sin_U1 * sin_U2 + cos_U1 * cos_U2 * cos_lam
            sigma = math.atan2(sin_sigma, cos_sigma)
            
            sin_alpha = cos_U1 * cos_U2 * sin_lam / sin_sigma
            cos2_alpha = 1 - sin_alpha ** 2
            
            if cos2_alpha == 0:
                cos_2_sigma_m = 0
            else:
                cos_2_sigma_m = cos_sigma - 2 * sin_U1 * sin_U2 / cos2_alpha
            
            C = f / 16 * cos2_alpha * (4 + f * (4 - 3 * cos2_alpha))
            
            lam_prev = lam
            lam = L + (1 - C) * f * sin_alpha * (
                sigma + C * sin_sigma * (
                    cos_2_sigma_m + C * cos_sigma * (
                        -1 + 2 * cos_2_sigma_m ** 2
                    )
                )
            )
            
            if abs(lam - lam_prev) < tolerance:
                break
        
        u2 = cos2_alpha * (a ** 2 - b ** 2) / b ** 2
        A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
        B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
        
        delta_sigma = B * sin_sigma * (
            cos_2_sigma_m + B / 4 * (
                cos_sigma * (-1 + 2 * cos_2_sigma_m ** 2) -
                B / 6 * cos_2_sigma_m * (-3 + 4 * sin_sigma ** 2) * (-3 + 4 * cos_2_sigma_m ** 2)
            )
        )
        
        s = b * A * (sigma - delta_sigma)
        
        return s
    
    def euclidean(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        欧几里得距离（平面近似，适用于小范围）
        
        Args:
            lat1, lon1: 起点坐标（度）
            lat2, lon2: 终点坐标（度）
            
        Returns:
            距离（米）
        """
        # 每度对应的米数（近似）
        lat_per_m = 1 / 111320
        lon_per_m = 1 / (111320 * math.cos(math.radians((lat1 + lat2) / 2)))
        
        dx = (lon2 - lon1) / lon_per_m
        dy = (lat2 - lat1) / lat_per_m
        
        return math.sqrt(dx ** 2 + dy ** 2)
    
    def manhattan(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        曼哈顿距离
        
        Args:
            lat1, lon1: 起点坐标（度）
            lat2, lon2: 终点坐标（度）
            
        Returns:
            距离（米）
        """
        d_lat = self.euclidean(lat1, lon1, lat2, lon1)
        d_lon = self.euclidean(lat2, lon1, lat2, lon2)
        return d_lat + d_lon
    
    def to_meters(self, distance: float, unit: str) -> float:
        """转换为米"""
        conversions = {
            "m": 1,
            "km": 1000,
            "miles": 1609.344,
            "nautical_miles": 1852,
            "feet": 0.3048
        }
        return distance * conversions.get(unit, 1)
    
    def convert_unit(self, value: float, from_unit: str, to_unit: str) -> float:
        """单位转换"""
        meters = self.to_meters(value, from_unit)
        return meters / self._unit_to_factor(to_unit)
    
    def _unit_to_factor(self, unit: str) -> float:
        """获取单位对应的米数"""
        return self.to_meters(1, unit)
    
    def calculate_path_distance(
        self,
        points: List[Tuple[float, float]],
        method: str = "haversine"
    ) -> Dict[str, Any]:
        """
        计算路径总距离
        
        Args:
            points: 坐标点列表 [(lat, lon), ...]
            method: 计算方法
            
        Returns:
            路径信息和总距离
        """
        if len(points) < 2:
            return {"total_distance": 0, "segments": [], "unit": "km"}
        
        total = 0
        segments = []
        
        for i in range(len(points) - 1):
            lat1, lon1 = points[i]
            lat2, lon2 = points[i + 1]
            
            if method == "haversine":
                dist = self.haversine(lat1, lon1, lat2, lon2)
            elif method == "vincenty":
                dist = self.vincenty(lat1, lon1, lat2, lon2) / 1000
            else:
                dist = self.euclidean(lat1, lon1, lat2, lon2) / 1000
            
            total += dist
            segments.append({
                "from": {"lat": lat1, "lon": lon1},
                "to": {"lat": lat2, "lon": lon2},
                "distance": dist
            })
        
        return {
            "total_distance": total,
            "unit": "km",
            "segment_count": len(segments),
            "segments": segments
        }
    
    def generate_distance_matrix(
        self,
        points: List[Dict[str, float]]
    ) -> Dict[str, Any]:
        """
        生成距离矩阵
        
        Args:
            points: 坐标点列表 [{"lat": x, "lon": y}, ...]
            
        Returns:
            距离矩阵
        """
        n = len(points)
        matrix = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(i + 1, n):
                dist = self.haversine(
                    points[i]["lat"], points[i]["lon"],
                    points[j]["lat"], points[j]["lon"]
                )
                matrix[i][j] = dist
                matrix[j][i] = dist
        
        return {
            "matrix": matrix,
            "size": n,
            "unit": "km"
        }
    
    def find_nearest_point(
        self,
        target: Tuple[float, float],
        candidates: List[Tuple[float, float]]
    ) -> Dict[str, Any]:
        """
        找到最近点
        
        Args:
            target: 目标点 (lat, lon)
            candidates: 候选点列表
            
        Returns:
            最近点信息和距离
        """
        if not candidates:
            return {"error": "No candidates provided"}
        
        min_dist = float("inf")
        nearest_idx = 0
        
        for i, candidate in enumerate(candidates):
            dist = self.haversine(
                target[0], target[1],
                candidate[0], candidate[1]
            )
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i
        
        return {
            "nearest_index": nearest_idx,
            "nearest_point": {
                "lat": candidates[nearest_idx][0],
                "lon": candidates[nearest_idx][1]
            },
            "distance_km": min_dist
        }
    
    def health_check(self) -> bool:
        """健康检查"""
        # 距离工具不需要外部依赖
        test_result = self.haversine(0, 0, 1, 1)
        return 0 < test_result < 10000  # 验证计算结果合理
    
    def get_capabilities(self) -> Dict[str, Any]:
        """获取工具能力"""
        return {
            "name": self.name,
            "category": self.category,
            "methods": ["haversine", "vincenty", "euclidean", "manhattan"],
            "units": ["m", "km", "miles", "nautical_miles", "feet"],
            "features": [
                "Two-point distance calculation",
                "Path distance (multi-point)",
                "Distance matrix generation",
                "Unit conversion",
                "Nearest point search"
            ]
        }


# ── 自动注册 ─────────────────────────────────────────────────────────

def _auto_register():
    """自动注册工具到 ToolRegistry"""
    try:
        from client.src.business.tools.tool_registry import ToolRegistry
        registry = ToolRegistry.get_instance()
        
        tool = DistanceTool()
        if registry.register_tool(tool):
            logger.info(f"Auto-registered: {tool.name}")
            return True
    except Exception as e:
        logger.error(f"Auto-registration error: {e}")
    return False


# 调试用
if __name__ == "__main__":
    tool = DistanceTool()
    
    # 测试用例：北京到上海
    beijing = (39.9042, 116.4074)
    shanghai = (31.2304, 121.4737)
    
    print("=" * 50)
    print("Distance Tool Test")
    print("=" * 50)
    
    # Haversine
    dist_haversine = tool.haversine(*beijing, *shanghai)
    print(f"\nBeijing to Shanghai:")
    print(f"  Haversine: {dist_haversine:.2f} km")
    
    # Vincenty
    dist_vincenty = tool.vincenty(*beijing, *shanghai) / 1000
    print(f"  Vincenty:  {dist_vincenty:.2f} km")
    
    # Euclidean
    dist_euclidean = tool.euclidean(*beijing, *shanghai) / 1000
    print(f"  Euclidean: {dist_euclidean:.2f} km")
    
    print(f"\nTool capabilities: {tool.get_capabilities()}")
