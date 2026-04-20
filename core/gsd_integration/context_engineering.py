"""
上下文工程模块

GSD 的核心模块，解决 context rot 问题：
- 上下文范围管理
- 上下文压缩
- 多级上下文存储
- 上下文质量保证
"""

import re
import time
from typing import List, Dict, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json


class ContextLevel(Enum):
    """上下文级别"""
    GLOBAL = "global"      # 全局项目上下文
    PHASE = "phase"       # 阶段上下文
    TASK = "task"         # 任务上下文
    SESSION = "session"   # 会话上下文


class ContextScope(Enum):
    """上下文范围"""
    PROJECT = "project"
    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    DEPLOYMENT = "deployment"


@dataclass
class ContextChunk:
    """上下文块"""
    chunk_id: str
    content: str
    scope: ContextScope
    priority: float = 1.0
    tokens: int = 0
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.tokens == 0:
            self.tokens = self._estimate_tokens()

    def _estimate_tokens(self) -> int:
        """估算 token 数量（中英文混合）"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', self.content))
        english_words = len(re.findall(r'[a-zA-Z]+', self.content))
        return int(chinese_chars * 1.5 + english_words * 0.25)


@dataclass
class ContextDocument:
    """上下文文档"""
    doc_id: str
    title: str
    scope: ContextScope
    chunks: List[ContextChunk] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return sum(c.tokens for c in self.chunks)

    @property
    def total_chars(self) -> int:
        return sum(len(c.content) for c in self.chunks)


class ContextManager:
    """
    上下文管理器

    核心功能：
    1. 多级上下文存储
    2. 智能上下文压缩
    3. 上下文范围管理
    4. 上下文质量追踪
    """

    MAX_CONTEXT_TOKENS = 200000
    WARNING_THRESHOLD = 160000
    CRITICAL_THRESHOLD = 180000

    def __init__(self):
        self.documents: Dict[str, ContextDocument] = {}
        self.global_chunks: List[ContextChunk] = []
        self.session_chunks: List[ContextChunk] = []
        self.current_scope: ContextScope = ContextScope.PROJECT
        self._access_order: List[str] = []

    def add_document(
        self,
        doc_id: str,
        title: str,
        content: str,
        scope: ContextScope,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = 4000,
        overlap: int = 200
    ) -> ContextDocument:
        """
        添加上下文文档

        Args:
            doc_id: 文档 ID
            title: 文档标题
            content: 文档内容
            scope: 上下文范围
            metadata: 元数据
            chunk_size: 块大小（字符）
            overlap: 重叠大小

        Returns:
            ContextDocument: 创建的文档
        """
        chunks = self._chunk_content(content, chunk_size, overlap)

        doc_chunks = []
        for i, chunk_text in enumerate(chunks):
            chunk = ContextChunk(
                chunk_id=f"{doc_id}_chunk_{i}",
                content=chunk_text,
                scope=scope,
                priority=self._calculate_priority(chunk_text, scope),
                metadata=metadata or {}
            )
            doc_chunks.append(chunk)

        doc = ContextDocument(
            doc_id=doc_id,
            title=title,
            scope=scope,
            chunks=doc_chunks,
            metadata=metadata or {}
        )

        self.documents[doc_id] = doc

        if scope == ContextScope.PROJECT:
            self.global_chunks.extend(doc_chunks)
        else:
            self.session_chunks.extend(doc_chunks)

        self._update_access_order(doc_id)
        return doc

    def get_context(
        self,
        query: Optional[str] = None,
        max_tokens: int = 4000,
        scope_filter: Optional[ContextScope] = None
    ) -> str:
        """
        获取上下文

        Args:
            query: 查询字符串（用于相关性排序）
            max_tokens: 最大 token 数
            scope_filter: 范围过滤器

        Returns:
            str: 格式化后的上下文
        """
        chunks = self._select_chunks(query, scope_filter)
        selected = self._fit_to_token_limit(chunks, max_tokens)
        return self._format_context(selected)

    def _select_chunks(
        self,
        query: Optional[str],
        scope_filter: Optional[ContextScope]
    ) -> List[ContextChunk]:
        """选择相关块"""
        candidate_chunks = []

        for doc in self.documents.values():
            if scope_filter and doc.scope != scope_filter:
                continue
            candidate_chunks.extend(doc.chunks)

        if not query:
            return self._sort_by_relevance(candidate_chunks, self.current_scope.value)

        query_lower = query.lower()
        scored_chunks = []

        for chunk in candidate_chunks:
            score = self._relevance_score(chunk, query_lower)
            scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored_chunks]

    def _relevance_score(self, chunk: ContextChunk, query: str) -> float:
        """计算相关性分数"""
        content_lower = chunk.content.lower()
        query_words = set(query.split())

        word_matches = sum(1 for w in query_words if w in content_lower)
        word_score = word_matches / max(len(query_words), 1)

        scope_score = 1.0 if chunk.scope == self.current_scope else 0.5

        access_score = min(chunk.access_count / 10, 1.0)

        recency_score = self._recency_score(chunk.accessed_at)

        return (
            word_score * 0.4 +
            scope_score * 0.3 +
            access_score * 0.1 +
            recency_score * 0.1 +
            chunk.priority * 0.1
        )

    def _recency_score(self, timestamp: float) -> float:
        """计算时间衰减分数"""
        age_hours = (time.time() - timestamp) / 3600
        return max(0, 1.0 - age_hours / 168)

    def _sort_by_relevance(
        self,
        chunks: List[ContextChunk],
        default_scope: str
    ) -> List[ContextChunk]:
        """按相关性排序"""
        def sort_key(c: ContextChunk):
            scope_weight = 1.0 if c.scope.value == default_scope else 0.5
            return (
                c.priority * scope_weight,
                c.access_count,
                c.accessed_at
            )

        return sorted(chunks, key=sort_key, reverse=True)

    def _fit_to_token_limit(
        self,
        chunks: List[ContextChunk],
        max_tokens: int
    ) -> List[ContextChunk]:
        """限制 token 数量"""
        selected = []
        total_tokens = 0

        for chunk in chunks:
            if total_tokens + chunk.tokens <= max_tokens:
                selected.append(chunk)
                total_tokens += chunk.tokens
            elif total_tokens < max_tokens // 2:
                partial = self._truncate_chunk(chunk, max_tokens - total_tokens)
                if partial:
                    selected.append(partial)
                    total_tokens += partial.tokens

        return selected

    def _truncate_chunk(self, chunk: ContextChunk, max_tokens: int) -> Optional[ContextChunk]:
        """截断块"""
        if max_tokens < 100:
            return None

        avg_char_per_token = len(chunk.content) / max(chunk.tokens, 1)
        max_chars = int(max_tokens * avg_char_per_token)

        truncated_content = chunk.content[:max_chars]

        truncated = ContextChunk(
            chunk_id=f"{chunk.chunk_id}_truncated",
            content=truncated_content,
            scope=chunk.scope,
            priority=chunk.priority * 0.5,
            tokens=max_tokens,
            metadata=chunk.metadata
        )
        return truncated

    def _format_context(self, chunks: List[ContextChunk]) -> str:
        """格式化上下文"""
        if not chunks:
            return ""

        formatted_parts = []
        current_scope = None

        for chunk in chunks:
            if chunk.scope != current_scope:
                formatted_parts.append(f"\n## {chunk.scope.value.upper()} CONTEXT\n")
                current_scope = chunk.scope

            formatted_parts.append(f"\n### {chunk.chunk_id}\n")
            formatted_parts.append(chunk.content)

        return "".join(formatted_parts)

    def _chunk_content(
        self,
        content: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """分块内容"""
        if len(content) <= chunk_size:
            return [content]

        chunks = []
        start = 0

        while start < len(content):
            end = start + chunk_size

            if end < len(content):
                boundary = max(
                    content.rfind('. ', start, end),
                    content.rfind('。', start, end),
                    content.rfind('\n', start, end),
                    content.rfind('; ', start, end),
                )
                if boundary > start:
                    end = boundary + 1

            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    def _calculate_priority(self, content: str, scope: ContextScope) -> float:
        """计算优先级"""
        priority = 1.0

        if scope == ContextScope.ARCHITECTURE:
            priority += 0.3
        elif scope == ContextScope.REQUIREMENTS:
            priority += 0.2

        if any(kw in content.lower() for kw in ['important', '关键', '核心', 'critical']):
            priority += 0.2

        if any(kw in content.lower() for kw in ['TODO', 'FIXME', 'HACK']):
            priority += 0.1

        return min(priority, 2.0)

    def _update_access_order(self, doc_id: str):
        """更新访问顺序"""
        if doc_id in self._access_order:
            self._access_order.remove(doc_id)
        self._access_order.append(doc_id)

        if len(self._access_order) > 100:
            self._access_order = self._access_order[-100:]

    def mark_accessed(self, chunk_id: str):
        """标记已访问"""
        for doc in self.documents.values():
            for chunk in doc.chunks:
                if chunk.chunk_id == chunk_id:
                    chunk.accessed_at = time.time()
                    chunk.access_count += 1
                    return

    def get_context_stats(self) -> Dict[str, Any]:
        """获取上下文统计"""
        total_tokens = sum(d.total_tokens for d in self.documents.values())
        usage_percent = (total_tokens / self.MAX_CONTEXT_TOKENS) * 100

        scope_counts = {}
        for doc in self.documents.values():
            scope = doc.scope.value
            scope_counts[scope] = scope_counts.get(scope, 0) + doc.total_tokens

        return {
            "total_documents": len(self.documents),
            "total_chunks": sum(len(d.chunks) for d in self.documents.values()),
            "total_tokens": total_tokens,
            "max_tokens": self.MAX_CONTEXT_TOKENS,
            "usage_percent": usage_percent,
            "scope_distribution": scope_counts,
            "warning": total_tokens > self.WARNING_THRESHOLD,
            "critical": total_tokens > self.CRITICAL_THRESHOLD
        }

    def compress_context(self, target_tokens: int = 5000) -> int:
        """
        压缩上下文

        Args:
            target_tokens: 目标 token 数量

        Returns:
            int: 释放的 token 数量
        """
        current_tokens = sum(d.total_tokens for d in self.documents.values())
        if current_tokens <= target_tokens:
            return 0

        freed_tokens = 0

        for doc in sorted(
            self.documents.values(),
            key=lambda d: min(c.accessed_at for c in d.chunks) if d.chunks else time.time()
        ):
            if current_tokens - freed_tokens <= target_tokens:
                break

            for chunk in sorted(doc.chunks, key=lambda c: c.accessed_at):
                if current_tokens - freed_tokens <= target_tokens:
                    break

                freed_tokens += chunk.tokens
                chunk.priority *= 0.8
                chunk.content = f"[已压缩] {chunk.content[:500]}..."

        return freed_tokens

    def set_scope(self, scope: ContextScope):
        """设置当前范围"""
        self.current_scope = scope

    def get_documents_by_scope(self, scope: ContextScope) -> List[ContextDocument]:
        """按范围获取文档"""
        return [d for d in self.documents.values() if d.scope == scope]


_global_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取上下文管理器"""
    global _global_context_manager
    if _global_context_manager is None:
        _global_context_manager = ContextManager()
    return _global_context_manager