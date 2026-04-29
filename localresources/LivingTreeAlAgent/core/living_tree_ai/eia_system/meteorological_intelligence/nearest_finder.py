"""
最近站点查找器
==============

根据项目坐标动态匹配最近气象站：
1. 球面距离计算
2. 缓存优先策略
3. 多级降级（缓存→下载→合成）

Author: Hermes Desktop EIA System
"""

import math
from typing import Optional, List, Tuple, Dict, Callable, Awaitable
from dataclasses import dataclass

from .models import (
    WeatherStation,
    ProjectLocation,
    MatchedStation,
    MetDataFile,
    DataStatus,
    DownloadTask,
)
from .station_index import StationIndexManager, get_station_index_manager
from .met_cache_manager import MetCacheManager, get_met_cache_manager


# 地球半径(km)
EARTH_RADIUS_KM = 6371.0

# 最大匹配距离阈值(度)，超过则认为无合适站点
MAX_DISTANCE_DEG = 3.0

# 缓存优先阈值(度)，超过则优先下载而非使用远距离缓存
CACHE_THRESHOLD_DEG = 0.5


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    使用 Haversine 公式计算两点间的球面距离

    Args:
        lat1, lon1: 第一个点的纬度和经度
        lat2, lon2: 第二个点的纬度和经度

    Returns:
        距离(km)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def deg_to_km(deg: float, latitude: float = 45.0) -> float:
    """
    将纬度度数转换为近似公里数

    Args:
        deg: 度数
        latitude: 参考纬度（影响经度方向的距离）

    Returns:
        近似公里数
    """
    # 1度纬度 ≈ 111 km
    lat_km = deg * 111.0
    # 1度经度 ≈ 111 * cos(lat) km
    lon_km = deg * 111.0 * math.cos(math.radians(latitude))
    # 取平均值
    return (lat_km + lon_km) / 2


@dataclass
class MatchOptions:
    """匹配选项"""
    max_distance_deg: float = MAX_DISTANCE_DEG
    cache_threshold_deg: float = CACHE_THRESHOLD_DEG
    province_hint: Optional[str] = None  # 省份提示
    require_cached: bool = False          # 是否必须缓存
    year_hint: int = 2020               # 数据年份


class NearestStationFinder:
    """
    最近站点查找器

    匹配策略：
    1. 计算项目坐标到所有站点的球面距离
    2. 按距离排序
    3. 检查最近站点的缓存状态
    4. 返回匹配结果（含缓存状态和气象文件路径）
    """

    def __init__(
        self,
        station_manager: Optional[StationIndexManager] = None,
        cache_manager: Optional[MetCacheManager] = None
    ):
        """
        Args:
            station_manager: 站点索引管理器
            cache_manager: 气象缓存管理器
        """
        self.station_manager = station_manager or get_station_index_manager()
        self.cache_manager = cache_manager or get_met_cache_manager()

    def find_nearest(
        self,
        project: ProjectLocation,
        options: Optional[MatchOptions] = None
    ) -> Optional[MatchedStation]:
        """
        查找最近的可用站点

        Args:
            project: 项目位置
            options: 匹配选项

        Returns:
            MatchedStation 或 None（无合适站点）
        """
        options = options or MatchOptions()

        # 确保索引已加载
        self.station_manager.load()

        # 查找最近站点
        station, dist_deg = self.station_manager.find_nearest_one(
            project.latitude,
            project.longitude,
            province=options.province_hint
        )

        if station is None:
            return None

        # 检查距离是否超限
        if dist_deg > options.max_distance_deg:
            return None

        # 检查缓存状态
        cache_status = self.cache_manager.check_cache(station.station_id)
        met_files = None

        if cache_status == DataStatus.AVAILABLE:
            met_files = self.cache_manager.get_met_files(station.station_id)
            # 记录缓存命中
            self.cache_manager.register_cache_hit(
                station.station_id,
                project.project_id,
                dist_deg
            )
        else:
            # 记录缓存未命中
            self.cache_manager.register_cache_miss(station.station_id)

        # 转换距离为km
        dist_km = deg_to_km(dist_deg, project.latitude)

        return MatchedStation(
            project=project,
            station=station,
            distance_deg=dist_deg,
            distance_km=dist_km,
            cache_status=cache_status,
            met_files=met_files
        )

    def find_top_n(
        self,
        project: ProjectLocation,
        n: int = 5,
        options: Optional[MatchOptions] = None
    ) -> List[MatchedStation]:
        """
        查找最近的N个站点

        Args:
            project: 项目位置
            n: 返回数量
            options: 匹配选项

        Returns:
            MatchedStation 列表
        """
        options = options or MatchOptions()

        # 确保索引已加载
        self.station_manager.load()

        # 查找最近的N个站点
        results = self.station_manager.find_nearest(
            project.latitude,
            project.longitude,
            max_distance_deg=options.max_distance_deg,
            province=options.province_hint
        )

        matched = []
        for station, dist_deg in results[:n]:
            cache_status = self.cache_manager.check_cache(station.station_id)
            met_files = None

            if cache_status == DataStatus.AVAILABLE:
                met_files = self.cache_manager.get_met_files(station.station_id)

            dist_km = deg_to_km(dist_deg, project.latitude)

            matched.append(MatchedStation(
                project=project,
                station=station,
                distance_deg=dist_deg,
                distance_km=dist_km,
                cache_status=cache_status,
                met_files=met_files
            ))

        return matched

    def get_alternative(
        self,
        project: ProjectLocation,
        original_station: WeatherStation,
        options: Optional[MatchOptions] = None
    ) -> Optional[MatchedStation]:
        """
        获取备选站点（当原站点不可用时）

        Args:
            project: 项目位置
            original_station: 原站点
            options: 匹配选项

        Returns:
            备选 MatchedStation 或 None
        """
        # 获取top列表，排除原站点
        all_matches = self.find_top_n(
            project,
            n=10,
            options=options
        )

        for match in all_matches:
            if match.station.station_id != original_station.station_id:
                if match.cache_status == DataStatus.AVAILABLE or not options.require_cached:
                    return match

        return None


