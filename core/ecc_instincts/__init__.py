"""
ECC Instinct System - 本地向量记忆系统
Inspired by Everything Claude Code (ECC)

Instinct 是本地向量记忆，集成 PageIndex 实现对话/代码历史索引

核心概念:
- Memory Chunk: 记忆片段
- Vector Index: 向量索引
- Query: 语义查询
- PageIndex: 文档/代码索引

功能:
- 代码片段记忆
- 对话历史记忆
- 项目上下文记忆
- 语义搜索
"""

import json
import sqlite3
import time
import threading
import hashlib
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


# 向量维度
EMBEDDING_DIM = 384
DEFAULT_MODEL = "all-MiniLM-L6-v2"


class MemoryType(Enum):
    """记忆类型"""
    CODE_SNIPPET = "code_snippet"
    CONVERSATION = "conversation"
    PROJECT_CONTEXT = "project_context"
    DOCUMENT = "document"
    TASK = "task"
    DECISION = "decision"


@dataclass
class MemoryChunk:
    """记忆片段"""
    chunk_id: str
    content: str                    # 原始内容
    memory_type: MemoryType          # 记忆类型
    embedding: Optional[List[float]] = None  # 向量
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 元数据
    source_file: str = ""
    source_line_start: int = 0
    source_line_end: int = 0
    language: str = ""
    project_path: str = ""
    session_id: str = ""
    # 统计
    access_count: int = 0
    last_accessed: Optional[float] = None
    importance: float = 0.5  # 0-1, 重要性评分
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "metadata": self.metadata,
            "source_file": self.source_file,
            "source_line_start": self.source_line_start,
            "source_line_end": self.source_line_end,
            "language": self.language,
            "project_path": self.project_path,
            "session_id": self.session_id,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "importance": self.importance,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryChunk":
        return cls(
            chunk_id=d["chunk_id"],
            content=d["content"],
            memory_type=MemoryType(d.get("memory_type", "code_snippet")),
            metadata=d.get("metadata", {}),
            source_file=d.get("source_file", ""),
            source_line_start=d.get("source_line_start", 0),
            source_line_end=d.get("source_line_end", 0),
            language=d.get("language", ""),
            project_path=d.get("project_path", ""),
            session_id=d.get("session_id", ""),
            access_count=d.get("access_count", 0),
            last_accessed=d.get("last_accessed"),
            importance=d.get("importance", 0.5),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
        )


