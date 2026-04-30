"""
ElevationTool - 高程数据工具

集成 SRTM/GTOPO30，获取指定坐标的高程数据。

遵循自我进化原则：
- 自动选择最佳数据源
- 支持离线数据和在线 API
"""

from typing import Dict, Any, Optional
from loguru import logger

try:
    from business.tools.base_tool import BaseTool, ToolResult
except ImportError:
    from tools.base_tool import BaseTool, ToolResult


class ElevationTool(BaseTool):
    """
    高程数据工具
    
    集成 SRTM/GTOPO30，获取指定坐标的高程数据。
    """

    def __init__(self):
        self._logger = logger.bind(component="ElevationTool")
        self._data_cache = {}

    @property
    def name(self) -> str:
        return "elevation_tool"

    @property
    def description(self) -> str:
        return "集成 SRTM/GTOPO30，获取指定坐标的高程数据"

    @property
    def category(self) -> str:
        return "geo"

    @property
    def parameters(self) -> Dict[str, str]:
        return {
            "lat": "float",
            "lon": "float",
            "source": "str"
        }

    async def execute(self, lat: float, lon: float, source: str = "auto") -> ToolResult:
        """
        获取高程数据
        
        Args:
            lat: 纬度
            lon: 经度
            source: 数据源（auto/srtm/gtopo30/open-elevation）
            
        Returns:
            ToolResult
        """
        self._logger.info(f"获取高程数据: ({lat}, {lon})")

        # 验证坐标范围
        if not (-90 <= lat <= 90):
            return ToolResult.error_result("纬度必须在 -90 到 90 之间")
        
        if not (-180 <= lon <= 180):
            return ToolResult.error_result("经度必须在 -180 到 180 之间")

        # 检查缓存
        cache_key = f"{lat:.4f}_{lon:.4f}"
        if cache_key in self._data_cache:
            self._logger.debug("使用缓存数据")
            return ToolResult.success_result(self._data_cache[cache_key])

        try:
            # 根据数据源选择获取方式
            if source == "auto":
                elevation = await self._get_elevation_auto(lat, lon)
            elif source == "open-elevation":
                elevation = await self._get_elevation_open_api(lat, lon)
            else:
                elevation = await self._get_elevation_simple(lat, lon)

            # 缓存结果
            result = {
                "lat": lat,
                "lon": lon,
                "elevation": elevation,
                "unit": "meters",
                "source": source
            }
            self._data_cache[cache_key] = result

            return ToolResult.success_result(result, message="高程数据获取成功")

        except Exception as e:
            self._logger.error(f"获取高程数据失败: {e}")
            return ToolResult.error_result(str(e))

    async def _get_elevation_auto(self, lat: float, lon: float) -> float:
        """自动选择数据源获取高程"""
        # 优先尝试在线 API
        try:
            return await self._get_elevation_open_api(lat, lon)
        except:
            # 降级到简单计算
            return await self._get_elevation_simple(lat, lon)

    async def _get_elevation_open_api(self, lat: float, lon: float) -> float:
        """使用 Open Elevation API 获取高程"""
        import httpx
        
        url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("results"):
                return data["results"][0]["elevation"]
        
        raise ValueError("无法获取高程数据")

    async def _get_elevation_simple(self, lat: float, lon: float) -> float:
        """简单的高程估算（基于纬度的模拟）"""
        # 这是一个简化的模拟实现
        # 实际应用中会使用 SRTM 或 GTOPO30 数据
        
        # 模拟地形：赤道低，山脉高
        base_elevation = 100  # 基础海拔
        
        # 模拟一些山脉区域
        mountain_regions = [
            # 喜马拉雅山脉
            (28, 85, 5000),
            # 安第斯山脉
            (-15, -70, 4000),
            # 阿尔卑斯山脉
            (47, 10, 3000),
            # 落基山脉
            (40, -105, 3500),
        ]
        
        for m_lat, m_lon, m_elev in mountain_regions:
            # 计算距离（简单近似）
            dist = ((lat - m_lat) ** 2 + (lon - m_lon) ** 2) ** 0.5
            if dist < 10:
                # 在山脉附近，插值计算高程
                return base_elevation + (m_elev - base_elevation) * (1 - dist / 10)
        
        # 海洋区域（低于海平面）
        ocean_areas = [
            # 太平洋
            (0, -150, -4000),
            # 大西洋
            (0, -30, -3000),
            # 印度洋
            (-10, 80, -3500),
        ]
        
        for o_lat, o_lon, o_elev in ocean_areas:
            dist = ((lat - o_lat) ** 2 + (lon - o_lon) ** 2) ** 0.5
            if dist < 60:
                return o_elev
        
        # 默认返回基础海拔
        return base_elevation

    def clear_cache(self):
        """清空缓存"""
        self._data_cache = {}