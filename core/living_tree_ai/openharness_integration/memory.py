"""OpenHarness 内存系统集成"""

import os
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class MemoryItem:
    """内存项定义"""
    id: str
    content: Any
    timestamp: float
    tags: List[str] = None
    metadata: Dict[str, Any] = None


class MemorySystem:
    """OpenHarness 内存系统"""
    
    def __init__(self, memory_dir: str = "~/.living_tree_ai/openharness/memory"):
        """初始化内存系统"""
        self.memory_dir = os.path.expanduser(memory_dir)
        self.memory: Dict[str, MemoryItem] = {}
        self._ensure_memory_dir()
        self._load_memory()
    
    def _ensure_memory_dir(self):
        """确保内存目录存在"""
        os.makedirs(self.memory_dir, exist_ok=True)
    
    def _load_memory(self):
        """加载内存数据"""
        memory_file = os.path.join(self.memory_dir, "memory.json")
        if os.path.exists(memory_file):
            try:
                with open(memory_file, 'r', encoding='utf-8') as f:
                    memory_data = json.load(f)
                
                for item_id, item_data in memory_data.items():
                    item = MemoryItem(
                        id=item_id,
                        content=item_data["content"],
                        timestamp=item_data["timestamp"],
                        tags=item_data.get("tags", []),
                        metadata=item_data.get("metadata", {})
                    )
                    self.memory[item_id] = item
                
                print(f"[MemorySystem] 加载了 {len(self.memory)} 条内存数据")
            except Exception as e:
                print(f"[MemorySystem] 加载内存失败: {e}")
    
    def save_memory(self):
        """保存内存数据"""
        memory_file = os.path.join(self.memory_dir, "memory.json")
        memory_data = {}
        
        for item_id, item in self.memory.items():
            memory_data[item_id] = {
                "content": item.content,
                "timestamp": item.timestamp,
                "tags": item.tags,
                "metadata": item.metadata
            }
        
        try:
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(memory_data, f, indent=2, ensure_ascii=False)
            print(f"[MemorySystem] 保存了 {len(self.memory)} 条内存数据")
        except Exception as e:
            print(f"[MemorySystem] 保存内存失败: {e}")
    
    def add_memory(self, content: Any, tags: List[str] = None, metadata: Dict[str, Any] = None) -> str:
        """添加内存项"""
        item_id = f"mem_{int(time.time() * 1000)}"
        item = MemoryItem(
            id=item_id,
            content=content,
            timestamp=time.time(),
            tags=tags or [],
            metadata=metadata or {}
        )
        self.memory[item_id] = item
        self.save_memory()
        print(f"[MemorySystem] 添加内存项: {item_id}")
        return item_id
    
    def get_memory(self, item_id: str) -> Optional[MemoryItem]:
        """获取内存项"""
        return self.memory.get(item_id)
    
    def get_all_memory(self) -> List[MemoryItem]:
        """获取所有内存项"""
        return list(self.memory.values())
    
    def search_memory(self, query: str, tags: List[str] = None) -> List[MemoryItem]:
        """搜索内存项"""
        results = []
        
        for item in self.memory.values():
            # 检查内容是否包含查询字符串
            if isinstance(item.content, str) and query in item.content:
                # 检查标签是否匹配
                if tags:
                    if any(tag in (item.tags or []) for tag in tags):
                        results.append(item)
                else:
                    results.append(item)
        
        # 按时间戳排序
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results
    
    def delete_memory(self, item_id: str):
        """删除内存项"""
        if item_id in self.memory:
            del self.memory[item_id]
            self.save_memory()
            print(f"[MemorySystem] 删除内存项: {item_id}")
        else:
            print(f"[MemorySystem] 内存项不存在: {item_id}")
    
    def update_memory(self, item_id: str, content: Any = None, tags: List[str] = None, metadata: Dict[str, Any] = None):
        """更新内存项"""
        if item_id in self.memory:
            item = self.memory[item_id]
            if content is not None:
                item.content = content
            if tags is not None:
                item.tags = tags
            if metadata is not None:
                item.metadata = metadata
            item.timestamp = time.time()
            self.save_memory()
            print(f"[MemorySystem] 更新内存项: {item_id}")
        else:
            print(f"[MemorySystem] 内存项不存在: {item_id}")
    
    def get_memory_by_tags(self, tags: List[str]) -> List[MemoryItem]:
        """根据标签获取内存项"""
        results = []
        for item in self.memory.values():
            if any(tag in (item.tags or []) for tag in tags):
                results.append(item)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results
    
    def clear_memory(self):
        """清空内存"""
        self.memory.clear()
        self.save_memory()
        print("[MemorySystem] 清空内存")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计信息"""
        stats = {
            "total_items": len(self.memory),
            "tags": {},
            "timestamp_range": {
                "min": None,
                "max": None
            }
        }
        
        if self.memory:
            timestamps = [item.timestamp for item in self.memory.values()]
            stats["timestamp_range"]["min"] = min(timestamps)
            stats["timestamp_range"]["max"] = max(timestamps)
        
        # 统计标签
        for item in self.memory.values():
            for tag in (item.tags or []):
                stats["tags"][tag] = stats["tags"].get(tag, 0) + 1
        
        return stats