class LocalVectorStore:
    """
    本地向量存储 (简化版，不依赖 faiss)

    使用 SQLite 存储 + 简单余弦相似度计算
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (Path(__file__).parent.parent.parent / "data" / "ecc_instincts.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_chunks (
                chunk_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                embedding BLOB,
                metadata TEXT DEFAULT '{}',
                source_file TEXT DEFAULT '',
                source_line_start INTEGER DEFAULT 0,
                source_line_end INTEGER DEFAULT 0,
                language TEXT DEFAULT '',
                project_path TEXT DEFAULT '',
                session_id TEXT DEFAULT '',
                access_count INTEGER DEFAULT 0,
                last_accessed REAL,
                importance REAL DEFAULT 0.5,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_chunks(memory_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_project ON memory_chunks(project_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON memory_chunks(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON memory_chunks(created_at)")
        conn.commit()
        conn.close()

    def add(self, chunk: MemoryChunk) -> bool:
        """添加记忆"""
        import pickle
        conn = sqlite3.connect(str(self.db_path))
        try:
            embedding = pickle.dumps(chunk.embedding) if chunk.embedding else None
            conn.execute("""
                INSERT OR REPLACE INTO memory_chunks
                (chunk_id, content, memory_type, embedding, metadata, source_file,
                 source_line_start, source_line_end, language, project_path,
                 session_id, access_count, last_accessed, importance, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk.chunk_id, chunk.content, chunk.memory_type.value, embedding,
                json.dumps(chunk.metadata), chunk.source_file, chunk.source_line_start,
                chunk.source_line_end, chunk.language, chunk.project_path, chunk.session_id,
                chunk.access_count, chunk.last_accessed, chunk.importance,
                chunk.created_at, chunk.updated_at,
            ))
            conn.commit()
            return True
        finally:
            conn.close()

    def get(self, chunk_id: str) -> Optional[MemoryChunk]:
        """获取记忆"""
        import pickle
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT * FROM memory_chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
            if row:
                keys = [desc[0] for desc in conn.execute("SELECT * FROM memory_chunks LIMIT 0").description]
                d = dict(zip(keys, row))
                if d["embedding"]:
                    d["embedding"] = pickle.loads(d["embedding"])
                return MemoryChunk.from_dict(d)
            return None
        finally:
            conn.close()

    def delete(self, chunk_id: str) -> bool:
        """删除记忆"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM memory_chunks WHERE chunk_id = ?", (chunk_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    def search(self, query_embedding: List[float], top_k: int = 10,
              memory_type: Optional[MemoryType] = None,
              project_path: Optional[str] = None,
              min_importance: float = 0.0) -> List[Tuple[MemoryChunk, float]]:
        """
        向量搜索

        Returns:
            List of (chunk, similarity_score)
        """
        import pickle
        conn = sqlite3.connect(str(self.db_path))
        try:
            query = "SELECT * FROM memory_chunks WHERE importance >= ?"
            params = [min_importance]

            if memory_type:
                query += " AND memory_type = ?"
                params.append(memory_type.value)

            if project_path:
                query += " AND project_path = ?"
                params.append(project_path)

            rows = conn.execute(query, params).fetchall()
            keys = [desc[0] for desc in conn.execute("SELECT * FROM memory_chunks LIMIT 0").description]

            results = []
            for row in rows:
                d = dict(zip(keys, row))
                if d["embedding"]:
                    embedding = pickle.loads(d["embedding"])
                    # 计算余弦相似度
                    score = self._cosine_similarity(query_embedding, embedding)
                    d["embedding"] = embedding
                    results.append((MemoryChunk.from_dict(d), score))

            # 排序并返回 top_k
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
        finally:
            conn.close()

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if not a or not b:
            return 0.0
        a = np.array(a)
        b = np.array(b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def update_access(self, chunk_id: str):
        """更新访问统计"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                UPDATE memory_chunks
                SET access_count = access_count + 1,
                    last_accessed = ?
                WHERE chunk_id = ?
            """, (time.time(), chunk_id))
            conn.commit()
        finally:
            conn.close()

    def count(self) -> int:
        """统计记忆数量"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            return conn.execute("SELECT COUNT(*) FROM memory_chunks").fetchone()[0]
        finally:
            conn.close()


