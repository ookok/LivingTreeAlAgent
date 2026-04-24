# -*- coding: utf-8 -*-
"""
冲突解决器 - Conflict Resolver
==============================

功能：
1. 多种冲突解决策略
2. 自动/手动冲突处理
3. 合并算法

Author: Hermes Desktop Team
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .data_types import SyncConflict, ConflictStrategy, SyncRecord

logger = logging.getLogger(__name__)


class ConflictResolver:
    """
    冲突解决器
    
    提供多种冲突解决策略
    """
    
    def __init__(self, default_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS):
        self.default_strategy = default_strategy
        self._custom_resolvers: Dict[str, callable] = {}
    
    def register_resolver(self, data_type: str, resolver: callable):
        """注册自定义解析器"""
        self._custom_resolvers[data_type] = resolver
    
    def resolve(
        self,
        conflict: SyncConflict,
        strategy: Optional[ConflictStrategy] = None
    ) -> Tuple[Dict[str, Any], str]:
        """
        解决冲突
        
        Returns:
            (resolved_data, resolution_type)
        """
        strategy = strategy or conflict.strategy or self.default_strategy
        
        # 检查是否有自定义解析器
        if conflict.record_id in self._custom_resolvers:
            resolver = self._custom_resolvers[conflict.record_id]
            resolved = resolver(conflict)
            return resolved, "custom"
        
        # 根据策略解决
        if strategy == ConflictStrategy.LAST_WRITE_WINS:
            return self._resolve_last_write_wins(conflict), "last_write_wins"
        
        elif strategy == ConflictStrategy.MERGE:
            return self._resolve_merge(conflict), "merge"
        
        elif strategy == ConflictStrategy.KEEP_LOCAL:
            return conflict.local_data, "keep_local"
        
        elif strategy == ConflictStrategy.KEEP_REMOTE:
            return conflict.remote_data, "keep_remote"
        
        elif strategy == ConflictStrategy.USER_CHOICE:
            logger.warning("USER_CHOICE requires manual resolution")
            return conflict.local_data, "keep_local"  # 默认保持本地
        
        return conflict.local_data, "default"
    
    def _resolve_last_write_wins(self, conflict: SyncConflict) -> Dict[str, Any]:
        """最后写入优先"""
        if conflict.remote_updated_at > conflict.local_updated_at:
            logger.info(f"Keeping remote data (newer): {conflict.record_id}")
            return conflict.remote_data
        else:
            logger.info(f"Keeping local data (newer): {conflict.record_id}")
            return conflict.local_data
    
    def _resolve_merge(self, conflict: SyncConflict) -> Dict[str, Any]:
        """智能合并"""
        local = conflict.local_data
        remote = conflict.remote_data
        
        if not isinstance(local, dict) or not isinstance(remote, dict):
            # 非字典类型，使用远程（通常更新）
            return remote
        
        merged = {}
        
        # 合并所有键
        all_keys = set(local.keys()) | set(remote.keys())
        
        for key in all_keys:
            if key not in local:
                merged[key] = remote[key]
            elif key not in remote:
                merged[key] = local[key]
            elif local[key] == remote[key]:
                merged[key] = local[key]  # 相同
            else:
                # 值不同，递归合并
                if isinstance(local[key], dict) and isinstance(remote[key], dict):
                    merged[key] = self._merge_dicts(local[key], remote[key])
                elif isinstance(local[key], list) and isinstance(remote[key], list):
                    merged[key] = self._merge_lists(local[key], remote[key])
                else:
                    # 使用更新的
                    if conflict.remote_updated_at > conflict.local_updated_at:
                        merged[key] = remote[key]
                    else:
                        merged[key] = local[key]
        
        return merged
    
    def _merge_dicts(self, local: Dict, remote: Dict) -> Dict:
        """合并字典"""
        merged = {**local, **remote}
        return merged
    
    def _merge_lists(self, local: List, remote: List) -> List:
        """合并列表 - 去重合并"""
        result = []
        seen = set()
        
        for item in local + remote:
            key = str(item) if not isinstance(item, (str, int, float)) else item
            if key not in seen:
                seen.add(key)
                result.append(item)
        
        return result
    
    def batch_resolve(
        self,
        conflicts: List[SyncConflict],
        strategy: ConflictStrategy
    ) -> Dict[str, Tuple[Dict[str, Any], str]]:
        """批量解决冲突"""
        results = {}
        
        for conflict in conflicts:
            try:
                resolved, resolution_type = self.resolve(conflict, strategy)
                results[conflict.record_id] = (resolved, resolution_type)
            except Exception as e:
                logger.error(f"Failed to resolve conflict {conflict.record_id}: {e}")
                results[conflict.record_id] = (conflict.local_data, "error")
        
        return results
    
    def preview_resolution(
        self,
        conflict: SyncConflict
    ) -> Dict[str, Dict[str, Any]]:
        """预览所有策略的结果"""
        previews = {}
        
        for strategy in ConflictStrategy:
            try:
                result, _ = self.resolve(conflict, strategy)
                previews[strategy.value] = result
            except Exception as e:
                previews[strategy.value] = {"error": str(e)}
        
        return previews


# ── 特定类型的冲突解决器 ──────────────────────────────────────────────────────


class SessionConflictResolver:
    """会话冲突解决器"""
    
    @staticmethod
    def resolve(session_conflict: SyncConflict) -> Dict[str, Any]:
        """解决会话冲突"""
        local = session_conflict.local_data
        remote = session_conflict.remote_data
        
        # 合并消息历史
        local_messages = local.get('messages', [])
        remote_messages = remote.get('messages', [])
        
        # 去重合并
        seen_ids = set()
        merged_messages = []
        
        for msg in remote_messages + local_messages:
            msg_id = msg.get('id', str(msg))
            if msg_id not in seen_ids:
                seen_ids.add(msg_id)
                merged_messages.append(msg)
        
        # 按时间排序
        merged_messages.sort(key=lambda m: m.get('timestamp', ''))
        
        return {
            **local,
            'messages': merged_messages,
            'updated_at': datetime.now().isoformat(),
            '_conflict_resolved': True
        }


class KnowledgeConflictResolver:
    """知识库冲突解决器"""
    
    @staticmethod
    def resolve(knowledge_conflict: SyncConflict) -> Dict[str, Any]:
        """解决知识库冲突"""
        local = knowledge_conflict.local_data
        remote = knowledge_conflict.remote_data
        
        # 知识库使用向量相似度判断优先级
        # 这里简化处理，保留更新的
        if knowledge_conflict.remote_updated_at > knowledge_conflict.local_updated_at:
            return remote
        else:
            return local


class SettingsConflictResolver:
    """设置冲突解决器"""
    
    @staticmethod
    def resolve(settings_conflict: SyncConflict) -> Dict[str, Any]:
        """解决设置冲突 - 保留本地偏好"""
        local = settings_conflict.local_data
        remote = settings_conflict.remote_data
        
        # 设置通常以本地为准，除非远程是新增配置
        merged = {**remote, **local}
        
        return merged
