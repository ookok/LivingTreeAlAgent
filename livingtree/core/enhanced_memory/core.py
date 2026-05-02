"""
记忆核心 (Memory Core)

三层记忆架构：
- 工作记忆 (Working Memory) - 当前上下文，容量有限
- 短期记忆 (Short-term Memory) - 近期交互历史
- 长期记忆 (Long-term Memory) - 持久化知识和经验
"""

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class MemoryType(Enum):
    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


@dataclass
class MemoryEntry:
    entry_id: str
    content: str
    memory_type: MemoryType = MemoryType.WORKING
    timestamp: float = field(default_factory=time.time)
    importance: float = 1.0
    access_count: int = 0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_context(self) -> str:
        return f"[{self.memory_type.value}] {self.content[:300]}"


class MemoryCore:
    """三层记忆系统核心"""

    WORKING_MEMORY_CAPACITY = 10
    SHORT_TERM_CAPACITY = 100

    def __init__(self):
        self._working_memory: List[MemoryEntry] = []
        self._short_term_memory: List[MemoryEntry] = []
        self._long_term_memory: Dict[str, MemoryEntry] = {}
        self._importance_threshold = 0.5

    def add(self, content: str, memory_type: MemoryType = MemoryType.WORKING,
            importance: float = None, tags: List[str] = None) -> str:
        if importance is None:
            importance = self._estimate_importance(content)

        entry_id = f"mem_{uuid.uuid4().hex[:8]}"
        entry = MemoryEntry(
            entry_id=entry_id, content=content,
            memory_type=memory_type, importance=importance,
            tags=tags or [])

        if memory_type == MemoryType.WORKING:
            self._working_memory.append(entry)
            self._trim_working_memory()
        elif memory_type == MemoryType.SHORT_TERM:
            self._short_term_memory.append(entry)
            self._trim_short_term_memory()
        elif memory_type in (MemoryType.LONG_TERM, MemoryType.EPISODIC,
                            MemoryType.SEMANTIC):
            self._long_term_memory[entry_id] = entry

        return entry_id

    def recall(self, query: str, top_k: int = 5,
               memory_types: List[MemoryType] = None) -> List[MemoryEntry]:
        results = []

        all_entries = []
        if memory_types is None or MemoryType.WORKING in memory_types:
            all_entries.extend(
                (e, 10) for e in self._working_memory)
        if memory_types is None or MemoryType.SHORT_TERM in memory_types:
            all_entries.extend(
                (e, 5) for e in self._short_term_memory)
        if memory_types is None or MemoryType.LONG_TERM in memory_types:
            all_entries.extend(
                (e, 3) for e in self._long_term_memory.values())

        query_lower = query.lower()
        scored = []
        for entry, type_weight in all_entries:
            score = type_weight * entry.importance
            content_lower = entry.content.lower()
            if query_lower in content_lower:
                score += 5
            query_words = set(query_lower.split())
            content_words = set(content_lower.split())
            overlap = query_words & content_words
            score += len(overlap) * 2
            for tag in entry.tags:
                if query_lower in tag.lower():
                    score += 3
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: -x[0])
        results = [entry for _, entry in scored[:top_k]]

        for entry in results:
            entry.access_count += 1

        return results

    def build_context(self, query: str,
                      max_entries: int = 5) -> str:
        entries = self.recall(query, top_k=max_entries)
        if not entries:
            return ""

        context = "=== 相关记忆 ===\n"
        for i, entry in enumerate(entries, 1):
            context += f"{i}. {entry.to_context()}\n"

        return context

    def consolidate(self):
        """将工作记忆中的重要信息转移到短期/长期记忆"""
        for entry in self._working_memory[:]:
            if entry.importance > self._importance_threshold:
                entry.memory_type = MemoryType.SHORT_TERM
                self._working_memory.remove(entry)
                self._short_term_memory.append(entry)

        self._trim_short_term_memory()

        for entry in self._short_term_memory[:]:
            if entry.importance > 0.8 and entry.access_count > 3:
                entry.memory_type = MemoryType.LONG_TERM
                self._short_term_memory.remove(entry)
                self._long_term_memory[entry.entry_id] = entry

    def _trim_working_memory(self):
        if len(self._working_memory) > self.WORKING_MEMORY_CAPACITY:
            self._working_memory.sort(key=lambda e: -e.importance)
            overflow = self._working_memory[self.WORKING_MEMORY_CAPACITY:]
            self._working_memory = self._working_memory[:self.WORKING_MEMORY_CAPACITY]
            for entry in overflow:
                if entry.importance > 0.7:
                    entry.memory_type = MemoryType.SHORT_TERM
                    self._short_term_memory.append(entry)

    def _trim_short_term_memory(self):
        if len(self._short_term_memory) > self.SHORT_TERM_CAPACITY:
            self._short_term_memory.sort(
                key=lambda e: (e.importance, e.timestamp), reverse=True)
            overflow = self._short_term_memory[self.SHORT_TERM_CAPACITY:]
            self._short_term_memory = self._short_term_memory[:self.SHORT_TERM_CAPACITY]
            for entry in overflow:
                if entry.importance > 0.9:
                    entry.memory_type = MemoryType.LONG_TERM
                    self._long_term_memory[entry.entry_id] = entry

    def _estimate_importance(self, content: str) -> float:
        importance_signals = {
            "重要": 0.3, "关键": 0.3, "紧急": 0.3,
            "记住": 0.2, "记录": 0.2, "核心": 0.2,
            "?" : 0.1, "!" : 0.1,
        }
        score = 0.3
        content_lower = content.lower()
        for signal, weight in importance_signals.items():
            if signal.lower() in content_lower:
                score += weight
        score += min(0.2, len(content) / 2000 * 0.2)
        return min(1.0, score)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "working_memory": len(self._working_memory),
            "short_term_memory": len(self._short_term_memory),
            "long_term_memory": len(self._long_term_memory),
            "total": (len(self._working_memory)
                      + len(self._short_term_memory)
                      + len(self._long_term_memory)),
        }


__all__ = ["MemoryType", "MemoryEntry", "MemoryCore"]
