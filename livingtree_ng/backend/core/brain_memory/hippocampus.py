"""
海马体模块 - 记忆编码与巩固
借鉴大脑海马体的工作原理
"""

import uuid
import time
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """记忆类型"""
    EPISODIC = "episodic"     # 情景记忆
    SEMANTIC = "semantic"     # 语义记忆
    PROCEDURAL = "procedural" # 程序记忆
    EMOTIONAL = "emotional"   # 情绪记忆


@dataclass
class MemoryTrace:
    """记忆痕迹"""
    memory_id: str
    content: str
    memory_type: MemoryType
    metadata: Dict[str, Any]
    weight: float = 1.0
    creation_time: float = None
    last_access: float = None
    access_count: int = 0
    consolidation_level: float = 0.0
    
    def __post_init__(self):
        if self.creation_time is None:
            self.creation_time = time.time()
        if self.last_access is None:
            self.last_access = self.creation_time
    
    def to_dict(self) -> Dict:
        return {
            'memory_id': self.memory_id,
            'content': self.content,
            'memory_type': self.memory_type.value,
            'metadata': self.metadata,
            'weight': self.weight,
            'creation_time': self.creation_time,
            'last_access': self.last_access,
            'access_count': self.access_count,
            'consolidation_level': self.consolidation_level
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryTrace':
        data['memory_type'] = MemoryType(data['memory_type'])
        return cls(**data)


class Hippocampus:
    """
    海马体 - 快速记忆编码
    负责将新经验编码为短期记忆
    """
    
    def __init__(self, storage_path: str = "data/memory/hippocampus"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._traces: Dict[str, MemoryTrace] = {}
        self._load_traces()
        
        # 记忆索引（用于快速检索）
        self._index: Dict[str, List[str]] = {}
        
    def encode_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        metadata: Optional[Dict] = None
    ) -> str:
        """编码新记忆"""
        memory_id = str(uuid.uuid4())
        metadata = metadata or {}
        
        trace = MemoryTrace(
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            metadata=metadata,
            weight=1.0,
            consolidation_level=0.0
        )
        
        self._traces[memory_id] = trace
        self._save_trace(trace)
        
        # 更新索引
        keywords = self._extract_keywords(content)
        for keyword in keywords:
            if keyword not in self._index:
                self._index[keyword] = []
            if memory_id not in self._index[keyword]:
                self._index[keyword].append(memory_id)
        
        logger.debug(f"Encoded memory: {memory_id}")
        return memory_id
    
    def retrieve_by_cue(self, cue: str) -> List[MemoryTrace]:
        """通过线索检索记忆"""
        # 简单的联想检索
        keywords = self._extract_keywords(cue)
        memory_ids = set()
        
        for keyword in keywords:
            if keyword in self._index:
                memory_ids.update(self._index[keyword])
        
        # 按权重排序
        traces = [self._traces[mid] for mid in memory_ids if mid in self._traces]
        traces.sort(key=lambda t: t.weight, reverse=True)
        
        # 更新访问信息
        for trace in traces:
            trace.access_count += 1
            trace.last_access = time.time()
            trace.weight = min(2.0, trace.weight + 0.05)  # Hebbian学习
        
        return traces
    
    def get_all_memories(self) -> List[Dict]:
        """获取所有记忆（用于UI显示）"""
        return [
            {
                'memory_id': t.memory_id,
                'content': t.content,
                'type': t.memory_type.value,
                'created_at': time.ctime(t.creation_time),
                'weight': t.weight,
                'consolidation_level': t.consolidation_level
            }
            for t in self._traces.values()
        ]
    
    def get_memory(self, memory_id: str) -> Optional[MemoryTrace]:
        """获取单个记忆"""
        return self._traces.get(memory_id)
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id in self._traces:
            del self._traces[memory_id]
            # 删除索引
            for keyword, ids in list(self._index.items()):
                if memory_id in ids:
                    ids.remove(memory_id)
            # 删除文件
            file_path = self.storage_path / f"{memory_id}.json"
            if file_path.exists():
                file_path.unlink()
            logger.info(f"Deleted memory: {memory_id}")
            return True
        return False
    
    def consolidate(self, target_level: float = 0.8) -> int:
        """记忆巩固 - 类似睡眠过程"""
        count = 0
        for trace in self._traces.values():
            if trace.consolidation_level < target_level:
                # 模拟巩固过程
                trace.consolidation_level = min(
                    target_level,
                    trace.consolidation_level + 0.1
                )
                count += 1
                self._save_trace(trace)
                logger.debug(f"Consolidated: {trace.memory_id}")
        
        logger.info(f"Consolidated {count} memories")
        return count
    
    def _extract_keywords(self, content: str) -> List[str]:
        """简单的关键词提取"""
        words = content.lower().split()
        # 简单过滤（实际可用NLP库）
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for', 'this', 'that', 'with'}
        return [w for w in words if w not in stop_words and len(w) > 2]
    
    def _save_trace(self, trace: MemoryTrace):
        """保存记忆痕迹"""
        file_path = self.storage_path / f"{trace.memory_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(trace.to_dict(), f)
    
    def _load_traces(self):
        """加载记忆痕迹"""
        if not self.storage_path.exists():
            return
        
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    trace = MemoryTrace.from_dict(data)
                    self._traces[trace.memory_id] = trace
                    
                    # 重建索引
                    keywords = self._extract_keywords(trace.content)
                    for keyword in keywords:
                        if keyword not in self._index:
                            self._index[keyword] = []
                        if trace.memory_id not in self._index[keyword]:
                            self._index[keyword].append(trace.memory_id)
            except Exception as e:
                logger.error(f"Load trace error: {e}")