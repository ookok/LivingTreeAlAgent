"""
气象数据模型
============

气象站、气象数据、站点索引等数据模型定义

Author: Hermes Desktop EIA System
"""

import json
import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime


class StationType(str, Enum):
    """气象站类型"""
    SYNOPTIC = "synoptic"           # 国家基准气候站
    GENERAL = "general"            # 一般气象站
    AUTO = "auto"                  # 自动气象站
    WIND = "wind"                  # 高空风观测站
    RADIOSONDE = "radiosonde"      # 探空站


class DataStatus(str, Enum):
    """数据状态"""
    AVAILABLE = "available"        # 可用
    PROCESSING = "processing"      # 处理中
    DOWNLOADING = "downloading"    # 下载中
    MISSING = "missing"            # 缺失
    DEPRECATED = "deprecated"      # 已废弃


@dataclass
class WeatherStation:
    """气象站点"""
    station_id: str               # 站号 (如 "54511")
    name: str                     # 站名 (如 "北京")
    province: str = ""            # 省份
    city: str = ""                # 城市
    latitude: float = 0.0         # 纬度
    longitude: float = 0.0         # 经度
    altitude: float = 0.0          # 海拔高度 (m)
    station_type: StationType = StationType.GENERAL
    data_status: DataStatus = DataStatus.AVAILABLE

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "WeatherStation":
        return cls(**d)

    def distance_to(self, lat: float, lon: float) -> float:
        """计算到某点的球面距离（度）"""
        return math.sqrt((self.latitude - lat) ** 2 + (self.longitude - lon) ** 2)

    def __hash__(self):
        return hash(self.station_id)


@dataclass
class MetDataFile:
    """气象数据文件"""
    station_id: str
    year: int                      # 数据年份
    file_sfc: str = ""             # 地面气象文件路径 (.sfc)
    file_pc: str = ""              # 探空气象文件路径 (.pc)
    file_met: str = ""             # AERMET中间格式 (.met)
    is_processed: bool = False    # 是否已处理
    processed_at: Optional[datetime] = None
    file_size: int = 0             # 文件大小 (bytes)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["processed_at"] = self.processed_at.isoformat() if self.processed_at else None
        return d


@dataclass
class StationIndex:
    """站点索引"""
    stations: List[WeatherStation] = field(default_factory=list)
    version: str = "1.0"           # 索引版本
    updated_at: datetime = field(default_factory=datetime.now)
    total_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "version": self.version,
            "updated_at": self.updated_at.isoformat(),
            "total_count": self.total_count,
            "stations": [s.to_dict() for s in self.stations]
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "StationIndex":
        d = d.copy()
        d["updated_at"] = datetime.fromisoformat(d["updated_at"])
        d["stations"] = [WeatherStation.from_dict(s) for s in d["stations"]]
        return cls(**d)

    def save_to(self, path: str):
        """保存到JSON文件"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from(cls, path: str) -> "StationIndex":
        """从JSON文件加载"""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


@dataclass
class MetCacheEntry:
    """气象缓存条目"""
    station_id: str
    matched_project_id: Optional[str] = None     # 匹配的项目ID
    distance: float = 0.0                         # 匹配距离（度）
    used_count: int = 0                           # 使用次数
    last_used: Optional[datetime] = None
    hit_rate: float = 0.0                         # 命中率

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["last_used"] = self.last_used.isoformat() if self.last_used else None
        return d


@dataclass
class MetCacheManifest:
    """气象缓存清单"""
    cache_dir: str = ""                            # 缓存目录
    entries: Dict[str, MetCacheEntry] = field(default_factory=dict)  # station_id -> entry
    total_size: int = 0                            # 总大小 (bytes)
    hit_count: int = 0                             # 命中次数
    miss_count: int = 0                            # 未命中次数

    def get_hit_rate(self) -> float:
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0

    def to_dict(self) -> Dict:
        return {
            "cache_dir": self.cache_dir,
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "total_size": self.total_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": self.get_hit_rate()
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "MetCacheManifest":
        d = d.copy()
        d["entries"] = {k: MetCacheEntry(**v) for k, v in d["entries"].items()}
        return cls(**d)

    def save_to(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from(cls, path: str) -> "MetCacheManifest":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


@dataclass
class ProjectLocation:
    """项目位置"""
    project_id: str
    project_name: str
    latitude: float
    longitude: float
    altitude: float = 0.0
    location_desc: str = ""       # 位置描述

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MatchedStation:
    """匹配结果"""
    project: ProjectLocation
    station: WeatherStation
    distance_deg: float            # 球面距离（度）
    distance_km: float             # 球面距离（km）
    cache_status: DataStatus       # 缓存状态
    met_files: Optional[MetDataFile] = None  # 气象文件

    def is_cached(self) -> bool:
        return self.cache_status == DataStatus.AVAILABLE and self.met_files is not None

    def to_dict(self) -> Dict:
        return {
            "project": self.project.to_dict(),
            "station": self.station.to_dict(),
            "distance_deg": self.distance_deg,
            "distance_km": self.distance_km,
            "cache_status": self.cache_status.value,
            "is_cached": self.is_cached(),
            "met_files": self.met_files.to_dict() if self.met_files else None
        }


@dataclass
class AERMODInput:
    """AERMOD输入文件内容"""
    title: str = ""
    location: Tuple[float, float, float] = (0, 0, 0)  # X, Y, Height
    sources: List[Dict] = field(default_factory=list)
    met_sfc_file: str = ""
    met_pc_file: str = ""
    output_options: Dict = field(default_factory=dict)

    def to_inp_string(self) -> str:
        """生成INP文件内容"""
        lines = ["CO STARTING"]
        lines.append(f"   TITLEONE {self.title}")
        lines.append(f"   TITLETWO Project AERMOD Simulation")
        lines.append("")

        # 源定义
        for i, src in enumerate(self.sources):
            lines.append(f"SO LOCATION {src['id']} {src['x']} {src['y']} {src['height']} {src['type']}")
            lines.append(f"   SRCPARAM {src['id']} {src['q']} {src['height']} {src.get('sigma_z', 10)} {src.get('sigma_y', 20)}")

        lines.append("")

        # 气象文件
        if self.met_sfc_file:
            lines.append(f"   ME SURFFILE {self.met_sfc_file}")
        if self.met_pc_file:
            lines.append(f"   ME PROFFILE {self.met_pc_file}")

        lines.append("")

        # 输出选项
        lines.append("   OU PLOTFILE ALL ./output/results.txt")
        lines.append("CO FINISHED")

        return "\n".join(lines)


@dataclass
class DownloadTask:
    """下载任务"""
    task_id: str
    station_id: str
    year: int
    status: str = "pending"        # pending, downloading, processing, completed, failed
    progress: float = 0.0          # 0-1
    error: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "station_id": self.station_id,
            "year": self.year,
            "status": self.status,
            "progress": self.progress,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
