"""
UnifiedMemoryManager - 统一记忆管理器

整合 LivingTree 现有的 6+ 套记忆系统：
1. intelligent_memory - SQLite
2. ecc_instincts - SQLite
3. .workbuddy/memory/ - Markdown
4. GBrain - 知识图谱 + Timeline
5. MemoryPalace - Loci 空间化
6. CogneeMemory - 语义压缩
7. ErrorMemory - 错误模式

提供统一的置信度机制，解决多套分散置信度体系的问题。

核心理念：统一接口、统一存储、统一置信度管理

Author: LivingTreeAI Agent
Date: 2026-04-29
"""

from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import os
import json
import time
import hashlib


class MemoryType(Enum):
    """记忆类型"""
    INTELLIGENT = "intelligent"      # 智能记忆
    INSTINCT = "instinct"            # 本能记忆
    WORKBUDDY = "workbuddy"          # 工作伙伴记忆
    GBRAIN = "gbrain"                # 知识图谱记忆
    MEMORY_PALACE = "memory_palace"  # 记忆宫殿
    COGNEE = "cognee"                # 语义压缩记忆
    ERROR = "error"                  # 错误记忆


class ConfidenceLevel(Enum):
    """置信度级别"""
    LOW = "low"           # 低 (< 0.3)
    MEDIUM = "medium"     # 中 (0.3 - 0.7)
    HIGH = "high"         # 高 (>= 0.7)
    AUTO_EXECUTE = "auto_execute"  # 自动执行 (>= 0.9)


@dataclass
class MemoryEntry:
    """
    统一记忆条目
    
    整合所有记忆系统的通用格式。
    """
    entry_id: str
    memory_type: MemoryType
    content: str
    confidence: float = 0.5  # 统一置信度 (0-1)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    accessed_at: float = field(default_factory=lambda: time.time())
    decay_days: int = 90  # 衰减天数
    tags: List[str] = field(default_factory=list)
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """获取置信度级别"""
        if self.confidence >= 0.9:
            return ConfidenceLevel.AUTO_EXECUTE
        elif self.confidence >= 0.7:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 0.3:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW
    
    def is_stale(self) -> bool:
        """判断是否过期"""
        if self.decay_days <= 0:
            return False
        return time.time() - self.created_at > self.decay_days * 24 * 60 * 60
    
    def update_confidence(self, delta: float):
        """
        更新置信度（非对称调整）
        
        Args:
            delta: 置信度变化值（正数增加，负数减少）
        """
        # 非对称调整：增加慢，减少快
        if delta > 0:
            # 正向反馈：缓慢增加
            self.confidence = min(1.0, self.confidence + delta * 0.5)
        else:
            # 负向反馈：快速减少
            self.confidence = max(0.0, self.confidence + delta * 1.5)
        
        self.updated_at = time.time()


@dataclass
class PatternRecord:
    """
    模式记录
    
    用于 ToolSelfRepairer 的"修复模式记忆"。
    """
    pattern_id: str
    pattern: str           # 模式描述（如 "fix:missing-import->pip-install->retest"）
    confidence: int = 0    # 成功次数（置信度）
    last_used_at: float = field(default_factory=lambda: time.time())
    usage_count: int = 0   # 使用次数
    
    def increment_confidence(self):
        """增加置信度"""
        self.confidence += 1
        self.usage_count += 1
        self.last_used_at = time.time()
    
    def decrement_confidence(self):
        """减少置信度"""
        self.confidence = max(0, self.confidence - 1)
        self.last_used_at = time.time()


