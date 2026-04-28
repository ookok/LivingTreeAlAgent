"""
DistanceCalculator - 距离计算工具

使用 Haversine 公式计算两点间的大圆距离。

遵循自我进化原则：
- 支持多种距离单位
- 自动学习常用坐标对
"""

import math
from typing import Dict, Any
from loguru import logger

try:
    from client.src.business.tools.base_tool import BaseTool, ToolResult
except ImportError:
    from tools.base_tool import BaseTool, ToolResult


@dataclass
class DistanceResult:
    """距离计算结果"""
    distance_km: float
    distance_miles: float
    distance_meters: float
    unit: str


class DistanceCalculator(BaseTool):
    """
    距离计算工具
    
    使用 Haversine 公式计算两点间的大圆距离。
    """

    def __init__(self):
        self._logger = logger.bind(component="DistanceCalculator")
        self._calculation_history = []

    @property
    def name(self) -> str:
        return "distance_calculator"

    @property
    def description(self) -> str:
        return "Haversine 公式计算两点间大圆距离"

    @property
    def category(self) -> str:
        return "geo"

    @property
    def parameters(self) -> Dict[str, str]:
        return {
            "lat1": "float",
            "lon1": "float",
            "lat2": "float",
            "lon2": "float",
            "unit": "str"
        }

    async def execute(self, lat1: float, lon1: float, lat2: float, lon2: float, 
                      unit: str = "km") -> ToolResult:
        """
        计算两点间距离
        
        Args:
            lat1: 点1纬度
            lon1: 点1经度
            lat2: 点2纬度
            lon2: 点2经度
            unit: 输出单位（km/miles/meters）
            
        Returns:
            ToolResult
        """
        self._logger.info(f"计算距离: ({lat1}, {lon1}) -> ({lat2}, {lon2})")

        try:
            # 验证坐标范围
            if not (-90 <= lat1 <= 90) or not (-90 <= lat2 <= 90):
                return ToolResult.error_result("纬度必须在 -90 到 90 之间")
            
            if not (-180 <= lon1 <= 180) or not (-180 <= lon2 <= 180):
                return ToolResult.error_result("经度必须在 -180 到 180 之间")

            # 使用 Haversine 公式计算
            distance_km = self._haversine(lat1, lon1, lat2, lon2)
            
            # 转换为不同单位
            distance_miles = distance_km * 0.621371
            distance_meters = distance_km * 1000

            # 记录计算历史
            self._calculation_history.append({
                "lat1": lat1, "lon1": lon1,
                "lat2": lat2, "lon2": lon2,
                "distance_km": distance_km
            })

            # 根据单位返回结果
            if unit == "miles":
                result = {"distance": distance_miles, "unit": "miles"}
            elif unit == "meters":
                result = {"distance": distance_meters, "unit": "meters"}
            else:
                result = {"distance": distance_km, "unit": "km"}

            return ToolResult.success_result(result, message=f"距离计算完成")

        except Exception as e:
            self._logger.error(f"距离计算失败: {e}")
            return ToolResult.error_result(str(e))

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Haversine 公式计算两点间大圆距离（单位：公里）
        
        Args:
            lat1, lon1: 点1的经纬度
            lat2, lon2: 点2的经纬度
            
        Returns:
            两点间距离（公里）
        """
        # 将角度转换为弧度
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Haversine 公式
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        # 地球半径（公里）
        r = 6371.0
        
        return r * c

    def get_history(self):
        """获取计算历史"""
        return self._calculation_history

from dataclasses import dataclass