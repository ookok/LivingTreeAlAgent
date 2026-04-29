"""
空间智能模块
============

基于地图API的空间分析能力：
1. POI敏感点自动识别
2. 地形与高程分析
3. 环境敏感区边界计算
4. GIS矢量数据叠加

Author: Hermes Desktop EIA System
"""

import json
import math
import hashlib
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime
import re


class POICategory(str, Enum):
    """POI类别"""
    # 环境敏感区
    SCHOOL = "学校"                    # 学校（中小学、幼儿园）
    HOSPITAL = "医院"                  # 医院、医疗设施
    NURSING_HOME = "养老院"            # 养老院、敬老院
    RESERVE = "自然保护区"            # 自然保护区、风景名胜区
    WATER_SOURCE = "饮用水源"          # 饮用水水源保护区
    RESIDENTIAL = "居民区"            # 居民区、住宅小区
    FARM = "农田"                      # 基本农田、蔬菜基地
    RIVER = "河流"                     # 河流、湖泊、水库
    HERITAGE = "文物"                  # 文物保护单位

    # 产业设施
    FACTORY = "工厂"                   # 工厂、工业企业
    INDUSTRIAL_ZONE = "工业园区"       # 工业园区、经济开发区
    DANGER_SOURCE = "危险源"           # 重大危险源

    # 环境功能区
    AIR_MONITOR = "环境空气监测站"      # 环境空气自动监测站
    WATER_MONITOR = "水质监测站"        # 水质自动监测站
    WEATHER_STATION = "气象站"         # 气象观测站


@dataclass
class POIPoint:
    """POI点"""
    id: str
    name: str
    category: POICategory
    latitude: float
    longitude: float
    address: str = ""
    distance_to_project: Optional[float] = None  # 距项目距离(米)
    azimuth: Optional[float] = None              # 方位角(度)
    is_protected: bool = False                  # 是否在保护区范围内


@dataclass
class SensitiveZone:
    """敏感区"""
    id: str
    name: str
    zone_type: str                    # 类别：水源保护区/生态红线/禁止区等
    center_lat: float
    center_lon: float
    radius: float = 0                 # 圆形区域半径(米)
    boundary_points: List[Tuple[float, float]] = field(default_factory=list)  # 多边形边界
    protection_level: str = "一级"     # 保护等级
    legal_basis: str = ""             # 法律依据


@dataclass
class TerrainData:
    """地形数据"""
    elevation: float                   # 海拔高程(米)
    slope: float = 0                  # 坡度(度)
    aspect: float = 0                 # 坡向(度)
    terrain_type: str = "平原"         # 地形类型
    nearby_peaks: List[Dict] = field(default_factory=list)  # 附近山峰


@dataclass
class SpatialAnalysisResult:
    """空间分析结果"""
    project_id: str
    project_name: str
    center_lat: float
    center_lon: float
    analysis_time: datetime
    pois: List[POIPoint] = field(default_factory=list)
    sensitive_zones: List[SensitiveZone] = field(default_factory=list)
    terrain: Optional[TerrainData] = None
    within_protected_areas: List[str] = field(default_factory=list)
    nearest_residential: Optional[POIPoint] = None
    wind_rose_data: Optional[Dict] = None


