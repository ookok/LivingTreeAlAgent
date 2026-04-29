"""
气象数据缓存管理器
==================

管理预处理的AERMOD气象数据文件(.sfc/.pc)：
1. 本地缓存查询
2. 缓存命中/未命中处理
3. 缓存目录管理
4. 缓存统计

Author: Hermes Desktop EIA System
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime

from .models import (
    MetDataFile,
    MetCacheEntry,
    MetCacheManifest,
    DataStatus,
)
from .station_index import get_station_index_manager


class MetCacheManager:
    """
    气象数据缓存管理器

    缓存策略：
    - met_lib/: 开发期预处理的全国站点文件
    - met_cache/: 运行时动态下载的站点文件

    缓存命名规则：
    - {station_id}.sfc - 地面气象文件
    - {station_id}.pc  - 探空气象文件
    """

    def __init__(
        self,
        met_lib_dir: str = "",
        met_cache_dir: str = "",
        manifest_path: str = ""
    ):
        """
        Args:
            met_lib_dir: 预处理气象文件目录 (met_lib/)
            met_cache_dir: 运行时缓存目录 (met_cache/)
            manifest_path: 缓存清单文件路径
        """
        # 默认路径
        if not met_lib_dir:
            met_lib_dir = str(Path(__file__).parent.parent.parent.parent.parent / "met_lib")
        if not met_cache_dir:
            met_cache_dir = str(Path(__file__).parent.parent.parent.parent.parent / "met_cache")
        if not manifest_path:
            manifest_path = str(Path(met_cache_dir) / "cache_manifest.json")

        self.met_lib_dir = Path(met_lib_dir)
        self.met_cache_dir = Path(met_cache_dir)
        self.manifest_path = Path(manifest_path)

        # 确保目录存在
        self.met_lib_dir.mkdir(parents=True, exist_ok=True)
        self.met_cache_dir.mkdir(parents=True, exist_ok=True)

        # 加载缓存清单
        self._manifest: Optional[MetCacheManifest] = None
        self._load_manifest()

    def _load_manifest(self):
        """加载缓存清单"""
        if self.manifest_path.exists():
            try:
                self._manifest = MetCacheManifest.load_from(str(self.manifest_path))
                self._manifest.cache_dir = str(self.met_cache_dir)
            except Exception as e:
                print(f"加载缓存清单失败: {e}")
                self._manifest = MetCacheManifest(cache_dir=str(self.met_cache_dir))
        else:
            self._manifest = MetCacheManifest(cache_dir=str(self.met_cache_dir))

    def _save_manifest(self):
        """保存缓存清单"""
        if self._manifest:
            self._manifest.save_to(str(self.manifest_path))

    def _get_met_files(self, station_id: str) -> Optional[MetDataFile]:
        """获取站点的气象文件信息"""
        # 优先查 met_lib
        sfc_lib = self.met_lib_dir / f"{station_id}.sfc"
        pc_lib = self.met_lib_dir / f"{station_id}.pc"

        # 次查 met_cache
        sfc_cache = self.met_cache_dir / f"{station_id}.sfc"
        pc_cache = self.met_cache_dir / f"{station_id}.pc"

        sfc_file = str(sfc_lib) if sfc_lib.exists() else (str(sfc_cache) if sfc_cache.exists() else "")
        pc_file = str(pc_lib) if pc_lib.exists() else (str(pc_cache) if pc_cache.exists() else "")

        if sfc_file or pc_file:
            is_processed = bool(sfc_file)
            file_size = 0
            if sfc_file and Path(sfc_file).exists():
                file_size += Path(sfc_file).stat().st_size
            if pc_file and Path(pc_file).exists():
                file_size += Path(pc_file).stat().st_size

            return MetDataFile(
                station_id=station_id,
                year=2020,  # 默认2020年
                file_sfc=sfc_file,
                file_pc=pc_file,
                is_processed=is_processed,
                processed_at=datetime.now(),
                file_size=file_size
            )

        return None

    def check_cache(self, station_id: str) -> DataStatus:
        """
        检查站点气象数据是否在缓存中

        Returns:
            DataStatus: AVAILABLE / MISSING
        """
        met_files = self._get_met_files(station_id)
        return DataStatus.AVAILABLE if met_files else DataStatus.MISSING

    def get_met_files(self, station_id: str) -> Optional[MetDataFile]:
        """获取站点的气象文件"""
        return self._get_met_files(station_id)

    def register_cache_hit(
        self,
        station_id: str,
        project_id: Optional[str] = None,
        distance: float = 0.0
    ):
        """
        记录缓存命中

        Args:
            station_id: 站点ID
            project_id: 匹配的项目ID
            distance: 匹配距离
        """
        if not self._manifest:
            return

        # 更新命中统计
        self._manifest.hit_count += 1

        # 更新条目
        if station_id in self._manifest.entries:
            entry = self._manifest.entries[station_id]
            entry.used_count += 1
            entry.last_used = datetime.now()
            entry.hit_rate = entry.used_count / max(1, self._manifest.hit_count + self._manifest.miss_count)
        else:
            entry = MetCacheEntry(
                station_id=station_id,
                matched_project_id=project_id,
                distance=distance,
                used_count=1,
                last_used=datetime.now(),
                hit_rate=0.0
            )
            self._manifest.entries[station_id] = entry

        self._save_manifest()

    def register_cache_miss(self, station_id: str):
        """记录缓存未命中"""
        if not self._manifest:
            return

        self._manifest.miss_count += 1
        self._save_manifest()

    def add_to_cache(
        self,
        station_id: str,
        sfc_data: Optional[bytes] = None,
        pc_data: Optional[bytes] = None,
        year: int = 2020
    ) -> MetDataFile:
        """
        添加气象数据到缓存

        Args:
            station_id: 站点ID
            sfc_data: 地面气象文件数据
            pc_data: 探空气象文件数据
            year: 数据年份

        Returns:
            MetDataFile: 气象文件信息
        """
        sfc_file = self.met_cache_dir / f"{station_id}.sfc"
        pc_file = self.met_cache_dir / f"{station_id}.pc"

        file_size = 0

        if sfc_data:
            sfc_file.write_bytes(sfc_data)
            file_size += len(sfc_data)

        if pc_data:
            pc_file.write_bytes(pc_data)
            file_size += len(pc_data)

        met_files = MetDataFile(
            station_id=station_id,
            year=year,
            file_sfc=str(sfc_file),
            file_pc=str(pc_file),
            is_processed=True,
            processed_at=datetime.now(),
            file_size=file_size
        )

        # 更新缓存条目
        if station_id in self._manifest.entries:
            entry = self._manifest.entries[station_id]
            entry.last_used = datetime.now()
        else:
            entry = MetCacheEntry(station_id=station_id)
            self._manifest.entries[station_id] = entry

        self._manifest.total_size += file_size
        self._save_manifest()

        return met_files

    def remove_from_cache(self, station_id: str):
        """从缓存中移除气象数据"""
        sfc_file = self.met_cache_dir / f"{station_id}.sfc"
        pc_file = self.met_cache_dir / f"{station_id}.pc"

        file_size = 0
        if sfc_file.exists():
            file_size += sfc_file.stat().st_size
            sfc_file.unlink()
        if pc_file.exists():
            file_size += pc_file.stat().st_size
            pc_file.unlink()

        if self._manifest:
            if station_id in self._manifest.entries:
                del self._manifest.entries[station_id]
            self._manifest.total_size = max(0, self._manifest.total_size - file_size)
            self._save_manifest()

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        if not self._manifest:
            return {}

        return {
            "total_size_mb": round(self._manifest.total_size / 1024 / 1024, 2),
            "cached_stations": len(self._manifest.entries),
            "hit_count": self._manifest.hit_count,
            "miss_count": self._manifest.miss_count,
            "hit_rate": round(self._manifest.get_hit_rate() * 100, 2),
            "met_lib_count": len(list(self.met_lib_dir.glob("*.sfc"))),
            "met_cache_count": len(list(self.met_cache_dir.glob("*.sfc"))),
        }

    def get_cached_stations(self) -> List[str]:
        """获取已缓存的站点ID列表"""
        stations = set()

        # met_lib
        for f in self.met_lib_dir.glob("*.sfc"):
            stations.add(f.stem)

        # met_cache
        for f in self.met_cache_dir.glob("*.sfc"):
            stations.add(f.stem)

        return sorted(list(stations))

    def clear_cache(self, keep_lib: bool = True):
        """
        清理缓存

        Args:
            keep_lib: 是否保留 met_lib 目录
        """
        if not keep_lib:
            shutil.rmtree(str(self.met_lib_dir), ignore_errors=True)
            self.met_lib_dir.mkdir(parents=True, exist_ok=True)

        shutil.rmtree(str(self.met_cache_dir), ignore_errors=True)
        self.met_cache_dir.mkdir(parents=True, exist_ok=True)

        if self._manifest:
            self._manifest = MetCacheManifest(cache_dir=str(self.met_cache_dir))
            self._save_manifest()


# 全局实例
_global_cache_manager: Optional[MetCacheManager] = None


def get_met_cache_manager(
    met_lib_dir: str = "",
    met_cache_dir: str = ""
) -> MetCacheManager:
    """获取全局气象缓存管理器"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = MetCacheManager(met_lib_dir, met_cache_dir)
    return _global_cache_manager


def check_met_cache(station_id: str) -> DataStatus:
    """快捷函数：检查站点气象数据是否已缓存"""
    manager = get_met_cache_manager()
    return manager.check_cache(station_id)