class InstinctSystem:
    """
    Instinct 系统 - 本地向量记忆

    集成 PageIndex 实现:
    - 代码索引
    - 对话历史索引
    - 项目上下文
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.vector_store = LocalVectorStore(db_path)
        self._embedding_model = None
        self._use_fallback = False
        self._init_embedding_model()

    def _init_embedding_model(self):
        """初始化嵌入模型"""
        try:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer(DEFAULT_MODEL)
            print(f"Loaded embedding model: {DEFAULT_MODEL}")
        except ImportError:
            print("sentence-transformers not available, using fallback")
            self._use_fallback = True
        except Exception as e:
            print(f"Failed to load embedding model: {e}")
            self._use_fallback = True

    def _generate_id(self, content: str, prefix: str = "") -> str:
        """生成唯一 ID"""
        hash_val = hashlib.md5(content.encode()).hexdigest()[:12]
        return f"{prefix}_{hash_val}" if prefix else hash_val

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """获取文本嵌入向量"""
        if self._use_fallback:
            # 简单 TF-IDF fallback
            return self._simple_embedding(text)

        if self._embedding_model is None:
            return None

        try:
            embedding = self._embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            print(f"Embedding error: {e}")
            return None

    def _simple_embedding(self, text: str, dim: int = EMBEDDING_DIM) -> List[float]:
        """简单词袋 embedding (fallback)"""
        words = text.lower().split()
        vec = [0.0] * dim
        for i, word in enumerate(words[:dim]):
            vec[i % dim] += hash(word) % 100 / 100.0
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def remember_code(self, code: str, file_path: str = "",
                     language: str = "", project_path: str = "",
                     importance: float = 0.5) -> Optional[str]:
        """记忆代码片段"""
        chunk_id = self._generate_id(code, "code")
        embedding = self._get_embedding(code)

        chunk = MemoryChunk(
            chunk_id=chunk_id,
            content=code,
            memory_type=MemoryType.CODE_SNIPPET,
            embedding=embedding,
            source_file=file_path,
            language=language,
            project_path=project_path,
            importance=importance,
        )

        self.vector_store.add(chunk)
        return chunk_id

    def remember_conversation(self, content: str, session_id: str,
                           importance: float = 0.5) -> Optional[str]:
        """记忆对话片段"""
        chunk_id = self._generate_id(content, "conv")
        embedding = self._get_embedding(content)

        chunk = MemoryChunk(
            chunk_id=chunk_id,
            content=content,
            memory_type=MemoryType.CONVERSATION,
            embedding=embedding,
            session_id=session_id,
            importance=importance,
        )

        self.vector_store.add(chunk)
        return chunk_id

    def remember_decision(self, context: str, decision: str,
                         reasoning: str = "",
                         project_path: str = "",
                         importance: float = 0.7) -> Optional[str]:
        """记忆决策"""
        content = f"Context: {context}\nDecision: {decision}"
        if reasoning:
            content += f"\nReasoning: {reasoning}"

        chunk_id = self._generate_id(content, "dec")
        embedding = self._get_embedding(content)

        chunk = MemoryChunk(
            chunk_id=chunk_id,
            content=content,
            memory_type=MemoryType.DECISION,
            embedding=embedding,
            metadata={"reasoning": reasoning},
            project_path=project_path,
            importance=importance,
        )

        self.vector_store.add(chunk)
        return chunk_id

    def recall(self, query: str, top_k: int = 10,
              memory_type: Optional[MemoryType] = None,
              project_path: Optional[str] = None,
              min_importance: float = 0.0) -> List[Tuple[MemoryChunk, float]]:
        """
        语义检索记忆

        Returns:
            List of (chunk, similarity_score)
        """
        embedding = self._get_embedding(query)
        if not embedding:
            return []

        results = self.vector_store.search(
            embedding, top_k, memory_type, project_path, min_importance
        )

        # 更新访问统计
        for chunk, score in results:
            self.vector_store.update_access(chunk.chunk_id)

        return results

    def get_context(self, query: str, project_path: Optional[str] = None,
                   max_chunks: int = 5) -> str:
        """
        获取相关上下文 (用于注入 System Prompt)

        Returns:
            格式化的上下文字符串
        """
        results = self.recall(query, top_k=max_chunks, project_path=project_path)

        if not results:
            return ""

        lines = ["## Relevant Memory Context\n"]
        for chunk, score in results:
            lines.append(f"### [{chunk.memory_type.value}] (relevance: {score:.2f})")
            if chunk.source_file:
                lines.append(f"Source: {chunk.source_file}")
            lines.append(chunk.content)
            lines.append("")

        return "\n".join(lines)

    def get_recent_codes(self, project_path: Optional[str] = None,
                        limit: int = 10) -> List[MemoryChunk]:
        """获取最近的代码记忆"""
        conn = sqlite3.connect(str(self.vector_store.db_path))
        try:
            query = """
                SELECT * FROM memory_chunks
                WHERE memory_type = ?
            """
            params = [MemoryType.CODE_SNIPPET.value]

            if project_path:
                query += " AND project_path = ?"
                params.append(project_path)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            keys = [desc[0] for desc in conn.execute("SELECT * FROM memory_chunks LIMIT 0").description]

            return [MemoryChunk.from_dict(dict(zip(keys, row))) for row in rows]
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        conn = sqlite3.connect(str(self.vector_store.db_path))
        try:
            total = conn.execute("SELECT COUNT(*) FROM memory_chunks").fetchone()[0]

            by_type = {}
            for mt in MemoryType:
                count = conn.execute(
                    "SELECT COUNT(*) FROM memory_chunks WHERE memory_type = ?",
                    (mt.value,)
                ).fetchone()[0]
                by_type[mt.value] = count

            recent_count = conn.execute(
                "SELECT COUNT(*) FROM memory_chunks WHERE created_at > ?",
                (time.time() - 86400,)
            ).fetchone()[0]  # 最近24小时

            return {
                "total_chunks": total,
                "by_type": by_type,
                "recent_24h": recent_count,
            }
        finally:
            conn.close()


# Singleton
_instinct_system: Optional[InstinctSystem] = None


def get_instinct_system() -> InstinctSystem:
    global _instinct_system
    if _instinct_system is None:
        _instinct_system = InstinctSystem()
    return _instinct_system