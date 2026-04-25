"""
Cognee Memory 记忆系统

完整的知识引擎实现：
- 向量嵌入（sentence-transformers）
- 多模态数据摄入
- RAG 管道
- 知识图谱
- 记忆 API（remember/recall/forget/improve）

借鉴 https://github.com/topoteretes/cognee
"""

import json
import time
import threading
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import asyncio

# 导入子模块
from .embedding import (
    EmbeddingEngine,
    EmbeddingConfig,
    VectorStore,
    SemanticSearch,
    get_embedding_engine,
    get_semantic_search,
)

from .multimodal_ingestion import (
    MultimodalIngester,
    IngestionConfig,
    DataItem,
    ChunkProcessor,
    get_multimodal_ingester,
)

from .rag_pipeline import (
    RAGPipeline,
    RAGConfig,
    RAGContext,
    KnowledgeGraph,
    RetrievalStrategy,
    RetrievalResult,
    CogneeRAGAdapter,
    get_cognee_rag,
)


class MemoryType(Enum):
    """记忆类型"""
    PERMANENT = "permanent"      # 永久知识图谱
    SESSION = "session"          # 会话缓存
    WORKING = "working"          # 工作记忆


@dataclass
class MemoryItem:
    """记忆条目"""
    id: str = ""
    content: str = ""
    memory_type: MemoryType = MemoryType.PERMANENT
    session_id: str = ""
    entities: List[str] = field(default_factory=list)
    relations: List[Dict[str, str]] = field(default_factory=list)
    embedding: str = ""  # 向量哈希
    quality_score: float = 1.0
    access_count: int = 0
    last_access: float = 0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CogneeDatabase:
    """Cognee 记忆数据库"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT DEFAULT 'permanent',
                    session_id TEXT DEFAULT '',
                    entities TEXT DEFAULT '[]',
                    relations TEXT DEFAULT '[]',
                    embedding TEXT DEFAULT '',
                    quality_score REAL DEFAULT 1.0,
                    access_count INTEGER DEFAULT 0,
                    last_access REAL DEFAULT 0,
                    created_at REAL DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    entity_type TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    attributes TEXT DEFAULT '{}',
                    memory_ids TEXT DEFAULT '[]',
                    created_at REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS relations (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    context TEXT DEFAULT '',
                    created_at REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    score_delta REAL DEFAULT 0,
                    note TEXT DEFAULT '',
                    created_at REAL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type);
                CREATE INDEX IF NOT EXISTS idx_memory_session ON memories(session_id);
                CREATE INDEX IF NOT EXISTS idx_entity_name ON entities(name);
                CREATE INDEX IF NOT EXISTS idx_feedback_memory ON feedback(memory_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _generate_id(self, *parts: str) -> str:
        """生成唯一ID"""
        raw = "|".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def save_memory(self, memory: MemoryItem) -> str:
        """保存记忆"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                if not memory.id:
                    memory.id = self._generate_id(memory.content, memory.memory_type.value)

                conn.execute("""
                    INSERT OR REPLACE INTO memories
                    (id, content, memory_type, session_id, entities, relations,
                     embedding, quality_score, access_count, last_access,
                     created_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    memory.id, memory.content, memory.memory_type.value,
                    memory.session_id, json.dumps(memory.entities),
                    json.dumps(memory.relations), memory.embedding,
                    memory.quality_score, memory.access_count,
                    memory.last_access, memory.created_at,
                    json.dumps(memory.metadata)
                ))
                conn.commit()
                return memory.id
            finally:
                conn.close()

    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """获取记忆"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                row = conn.execute(
                    "SELECT * FROM memories WHERE id = ?", (memory_id,)
                ).fetchone()
                return self._row_to_memory(row) if row else None
            finally:
                conn.close()

    def search_memories(
        self,
        query: str,
        memory_type: MemoryType = None,
        session_id: str = None,
        limit: int = 10
    ) -> List[MemoryItem]:
        """搜索记忆"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conditions = ["content LIKE ?"]
                params = [f"%{query}%"]

                if memory_type:
                    conditions.append("memory_type = ?")
                    params.append(memory_type.value)

                if session_id:
                    conditions.append("session_id = ?")
                    params.append(session_id)

                params.append(limit)

                rows = conn.execute(f"""
                    SELECT * FROM memories
                    WHERE {' AND '.join(conditions)}
                    ORDER BY (quality_score * access_count + 1) DESC
                    LIMIT ?
                """, params).fetchall()

                return [self._row_to_memory(row) for row in rows]
            finally:
                conn.close()

    def increment_access(self, memory_id: str):
        """增加访问次数"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    UPDATE memories
                    SET access_count = access_count + 1, last_access = ?
                    WHERE id = ?
                """, (time.time(), memory_id))
                conn.commit()
            finally:
                conn.close()

    def delete_memory(self, memory_id: str):
        """删除记忆"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                conn.commit()
            finally:
                conn.close()

    def save_entity(self, name: str, entity_type: str = "", description: str = "") -> str:
        """保存实体"""
        entity_id = self._generate_id(name, entity_type)
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO entities
                    (id, name, entity_type, description, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (entity_id, name, entity_type, description, time.time()))
                conn.commit()
                return entity_id
            finally:
                conn.close()

    def link_memory_to_entity(self, memory_id: str, entity_name: str):
        """关联记忆到实体"""
        entity_id = self._generate_id(entity_name, "")
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                row = conn.execute(
                    "SELECT memory_ids FROM entities WHERE id = ?", (entity_id,)
                ).fetchone()

                memory_ids = json.loads(row[0] if row else "[]")
                if memory_id not in memory_ids:
                    memory_ids.append(memory_id)

                conn.execute("""
                    INSERT OR REPLACE INTO entities (id, memory_ids, updated_at)
                    VALUES (?, ?, ?)
                """, (entity_id, json.dumps(memory_ids), time.time()))
                conn.commit()
            finally:
                conn.close()

    def add_feedback(self, memory_id: str, feedback_type: str, score_delta: float):
        """添加反馈"""
        feedback_id = self._generate_id(memory_id, feedback_type, str(time.time()))
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    INSERT INTO feedback (id, memory_id, feedback_type, score_delta, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (feedback_id, memory_id, feedback_type, score_delta, time.time()))

                conn.execute("""
                    UPDATE memories
                    SET quality_score = MAX(0.0, MIN(1.0, quality_score + ?))
                    WHERE id = ?
                """, (score_delta, memory_id))
                conn.commit()
            finally:
                conn.close()

    def _row_to_memory(self, row: tuple) -> MemoryItem:
        return MemoryItem(
            id=row[0], content=row[1],
            memory_type=MemoryType(row[2]) if row[2] else MemoryType.PERMANENT,
            session_id=row[3] or "",
            entities=json.loads(row[4] or "[]"),
            relations=json.loads(row[5] or "[]"),
            embedding=row[6] or "",
            quality_score=row[7] or 1.0,
            access_count=row[8] or 0,
            last_access=row[9] or 0,
            created_at=row[10] or time.time(),
            metadata=json.loads(row[11] or "{}")
        )

    def get_stats(self) -> Dict[str, int]:
        """获取统计"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                return {
                    "total_memories": conn.execute(
                        "SELECT COUNT(*) FROM memories").fetchone()[0],
                    "permanent_memories": conn.execute(
                        "SELECT COUNT(*) FROM memories WHERE memory_type = 'permanent'"
                    ).fetchone()[0],
                    "entities": conn.execute(
                        "SELECT COUNT(*) FROM entities").fetchone()[0],
                    "relations": conn.execute(
                        "SELECT COUNT(*) FROM relations").fetchone()[0],
                }
            finally:
                conn.close()


class CogneeMemoryAdapter:
    """
    Cognee 记忆适配器

    完整 API：
    await cognee.remember("事实")           # 存储到知识图谱
    await cognee.recall("查询")             # 查询记忆
    await cognee.forget(dataset="...")      # 删除数据
    await cognee.improve(feedback)          # 持续改进
    await cognee.add_knowledge(data)         # 添加知识（RAG）
    await cognee.query(question)            # RAG 查询
    """

    def __init__(self, db_path: str | Path = None):
        from client.src.business.config import get_config_dir

        if db_path is None:
            db_path = get_config_dir() / "cognee_memory.db"

        self.db = CogneeDatabase(db_path)
        self._default_session = "default"
        self._extractors = []
        self._add_default_extractors()

        # RAG 组件
        self.rag = get_cognee_rag()

    def _add_default_extractors(self):
        """添加默认提取器"""
        import re

        def extract_entities(text: str) -> List[str]:
            entities = re.findall(r'"([^"]+)"', text)
            tech_terms = re.findall(r'\b[A-Z][a-zA-Z]+\b', text)
            entities.extend(tech_terms)
            return list(set(entities))

        def extract_relations(text: str) -> List[Dict[str, str]]:
            relations = []
            patterns = [
                (r'(\w+)是(\w+)', '是'),
                (r'(\w+)属于(\w+)', '属于'),
                (r'(\w+)使用(\w+)', '使用'),
            ]
            for pattern, rel_type in patterns:
                matches = re.finditer(pattern, text)
                for m in matches:
                    relations.append({
                        "source": m.group(1),
                        "target": m.group(2),
                        "type": rel_type
                    })
            return relations

        self._extractors = [extract_entities, extract_relations]

    def remember(
        self,
        content: str,
        session_id: str = None,
        memory_type: MemoryType = MemoryType.PERMANENT,
        metadata: Dict[str, Any] = None
    ) -> str:
        """存储到知识图谱"""
        entities = []
        relations = []
        for extractor in self._extractors:
            result = extractor(content)
            if isinstance(result, list) and result:
                if isinstance(result[0], str):
                    entities.extend(result)
                elif isinstance(result[0], dict):
                    relations.extend(result)

        memory = MemoryItem(
            content=content,
            memory_type=memory_type,
            session_id=session_id or self._default_session,
            entities=list(set(entities)),
            relations=relations,
            embedding=hashlib.md5(content.encode()).hexdigest()[:32],
            metadata=metadata or {}
        )

        memory_id = self.db.save_memory(memory)

        for entity_name in memory.entities:
            self.db.save_entity(entity_name)
            self.db.link_memory_to_entity(memory_id, entity_name)

        # 同时添加到 RAG
        asyncio.create_task(self.rag.add_knowledge(content, "text"))

        return memory_id

    def recall(
        self,
        query: str,
        session_id: str = None,
        memory_type: MemoryType = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """查询记忆（混合搜索）"""
        memories = self.db.search_memories(
            query=query,
            memory_type=memory_type,
            session_id=session_id,
            limit=limit
        )

        results = []
        for memory in memories:
            self.db.increment_access(memory.id)
            results.append({
                "id": memory.id,
                "content": memory.content,
                "type": memory.memory_type.value,
                "entities": memory.entities,
                "quality": memory.quality_score,
                "relevance": self._calculate_relevance(query, memory)
            })

        results.sort(key=lambda x: x["relevance"] * x["quality"], reverse=True)

        # 同时从 RAG 检索
        asyncio.create_task(self._rag_recall(query, limit))

        return results

    async def _rag_recall(self, query: str, limit: int):
        """RAG 检索"""
        try:
            await self.rag.query(query)
        except:
            pass

    def _calculate_relevance(self, query: str, memory: MemoryItem) -> float:
        """计算相关性"""
        query_lower = query.lower()
        content_lower = memory.content.lower()

        query_words = set(query_lower.split())
        content_words = set(content_lower.split())
        word_match = len(query_words & content_words) / max(len(query_words), 1)

        entity_match = 0
        for entity in memory.entities:
            if entity.lower() in query_lower:
                entity_match += 1
        entity_match = min(entity_match / max(len(memory.entities), 1), 1.0)

        return 0.6 * word_match + 0.4 * entity_match

    def forget(self, memory_id: str = None, session_id: str = None):
        """删除数据"""
        if memory_id:
            self.db.delete_memory(memory_id)
        elif session_id:
            self.db.delete_by_session(session_id)

    def improve(self, memory_id: str, is_helpful: bool, note: str = ""):
        """持续改进"""
        score_delta = 0.1 if is_helpful else -0.1
        self.db.add_feedback(
            memory_id=memory_id,
            feedback_type="helpfulness",
            score_delta=score_delta
        )

    async def add_knowledge(
        self,
        data: str,
        data_type: str = "text"
    ) -> bool:
        """添加知识（RAG）"""
        return await self.rag.add_knowledge(data, data_type)

    async def query(
        self,
        question: str,
        use_rag: bool = True
    ) -> Dict[str, Any]:
        """RAG 查询"""
        return await self.rag.query(question, use_rag)

    def get_session_context(self, session_id: str = None, limit: int = 10) -> List[str]:
        """获取会话上下文"""
        memories = self.db.search_memories(
            query="",
            memory_type=MemoryType.SESSION,
            session_id=session_id or self._default_session,
            limit=limit
        )
        return [m.content for m in memories]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        db_stats = self.db.get_stats()
        rag_stats = self.rag.get_stats()
        return {
            **db_stats,
            "rag": rag_stats
        }


# 全局实例
_cognee_adapter: Optional[CogneeMemoryAdapter] = None


def get_cognee_memory() -> CogneeMemoryAdapter:
    """获取 Cognee 记忆适配器"""
    global _cognee_adapter
    if _cognee_adapter is None:
        _cognee_adapter = CogneeMemoryAdapter()
    return _cognee_adapter


# 便捷函数
async def remember(text: str, session_id: str = None) -> str:
    """remember API"""
    return get_cognee_memory().remember(text, session_id)


async def recall(query: str, session_id: str = None, limit: int = 5) -> List[Dict[str, Any]]:
    """recall API"""
    return get_cognee_memory().recall(query, session_id, limit=limit)


async def forget(memory_id: str = None, session_id: str = None):
    """forget API"""
    get_cognee_memory().forget(memory_id, session_id)


async def improve(memory_id: str, is_helpful: bool, note: str = ""):
    """improve API"""
    get_cognee_memory().improve(memory_id, is_helpful, note)


async def add_knowledge(data: str, data_type: str = "text") -> bool:
    """添加知识"""
    return await get_cognee_memory().add_knowledge(data, data_type)


async def query(question: str, use_rag: bool = True) -> Dict[str, Any]:
    """RAG 查询"""
    return await get_cognee_memory().query(question, use_rag)


__all__ = [
    # 子模块
    "EmbeddingEngine",
    "EmbeddingConfig",
    "VectorStore",
    "SemanticSearch",
    "get_embedding_engine",
    "get_semantic_search",

    "MultimodalIngester",
    "IngestionConfig",
    "DataItem",
    "ChunkProcessor",
    "get_multimodal_ingester",

    "RAGPipeline",
    "RAGConfig",
    "RAGContext",
    "KnowledgeGraph",
    "RetrievalStrategy",
    "RetrievalResult",
    "CogneeRAGAdapter",
    "get_cognee_rag",

    # 核心
    "CogneeDatabase",
    "CogneeMemoryAdapter",
    "MemoryItem",
    "MemoryType",
    "get_cognee_memory",

    # API
    "remember",
    "recall",
    "forget",
    "improve",
    "add_knowledge",
    "query",
]
