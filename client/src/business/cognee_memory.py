#!/usr/bin/env python3
"""
记忆系统 - 参考 Cognee 风格设计
支持语义记忆、情景记忆、工作记忆的统一管理
"""

import hashlib
import json
import time
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class MemoryType(Enum):
    """记忆类型"""
    SEMANTIC = "semantic"       # 语义记忆 - 事实、概念、知识
    EPISODIC = "episodic"       # 情景记忆 - 事件、经历
    WORKING = "working"          # 工作记忆 - 当前任务相关信息
    PROCEDURAL = "procedural"    # 程序记忆 - 技能、习惯


class MemoryImportance(Enum):
    """记忆重要性"""
    CRITICAL = 5   # 关键信息
    HIGH = 4       # 重要
    MEDIUM = 3     # 一般
    LOW = 2        # 次要
    TRIVIAL = 1    # 琐碎


@dataclass
class Memory:
    """记忆单元"""
    memory_id: str
    content: str
    memory_type: MemoryType
    importance: MemoryImportance
    embedding: Optional[List[float]] = None  # 简化为列表
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    decay_score: float = 1.0  # 衰减分数
    tags: List[str] = field(default_factory=list)
    source: str = "unknown"  # 来源
    session_id: Optional[str] = None
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "importance": self.importance.value,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "tags": self.tags,
            "source": self.source,
            "session_id": self.session_id,
            "user_id": self.user_id,
        }


