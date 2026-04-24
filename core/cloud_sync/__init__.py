# -*- coding: utf-8 -*-
"""
跨平台同步模块 - Cloud Sync Module
===================================

功能：
1. 用户数据跨设备同步
2. 会话历史云端备份
3. 知识库多端一致
4. 配置偏好同步

架构：
- WebSocket 长连接实时同步
- SQLite 本地存储 + 云端同步
- 冲突解决策略（最后写入优先/用户选择）
- 增量同步优化

Author: Hermes Desktop Team
"""

from .sync_client import SyncClient, SyncConfig
from .conflict_resolver import ConflictResolver, ConflictStrategy
from .data_types import SyncData, SyncRecord, SyncStatus
from .sync_server import SyncServer

__all__ = [
    'SyncClient',
    'SyncConfig', 
    'ConflictResolver',
    'ConflictStrategy',
    'SyncData',
    'SyncRecord',
    'SyncStatus',
    'SyncServer',
]