class AMapAPI:
    """
    高德地图API客户端

    使用说明：
    1. 需要在高德开放平台申请Web服务API Key
    2. 支持POI搜索、地理编码、距离测量等功能
    3. 免费额度：每Key每天5000次调用
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.base_url = "https://restapi.amap.com/v3"
        self._rate_limit = asyncio.Semaphore(100)  # 限制并发

    async def search_poi(
        self,
        keywords: str,
        location: Tuple[float, float] = None,
        radius: int = 3000,
        types: str = None
    ) -> List[Dict]:
        """
        POI搜索

        Args:
            keywords: 搜索关键字
            location: 中心点坐标 (lat, lon)
            radius: 搜索半径(米)
            types: POI类型代码
        """
        import httpx

        params = {
            "key": self.api_key,
            "keywords": keywords,
            "city": "全国",
            "offset": 20,
            "page": 1,
            "extensions": "all"
        }

        if location:
            params["location"] = f"{location[1]},{location[0]}"  # 高德是lon,lat
            params["radius"] = radius

        if types:
            params["types"] = types

        url = f"{self.base_url}/place/text"

        async with self._rate_limit:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                data = response.json()

                if data.get("status") == "1" and data.get("pois"):
                    return data["pois"]
                return []

    async def search_sensitive_points(
        self,
        lat: float,
        lon: float,
        radius: int = 5000
    ) -> List[POIPoint]:
        """
        搜索周边敏感点

        敏感点类型：
        - 学校、医院、养老院
        - 自然保护区、风景名胜区
        - 饮用水源保护区
        - 居民区
        """
        pois = []

        # 定义敏感点搜索关键词
        sensitive_keywords = {
            POICategory.SCHOOL: ["学校", "小学", "中学", "幼儿园"],
            POICategory.HOSPITAL: ["医院", "卫生院", "诊所", "医疗"],
            POICategory.NURSING_HOME: ["养老院", "敬老院", "福利院", "老年公寓"],
            POICategory.RESERVE: ["自然保护区", "森林公园", "湿地公园", "风景名胜区"],
            POICategory.RESIDENTIAL: ["居民区", "住宅小区", "村庄", "屯"],
            POICategory.WATER_SOURCE: ["水源地", "饮用水源", "取水口"],
        }

        for category, keywords in sensitive_keywords.items():
            for keyword in keywords:
                results = await self.search_poi(
                    keywords=keyword,
                    location=(lat, lon),
                    radius=radius
                )

                for item in results:
                    poi = POIPoint(
                        id=item.get("id", ""),
                        name=item.get("name", ""),
                        category=category,
                        latitude=float(item.get("location", "0,0").split(",")[1] or 0),
                        longitude=float(item.get("location", "0,0").split(",")[0] or 0),
                        address=item.get("address", ""),
                        distance_to_project=self._calculate_distance(
                            lat, lon,
                            float(item.get("location", "0,0").split(",")[1] or 0),
                            float(item.get("location", "0,0").split(",")[0] or 0)
                        )
                    )
                    pois.append(poi)

        return pois

    async def get_terrain(self, lat: float, lon: float) -> Optional[TerrainData]:
        """
        获取地形数据

        使用高德海拔API或3D地形服务
        """
        import httpx

        url = f"{self.base_url}/geocode/geo"
        params = {
            "key": self.api_key,
            "location": f"{lon},{lat}"
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                data = response.json()

                if data.get("status") == "1" and data.get("geocodes"):
                    # 高德基础API不提供海拔，使用SRTM或其他源
                    # 这里返回简化数据
                    return TerrainData(
                        elevation=0,  # 需要接入SRTM API
                        slope=0,
                        aspect=0,
                        terrain_type="待获取"
                    )
        except Exception:
            pass

        return None

    async def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        """地址转坐标"""
        import httpx

        url = f"{self.base_url}/geocode/geo"
        params = {
            "key": self.api_key,
            "address": address
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                data = response.json()

                if data.get("status") == "1" and data.get("geocodes"):
                    loc = data["geocodes"][0]["location"]
                    lon, lat = loc.split(",")
                    return float(lat), float(lon)
        except Exception:
            pass

        return None

    async def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict]:
        """坐标转地址"""
        import httpx

        url = f"{self.base_url}/geocode/regeo"
        params = {
            "key": self.api_key,
            "location": f"{lon},{lat}",
            "extensions": "all"
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                data = response.json()

                if data.get("status") == "1":
                    return data.get("regeocode", {})
        except Exception:
            pass

        return None

    def _calculate_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """计算两点间距离（米）- Haversine公式"""
        R = 6371000  # 地球半径(米)

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (math.sin(delta_phi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


class TiandituAPI:
    """
    天地图API客户端

    国家地理信息公共服务平台
    提供水系图层、DEM数字高程等数据
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.base_url = "https://api.tianditu.gov.cn"

    async def get_water_systems(self, bbox: Tuple[float, float, float, float]) -> List[Dict]:
        """
        获取水系数据

        Args:
            bbox: 边界框 (min_lon, min_lat, max_lon, max_lat)
        """
        # 天地图WFS服务
        url = f"{self.base_url}/WFS"

        params = {
            "key": self.api_key,
            "request": "GetFeature",
            "service": "WFS",
            "version": "1.1.0",
            "typeName": "TK_WATERLINE",  # 水系线
            "bbox": ",".join(str(x) for x in bbox)
        }

        # 实际实现需要接入天地图WFS服务
        return []

    async def get_dem_elevation(self, lat: float, lon: float) -> Optional[float]:
        """
        获取DEM高程数据

        使用SRTM或天地图DEM服务
        """
        # 实际实现需要接入DEM API
        # 这里返回模拟数据
        return 25.0  # 米