async def find_and_prepare_station(
    project: ProjectLocation,
    download_callback: Optional[Callable[[str, int], Awaitable[MetDataFile]]] = None,
    options: Optional[MatchOptions] = None
) -> Tuple[Optional[MatchedStation], bool]:
    """
    查找并准备站点气象数据

    策略：
    1. 查找最近站点
    2. 如果缓存命中 → 直接返回
    3. 如果缓存未命中 → 触发后台下载

    Args:
        project: 项目位置
        download_callback: 下载回调函数 (station_id, year) -> MetDataFile
        options: 匹配选项

    Returns:
        (MatchedStation, needs_download): 匹配结果和是否需要下载
    """
    finder = NearestStationFinder()
    options = options or MatchOptions()

    # 查找最近站点
    matched = finder.find_nearest(project, options)

    if matched is None:
        return None, False

    if matched.is_cached():
        # 缓存命中
        return matched, False
    else:
        # 缓存未命中，需要下载
        if download_callback:
            try:
                met_files = await download_callback(matched.station.station_id, options.year_hint)
                matched.met_files = met_files
                matched.cache_status = DataStatus.AVAILABLE
                return matched, True
            except Exception as e:
                print(f"下载气象数据失败: {e}")
                return matched, True  # 仍返回matched，但标记需要下载

        return matched, True


# 全局实例
_global_finder: Optional[NearestStationFinder] = None


def get_nearest_finder() -> NearestStationFinder:
    """获取全局最近站点查找器"""
    global _global_finder
    if _global_finder is None:
        _global_finder = NearestStationFinder()
    return _global_finder


def find_nearest_for_project(
    project_id: str,
    project_name: str,
    latitude: float,
    longitude: float,
    province: Optional[str] = None
) -> Optional[MatchedStation]:
    """
    快捷函数：根据项目坐标查找最近气象站

    Args:
        project_id: 项目ID
        project_name: 项目名称
        latitude: 项目纬度
        longitude: 项目经度
        province: 省份（可选）

    Returns:
        MatchedStation 或 None
    """
    project = ProjectLocation(
        project_id=project_id,
        project_name=project_name,
        latitude=latitude,
        longitude=longitude
    )

    options = MatchOptions(province_hint=province)
    finder = get_nearest_finder()

    return finder.find_nearest(project, options)
