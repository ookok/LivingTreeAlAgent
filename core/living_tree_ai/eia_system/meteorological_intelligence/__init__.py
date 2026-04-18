"""
气象智能模块
============

动态气象站匹配系统，实现"按项目坐标自动选址"：
1. 站点索引管理 - 全国2400+气象站
2. 缓存管理器 - met_lib/met_cache两级缓存
3. 最近站点查找 - 球面距离算法
4. AERMOD输入生成 - 动态INP文件

核心流程：
输入项目坐标 → 动态匹配最近站点 → 优先使用本地缓存 →
缓存未命中则触发下载 → 生成AERMOD输入文件

Author: Hermes Desktop EIA System
"""

from .models import (
    # 枚举
    StationType,
    DataStatus,
    # 站点
    WeatherStation,
    MetDataFile,
    StationIndex,
    MetCacheEntry,
    MetCacheManifest,
    # 项目
    ProjectLocation,
    MatchedStation,
    # AERMOD
    AERMODInput,
    AERMODConfig,
    EmissionSource,
    # 任务
    DownloadTask,
)

from .station_index import (
    StationIndexManager,
    get_station_index_manager,
    find_nearest_station,
)

from .met_cache_manager import (
    MetCacheManager,
    get_met_cache_manager,
    check_met_cache,
)

from .nearest_finder import (
    NearestStationFinder,
    NearestStationFinder,
    MatchOptions,
    find_nearest_for_project,
    find_and_prepare_station,
    deg_to_km,
    haversine_distance_km,
)

from .aermod_input_generator import (
    AERMODInputGenerator,
    AERMODConfig,
    EmissionSource,
    generate_aermod_inp,
    create_sample_inp,
)

from .meteorological_service import (
    MeteorologicalService,
    MetServiceConfig,
    ServiceStatus,
    get_meteorological_service,
    match_nearest,
    generate_inp,
)


__all__ = [
    # 枚举
    "StationType",
    "DataStatus",
    "ServiceStatus",

    # 模型
    "WeatherStation",
    "MetDataFile",
    "StationIndex",
    "MetCacheEntry",
    "MetCacheManifest",
    "ProjectLocation",
    "MatchedStation",
    "AERMODInput",
    "AERMODConfig",
    "EmissionSource",
    "DownloadTask",

    # 站点管理
    "StationIndexManager",
    "get_station_index_manager",
    "find_nearest_station",

    # 缓存管理
    "MetCacheManager",
    "get_met_cache_manager",
    "check_met_cache",

    # 最近查找
    "NearestStationFinder",
    "MatchOptions",
    "find_nearest_for_project",
    "find_and_prepare_station",
    "deg_to_km",
    "haversine_distance_km",

    # AERMOD生成
    "AERMODInputGenerator",
    "generate_aermod_inp",
    "create_sample_inp",

    # 服务
    "MeteorologicalService",
    "MetServiceConfig",
    "get_meteorological_service",
    "match_nearest",
    "generate_inp",
]
