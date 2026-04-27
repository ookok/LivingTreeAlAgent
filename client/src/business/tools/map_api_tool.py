"""
MapAPITool - 地图 API 工具

封装高德地图和天地图 API，支持地理编码、路径规划、POI搜索等功能
"""

import os
import json
import time
import hashlib
import urllib.parse
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from abc import ABC, abstractmethod

import requests
from loguru import logger

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult


@dataclass
class GeoLocation:
    """地理位置"""
    lat: float
    lon: float
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    name: Optional[str] = None


@dataclass
class POI:
    """兴趣点"""
    id: str
    name: str
    location: GeoLocation
    address: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    type: Optional[str] = None
    distance: Optional[float] = None


class BaseMapProvider(ABC):
    """地图提供商基类"""
    
    @abstractmethod
    def geocode(self, address: str) -> Optional[GeoLocation]:
        """地理编码：地址转坐标"""
        pass
    
    @abstractmethod
    def reverse_geocode(self, lat: float, lon: float) -> Optional[GeoLocation]:
        """逆地理编码：坐标转地址"""
        pass
    
    @abstractmethod
    def search_nearby(self, lat: float, lon: float, keyword: str, radius: int = 1000) -> List[POI]:
        """周边搜索"""
        pass
    
    @abstractmethod
    def route_planning(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float, mode: str = "driving") -> Dict:
        """路径规划"""
        pass


class AMapProvider(BaseMapProvider):
    """高德地图 API 提供商"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://restapi.amap.com/v3"
    
    def _request(self, endpoint: str, params: Dict) -> Dict:
        """发送 API 请求"""
        params["key"] = self.api_key
        
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        
        data = response.json()
        
        if data.get("status") != "1":
            raise Exception(f"API Error: {data.get('info', 'Unknown')}")
        
        return data
    
    def geocode(self, address: str) -> Optional[GeoLocation]:
        """地理编码"""
        try:
            data = self._request("geocode/geo", {
                "address": address
            })
            
            geocodes = data.get("geocodes", [])
            if not geocodes:
                return None
            
            g = geocodes[0]
            location = g["location"].split(",")
            
            return GeoLocation(
                lat=float(location[1]),
                lon=float(location[0]),
                province=g.get("province"),
                city=g.get("city"),
                district=g.get("district"),
                address=g.get("formatted_address"),
                name=g.get("name")
            )
        except Exception as e:
            logger.error(f"Geocode failed: {e}")
            return None
    
    def reverse_geocode(self, lat: float, lon: float) -> Optional[GeoLocation]:
        """逆地理编码"""
        try:
            data = self._request("geocode/regeo", {
                "location": f"{lon},{lat}"
            })
            
            regeocode = data.get("regeocode", {})
            if not regeocode:
                return None
            
            address_component = regeocode.get("addressComponent", {})
            formatted_address = regeocode.get("formatted_address", "")
            
            return GeoLocation(
                lat=lat,
                lon=lon,
                province=address_component.get("province"),
                city=address_component.get("city", [None])[0] if address_component.get("city") else None,
                district=address_component.get("district"),
                address=formatted_address
            )
        except Exception as e:
            logger.error(f"Reverse geocode failed: {e}")
            return None
    
    def search_nearby(self, lat: float, lon: float, keyword: str, radius: int = 1000) -> List[POI]:
        """周边搜索"""
        try:
            data = self._request("place/around", {
                "location": f"{lon},{lat}",
                "keywords": keyword,
                "radius": radius,
                "offset": 20,
                "page": 1,
                "extensions": "all"
            })
            
            pois = []
            for item in data.get("pois", []):
                location = item["location"].split(",")
                pois.append(POI(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    location=GeoLocation(
                        lat=float(location[1]),
                        lon=float(location[0])
                    ),
                    address=item.get("address"),
                    province=item.get("pname"),
                    city=item.get("cityname"),
                    district=item.get("adname"),
                    type=item.get("type"),
                    distance=float(item.get("distance", 0))
                ))
            
            return pois
        except Exception as e:
            logger.error(f"Search nearby failed: {e}")
            return []
    
    def route_planning(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float, mode: str = "driving") -> Dict:
        """路径规划"""
        mode_map = {
            "driving": "driving",
            "walking": "walking",
            "bicycling": "bicycling",
            "bus": "bus",
            "transit": "transit"
        }
        
        strategy_map = {
            "driving": "0",  # 最速度优先
            "walking": "0",
            "bicycling": "0",
            "bus": "0"  # 最快
        }
        
        try:
            endpoint = f"direction/{mode_map.get(mode, 'driving')}"
            params = {
                "origin": f"{from_lon},{from_lat}",
                "destination": f"{to_lon},{to_lat}"
            }
            
            if mode == "driving":
                params["strategy"] = strategy_map.get(mode, "0")
            
            data = self._request(endpoint, params)
            
            # 简化返回
            path = data.get("route", {}).get("paths", [{}])[0]
            
            return {
                "distance": int(path.get("distance", 0)),  # 米
                "duration": int(path.get("duration", 0)),  # 秒
                "strategy": path.get("strategy", ""),
                "steps": [
                    {
                        "instruction": step.get("instruction", ""),
                        "road": step.get("road", ""),
                        "distance": int(step.get("distance", 0)),
                        "duration": int(step.get("duration", 0))
                    }
                    for step in path.get("steps", [])
                ]
            }
        except Exception as e:
            logger.error(f"Route planning failed: {e}")
            return {"error": str(e)}


class TiandituProvider(BaseMapProvider):
    """天地图 API 提供商"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.tianditu.gov.cn"
    
    def _request(self, endpoint: str, params: Dict) -> Dict:
        """发送 API 请求"""
        params["tk"] = self.api_key
        
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
        
        return response.json()
    
    def geocode(self, address: str) -> Optional[GeoLocation]:
        """地理编码（简化版）"""
        try:
            data = self._request("geocoder/v2", {
                "address": address
            })
            
            if data.get("status") != "0":
                return None
            
            location = data["result"]["location"].split(",")
            
            return GeoLocation(
                lat=float(location[1]),
                lon=float(location[0]),
                address=data["result"]["formatted_address"]
            )
        except Exception as e:
            logger.error(f"Geocode failed: {e}")
            return None
    
    def reverse_geocode(self, lat: float, lon: float) -> Optional[GeoLocation]:
        """逆地理编码"""
        try:
            data = self._request("geocoder/v2", {
                "lon": lon,
                "lat": lat
            })
            
            if data.get("status") != "0":
                return None
            
            return GeoLocation(
                lat=lat,
                lon=lon,
                address=data["result"]["formatted_address"]
            )
        except Exception as e:
            logger.error(f"Reverse geocode failed: {e}")
            return None
    
    def search_nearby(self, lat: float, lon: float, keyword: str, radius: int = 1000) -> List[POI]:
        """周边搜索（简化版）"""
        # 天地图没有直接的周边搜索 API，需要使用搜索服务
        return []
    
    def route_planning(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float, mode: str = "driving") -> Dict:
        """路径规划（简化版）"""
        # 天地图路径规划需要额外的服务
        return {"error": "Route planning not implemented for Tianditu"}


