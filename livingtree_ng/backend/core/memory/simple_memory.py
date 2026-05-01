"""
LivingTree NG - 简化版记忆系统
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import time
from datetime import datetime


@dataclass
class MemoryItem:
    """记忆条目"""
    id: str
    content: str
    type: str = "text"  # text, chat
    session_id: Optional[str] = None
    timestamp: float = 0.0
    metadata: Dict = None
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if self.metadata is None:
            self.metadata = {}


class SimpleMemory:
    """
    简化版记忆管理器
    
    功能:
        - 存储和检索对话历史
        - 保存重要信息
        - 按会话ID过滤
    """
    
    def __init__(self, config):
        self.config = config
        self._memory_file = Path(config.paths.data) / "memory.json"
        self._memories: List[MemoryItem] = self._load_memories()
    
    def _load_memories(self) -> List[MemoryItem]:
        """加载记忆"""
        if self._memory_file.exists():
            try:
                with open(self._memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return [MemoryItem(**item) for item in data]
            except:
                pass
        return []
    
    def _save_memories(self):
        """保存记忆"""
        try:
            data = [asdict(item) for item in self._memories]
            with open(self._memory_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def add_memory(self, content: str, memory_type: str = "text", 
                   session_id: Optional[str] = None, 
                   metadata: Optional[Dict] = None) -> str:
        """
        添加记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型
            session_id: 会话ID
            metadata: 元数据
            
        Returns:
            记忆ID
        """
        memory_id = f"mem_{int(time.time() * 1000)}"
        item = MemoryItem(
            id=memory_id,
            content=content,
            type=memory_type,
            session_id=session_id,
            metadata=metadata or {}
        )
        self._memories.append(item)
        self._save_memories()
        return memory_id
    
    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """获取单个记忆"""
        for item in self._memories:
            if item.id == memory_id:
                return item
        return None
    
    def search_memories(self, query: str, 
                        session_id: Optional[str] = None,
                        limit: int = 10) -> List[Dict]:
        """
        搜索记忆
        
        Args:
            query: 查询关键词
            session_id: 可选的会话过滤
            limit: 返回数量限制
            
        Returns:
            匹配的记忆列表
        """
        results = []
        query_lower = query.lower()
        
        for item in reversed(self._memories):  # 从新到旧
            # 会话过滤
            if session_id and item.session_id != session_id:
                continue
            
            # 简单关键词匹配
            if query_lower in item.content.lower():
                results.append({
                    "id": item.id,
                    "content": item.content,
                    "type": item.type,
                    "session_id": item.session_id,
                    "timestamp": item.timestamp,
                    "score": 1.0
                })
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_session_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """
        获取会话历史
        
        Args:
            session_id: 会话ID
            limit: 数量限制
            
        Returns:
            历史记录列表
        """
        history = []
        for item in self._memories:
            if item.session_id == session_id:
                history.append({
                    "id": item.id,
                    "content": item.content,
                    "type": item.type,
                    "timestamp": item.timestamp
                })
        
        # 按时间排序（新的在后）
        history.sort(key=lambda x: x["timestamp"])
        return history[-limit:]
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        for i, item in enumerate(self._memories):
            if item.id == memory_id:
                self._memories.pop(i)
                self._save_memories()
                return True
        return False
    
    def clear_session(self, session_id: str):
        """清除指定会话的所有记忆"""
        self._memories = [
            item for item in self._memories 
            if item.session_id != session_id
        ]
        self._save_memories()
    
    def get_all_sessions(self) -> List[str]:
        """获取所有会话ID列表"""
        sessions = set()
        for item in self._memories:
            if item.session_id:
                sessions.add(item.session_id)
        return sorted(list(sessions))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_memories": len(self._memories),
            "sessions": len(self.get_all_sessions()),
            "memory_file": str(self._memory_file)
        }


# 全局记忆管理器实例（延迟初始化）
_memory_instance = None


def get_memory_manager(config=None) -> SimpleMemory:
    """获取记忆管理器实例"""
    global _memory_instance
    if _memory_instance is None and config is not None:
        _memory_instance = SimpleMemory(config)
    return _memory_instance
