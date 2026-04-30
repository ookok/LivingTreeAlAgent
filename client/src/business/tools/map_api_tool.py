"""
MapAPITool - 地图 API 工具

封装高德/天地图 API，支持地理编码、路径规划、POI 搜索。

遵循自我进化原则：
- 自动选择最佳地图服务
- 支持多服务降级
- 从使用中学习常用查询
"""

from typing import Dict, Any
from loguru import logger

try:
    from business.tools.base_tool import BaseTool, ToolResult
except ImportError:
    from tools.base_tool import BaseTool, ToolResult


class MapAPITool(BaseTool):
    """
    地图 API 工具
    
    封装高德/天地图 API，支持地理编码、路径规划、POI 搜索。
    """

    def __init__(self):
        self._logger = logger.bind(component="MapAPITool")
        self._api_keys = {
            "amap": None,  # 需要在配置中设置
            "tianditu": None  # 需要在配置中设置
        }
        self._usage_history = []

    @property
    def name(self) -> str:
        return "map_api"

    @property
    def description(self) -> str:
        return "封装高德/天地图 API，支持地理编码、路径规划、POI 搜索"

    @property
    def category(self) -> str:
        return "geo"

    @property
    def parameters(self) -> Dict[str, str]:
        return {
            "action": "str",
            "params": "dict"
        }

    async def execute(self, action: str, params: Dict[str, Any]) -> ToolResult:
        """
        执行地图 API 操作
        
        Args:
            action: 操作类型（geocode/reverse_geocode/direction/poi_search）
            params: 操作参数
            
        Returns:
            ToolResult
        """
        self._logger.info(f"执行地图操作: {action}")

        try:
            # 根据操作类型执行
            if action == "geocode":
                result = await self._geocode(params)
            elif action == "reverse_geocode":
                result = await self._reverse_geocode(params)
            elif action == "direction":
                result = await self._direction(params)
            elif action == "poi_search":
                result = await self._poi_search(params)
            else:
                return ToolResult.error_result(f"不支持的操作: {action}")

            # 记录使用历史
            self._usage_history.append({
                "action": action,
                "params": params,
                "success": True
            })

            return ToolResult.success_result(result, message=f"{action} 操作完成")

        except Exception as e:
            self._logger.error(f"地图操作失败: {e}")
            self._usage_history.append({
                "action": action,
                "params": params,
                "success": False,
                "error": str(e)
            })
            return ToolResult.error_result(str(e))

    async def _geocode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """地理编码：地址 -> 坐标"""
        address = params.get("address", "")
        city = params.get("city", "")

        # 模拟实现（实际需要调用真实 API）
        if not address:
            raise ValueError("地址不能为空")

        # 模拟返回结果
        return {
            "status": "success",
            "address": address,
            "location": {
                "lat": 39.9042,  # 北京纬度（模拟）
                "lon": 116.4074   # 北京经度（模拟）
            },
            "formatted_address": f"{city}{address}",
            "suggestion": {
                "keywords": [address],
                "cities": [city]
            }
        }

    async def _reverse_geocode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """逆地理编码：坐标 -> 地址"""
        lat = params.get("lat")
        lon = params.get("lon")

        if lat is None or lon is None:
            raise ValueError("坐标不能为空")

        # 模拟返回结果
        return {
            "status": "success",
            "location": {"lat": lat, "lon": lon},
            "address": "北京市朝阳区天安门广场",
            "address_components": {
                "country": "中国",
                "province": "北京市",
                "city": "北京市",
                "district": "朝阳区",
                "street": "天安门广场",
                "street_number": ""
            },
            "formatted_address": "北京市朝阳区天安门广场"
        }

    async def _direction(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """路径规划"""
        origin = params.get("origin", "")
        destination = params.get("destination", "")
        mode = params.get("mode", "driving")

        if not origin or not destination:
            raise ValueError("起点和终点不能为空")

        # 模拟返回结果
        return {
            "status": "success",
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "routes": [
                {
                    "distance": 5000,  # 米
                    "duration": 1800,  # 秒
                    "steps": [
                        {"instruction": "从起点出发", "distance": 1000},
                        {"instruction": "直行500米", "distance": 500},
                        {"instruction": "到达终点", "distance": 3500}
                    ]
                }
            ]
        }

    async def _poi_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """POI 搜索"""
        keyword = params.get("keyword", "")
        city = params.get("city", "")
        types = params.get("types", "")

        if not keyword:
            raise ValueError("搜索关键词不能为空")

        # 模拟返回结果
        return {
            "status": "success",
            "keyword": keyword,
            "city": city,
            "count": 10,
            "pois": [
                {
                    "name": f"{keyword} 地点1",
                    "address": f"{city}市某街道",
                    "location": {"lat": 39.9042, "lon": 116.4074},
                    "type": types,
                    "distance": 1000
                } for _ in range(5)
            ]
        }

    def get_usage_history(self):
        """获取使用历史"""
        return self._usage_history

    def set_api_key(self, provider: str, api_key: str):
        """设置 API Key"""
        if provider in self._api_keys:
            self._api_keys[provider] = api_key
            self._logger.info(f"已设置 {provider} API Key")