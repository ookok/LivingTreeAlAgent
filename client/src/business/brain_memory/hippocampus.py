"""
海马体模块 - 记忆编码与巩固
借鉴大脑海马体的工作原理

功能：
1. 快速记忆编码
2. 联想线索检索
3. Hebbian学习更新权重
4. 记忆巩固模拟
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
    EPISODIC = "episodic"     # 情景记忆 - 个人经历
    SEMANTIC = "semantic"     # 语义记忆 - 事实知识
    PROCEDURAL = "procedural" # 程序记忆 - 技能方法
    EMOTIONAL = "emotional"   # 情绪记忆 - 情感关联
    WORKING = "working"       # 工作记忆 - 当前任务


@dataclass
class MemoryTrace:
    """记忆痕迹 - 海马体中的记忆单元"""
    memory_id: str
    content: str
    memory_type: MemoryType
    metadata: Dict[str, Any]
    weight: float = 1.0
    creation_time: float = None
    last_access: float = None
    access_count: int = 0
    consolidation_level: float = 0.0
    decay_rate: float = 0.01  # 衰减率
    
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
            'consolidation_level': self.consolidation_level,
            'decay_rate': self.decay_rate
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryTrace':
        data['memory_type'] = MemoryType(data['memory_type'])
        return cls(**data)
    
    def decay(self):
        """记忆衰减 - 模拟时间对记忆的影响"""
        elapsed = time.time() - self.last_access
        decay_factor = 1 - (elapsed / 3600) * self.decay_rate
        self.weight = max(0.1, self.weight * decay_factor)


class Hippocampus:
    """
    海马体 - 快速记忆编码与检索中心
    
    主要功能：
    1. 将新经验编码为短期记忆
    2. 通过联想线索检索记忆
    3. Hebbian学习更新权重
    4. 准备记忆进行巩固
    """
    
    def __init__(self, storage_path: str = "data/memory/hippocampus"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._traces: Dict[str, MemoryTrace] = {}
        self._load_traces()
        
        # 记忆索引（用于快速检索）
        self._index: Dict[str, List[str]] = {}
        self._build_index()
        
        # 定期清理过期记忆
        self._cleanup_interval = 3600  # 1小时
        self._last_cleanup = time.time()
    
    def encode_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        metadata: Optional[Dict] = None,
        priority: float = 1.0
    ) -> str:
        """编码新记忆"""
        memory_id = str(uuid.uuid4())
        metadata = metadata or {}
        
        trace = MemoryTrace(
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            metadata=metadata,
            weight=priority,
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
        
        logger.debug(f"Encoded memory: {memory_id} [{memory_type.value}]")
        return memory_id
    
    def retrieve_by_cue(self, cue: str, limit: int = 10) -> List[MemoryTrace]:
        """通过线索检索记忆（联想检索）"""
        # 先进行记忆衰减
        self._apply_decay()
        
        # 提取关键词
        keywords = self._extract_keywords(cue)
        memory_ids = set()
        
        # 多关键词匹配
        for keyword in keywords:
            if keyword in self._index:
                memory_ids.update(self._index[keyword])
        
        # 获取记忆并排序
        traces = [self._traces[mid] for mid in memory_ids if mid in self._traces]
        
        # 计算匹配分数
        scored_traces = []
        for trace in traces:
            score = self._calculate_match_score(trace, cue)
            scored_traces.append((trace, score))
        
        # 按分数排序
        scored_traces.sort(key=lambda x: x[1], reverse=True)
        
        # 更新访问信息（Hebbian学习）
        for trace, _ in scored_traces[:limit]:
            trace.access_count += 1
            trace.last_access = time.time()
            trace.weight = min(2.0, trace.weight + 0.05)  # Hebbian学习增强
            self._save_trace(trace)
        
        return [trace for trace, _ in scored_traces[:limit]]
    
    def retrieve_by_type(self, memory_type: MemoryType, limit: int = 10) -> List[MemoryTrace]:
        """按类型检索记忆"""
        traces = [
            t for t in self._traces.values()
            if t.memory_type == memory_type
        ]
        traces.sort(key=lambda t: t.weight, reverse=True)
        return traces[:limit]
    
    def get_memory(self, memory_id: str) -> Optional[MemoryTrace]:
        """获取单个记忆"""
        return self._traces.get(memory_id)
    
    def update_memory(self, memory_id: str, content: str = None, metadata: Dict = None):
        """更新记忆内容"""
        if memory_id in self._traces:
            trace = self._traces[memory_id]
            if content:
                # 更新索引
                old_keywords = self._extract_keywords(trace.content)
                new_keywords = self._extract_keywords(content)
                
                # 移除旧关键词索引
                for keyword in old_keywords:
                    if keyword in self._index and memory_id in self._index[keyword]:
                        self._index[keyword].remove(memory_id)
                
                trace.content = content
                
                # 添加新关键词索引
                for keyword in new_keywords:
                    if keyword not in self._index:
                        self._index[keyword] = []
                    if memory_id not in self._index[keyword]:
                        self._index[keyword].append(memory_id)
            
            if metadata:
                trace.metadata.update(metadata)
            
            trace.last_access = time.time()
            self._save_trace(trace)
            logger.debug(f"Updated memory: {memory_id}")
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id in self._traces:
            trace = self._traces[memory_id]
            
            # 删除索引
            keywords = self._extract_keywords(trace.content)
            for keyword in keywords:
                if keyword in self._index and memory_id in self._index[keyword]:
                    self._index[keyword].remove(memory_id)
            
            del self._traces[memory_id]
            
            # 删除文件
            file_path = self.storage_path / f"{memory_id}.json"
            if file_path.exists():
                file_path.unlink()
            
            logger.info(f"Deleted memory: {memory_id}")
            return True
        return False
    
    def consolidate(self, target_level: float = 0.8) -> List[str]:
        """
        记忆巩固 - 类似睡眠过程
        返回需要转移到新皮层的记忆ID列表
        """
        consolidated_ids = []
        for trace in self._traces.values():
            if trace.consolidation_level < target_level:
                # 模拟巩固过程（基于访问频率）
                consolidation_rate = 0.1 + (trace.access_count * 0.02)
                trace.consolidation_level = min(
                    target_level,
                    trace.consolidation_level + consolidation_rate
                )
                self._save_trace(trace)
                logger.debug(f"Consolidated: {trace.memory_id} -> {trace.consolidation_level:.2f}")
                
                # 完全巩固的记忆可以转移到新皮层
                if trace.consolidation_level >= target_level:
                    consolidated_ids.append(trace.memory_id)
        
        logger.info(f"Consolidated {len(consolidated_ids)} memories")
        return consolidated_ids
    
    def get_all_memories(self) -> List[Dict]:
        """获取所有记忆（用于UI显示）"""
        return [
            {
                'memory_id': t.memory_id,
                'content': t.content[:100] + "..." if len(t.content) > 100 else t.content,
                'type': t.memory_type.value,
                'created_at': time.ctime(t.creation_time),
                'weight': round(t.weight, 2),
                'consolidation_level': round(t.consolidation_level, 2),
                'access_count': t.access_count
            }
            for t in self._traces.values()
        ]
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        by_type = {}
        for t in self._traces.values():
            type_name = t.memory_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1
        
        return {
            'total_memories': len(self._traces),
            'by_type': by_type,
            'avg_weight': sum(t.weight for t in self._traces.values()) / len(self._traces) if self._traces else 0,
            'avg_consolidation': sum(t.consolidation_level for t in self._traces.values()) / len(self._traces) if self._traces else 0
        }
    
    def _calculate_match_score(self, trace: MemoryTrace, cue: str) -> float:
        """计算记忆与线索的匹配分数"""
        score = 0.0
        cue_lower = cue.lower()
        content_lower = trace.content.lower()
        
        # 内容匹配
        if cue_lower in content_lower:
            score += 0.5
        
        # 关键词匹配
        cue_keywords = set(self._extract_keywords(cue))
        content_keywords = set(self._extract_keywords(trace.content))
        overlap = cue_keywords.intersection(content_keywords)
        if overlap:
            score += len(overlap) / len(cue_keywords) * 0.3
        
        # 权重因素
        score += trace.weight * 0.2
        
        return score
    
    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        words = content.lower().split()
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for', 'this', 'that', 'with', 'and', 'or', 'but', 'not', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must'}
        return [w for w in words if w not in stop_words and len(w) > 2]
    
    def _apply_decay(self):
        """应用记忆衰减"""
        for trace in self._traces.values():
            trace.decay()
    
    def _cleanup_expired(self):
        """清理过期记忆（权重过低的）"""
        current_time = time.time()
        if current_time - self._last_cleanup >= self._cleanup_interval:
            expired_ids = [
                mid for mid, trace in self._traces.items()
                if trace.weight < 0.1 and current_time - trace.last_access > 86400  # 24小时未访问
            ]
            for mid in expired_ids:
                self.delete_memory(mid)
            self._last_cleanup = current_time
    
    def _build_index(self):
        """重建索引"""
        self._index.clear()
        for trace in self._traces.values():
            keywords = self._extract_keywords(trace.content)
            for keyword in keywords:
                if keyword not in self._index:
                    self._index[keyword] = []
                if trace.memory_id not in self._index[keyword]:
                    self._index[keyword].append(trace.memory_id)
    
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
            except Exception as e:
                logger.error(f"Load trace error: {e}")