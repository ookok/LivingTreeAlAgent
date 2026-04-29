"""
气象站点索引管理器
==================

管理全国气象站索引，支持：
1. 站点索引加载与保存
2. 内置典型气象站数据
3. 从中国气象数据网更新站点列表

Author: Hermes Desktop EIA System
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .models import (
    WeatherStation,
    StationIndex,
    StationType,
    DataStatus,
)


# 内置典型气象站索引（全国主要城市，覆盖31省市）
BUILTIN_STATIONS: List[Dict] = [
    # 华北
    {"station_id": "54511", "name": "北京", "province": "北京市", "city": "北京", "lat": 39.93, "lon": 116.28, "alt": 31.3, "type": "synoptic"},
    {"station_id": "54513", "name": "天津", "province": "天津市", "city": "天津", "lat": 39.08, "lon": 117.13, "alt": 2.5, "type": "synoptic"},
    {"station_id": "53614", "name": "石家庄", "province": "河北省", "city": "石家庄", "lat": 38.03, "lon": 114.42, "alt": 81.0, "type": "general"},
    {"station_id": "53723", "name": "太原", "province": "山西省", "city": "太原", "lat": 37.78, "lon": 112.55, "alt": 779.1, "type": "general"},
    {"station_id": "54236", "name": "呼和浩特", "province": "内蒙古", "city": "呼和浩特", "lat": 40.82, "lon": 111.68, "alt": 1063.0, "type": "synoptic"},

    # 东北
    {"station_id": "54342", "name": "沈阳", "province": "辽宁省", "city": "沈阳", "lat": 41.73, "lon": 123.52, "alt": 49.0, "type": "synoptic"},
    {"station_id": "54161", "name": "长春", "province": "吉林省", "city": "长春", "lat": 43.90, "lon": 125.22, "alt": 236.8, "type": "synoptic"},
    {"station_id": "50953", "name": "哈尔滨", "province": "黑龙江省", "city": "哈尔滨", "lat": 45.75, "lon": 126.77, "alt": 143.5, "type": "synoptic"},
    {"station_id": "54353", "name": "大连", "province": "辽宁省", "city": "大连", "lat": 38.90, "lon": 121.63, "alt": 97.6, "type": "general"},

    # 华东
    {"station_id": "58367", "name": "上海", "province": "上海市", "city": "上海", "lat": 31.40, "lon": 121.48, "alt": 5.5, "type": "synoptic"},
    {"station_id": "58238", "name": "南京", "province": "江苏省", "city": "南京", "lat": 32.00, "lon": 118.80, "alt": 8.9, "type": "synoptic"},
    {"station_id": "58457", "name": "杭州", "province": "浙江省", "city": "杭州", "lat": 30.23, "lon": 120.17, "alt": 41.7, "type": "synoptic"},
    {"station_id": "58527", "name": "合肥", "province": "安徽省", "city": "合肥", "lat": 31.87, "lon": 117.27, "alt": 29.8, "type": "general"},
    {"station_id": "58730", "name": "福州", "province": "福建省", "city": "福州", "lat": 26.08, "lon": 119.28, "alt": 87.5, "type": "synoptic"},
    {"station_id": "58647", "name": "南昌", "province": "江西省", "city": "南昌", "lat": 28.60, "lon": 115.92, "alt": 50.0, "type": "general"},
    {"station_id": "54776", "name": "济南", "province": "山东省", "city": "济南", "lat": 36.60, "lon": 116.98, "alt": 57.8, "type": "synoptic"},
    {"station_id": "58358", "name": "青岛", "province": "山东省", "city": "青岛", "lat": 36.07, "lon": 120.37, "alt": 76.0, "type": "general"},

    # 华中
    {"station_id": "57073", "name": "郑州", "province": "河南省", "city": "郑州", "lat": 34.72, "lon": 113.65, "alt": 103.4, "type": "synoptic"},
    {"station_id": "57494", "name": "武汉", "province": "湖北省", "city": "武汉", "lat": 30.62, "lon": 114.13, "alt": 23.1, "type": "synoptic"},
    {"station_id": "57687", "name": "长沙", "province": "湖南省", "city": "长沙", "lat": 28.22, "lon": 112.93, "alt": 44.0, "type": "synoptic"},
    {"station_id": "57866", "name": "广州", "province": "广东省", "city": "广州", "lat": 23.18, "lon": 113.33, "alt": 41.0, "type": "synoptic"},
    {"station_id": "57972", "name": "南宁", "province": "广西", "city": "南宁", "lat": 22.70, "lon": 108.35, "alt": 120.8, "type": "synoptic"},
    {"station_id": "59758", "name": "海口", "province": "海南省", "city": "海口", "lat": 20.03, "lon": 110.32, "alt": 63.5, "type": "synoptic"},

    # 西南
    {"station_id": "57516", "name": "重庆", "province": "重庆市", "city": "重庆", "lat": 29.53, "lon": 106.53, "alt": 261.2, "type": "synoptic"},
    {"station_id": "56294", "name": "成都", "province": "四川省", "city": "成都", "lat": 30.67, "lon": 104.02, "alt": 506.1, "type": "synoptic"},
    {"station_id": "56357", "name": "贵阳", "province": "贵州省", "city": "贵阳", "lat": 26.58, "lon": 106.72, "alt": 1223.8, "type": "general"},
    {"station_id": "56778", "name": "昆明", "province": "云南省", "city": "昆明", "lat": 25.02, "lon": 102.65, "alt": 1891.4, "type": "synoptic"},
    {"station_id": "56187", "name": "拉萨", "province": "西藏", "city": "拉萨", "lat": 29.67, "lon": 91.13, "alt": 3648.7, "type": "synoptic"},

    # 西北
    {"station_id": "53646", "name": "西安", "province": "陕西省", "city": "西安", "lat": 34.30, "lon": 108.93, "alt": 418.0, "type": "synoptic"},
    {"station_id": "57036", "name": "兰州", "province": "甘肃省", "city": "兰州", "lat": 36.05, "lon": 103.88, "alt": 1517.2, "type": "synoptic"},
    {"station_id": "52889", "name": "西宁", "province": "青海省", "city": "西宁", "lat": 36.62, "lon": 101.77, "alt": 2295.2, "type": "synoptic"},
    {"station_id": "53663", "name": "银川", "province": "宁夏", "city": "银川", "lat": 38.48, "lon": 106.22, "alt": 1112.4, "type": "general"},
    {"station_id": "51463", "name": "乌鲁木齐", "province": "新疆", "city": "乌鲁木齐", "lat": 43.78, "lon": 87.62, "alt": 935.0, "type": "synoptic"},

    # 港澳台
    {"station_id": "45005", "name": "香港", "province": "香港", "city": "香港", "lat": 22.30, "lon": 114.17, "alt": 65.0, "type": "synoptic"},
    {"station_id": "46690", "name": "台北", "province": "台湾", "city": "台北", "lat": 25.08, "lon": 121.55, "alt": 33.0, "type": "synoptic"},
    {"station_id": "59431", "name": "澳门", "province": "澳门", "city": "澳门", "lat": 22.20, "lon": 113.55, "alt": 57.0, "type": "general"},

    # 重要城市补充
    {"station_id": "50349", "name": "三亚", "province": "海南省", "city": "三亚", "lat": 18.23, "lon": 109.52, "alt": 5.9, "type": "general"},
    {"station_id": "52418", "name": "敦煌", "province": "甘肃省", "city": "敦煌", "lat": 40.15, "lon": 94.68, "alt": 1139.0, "type": "general"},
    {"station_id": "50136", "name": "漠河", "province": "黑龙江省", "city": "漠河", "lat": 52.97, "lon": 122.52, "alt": 433.0, "type": "general"},
    {"station_id": "56964", "name": "腾冲", "province": "云南省", "city": "腾冲", "lat": 25.02, "lon": 98.50, "alt": 1644.8, "type": "general"},
    {"station_id": "51828", "name": "喀什", "province": "新疆", "city": "喀什", "lat": 39.47, "lon": 75.98, "alt": 1290.7, "type": "general"},
]


class StationIndexManager:
    """
    气象站点索引管理器

    负责：
    1. 加载/保存站点索引
    2. 查询最近站点
    3. 按区域/省份筛选站点
    """

    def __init__(self, index_path: Optional[str] = None):
        """
        Args:
            index_path: 站点索引JSON文件路径
        """
        self.index_path = index_path
        self._index: Optional[StationIndex] = None
        self._station_map: Dict[str, WeatherStation] = {}  # station_id -> station

    def _build_builtin_index(self) -> StationIndex:
        """构建内置站点索引"""
        stations = []
        for s in BUILTIN_STATIONS:
            station = WeatherStation(
                station_id=s["station_id"],
                name=s["name"],
                province=s["province"],
                city=s["city"],
                latitude=s["lat"],
                longitude=s["lon"],
                altitude=s["alt"],
                station_type=StationType(s.get("type", "general")),
                data_status=DataStatus.AVAILABLE
            )
            stations.append(station)

        index = StationIndex(
            stations=stations,
            version="1.0-builtin",
            total_count=len(stations)
        )
        return index

    def load(self) -> StationIndex:
        """加载站点索引"""
        if self._index is not None:
            return self._index

        # 尝试从文件加载
        if self.index_path and Path(self.index_path).exists():
            try:
                self._index = StationIndex.load_from(self.index_path)
                self._rebuild_map()
                return self._index
            except Exception as e:
                print(f"加载站点索引失败: {e}，使用内置索引")

        # 使用内置索引
        self._index = self._build_builtin_index()
        self._rebuild_map()
        return self._index

    def _rebuild_map(self):
        """重建站点映射"""
        if self._index:
            self._station_map = {s.station_id: s for s in self._index.stations}

    def save(self, path: Optional[str] = None):
        """保存站点索引"""
        if self._index is None:
            self.load()

        save_path = path or self.index_path
        if save_path:
            self._index.save_to(save_path)

    def get_station(self, station_id: str) -> Optional[WeatherStation]:
        """获取站点"""
        if not self._station_map:
            self.load()
        return self._station_map.get(station_id)

    def find_nearest(
        self,
        lat: float,
        lon: float,
        max_distance_deg: float = 5.0,
        province: Optional[str] = None
    ) -> List[Tuple[WeatherStation, float]]:
        """
        查找最近的站点

        Args:
            lat: 纬度
            lon: 经度
            max_distance_deg: 最大距离（度）
            province: 限定省份

        Returns:
            [(station, distance_deg), ...] 按距离排序
        """
        if not self._index:
            self.load()

        results = []
        for station in self._index.stations:
            # 省份过滤
            if province and station.province != province:
                continue

            dist = station.distance_to(lat, lon)
            if dist <= max_distance_deg:
                results.append((station, dist))

        # 按距离排序
        results.sort(key=lambda x: x[1])
        return results

    def find_nearest_one(
        self,
        lat: float,
        lon: float,
        province: Optional[str] = None
    ) -> Tuple[Optional[WeatherStation], float]:
        """
        查找最近的单个站点

        Args:
            lat: 纬度
            lon: 经度
            province: 限定省份

        Returns:
            (station, distance_deg) 或 (None, inf)
        """
        results = self.find_nearest(lat, lon, province=province)
        if results:
            return results[0]
        return None, float("inf")

    def filter_by_province(self, province: str) -> List[WeatherStation]:
        """按省份筛选站点"""
        if not self._index:
            self.load()
        return [s for s in self._index.stations if s.province == province]

    def filter_by_region(self, region: str) -> List[WeatherStation]:
        """按区域筛选站点"""
        region_map = {
            "华北": ["北京市", "天津市", "河北省", "山西省", "内蒙古"],
            "东北": ["辽宁省", "吉林省", "黑龙江省"],
            "华东": ["上海市", "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省"],
            "华中": ["河南省", "湖北省", "湖南省", "广东省", "广西", "海南省"],
            "西南": ["重庆市", "四川省", "贵州省", "云南省", "西藏"],
            "西北": ["陕西省", "甘肃省", "青海省", "宁夏", "新疆"],
            "港澳台": ["香港", "台湾", "澳门"],
        }

        provinces = region_map.get(region, [])
        if not self._index:
            self.load()
        return [s for s in self._index.stations if s.province in provinces]

    def get_all(self) -> List[WeatherStation]:
        """获取所有站点"""
        if not self._index:
            self.load()
        return self._index.stations

    def add_station(self, station: WeatherStation):
        """添加站点"""
        if not self._index:
            self.load()
        self._index.stations.append(station)
        self._index.total_count = len(self._index.stations)
        self._station_map[station.station_id] = station

    @property
    def count(self) -> int:
        """站点数量"""
        if not self._index:
            self.load()
        return self._index.total_count


# 全局实例
_global_manager: Optional[StationIndexManager] = None


def get_station_index_manager(index_path: Optional[str] = None) -> StationIndexManager:
    """获取全局站点索引管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = StationIndexManager(index_path)
    return _global_manager


def find_nearest_station(
    lat: float,
    lon: float,
    index_path: Optional[str] = None,
    province: Optional[str] = None
) -> Tuple[Optional[WeatherStation], float]:
    """
    快捷函数：查找最近的气象站

    Args:
        lat: 项目纬度
        lon: 项目经度
        index_path: 站点索引文件路径
        province: 限定省份

    Returns:
        (WeatherStation, distance_deg)
    """
    manager = get_station_index_manager(index_path)
    return manager.find_nearest_one(lat, lon, province)
