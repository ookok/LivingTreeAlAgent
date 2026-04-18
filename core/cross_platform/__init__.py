"""
Cross Platform - 跨平台支持模块
==============================

提供三端统一的核心能力:
- Web API 层 (web/web_api.py)
- 移动端自适应布局 (mobile/adaptive_layout.py)
- 平板增强功能 (mobile/tablet_features.py)
- 折叠屏支持 (mobile/foldable_support.py)
- 三端数据同步 (data_sync.py)
- Web/App 迁移工具 (migration_qr.py)
- 设备优化 (device_optimizer.py)
"""

from .data_sync import (
    UniversalDataSync, SyncManager, ConflictResolver,
    SyncSource, ConflictStrategy, DataSnapshot, SyncEvent,
    LocalStorage, P2PStorage
)
from .device_optimizer import (
    DeviceOptimizer, DeviceInfo,
    DEVICE_DETECTION_JS
)
from .migration_qr import (
    MigrationQR, WebToAppMigrator,
    MigrationType, MigrationData,
    MIGRATION_JS
)

__version__ = "1.0.0"

__all__ = [
    # 数据同步
    "UniversalDataSync",
    "SyncManager",
    "ConflictResolver",
    "SyncSource",
    "ConflictStrategy",
    "DataSnapshot",
    "SyncEvent",
    "LocalStorage",
    "P2PStorage",

    # 设备优化
    "DeviceOptimizer",
    "DeviceInfo",
    "DEVICE_DETECTION_JS",

    # 迁移工具
    "MigrationQR",
    "WebToAppMigrator",
    "MigrationType",
    "MigrationData",
    "MIGRATION_JS",
]