class GISDataLoader:
    """
    GIS矢量数据加载器

    支持加载：
    - Shapefile (.shp)
    - KML/KMZ
    - GeoJSON
    """

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    async def load_shapefile(self, file_path: str) -> Optional[Dict]:
        """加载Shapefile"""
        # 需要geopandas支持
        # 实际实现使用fiona读取shp
        return None

    async def load_kml(self, file_path: str) -> List[Dict]:
        """加载KML文件"""
        import xml.etree.ElementTree as ET

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            features = []
            ns = {"kml": "http://www.opengis.net/kml/2.2"}

            for placemark in root.findall(".//kml:Placemark", ns):
                name = placemark.find("kml:name", ns)
                coords = placemark.find(".//kml:coordinates", ns)

                if coords is not None:
                    coord_text = coords.text.strip()
                    parts = coord_text.split(",")
                    if len(parts) >= 2:
                        features.append({
                            "name": name.text if name is not None else "",
                            "lon": float(parts[0]),
                            "lat": float(parts[1])
                        })

            return features
        except Exception:
            return []

    async def load_geojson(self, file_path: str) -> Optional[Dict]:
        """加载GeoJSON"""
        import json

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


class SpatialIntelligenceEngine:
    """
    空间智能分析引擎

    整合多种地图API和数据源，提供：
    1. 敏感点自动识别
    2. 敏感区边界计算
    3. 防护距离分析
    4. 环境功能区判定
    """

    def __init__(self, amap_key: str = "", tianditu_key: str = ""):
        self.amap = AMapAPI(amap_key)
        self.tianditu = TiandituAPI(tianditu_key)
        self.gis_loader = GISDataLoader()

        # 内置敏感区模板
        self.sensitive_zone_templates = {
            "饮用水源一级保护区": {"radius": 1000, "level": "一级"},
            "饮用水源二级保护区": {"radius": 2000, "level": "二级"},
            "自然保护区核心区": {"radius": 500, "level": "核心区"},
            "自然保护区缓冲区": {"radius": 1000, "level": "缓冲区"},
            "基本农田": {"type": "polygon", "level": "永久"},
            "生态红线": {"type": "polygon", "level": "红线"},
        }

    async def analyze_spatial_context(
        self,
        project_id: str,
        project_name: str,
        lat: float,
        lon: float,
        radius: int = 5000
    ) -> SpatialAnalysisResult:
        """
        执行空间分析

        Args:
            project_id: 项目ID
            project_name: 项目名称
            lat: 项目中心纬度
            lon: 项目中心经度
            radius: 分析半径(米)
        """
        result = SpatialAnalysisResult(
            project_id=project_id,
            project_name=project_name,
            center_lat=lat,
            center_lon=lon,
            analysis_time=datetime.now()
        )

        # 1. 搜索周边敏感点
        result.pois = await self.amap.search_sensitive_points(lat, lon, radius)

        # 2. 计算方位角
        for poi in result.pois:
            poi.azimuth = self._calculate_azimuth(lat, lon, poi.latitude, poi.longitude)

        # 3. 获取地形数据
        result.terrain = await self.amap.get_terrain(lat, lon)

        # 4. 检查是否在敏感区内
        result.within_protected_areas = await self._check_protected_areas(lat, lon)

        # 5. 查找最近居民区
        result.nearest_residential = self._find_nearest(result.pois, POICategory.RESIDENTIAL)

        return result

    async def _check_protected_areas(self, lat: float, lon: float) -> List[str]:
        """检查是否在保护区内"""
        protected = []

        # 实际需要加载矢量数据判断
        # 这里简化处理
        return protected

    def _find_nearest(self, pois: List[POIPoint], category: POICategory) -> Optional[POIPoint]:
        """查找最近指定类型POI"""
        filtered = [p for p in pois if p.category == category]
        if not filtered:
            return None

        return min(filtered, key=lambda p: p.distance_to_project or float("inf"))

    def _calculate_azimuth(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """计算方位角（度）"""
        delta_lon = math.radians(lon2 - lon1)
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)

        x = math.sin(delta_lon) * math.cos(lat2_rad)
        y = (math.cos(lat1_rad) * math.sin(lat2_rad) -
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))

        azimuth = math.atan2(x, y)
        azimuth = math.degrees(azimuth)
        azimuth = (azimuth + 360) % 360

        return azimuth

    def generate_sensitive_zones_chapter(
        self,
        result: SpatialAnalysisResult
    ) -> str:
        """
        生成敏感目标章节内容

        Returns Markdown格式章节文本
        """
        lines = []

        lines.append("## 2.4 敏感目标分布\n")
        lines.append(f"### 2.4.1 项目周边敏感点\n")
        lines.append(f"根据现场踏勘和地图数据分析，项目中心坐标为（{result.center_lat:.6f}°N, {result.center_lon:.6f}°E），")
        lines.append(f"以项目为中心、半径{5000}m范围内共识别到环境敏感点 {len(result.pois)} 处，具体如下：\n")

        # 按类别分组
        by_category = {}
        for poi in result.pois:
            if poi.category not in by_category:
                by_category[poi.category] = []
            by_category[poi.category].append(poi)

        # 生成表格
        lines.append("| 序号 | 敏感点名称 | 类型 | 相对方位 | 距离(m) | 地址 |")
        lines.append("|------|------------|------|---------|---------|------|")

        idx = 1
        for category, pois in sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True):
            for poi in sorted(pois, key=lambda p: p.distance_to_project or float("inf")):
                direction = self._azimuth_to_direction(poi.azimuth)
                distance = poi.distance_to_project or 0
                lines.append(f"| {idx} | {poi.name} | {category.value} | {direction} | {distance:.0f} | {poi.address} |")
                idx += 1

        lines.append("")

        # 最近敏感点分析
        if result.nearest_residential:
            nearest = result.nearest_residential
            direction = self._azimuth_to_direction(nearest.azimuth)
            lines.append(f"**最近居民区**：{nearest.name}，位于项目{direction}方向，距离约 {nearest.distance_to_project:.0f} m。\n")

        # 保护区域检查
        if result.within_protected_areas:
            lines.append("### 2.4.2 环境敏感区判定\n")
            lines.append("根据分析，项目涉及以下环境敏感区：\n")
            for zone in result.within_protected_areas:
                lines.append(f"- {zone}")
            lines.append("\n")

        return "\n".join(lines)

    def _azimuth_to_direction(self, azimuth: float) -> str:
        """方位角转方向描述"""
        directions = [
            (0, "正北"),
            (45, "东北"),
            (90, "正东"),
            (135, "东南"),
            (180, "正南"),
            (225, "西南"),
            (270, "正西"),
            (315, "西北"),
            (360, "正北")
        ]

        for deg, name in directions:
            if abs(azimuth - deg) < 22.5:
                return name

        # 计算八方向
        idx = int((azimuth + 22.5) / 45) % 8
        names = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        return names[idx]


# ============ 全局实例 ============

_engine: Optional[SpatialIntelligenceEngine] = None


def get_spatial_engine(amap_key: str = "", tianditu_key: str = "") -> SpatialIntelligenceEngine:
    """获取空间智能引擎实例"""
    global _engine
    if _engine is None:
        _engine = SpatialIntelligenceEngine(amap_key, tianditu_key)
    return _engine


async def analyze_project_location(
    project_id: str,
    project_name: str,
    lat: float,
    lon: float,
    radius: int = 5000
) -> SpatialAnalysisResult:
    """便捷函数：分析项目位置"""
    engine = get_spatial_engine()
    return await engine.analyze_spatial_context(project_id, project_name, lat, lon, radius)