class MapAPITool(BaseTool):
    """
    地图 API 工具
    
    支持多种地图服务：
    - 高德地图（AMap）
    - 天地图（Tianditu）
    
    功能：
    - 地理编码/逆地理编码
    - 周边搜索
    - 路径规划
    - POI 查询
    """
    
    def __init__(
        self,
        provider: str = "amap",
        api_key: Optional[str] = None
    ):
        """
        初始化 MapAPITool
        
        Args:
            provider: 地图提供商 ("amap" 或 "tianditu")
            api_key: API 密钥（可从环境变量获取）
        """
        super().__init__(
            name="map_api_tool",
            description="Geographic information service supporting geocoding, reverse geocoding, "
                       "POI search, route planning, and nearby location queries.",
            category="geo",
            tags=["geocoding", "map", "location", "poi", "route", "navigation", "gis"]
        )
        
        # 从环境变量或参数获取 API Key
        self.api_key = api_key or os.environ.get("AMAP_API_KEY") or os.environ.get("TIANDITU_API_KEY", "")
        
        if not self.api_key:
            logger.warning("No API key provided for MapAPITool")
        
        # 初始化提供商
        self._init_provider(provider)
    
    def _init_provider(self, provider: str):
        """初始化地图提供商"""
        if provider == "amap" and self.api_key:
            self.provider: BaseMapProvider = AMapProvider(self.api_key)
        elif provider == "tianditu" and self.api_key:
            self.provider = TiandituProvider(self.api_key)
        else:
            self.provider = None
            logger.warning(f"Unknown provider or no API key: {provider}")
    
    def execute(self, **kwargs) -> ToolResult:
        """
        执行地图 API 操作
        
        Args:
            action: 操作类型 ("geocode", "reverse_geocode", "search_nearby", "route_planning")
            其他参数根据操作类型而定
            
        Returns:
            ToolResult
        """
        if not self.provider:
            return ToolResult.fail(error="No map provider configured. Please set API key.")
        
        try:
            action = kwargs.get("action", "")
            
            if action == "geocode":
                return self._geocode(kwargs)
            elif action == "reverse_geocode":
                return self._reverse_geocode(kwargs)
            elif action == "search_nearby":
                return self._search_nearby(kwargs)
            elif action == "route_planning":
                return self._route_planning(kwargs)
            else:
                return ToolResult.fail(error=f"Unknown action: {action}")
                
        except Exception as e:
            logger.error(f"Map API error: {e}")
            return ToolResult.fail(error=str(e))
    
    def _geocode(self, params: Dict) -> ToolResult:
        """地理编码"""
        address = params.get("address")
        if not address:
            return ToolResult.fail(error="address is required")
        
        result = self.provider.geocode(address)
        
        if result:
            return ToolResult.ok(
                data={
                    "lat": result.lat,
                    "lon": result.lon,
                    "province": result.province,
                    "city": result.city,
                    "district": result.district,
                    "address": result.address
                },
                message=f"Geocoded: {address} -> ({result.lat}, {result.lon})"
            )
        else:
            return ToolResult.fail(error=f"Address not found: {address}")
    
    def _reverse_geocode(self, params: Dict) -> ToolResult:
        """逆地理编码"""
        lat = params.get("lat")
        lon = params.get("lon")
        
        if lat is None or lon is None:
            return ToolResult.fail(error="lat and lon are required")
        
        result = self.provider.reverse_geocode(float(lat), float(lon))
        
        if result:
            return ToolResult.ok(
                data={
                    "lat": result.lat,
                    "lon": result.lon,
                    "province": result.province,
                    "city": result.city,
                    "district": result.district,
                    "address": result.address
                },
                message=f"Reverse geocoded: ({lat}, {lon})"
            )
        else:
            return ToolResult.fail(error=f"Location not found: ({lat}, {lon})")
    
    def _search_nearby(self, params: Dict) -> ToolResult:
        """周边搜索"""
        lat = params.get("lat")
        lon = params.get("lon")
        keyword = params.get("keyword", "")
        radius = int(params.get("radius", 1000))
        
        if lat is None or lon is None:
            return ToolResult.fail(error="lat and lon are required")
        
        pois = self.provider.search_nearby(
            float(lat), float(lon), keyword, radius
        )
        
        return ToolResult.ok(
            data={
                "count": len(pois),
                "pois": [
                    {
                        "name": poi.name,
                        "address": poi.address,
                        "lat": poi.location.lat,
                        "lon": poi.location.lon,
                        "distance": poi.distance,
                        "type": poi.type
                    }
                    for poi in pois
                ]
            },
            message=f"Found {len(pois)} POIs near ({lat}, {lon})"
        )
    
    def _route_planning(self, params: Dict) -> ToolResult:
        """路径规划"""
        from_lat = params.get("from_lat")
        from_lon = params.get("from_lon")
        to_lat = params.get("to_lat")
        to_lon = params.get("to_lon")
        mode = params.get("mode", "driving")
        
        if None in [from_lat, from_lon, to_lat, to_lon]:
            return ToolResult.fail(error="from_lat, from_lon, to_lat, to_lon are required")
        
        result = self.provider.route_planning(
            float(from_lat), float(from_lon),
            float(to_lat), float(to_lon),
            mode
        )
        
        if "error" in result:
            return ToolResult.fail(error=result["error"])
        
        return ToolResult.ok(
            data=result,
            message=f"Route planned: {result.get('distance', 0)}m, {result.get('duration', 0)}s"
        )
    
    def geocode_sync(self, address: str) -> Optional[GeoLocation]:
        """同步地理编码（便捷方法）"""
        if self.provider:
            return self.provider.geocode(address)
        return None
    
    def reverse_geocode_sync(self, lat: float, lon: float) -> Optional[GeoLocation]:
        """同步逆地理编码（便捷方法）"""
        if self.provider:
            return self.provider.reverse_geocode(lat, lon)
        return None
    
    def search_nearby_sync(self, lat: float, lon: float, keyword: str, radius: int = 1000) -> List[POI]:
        """同步周边搜索（便捷方法）"""
        if self.provider:
            return self.provider.search_nearby(lat, lon, keyword, radius)
        return []
    
    def health_check(self) -> bool:
        """健康检查"""
        return self.api_key is not None
    
    def get_capabilities(self) -> Dict[str, Any]:
        """获取工具能力"""
        return {
            "name": self.name,
            "category": self.category,
            "providers": ["amap", "tianditu"],
            "features": [
                "Geocoding (address to coordinates)",
                "Reverse geocoding (coordinates to address)",
                "Nearby POI search",
                "Route planning (driving, walking, cycling, transit)"
            ],
            "api_key_configured": bool(self.api_key)
        }


# ── 自动注册 ─────────────────────────────────────────────────────────

def _auto_register():
    """自动注册工具到 ToolRegistry"""
    try:
        from client.src.business.tools.tool_registry import ToolRegistry
        registry = ToolRegistry.get_instance()
        
        tool = MapAPITool()
        if registry.register_tool(tool):
            logger.info(f"Auto-registered: {tool.name}")
            return True
    except Exception as e:
        logger.error(f"Auto-registration error: {e}")
    return False


# 调试用
if __name__ == "__main__":
    tool = MapAPITool()
    
    print("=" * 50)
    print("Map API Tool Test")
    print("=" * 50)
    print(f"\nTool: {tool.name}")
    print(f"API Key Configured: {bool(tool.api_key)}")
    print(f"Capabilities: {tool.get_capabilities()}")
    
    # 如果有 API Key，进行测试
    if tool.api_key:
        # 测试地理编码
        result = tool.geocode_sync("北京市朝阳区")
        if result:
            print(f"\nGeocoded 'Beijing Chaoyang':")
            print(f"  Lat: {result.lat}, Lon: {result.lon}")
            print(f"  Address: {result.address}")
