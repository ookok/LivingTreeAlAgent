"""
数据同步管理器

负责数据的同步和一致性，处理版本控制和增量同步
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional, List

from .models import CDNData, DataVersion, DataMetadata

logger = logging.getLogger(__name__)


class DataSyncManager:
    """
    数据同步管理器
    负责数据的同步和一致性，处理版本控制和增量同步
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.pending_syncs: Dict[str, DataVersion] = {}
        self.sync_history: Dict[str, List[DataVersion]] = {}
    
    async def sync_data(self, data_id: str, version: int, source_node: str) -> bool:
        """
        同步数据
        
        Args:
            data_id: 数据 ID
            version: 版本号
            source_node: 源节点 ID
            
        Returns:
            是否同步成功
        """
        logger.info(f"Syncing data {data_id} version {version} from node {source_node}")
        
        # 这里需要实现与源节点的通信，获取数据
        # 实际项目中需要通过 P2P 网络获取数据
        
        # 模拟同步过程
        await asyncio.sleep(1)
        
        # 记录同步历史
        data_version = DataVersion(
            data_id=data_id,
            version=version,
            created_at=time.time(),
            node_id=source_node
        )
        
        if data_id not in self.sync_history:
            self.sync_history[data_id] = []
        self.sync_history[data_id].append(data_version)
        
        # 移除待同步项
        if data_id in self.pending_syncs:
            del self.pending_syncs[data_id]
        
        logger.info(f"Synced data {data_id} version {version} from node {source_node}")
        return True
    
    def add_pending_sync(self, data_id: str, version: int, source_node: str):
        """
        添加待同步项
        
        Args:
            data_id: 数据 ID
            version: 版本号
            source_node: 源节点 ID
        """
        data_version = DataVersion(
            data_id=data_id,
            version=version,
            created_at=time.time(),
            node_id=source_node
        )
        self.pending_syncs[data_id] = data_version
        logger.debug(f"Added pending sync for data {data_id} version {version} from node {source_node}")
    
    async def process_pending_syncs(self):
        """
        处理待同步项
        """
        pending = list(self.pending_syncs.items())
        for data_id, data_version in pending:
            try:
                await self.sync_data(
                    data_id,
                    data_version.version,
                    data_version.node_id
                )
            except Exception as e:
                logger.error(f"Failed to sync data {data_id}: {e}")
    
    def get_sync_history(self, data_id: str) -> List[DataVersion]:
        """
        获取同步历史
        
        Args:
            data_id: 数据 ID
            
        Returns:
            同步历史列表
        """
        return self.sync_history.get(data_id, [])
    
    def get_pending_syncs(self) -> Dict[str, DataVersion]:
        """
        获取待同步项
        
        Returns:
            待同步项字典
        """
        return self.pending_syncs
    
    def has_pending_syncs(self) -> bool:
        """
        是否有待同步项
        
        Returns:
            是否有待同步项
        """
        return len(self.pending_syncs) > 0
    
    async def resolve_conflict(self, data_id: str, versions: List[DataVersion]) -> Optional[DataVersion]:
        """
        解决冲突
        
        Args:
            data_id: 数据 ID
            versions: 冲突的版本列表
            
        Returns:
            解决后的版本
        """
        if not versions:
            return None
        
        # 简单的冲突解决策略：选择最新的版本
        latest_version = max(versions, key=lambda x: x.version)
        logger.info(f"Resolved conflict for data {data_id}, selected version {latest_version.version}")
        
        return latest_version
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取同步统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "pending_syncs_count": len(self.pending_syncs),
            "sync_history_count": sum(len(history) for history in self.sync_history.values()),
            "node_id": self.node_id
        }
