"""
空间感知工具 (Perception Tool)

功能：输入经纬度或地名，返回该点的"空间身份证"。

输出包含：
- 所属行政区
- 距离最近的水系/居民区
- 地形地貌
- 是否在生态红线内
- 是否在水源保护区内
- 是否在基本农田保护区内

应用场景：环评报告中"项目选址合规性分析"。
"""
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional

import requests


class ProtectionType(Enum):
    """保护类型"""
    ECOLOGICAL_RED_LINE = "ecological_red_line"
    WATER_SOURCE = "water_source"
    BASIC_FARMland = "basic_farmland"
    NATURE_RESERVE = "nature_reserve"
    SCENIC_AREA = "scenic_area"


@dataclass
class SpatialIdentity:
    """空间身份证"""
    # 基本信息
    name: str = ""
    address: str = ""
    longitude: float = 0.0
    latitude: float = 0.0
    
    # 行政区划
    province: str = ""
    city: str = ""
    district: str = ""
    town: str = ""
    
    # 周边信息
    nearest_water_distance: float = 0.0  # 最近水系距离(米)
    nearest_residential_distance: float = 0.0  # 最近居民区距离(米)
    terrain: str = ""  # 地形地貌
    
    # 保护区域判断
    protected_areas: List[Dict[str, Any]] = field(default_factory=list)
    
    # 合规性评估
    is_compliant: bool = True
    compliance_issues: List[str] = field(default_factory=list)