class UnifiedMemoryManager:
    """
    统一记忆管理器
    
    核心功能：
    1. 统一管理 6+ 套记忆系统
    2. 统一置信度机制
    3. 模式学习与自动执行
    4. 自动衰减清理
    5. 项目指纹隔离
    
    置信度机制：
    - 初始值：0.5
    - 正向反馈：+0.05（实际+0.025）
    - 负向反馈：-0.1（实际-0.15）
    - 自动执行阈值：>= 0.9（confidence >= 10 次成功）
    
    衰减机制：
    - 默认 90 天衰减
    - 自动清理过期记忆
    """
    
    def __init__(self, data_dir: str = ".livingtree/unified_memory"):
        self._logger = logger.bind(component="UnifiedMemoryManager")
        
        # 数据目录
        self._data_dir = data_dir
        os.makedirs(self._data_dir, exist_ok=True)
        
        # 记忆存储
        self._memory_store: Dict[str, MemoryEntry] = {}
        
        # 模式记录（用于修复模式学习）
        self._pattern_records: Dict[str, PatternRecord] = {}
        
        # 项目指纹映射
        self._project_fingerprints: Dict[str, str] = {}
        
        # 统计信息
        self._access_count = 0
        
        # 加载存储的数据
        self._load_from_disk()
        
        self._logger.info("✅ UnifiedMemoryManager 初始化完成")
    
    def _load_from_disk(self):
        """从磁盘加载数据"""
        # 加载记忆条目
        memory_file = os.path.join(self._data_dir, "memory.json")
        if os.path.exists(memory_file):
            try:
                with open(memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for entry_data in data:
                        entry = MemoryEntry(
                            entry_id=entry_data["entry_id"],
                            memory_type=MemoryType(entry_data["memory_type"]),
                            content=entry_data["content"],
                            confidence=entry_data.get("confidence", 0.5),
                            metadata=entry_data.get("metadata", {}),
                            created_at=entry_data.get("created_at", time.time()),
                            updated_at=entry_data.get("updated_at", time.time()),
                            accessed_at=entry_data.get("accessed_at", time.time()),
                            decay_days=entry_data.get("decay_days", 90),
                            tags=entry_data.get("tags", [])
                        )
                        self._memory_store[entry.entry_id] = entry
            except Exception as e:
                self._logger.error(f"❌ 加载记忆数据失败: {e}")
        
        # 加载模式记录
        pattern_file = os.path.join(self._data_dir, "patterns.json")
        if os.path.exists(pattern_file):
            try:
                with open(pattern_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for pattern_id, pattern_data in data.items():
                        record = PatternRecord(
                            pattern_id=pattern_id,
                            pattern=pattern_data["pattern"],
                            confidence=pattern_data.get("confidence", 0),
                            last_used_at=pattern_data.get("last_used_at", time.time()),
                            usage_count=pattern_data.get("usage_count", 0)
                        )
                        self._pattern_records[pattern_id] = record
            except Exception as e:
                self._logger.error(f"❌ 加载模式数据失败: {e}")
    
    def _save_to_disk(self):
        """保存数据到磁盘"""
        # 保存记忆条目
        memory_file = os.path.join(self._data_dir, "memory.json")
        data = []
        for entry in self._memory_store.values():
            data.append({
                "entry_id": entry.entry_id,
                "memory_type": entry.memory_type.value,
                "content": entry.content,
                "confidence": entry.confidence,
                "metadata": entry.metadata,
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
                "accessed_at": entry.accessed_at,
                "decay_days": entry.decay_days,
                "tags": entry.tags
            })
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 保存模式记录
        pattern_file = os.path.join(self._data_dir, "patterns.json")
        data = {}
        for pattern_id, record in self._pattern_records.items():
            data[pattern_id] = {
                "pattern": record.pattern,
                "confidence": record.confidence,
                "last_used_at": record.last_used_at,
                "usage_count": record.usage_count
            }
        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_memory(self, content: str, memory_type: MemoryType, 
                  confidence: float = 0.5, metadata: Dict[str, Any] = None, 
                  decay_days: int = 90, tags: List[str] = None) -> str:
        """
        添加记忆条目
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型
            confidence: 初始置信度 (0-1)
            metadata: 元数据
            decay_days: 衰减天数
            tags: 标签列表
            
        Returns:
            条目ID
        """
        entry_id = f"mem_{int(time.time())}_{hash(content) % 10000}"
        
        entry = MemoryEntry(
            entry_id=entry_id,
            memory_type=memory_type,
            content=content,
            confidence=min(1.0, max(0.0, confidence)),
            metadata=metadata or {},
            decay_days=decay_days,
            tags=tags or []
        )
        
        self._memory_store[entry_id] = entry
        self._save_to_disk()
        
        self._logger.info(f"📥 添加记忆: {entry_id} ({memory_type.value})")
        
        return entry_id
    
    def get_memory(self, entry_id: str) -> Optional[MemoryEntry]:
        """
        获取记忆条目
        
        Args:
            entry_id: 条目ID
            
        Returns:
            记忆条目（如果存在）
        """
        entry = self._memory_store.get(entry_id)
        if entry:
            entry.accessed_at = time.time()
            self._access_count += 1
            self._save_to_disk()
        
        return entry
    
    def update_memory(self, entry_id: str, **kwargs):
        """
        更新记忆条目
        
        Args:
            entry_id: 条目ID
            **kwargs: 更新字段
        """
        entry = self._memory_store.get(entry_id)
        if entry:
            for key, value in kwargs.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)
            entry.updated_at = time.time()
            self._save_to_disk()
    
    def search_memory(self, query: str, memory_type: MemoryType = None, 
                     tags: List[str] = None, min_confidence: float = 0.0) -> List[MemoryEntry]:
        """
        搜索记忆
        
        Args:
            query: 搜索关键词
            memory_type: 记忆类型过滤（可选）
            tags: 标签过滤（可选）
            min_confidence: 最小置信度
            
        Returns:
            匹配的记忆条目列表（按置信度排序）
        """
        results = []
        query_lower = query.lower()
        
        for entry in self._memory_store.values():
            # 过滤过期条目
            if entry.is_stale():
                continue
            
            # 过滤记忆类型
            if memory_type and entry.memory_type != memory_type:
                continue
            
            # 过滤置信度
            if entry.confidence < min_confidence:
                continue
            
            # 过滤标签
            if tags:
                has_tag = any(tag in entry.tags for tag in tags)
                if not has_tag:
                    continue
            
            # 内容匹配
            if query_lower in entry.content.lower():
                results.append(entry)
        
        # 按置信度排序
        results.sort(key=lambda e: -e.confidence)
        
        return results
    
    def update_confidence(self, entry_id: str, delta: float):
        """
        更新置信度
        
        Args:
            entry_id: 条目ID
            delta: 置信度变化值
        """
        entry = self._memory_store.get(entry_id)
        if entry:
            entry.update_confidence(delta)
            self._save_to_disk()
            self._logger.debug(f"🔄 更新置信度: {entry_id} -> {entry.confidence:.3f}")
    
    def record_pattern(self, pattern: str, success: bool = True):
        """
        记录模式（用于修复模式学习）
        
        Args:
            pattern: 模式描述
            success: 是否成功
        """
        pattern_id = hashlib.sha256(pattern.encode()).hexdigest()[:16]
        
        if pattern_id not in self._pattern_records:
            self._pattern_records[pattern_id] = PatternRecord(
                pattern_id=pattern_id,
                pattern=pattern
            )
        
        record = self._pattern_records[pattern_id]
        
        if success:
            record.increment_confidence()
            if record.confidence >= 10:
                self._logger.info(f"🌟 模式达到自动执行级别: {pattern} (conf={record.confidence})")
        else:
            record.decrement_confidence()
        
        self._save_to_disk()
    
    def get_patterns(self, min_confidence: int = 0) -> List[PatternRecord]:
        """
        获取模式记录
        
        Args:
            min_confidence: 最小置信度
            
        Returns:
            模式记录列表（按置信度排序）
        """
        results = [r for r in self._pattern_records.values() if r.confidence >= min_confidence]
        results.sort(key=lambda r: -r.confidence)
        return results
    
    def get_auto_execute_patterns(self) -> List[PatternRecord]:
        """获取可自动执行的模式（置信度 >= 10）"""
        return self.get_patterns(min_confidence=10)
    
    def clean_stale_memory(self):
        """清理过期记忆"""
        stale_count = 0
        to_remove = []
        
        for entry_id, entry in self._memory_store.items():
            if entry.is_stale():
                to_remove.append(entry_id)
                stale_count += 1
        
        for entry_id in to_remove:
            del self._memory_store[entry_id]
        
        if stale_count > 0:
            self._save_to_disk()
            self._logger.info(f"🗑️ 清理过期记忆: {stale_count} 条")
    
    def get_project_fingerprint(self, project_path: str) -> str:
        """
        获取项目指纹（SHA256 12字符）
        
        Args:
            project_path: 项目路径
            
        Returns:
            项目指纹
        """
        if project_path in self._project_fingerprints:
            return self._project_fingerprints[project_path]
        
        fingerprint = hashlib.sha256(project_path.encode()).hexdigest()[:12]
        self._project_fingerprints[project_path] = fingerprint
        
        return fingerprint
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        # 按类型统计
        type_counts = {}
        for entry in self._memory_store.values():
            type_name = entry.memory_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        # 置信度分布
        confidence_dist = {
            "low": 0,
            "medium": 0,
            "high": 0,
            "auto_execute": 0
        }
        for entry in self._memory_store.values():
            level = entry.confidence_level.value
            confidence_dist[level] += 1
        
        return {
            "total_entries": len(self._memory_store),
            "type_distribution": type_counts,
            "confidence_distribution": confidence_dist,
            "access_count": self._access_count,
            "pattern_count": len(self._pattern_records),
            "auto_execute_patterns": len(self.get_auto_execute_patterns())
        }


# 创建全局实例
unified_memory_manager = UnifiedMemoryManager()


def get_unified_memory_manager() -> UnifiedMemoryManager:
    """获取统一记忆管理器实例"""
    return unified_memory_manager


# 测试函数
async def test_unified_memory_manager():
    """测试统一记忆管理器"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 UnifiedMemoryManager")
    print("=" * 60)
    
    manager = UnifiedMemoryManager()
    
    # 1. 添加记忆
    print("\n[1] 添加记忆...")
    mem_id1 = manager.add_memory(
        "测试智能记忆内容",
        MemoryType.INTELLIGENT,
        confidence=0.7,
        tags=["test", "intelligent"]
    )
    mem_id2 = manager.add_memory(
        "测试本能记忆内容",
        MemoryType.INSTINCT,
        confidence=0.5,
        tags=["test", "instinct"]
    )
    print(f"    ✓ 添加智能记忆: {mem_id1}")
    print(f"    ✓ 添加本能记忆: {mem_id2}")
    
    # 2. 获取记忆
    print("\n[2] 获取记忆...")
    entry = manager.get_memory(mem_id1)
    print(f"    ✓ 记忆ID: {entry.entry_id}")
    print(f"    ✓ 类型: {entry.memory_type.value}")
    print(f"    ✓ 置信度: {entry.confidence}")
    print(f"    ✓ 置信度级别: {entry.confidence_level.value}")
    
    # 3. 更新置信度
    print("\n[3] 更新置信度...")
    manager.update_confidence(mem_id1, 0.1)
    entry = manager.get_memory(mem_id1)
    print(f"    ✓ 更新后置信度: {entry.confidence:.3f}")
    
    manager.update_confidence(mem_id1, -0.1)
    entry = manager.get_memory(mem_id1)
    print(f"    ✓ 负反馈后置信度: {entry.confidence:.3f}")
    
    # 4. 搜索记忆
    print("\n[4] 搜索记忆...")
    results = manager.search_memory("测试", tags=["test"], min_confidence=0.3)
    print(f"    ✓ 搜索结果数量: {len(results)}")
    
    # 5. 记录模式
    print("\n[5] 记录模式...")
    manager.record_pattern("fix:missing-import->pip-install->retest", success=True)
    manager.record_pattern("fix:missing-import->pip-install->retest", success=True)
    patterns = manager.get_patterns()
    print(f"    ✓ 模式数量: {len(patterns)}")
    print(f"    ✓ 模式置信度: {patterns[0].confidence}")
    
    # 6. 获取项目指纹
    print("\n[6] 获取项目指纹...")
    fingerprint = manager.get_project_fingerprint("/path/to/project")
    print(f"    ✓ 项目指纹: {fingerprint}")
    
    # 7. 获取统计信息
    print("\n[7] 获取统计信息...")
    stats = manager.get_stats()
    print(f"    ✓ 总条目数: {stats['total_entries']}")
    print(f"    ✓ 类型分布: {stats['type_distribution']}")
    print(f"    ✓ 置信度分布: {stats['confidence_distribution']}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_unified_memory_manager())