"""
气象智能服务
============

统一入口，整合站点索引、缓存管理、最近查找、AERMOD生成

核心流程：
1. 输入项目坐标 → 动态匹配最近气象站
2. 优先使用本地缓存 → 缓存命中则直接使用
3. 缓存未命中 → 触发后台下载
4. 生成AERMOD输入文件 → 调用大气预测模型

Author: Hermes Desktop EIA System
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from .models import (
    WeatherStation,
    ProjectLocation,
    MatchedStation,
    MetDataFile,
    DataStatus,
    DownloadTask,
    AERMODInput,
    AERMODConfig,
)
from .station_index import (
    StationIndexManager,
    StationIndex,
    get_station_index_manager,
    find_nearest_station,
)
from .met_cache_manager import (
    MetCacheManager,
    MetCacheManifest,
    get_met_cache_manager,
    check_met_cache,
)
from .nearest_finder import (
    NearestStationFinder,
    MatchOptions,
    find_nearest_for_project,
    find_and_prepare_station,
    deg_to_km,
)
from .aermod_input_generator import (
    AERMODInputGenerator,
    AERMODConfig,
    EmissionSource,
    generate_aermod_inp,
    create_sample_inp,
)


class ServiceStatus(str, Enum):
    """服务状态"""
    IDLE = "idle"
    MATCHING = "matching"
    DOWNLOADING = "downloading"
    GENERATING = "generating"
    READY = "ready"
    ERROR = "error"


@dataclass
class MetServiceConfig:
    """气象服务配置"""
    # 路径配置
    met_lib_dir: str = ""           # 预处理气象库目录
    met_cache_dir: str = ""         # 运行时缓存目录
    station_index_path: str = ""     # 站点索引文件
    # 匹配配置
    max_match_distance_deg: float = 3.0
    cache_threshold_deg: float = 0.5
    # AERMOD配置
    aermod_base_year: int = 2020
    aermod_utm_zone: int = 50
    # 下载配置
    enable_auto_download: bool = False
    download_timeout: int = 300


class MeteorologicalService:
    """
    气象智能服务

    统一管理气象站匹配、缓存、AERMOD输入生成
    """

    def __init__(self, config: Optional[MetServiceConfig] = None):
        """
        Args:
            config: 服务配置
        """
        self.config = config or MetServiceConfig()

        # 初始化组件
        self.station_manager = get_station_index_manager(self.config.station_index_path)
        self.cache_manager = get_met_cache_manager(
            self.config.met_lib_dir,
            self.config.met_cache_dir
        )
        self.finder = NearestStationFinder(
            self.station_manager,
            self.cache_manager
        )
        self.aermod_generator = AERMODInputGenerator(
            AERMODConfig(
                base_year=self.config.aermod_base_year,
                utm_zone=self.config.aermod_utm_zone
            )
        )

        # 状态
        self._status = ServiceStatus.IDLE
        self._download_tasks: Dict[str, DownloadTask] = {}
        self._last_match: Optional[MatchedStation] = None

    @property
    def status(self) -> ServiceStatus:
        return self._status

    def configure(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def load_station_index(self) -> StationIndex:
        """加载站点索引"""
        self._status = ServiceStatus.MATCHING
        index = self.station_manager.load()
        return index

    async def match_station(
        self,
        project: ProjectLocation,
        options: Optional[MatchOptions] = None,
        auto_download: bool = False,
        download_callback: Optional[Callable[[str, int], Awaitable[MetDataFile]]] = None
    ) -> Tuple[MatchedStation, bool]:
        """
        匹配气象站

        Args:
            project: 项目位置
            options: 匹配选项
            auto_download: 是否自动下载未缓存数据
            download_callback: 下载回调

        Returns:
            (MatchedStation, needs_download)
        """
        self._status = ServiceStatus.MATCHING

        # 查找最近站点
        matched, needs_download = await find_and_prepare_station(
            project,
            download_callback if auto_download else None,
            options or MatchOptions(
                max_distance_deg=self.config.max_match_distance_deg,
                cache_threshold_deg=self.config.cache_threshold_deg
            )
        )

        if matched is None:
            self._status = ServiceStatus.ERROR
            raise ValueError(f"未找到合适的气象站 (距离阈值: {self.config.max_match_distance_deg}°)")
            # 创建假的matched对象
            from .models import WeatherStation, DataStatus
            station = WeatherStation(
                station_id="UNKNOWN",
                name="未知",
                latitude=project.latitude,
                longitude=project.longitude
            )
            matched = MatchedStation(
                project=project,
                station=station,
                distance_deg=999.0,
                distance_km=999.0,
                cache_status=DataStatus.MISSING,
                met_files=None
            )
            needs_download = True

        self._last_match = matched

        if matched.is_cached():
            self._status = ServiceStatus.READY
        elif needs_download:
            self._status = ServiceStatus.DOWNLOADING
        else:
            self._status = ServiceStatus.READY

        return matched, needs_download

    def match_station_sync(
        self,
        project_id: str,
        project_name: str,
        latitude: float,
        longitude: float,
        province: Optional[str] = None
    ) -> MatchedStation:
        """
        同步匹配气象站（快捷方法）

        Args:
            project_id: 项目ID
            project_name: 项目名称
            latitude: 项目纬度
            longitude: 项目经度
            province: 省份（可选）

        Returns:
            MatchedStation
        """
        project = ProjectLocation(
            project_id=project_id,
            project_name=project_name,
            latitude=latitude,
            longitude=longitude
        )

        options = MatchOptions(
            province_hint=province,
            max_distance_deg=self.config.max_match_distance_deg
        )

        matched = self.finder.find_nearest(project, options)

        if matched is None:
            raise ValueError(f"未找到合适的气象站 (距离阈值: {self.config.max_match_distance_deg}°)")

        self._last_match = matched
        return matched

    def generate_aermod_input(
        self,
        matched: Optional[MatchedStation] = None,
        output_dir: str = "",
        sources: Optional[List[Dict]] = None
    ) -> str:
        """
        生成AERMOD输入文件

        Args:
            matched: 匹配的站点（None则使用上次匹配结果）
            output_dir: 输出目录
            sources: 源参数列表

        Returns:
            INP文件路径
        """
        self._status = ServiceStatus.GENERATING

        matched = matched or self._last_match
        if matched is None:
            raise ValueError("未指定匹配的站点，请先调用 match_station()")

        if not output_dir:
            output_dir = str(Path.cwd() / "output" / matched.project.project_id)

        if sources:
            inp_path = self.aermod_generator.generate_for_project(
                matched.project,
                matched,
                output_dir,
                sources
            )
        else:
            inp_path = self.aermod_generator.generate(matched, output_dir)

        self._status = ServiceStatus.READY
        return inp_path

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        return self.cache_manager.get_cache_stats()

    def get_cached_stations(self) -> List[str]:
        """获取已缓存的站点列表"""
        return self.cache_manager.get_cached_stations()

    def get_all_stations(self) -> List[WeatherStation]:
        """获取所有可用站点"""
        self.load_station_index()
        return self.station_manager.get_all()

    def find_stations_in_region(self, region: str) -> List[WeatherStation]:
        """按区域获取站点"""
        self.load_station_index()
        return self.station_manager.filter_by_region(region)

    def find_stations_in_province(self, province: str) -> List[WeatherStation]:
        """按省份获取站点"""
        self.load_station_index()
        return self.station_manager.filter_by_province(province)


# 全局实例
_global_service: Optional[MeteorologicalService] = None


def get_meteorological_service(config: Optional[MetServiceConfig] = None) -> MeteorologicalService:
    """获取全局气象服务"""
    global _global_service
    if _global_service is None:
        _global_service = MeteorologicalService(config)
    return _global_service


# ==================== 便捷函数 ====================

def match_nearest(
    lat: float,
    lon: float,
    project_id: str = "default",
    project_name: str = "Default Project",
    province: Optional[str] = None
) -> Dict[str, Any]:
    """
    快捷函数：一行代码匹配最近气象站

    Args:
        lat: 项目纬度
        lon: 项目经度
        project_id: 项目ID
        project_name: 项目名称
        province: 省份（可选）

    Returns:
        {
            "station_id": "54511",
            "station_name": "北京",
            "distance_km": 45.2,
            "is_cached": True,
            "sfc_file": "path/to/54511.sfc",
            "pc_file": "path/to/54511.pc"
        }
    """
    service = get_meteorological_service()

    matched = service.match_station_sync(
        project_id=project_id,
        project_name=project_name,
        latitude=lat,
        longitude=lon,
        province=province
    )

    return {
        "station_id": matched.station.station_id,
        "station_name": matched.station.name,
        "province": matched.station.province,
        "latitude": matched.station.latitude,
        "longitude": matched.station.longitude,
        "altitude": matched.station.altitude,
        "distance_deg": round(matched.distance_deg, 4),
        "distance_km": round(matched.distance_km, 2),
        "is_cached": matched.is_cached(),
        "cache_status": matched.cache_status.value,
        "sfc_file": matched.met_files.file_sfc if matched.met_files else None,
        "pc_file": matched.met_files.file_pc if matched.met_files else None,
    }


def generate_inp(
    lat: float,
    lon: float,
    sources: List[Dict],
    output_dir: str,
    project_name: str = "Project",
    project_id: str = "default"
) -> str:
    """
    快捷函数：匹配气象站 + 生成AERMOD输入

    Args:
        lat: 项目纬度
        lon: 项目经度
        sources: 源参数列表
        output_dir: 输出目录
        project_name: 项目名称
        project_id: 项目ID

    Returns:
        INP文件路径
    """
    service = get_meteorological_service()

    # 创建项目位置
    project = ProjectLocation(
        project_id=project_id,
        project_name=project_name,
        latitude=lat,
        longitude=lon
    )

    # 匹配站点
    matched, _ = asyncio.run(service.match_station(project))

    # 生成输入文件
    inp_path = service.generate_aermod_input(matched, output_dir, sources)

    return inp_path
