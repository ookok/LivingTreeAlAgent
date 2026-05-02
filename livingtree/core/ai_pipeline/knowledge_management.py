"""
知识管理模块 (Knowledge Management)

上下文知识管理：
- 知识条目创建和检索
- 知识库持久化
- 智能上下文拼接
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class KnowledgeType(Enum):
    FACT = "fact"
    CONCEPT = "concept"
    RULE = "rule"
    EXAMPLE = "example"
    CODE_SNIPPET = "code_snippet"
    DOCUMENT = "document"


@dataclass
class KnowledgeItem:
    item_id: str
    title: str
    content: str
    knowledge_type: KnowledgeType = KnowledgeType.FACT
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.item_id, "title": self.title,
            "content": self.content[:500],
            "type": self.knowledge_type.value,
            "tags": self.tags, "access_count": self.access_count}


class KnowledgeManager:

    def __init__(self):
        self._items: Dict[str, KnowledgeItem] = {}

    def add_item(self, title: str, content: str,
                 knowledge_type: KnowledgeType = KnowledgeType.FACT,
                 tags: List[str] = None) -> str:
        item_id = hashlib.md5(
            f"{title}:{content[:100]}".encode()).hexdigest()[:12]

        item = KnowledgeItem(
            item_id=item_id, title=title, content=content,
            knowledge_type=knowledge_type,
            tags=tags or [])
        self._items[item_id] = item
        return item_id

    def get_item(self, item_id: str) -> Optional[KnowledgeItem]:
        item = self._items.get(item_id)
        if item:
            item.access_count += 1
        return item

    def search(self, query: str, top_k: int = 5) -> List[KnowledgeItem]:
        query_lower = query.lower()
        results = []

        for item in self._items.values():
            score = 0
            if query_lower in item.title.lower():
                score += 3
            if query_lower in item.content.lower():
                score += 1
            for tag in item.tags:
                if query_lower in tag.lower():
                    score += 2
            if score > 0:
                results.append((score, item.access_count, item))

        results.sort(key=lambda x: (-x[0], -x[1]))
        return [r[2] for r in results[:top_k]]

    def get_context_for_query(self, query: str,
                              max_tokens: int = 2000) -> str:
        items = self.search(query, top_k=3)
        if not items:
            return ""

        context_parts = []
        total_chars = 0
        for item in items:
            snippet = f"【{item.title}】\n{item.content[:300]}\n"
            if total_chars + len(snippet) > max_tokens:
                break
            context_parts.append(snippet)
            total_chars += len(snippet)

        return "\n".join(context_parts)

    def export_items(self) -> List[dict]:
        return [item.to_dict() for item in self._items.values()]

    def get_stats(self) -> Dict[str, int]:
        type_counts = {}
        for item in self._items.values():
            t = item.knowledge_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        return {"total_items": len(self._items), **type_counts}


__all__ = ["KnowledgeType", "KnowledgeItem", "KnowledgeManager"]