class PerceptionTool:
    """
    空间感知工具
    
    核心能力：
    1. 地理编码（地址→坐标）
    2. 逆地理编码（坐标→地址）
    3. 空间身份识别（综合分析）
    """
    
    def __init__(self, api_key: str = None):
        from ..config import get_api_key, get_base_url
        self.api_key = api_key or get_api_key()
        self.base_url = get_base_url()
    
    def geocode(self, address: str) -> Optional[Dict[str, Any]]:
        """
        地理编码：地址→坐标
        
        Args:
            address: 地址字符串
        
        Returns:
            包含坐标的字典，失败返回None
        """
        try:
            url = f"{self.base_url}/geocode/geo"
            params = {
                "key": self.api_key,
                "address": address,
                "output": "json"
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if data.get("status") == "1" and data.get("geocodes"):
                result = data["geocodes"][0]
                return {
                    "longitude": float(result["location"].split(",")[0]),
                    "latitude": float(result["location"].split(",")[1]),
                    "formatted_address": result.get("formatted_address", ""),
                    "province": result.get("province", ""),
                    "city": result.get("city", ""),
                    "district": result.get("district", "")
                }
            
            return None
        except Exception as e:
            print(f"地理编码失败: {e}")
            return None
    
    def reverse_geocode(self, longitude: float, latitude: float) -> Optional[Dict[str, Any]]:
        """
        逆地理编码：坐标→地址
        
        Args:
            longitude: 经度
            latitude: 纬度
        
        Returns:
            包含地址信息的字典，失败返回None
        """
        try:
            url = f"{self.base_url}/geocode/regeo"
            params = {
                "key": self.api_key,
                "location": f"{longitude},{latitude}",
                "output": "json",
                "radius": "1000",
                "extensions": "all"
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if data.get("status") == "1" and data.get("regeocode"):
                regeocode = data["regeocode"]
                address_component = regeocode.get("addressComponent", {})
                
                return {
                    "formatted_address": regeocode.get("formatted_address", ""),
                    "province": address_component.get("province", ""),
                    "city": address_component.get("city", ""),
                    "district": address_component.get("district", ""),
                    "township": address_component.get("township", ""),
                    "neighborhood": address_component.get("neighborhood", {}).get("name", "")
                }
            
            return None
        except Exception as e:
            print(f"逆地理编码失败: {e}")
            return None
    
    def get_spatial_identity(self, longitude: float, latitude: float) -> SpatialIdentity:
        """
        获取坐标的空间身份证
        
        Args:
            longitude: 经度
            latitude: 纬度
        
        Returns:
            SpatialIdentity对象
        """
        identity = SpatialIdentity(
            longitude=longitude,
            latitude=latitude
        )
        
        # 1. 获取基本地址信息
        regeo_result = self.reverse_geocode(longitude, latitude)
        if regeo_result:
            identity.name = regeo_result.get("neighborhood", "未知位置")
            identity.address = regeo_result.get("formatted_address", "")
            identity.province = regeo_result.get("province", "")
            identity.city = regeo_result.get("city", "")
            identity.district = regeo_result.get("district", "")
            identity.town = regeo_result.get("township", "")
        
        # 2. 模拟周边分析（实际应调用GIS分析服务）
        identity.nearest_water_distance = self._calculate_nearest_water(longitude, latitude)
        identity.nearest_residential_distance = self._calculate_nearest_residential(longitude, latitude)
        identity.terrain = self._detect_terrain(longitude, latitude)
        
        # 3. 保护区域判断
        protected_areas = self._check_protected_areas(longitude, latitude)
        identity.protected_areas = protected_areas
        
        # 4. 合规性评估
        identity.is_compliant, identity.compliance_issues = self._evaluate_compliance(protected_areas)
        
        return identity
    
    def _calculate_nearest_water(self, longitude: float, latitude: float) -> float:
        """计算到最近水系的距离（模拟）"""
        # 实际应调用GIS分析或高德POI搜索
        # 这里模拟一个距离值
        import random
        return round(random.uniform(50, 5000), 2)
    
    def _calculate_nearest_residential(self, longitude: float, latitude: float) -> float:
        """计算到最近居民区的距离（模拟）"""
        import random
        return round(random.uniform(100, 3000), 2)
    
    def _detect_terrain(self, longitude: float, latitude: float) -> str:
        """检测地形地貌（模拟）"""
        terrains = ["平原", "丘陵", "山地", "河谷", "盆地"]
        import random
        return random.choice(terrains)
    
    def _check_protected_areas(self, longitude: float, latitude: float) -> List[Dict[str, Any]]:
        """检查是否在保护区域内（模拟）"""
        protected_areas = []
        
        # 模拟保护区域检测
        import random
        
        if random.random() < 0.2:
            protected_areas.append({
                "type": ProtectionType.ECOLOGICAL_RED_LINE.value,
                "name": "生态红线区",
                "distance": round(random.uniform(0, 500), 2),
                "overlap": True if random.random() < 0.3 else False
            })
        
        if random.random() < 0.15:
            protected_areas.append({
                "type": ProtectionType.WATER_SOURCE.value,
                "name": "饮用水源保护区",
                "distance": round(random.uniform(0, 1000), 2),
                "overlap": True if random.random() < 0.2 else False
            })
        
        if random.random() < 0.1:
            protected_areas.append({
                "type": ProtectionType.BASIC_FARMland.value,
                "name": "基本农田保护区",
                "distance": round(random.uniform(0, 800), 2),
                "overlap": True if random.random() < 0.15 else False
            })
        
        return protected_areas
    
    def _evaluate_compliance(self, protected_areas: List[Dict[str, Any]]) -> tuple:
        """评估合规性"""
        issues = []
        is_compliant = True
        
        for area in protected_areas:
            if area.get("overlap"):
                is_compliant = False
                issues.append(f"项目位于{area['name']}内，存在合规风险")
            elif area.get("distance", 10000) < 500:
                issues.append(f"项目距离{area['name']}仅{area['distance']}米，建议进一步评估")
        
        return is_compliant, issues
    
    def batch_analyze(self, coordinates: List[tuple]) -> List[SpatialIdentity]:
        """
        批量分析多个坐标
        
        Args:
            coordinates: 坐标列表 [(lon1, lat1), (lon2, lat2), ...]
        
        Returns:
            SpatialIdentity列表
        """
        results = []
        for lon, lat in coordinates:
            identity = self.get_spatial_identity(lon, lat)
            results.append(identity)
        return results