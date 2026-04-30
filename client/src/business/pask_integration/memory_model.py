"""
Memory Model - 混合记忆系统

实现 DD-MM-PAS 范式中的 Memory Modeling 组件。

三种记忆类型：
1. Workspace Memory - 工作空间记忆（短期）
2. User Memory - 用户记忆（长期个性化）
3. Global Memory - 全局记忆（共享知识）
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger
import json


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str
    type: str  # fact, preference, context, skill, knowledge
    timestamp: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at and datetime.now() > self.expires_at:
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "type": self.type,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata
        }


class WorkspaceMemory:
    """工作空间记忆 - 存储当前会话的短期上下文"""
    
    def __init__(self, max_size: int = 100):
        self._entries: List[MemoryEntry] = []
        self._max_size = max_size
        self._logger = logger.bind(component="WorkspaceMemory")
    
    def add_entry(self, content: str, entry_type: str = "context", metadata: Optional[Dict[str, Any]] = None):
        """添加记忆条目"""
        entry = MemoryEntry(
            id=self._generate_id(),
            content=content,
            type=entry_type,
            metadata=metadata or {}
        )
        self._entries.append(entry)
        
        # 保持大小限制
        self._trim()
    
    def get_recent_entries(self, count: int = 10) -> List[MemoryEntry]:
        """获取最近的记忆条目"""
        return list(reversed(self._entries[-count:]))
    
    def search(self, query: str) -> List[Tuple[MemoryEntry, float]]:
        """搜索记忆条目"""
        results = []
        query_lower = query.lower()
        
        for entry in self._entries:
            if query_lower in entry.content.lower():
                score = len(query) / len(entry.content)
                results.append((entry, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def clear(self):
        """清空工作空间"""
        self._entries.clear()
        self._logger.debug("工作空间已清空")
    
    def _trim(self):
        """修剪超出大小限制的条目"""
        while len(self._entries) > self._max_size:
            removed = self._entries.pop(0)
            self._logger.debug(f"移除过期工作空间条目: {removed.id}")
    
    def _generate_id(self) -> str:
        import uuid
        return f"ws_{str(uuid.uuid4())[:8]}"
    
    def __len__(self):
        return len(self._entries)


class UserMemory:
    """用户记忆 - 存储用户的长期偏好和历史"""
    
    def __init__(self, user_id: str, max_size: int = 1000, retention_days: int = 365):
        self._user_id = user_id
        self._entries: List[MemoryEntry] = []
        self._max_size = max_size
        self._retention_days = retention_days
        self._logger = logger.bind(component=f"UserMemory.{user_id}")
    
    def add_entry(self, content: str, entry_type: str = "preference", 
                  expires_days: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None):
        """添加用户记忆条目"""
        expires_at = None
        if expires_days:
            expires_at = datetime.now() + timedelta(days=expires_days)
        elif self._retention_days:
            expires_at = datetime.now() + timedelta(days=self._retention_days)
        
        entry = MemoryEntry(
            id=self._generate_id(),
            content=content,
            type=entry_type,
            expires_at=expires_at,
            metadata=metadata or {}
        )
        self._entries.append(entry)
        self._trim()
    
    def get_user_preferences(self) -> List[MemoryEntry]:
        """获取用户偏好"""
        return [e for e in self._entries if e.type == "preference" and not e.is_expired()]
    
    def get_user_history(self, limit: int = 100) -> List[MemoryEntry]:
        """获取用户历史"""
        valid = [e for e in self._entries if not e.is_expired()]
        return sorted(valid, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def search(self, query: str) -> List[Tuple[MemoryEntry, float]]:
        """搜索用户记忆"""
        results = []
        query_lower = query.lower()
        
        for entry in self._entries:
            if not entry.is_expired() and query_lower in entry.content.lower():
                score = len(query) / len(entry.content)
                results.append((entry, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def _trim(self):
        """修剪过期和超出大小限制的条目"""
        # 移除过期条目
        self._entries = [e for e in self._entries if not e.is_expired()]
        
        # 保持大小限制
        while len(self._entries) > self._max_size:
            oldest = min(self._entries, key=lambda x: x.timestamp)
            self._entries.remove(oldest)
            self._logger.debug(f"移除过期用户记忆: {oldest.id}")
    
    def _generate_id(self) -> str:
        import uuid
        return f"user_{self._user_id}_{str(uuid.uuid4())[:8]}"


class GlobalMemory:
    """全局记忆 - 存储共享知识和技能"""
    
    def __init__(self, max_size: int = 10000):
        self._entries: List[MemoryEntry] = []
        self._max_size = max_size
        self._logger = logger.bind(component="GlobalMemory")
    
    def add_entry(self, content: str, entry_type: str = "knowledge", metadata: Optional[Dict[str, Any]] = None):
        """添加全局记忆条目"""
        entry = MemoryEntry(
            id=self._generate_id(),
            content=content,
            type=entry_type,
            metadata=metadata or {}
        )
        self._entries.append(entry)
        self._trim()
    
    def search_knowledge(self, query: str) -> List[Tuple[MemoryEntry, float]]:
        """搜索知识"""
        results = []
        query_lower = query.lower()
        
        for entry in self._entries:
            if query_lower in entry.content.lower():
                score = len(query) / len(entry.content)
                # 根据类型加权
                if entry.type == "knowledge":
                    score *= 1.2
                elif entry.type == "skill":
                    score *= 1.1
                results.append((entry, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:20]
    
    def get_skills(self) -> List[MemoryEntry]:
        """获取所有技能"""
        return [e for e in self._entries if e.type == "skill"]
    
    def _trim(self):
        """修剪超出大小限制的条目"""
        while len(self._entries) > self._max_size:
            oldest = min(self._entries, key=lambda x: x.timestamp)
            self._entries.remove(oldest)
            self._logger.debug(f"移除全局记忆: {oldest.id}")
    
    def _generate_id(self) -> str:
        import uuid
        return f"global_{str(uuid.uuid4())[:8]}"


class HybridMemory:
    """混合记忆系统 - 整合三种记忆类型"""
    
    def __init__(self):
        self._workspace = WorkspaceMemory()
        self._user_memories: Dict[str, UserMemory] = {}
        self._global = GlobalMemory()
        self._active_user_id: Optional[str] = None
        self._logger = logger.bind(component="HybridMemory")
    
    @property
    def workspace(self) -> WorkspaceMemory:
        """获取工作空间记忆"""
        return self._workspace
    
    @property
    def global_memory(self) -> GlobalMemory:
        """获取全局记忆"""
        return self._global
    
    def get_user_memory(self, user_id: str) -> UserMemory:
        """获取用户记忆"""
        if user_id not in self._user_memories:
            self._user_memories[user_id] = UserMemory(user_id)
        return self._user_memories[user_id]
    
    def set_active_user(self, user_id: str):
        """设置活跃用户"""
        self._active_user_id = user_id
        self._logger.debug(f"设置活跃用户: {user_id}")
    
    def search_all(self, query: str) -> List[Tuple[MemoryEntry, float]]:
        """搜索所有记忆"""
        results = []
        
        # 搜索工作空间
        results.extend(self._workspace.search(query))
        
        # 搜索用户记忆
        if self._active_user_id:
            results.extend(self.get_user_memory(self._active_user_id).search(query))
        
        # 搜索全局记忆
        results.extend(self._global.search_knowledge(query))
        
        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:30]
    
    def add_context(self, content: str):
        """添加上下文到工作空间"""
        self._workspace.add_entry(content, "context")
    
    def add_preference(self, content: str):
        """添加用户偏好"""
        if self._active_user_id:
            self.get_user_memory(self._active_user_id).add_entry(content, "preference")
        else:
            self._logger.warning("未设置活跃用户，无法添加偏好")
    
    def add_knowledge(self, content: str):
        """添加全局知识"""
        self._global.add_entry(content, "knowledge")
    
    def clear_workspace(self):
        """清空工作空间"""
        self._workspace.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "workspace_entries": len(self._workspace),
            "user_count": len(self._user_memories),
            "global_entries": len(self._global._entries),
            "active_user": self._active_user_id
        }