class CogneeMemoryStore:
    """
    Cognee 风格记忆存储

    特性:
    1. 多层次记忆结构 - 语义/情景/工作/程序记忆
    2. 自动重要性评估
    3. 记忆衰减机制
    4. 语义相似度搜索
    5. 记忆固化与遗忘
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self._memories: Dict[str, Memory] = {}
        self._semantic_index: Dict[str, List[str]] = {}  # tag -> memory_ids
        self._session_memories: Dict[str, List[str]] = {}  # session_id -> memory_ids
        self._user_memories: Dict[str, List[str]] = {}  # user_id -> memory_ids
        self._embedding_func: Optional[Callable] = None
        self._next_id = 1

    def set_embedding_func(self, func: Callable[[str], List[float]]):
        """设置嵌入函数"""
        self._embedding_func = func

    def add(
        self,
        content: str,
        memory_type: MemoryType,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
        session_id: str = None,
        user_id: str = None,
        source: str = "unknown",
    ) -> str:
        """添加记忆"""
        memory_id = f"mem_{self._next_id:08d}"
        self._next_id += 1

        memory = Memory(
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
            session_id=session_id,
            user_id=user_id,
            source=source,
        )

        if self._embedding_func and content:
            try:
                memory.embedding = self._embedding_func(content)
            except Exception:
                memory.embedding = None

        self._memories[memory_id] = memory

        for tag in memory.tags:
            if tag not in self._semantic_index:
                self._semantic_index[tag] = []
            self._semantic_index[tag].append(memory_id)

        if session_id:
            if session_id not in self._session_memories:
                self._session_memories[session_id] = []
            self._session_memories[session_id].append(memory_id)

        if user_id:
            if user_id not in self._user_memories:
                self._user_memories[user_id] = []
            self._user_memories[user_id].append(memory_id)

        return memory_id

    def get(self, memory_id: str) -> Optional[Memory]:
        """获取记忆"""
        memory = self._memories.get(memory_id)
        if memory:
            memory.accessed_at = datetime.now()
            memory.access_count += 1
        return memory

    def recall(
        self,
        query: str,
        memory_type: MemoryType = None,
        limit: int = 10,
        min_importance: MemoryImportance = MemoryImportance.LOW,
    ) -> List[Memory]:
        """回忆 - 基于内容和类型搜索"""
        results = []

        if self._embedding_func and query:
            try:
                query_embedding = self._embedding_func(query)
            except Exception:
                query_embedding = None
            for memory in self._memories.values():
                if memory_type and memory.memory_type != memory_type:
                    continue
                if memory.importance.value < min_importance.value:
                    continue
                if memory.embedding is not None:
                    similarity = self._cosine_similarity(query_embedding, memory.embedding)
                    if similarity > 0.5:
                        results.append((memory, similarity))
        else:
            query_lower = query.lower()
            for memory in self._memories.values():
                if memory_type and memory.memory_type != memory_type:
                    continue
                if memory.importance.value < min_importance.value:
                    continue
                if query_lower in memory.content.lower():
                    results.append((memory, 1.0))

        results.sort(key=lambda x: (x[0].importance.value, x[1]), reverse=True)
        return [m for m, _ in results[:limit]]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if not a or not b:
            return 0.0
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def get_session_memories(self, session_id: str) -> List[Memory]:
        """获取会话相关的记忆"""
        memory_ids = self._session_memories.get(session_id, [])
        return [self._memories[mid] for mid in memory_ids if mid in self._memories]

    def get_user_memories(
        self,
        user_id: str,
        memory_type: MemoryType = None,
    ) -> List[Memory]:
        """获取用户的所有记忆"""
        memory_ids = self._user_memories.get(user_id, [])
        memories = [self._memories[mid] for mid in memory_ids if mid in self._memories]
        if memory_type:
            memories = [m for m in memories if m.memory_type == memory_type]
        return memories

    def consolidate(self) -> int:
        """
        记忆整合 - 将工作记忆中的重要信息固化为长期记忆
        减少不重要记忆的衰减分数
        """
        consolidated = 0
        for memory in self._memories.values():
            if memory.memory_type == MemoryType.WORKING:
                if memory.importance.value >= MemoryImportance.MEDIUM.value:
                    memory.memory_type = MemoryType.SEMANTIC
                    consolidated += 1
            memory.decay_score *= 0.95

        return consolidated

    def forget(self, threshold: float = 0.1) -> int:
        """
        遗忘 - 删除衰减分数过低的记忆
        """
        to_forget = [
            mid
            for mid, mem in self._memories.items()
            if mem.decay_score < threshold and mem.importance.value < MemoryImportance.HIGH.value
        ]

        for mid in to_forget:
            del self._memories[mid]

        return len(to_forget)

    def stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        type_counts = {}
        for mtype in MemoryType:
            type_counts[mtype.value] = len(
                [m for m in self._memories.values() if m.memory_type == mtype]
            )

        return {
            "total": len(self._memories),
            "by_type": type_counts,
            "total_tags": len(self._semantic_index),
            "active_sessions": len(self._session_memories),
        }


class CogneeMemoryAPI:
    """
    Cognee 风格的记忆 API

    提供 remember/recall/forget/improve 接口
    """

    def __init__(self, store: CogneeMemoryStore = None):
        self._store = store or CogneeMemoryStore()
        self._event_handlers: Dict[str, List[Callable]] = {
            "remember": [],
            "recall": [],
            "forget": [],
            "improve": [],
        }

    def remember(
        self,
        content: str,
        memory_type: str = "semantic",
        importance: str = "medium",
        **kwargs
    ) -> str:
        """
        记住信息

        Args:
            content: 要记忆的内容
            memory_type: 记忆类型 (semantic/episodic/working/procedural)
            importance: 重要性 (critical/high/medium/low/trivial)
            **kwargs: 其他参数 (tags, session_id, user_id, source)

        Returns:
            memory_id: 记忆ID
        """
        mem_type = MemoryType(memory_type)
        imp = MemoryImportance[importance.upper()]

        memory_id = self._store.add(
            content=content,
            memory_type=mem_type,
            importance=imp,
            **kwargs
        )

        self._trigger_event("remember", memory_id, content)

        return memory_id

    def recall(
        self,
        query: str,
        memory_type: str = None,
        limit: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        回忆信息

        Args:
            query: 查询内容
            memory_type: 记忆类型过滤
            limit: 返回数量

        Returns:
            记忆列表
        """
        mtype = MemoryType(memory_type) if memory_type else None

        memories = self._store.recall(
            query=query,
            memory_type=mtype,
            limit=limit,
            **kwargs
        )

        self._trigger_event("recall", query, memories)

        return [m.to_dict() for m in memories]

    def forget(self, memory_id: str = None, older_than_days: int = None) -> int:
        """
        遗忘信息

        Args:
            memory_id: 要遗忘的记忆ID
            older_than_days: 遗忘多少天前的记忆

        Returns:
            遗忘的记忆数量
        """
        if memory_id:
            if memory_id in self._store._memories:
                del self._store._memories[memory_id]
                self._trigger_event("forget", memory_id)
                return 1
            return 0

        if older_than_days:
            cutoff = datetime.now().timestamp() - older_than_days * 86400
            to_forget = [
                mid
                for mid, mem in self._store._memories.items()
                if mem.created_at.timestamp() < cutoff
                and mem.importance.value < MemoryImportance.HIGH.value
            ]
            for mid in to_forget:
                del self._store._memories[mid]
            self._trigger_event("forget", len(to_forget), older_than_days)
            return len(to_forget)

        return 0

    def improve(self, memory_id: str, new_content: str = None, delta_importance: int = None) -> bool:
        """
        改进记忆

        Args:
            memory_id: 记忆ID
            new_content: 更新后的内容
            delta_importance: 重要性变化 (+/-)

        Returns:
            是否成功
        """
        memory = self._store.get(memory_id)
        if not memory:
            return False

        if new_content:
            memory.content = new_content
            if self._store._embedding_func:
                memory.embedding = self._store._embedding_func(new_content)

        if delta_importance:
            new_val = max(1, min(5, memory.importance.value + delta_importance))
            memory.importance = MemoryImportance(new_val)

        memory.access_count += 1
        self._trigger_event("improve", memory_id, new_content, delta_importance)

        return True

    def register_handler(self, event: str, handler: Callable):
        """注册事件处理器"""
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def _trigger_event(self, event: str, *args, **kwargs):
        """触发事件"""
        for handler in self._event_handlers.get(event, []):
            try:
                handler(*args, **kwargs)
            except Exception as e:
                print(f"Event handler error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._store.stats()

    def set_embedding_model(self, embedding_func: Callable):
        """设置嵌入模型"""
        self._store.set_embedding_func(embedding_func)


def test_cognee_memory():
    """测试 Cognee 记忆系统"""
    print("=== 测试 Cognee 记忆系统 ===")

    api = CogneeMemoryAPI()

    print("\n1. 测试记住信息")
    memory_id1 = api.remember(
        content="Python 是一种高级编程语言",
        memory_type="semantic",
        importance="high",
        tags=["programming", "language"],
        source="user_input"
    )
    print(f"  记住: {memory_id1}")

    memory_id2 = api.remember(
        content="用户喜欢使用暗色主题",
        memory_type="episodic",
        importance="medium",
        tags=["preference", "ui"],
        source="interaction"
    )
    print(f"  记住: {memory_id2}")

    print("\n2. 测试回忆")
    results = api.recall("Python", limit=5)
    print(f"  查询 'Python': 找到 {len(results)} 条记忆")
    for r in results:
        print(f"    - {r['content'][:50]}... [{r['memory_type']}]")

    print("\n3. 测试改进记忆")
    success = api.improve(memory_id1, delta_importance=1)
    print(f"  改进成功: {success}")

    print("\n4. 测试统计")
    stats = api.get_stats()
    print(f"  统计: {stats}")

    print("\n5. 测试遗忘")
    forgotten = api.forget(memory_id=memory_id2)
    print(f"  遗忘: {forgotten} 条")

    print("\nCognee 记忆系统测试完成！")


if __name__ == "__main__":
    test_cognee_memory()