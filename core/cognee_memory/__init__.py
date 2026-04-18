"""
Cognee 记忆适配器
Cognify Your AI: 6行代码实现记忆增强

借鉴 https://github.com/topoteretes/cognee
实现 remember/recall/forget/improve API
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
    embedding: str = ""  # 简化：用内容hash代替向量
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
                -- 记忆表
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

                -- 实体表
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    entity_type TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    attributes TEXT DEFAULT '{}',
                    memory_ids TEXT DEFAULT '[]',
                    created_at REAL DEFAULT 0
                );

                -- 关系表
                CREATE TABLE IF NOT EXISTS relations (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    context TEXT DEFAULT '',
                    created_at REAL DEFAULT 0
                );

                -- 反馈表
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    score_delta REAL DEFAULT 0,
                    note TEXT DEFAULT '',
                    created_at REAL DEFAULT 0
                );

                -- 索引
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

    # === 记忆操作 ===

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

    def delete_by_session(self, session_id: str):
        """删除会话记忆"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("DELETE FROM memories WHERE session_id = ?", (session_id,))
                conn.commit()
            finally:
                conn.close()

    # === 实体操作 ===

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
                # 获取现有memory_ids
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

    # === 反馈操作 ===

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

                # 更新记忆质量
                conn.execute("""
                    UPDATE memories
                    SET quality_score = MAX(0.0, MIN(1.0, quality_score + ?))
                    WHERE id = ?
                """, (score_delta, memory_id))
                conn.commit()
            finally:
                conn.close()

    # === 辅助方法 ===

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
                    "session_memories": conn.execute(
                        "SELECT COUNT(*) FROM memories WHERE memory_type = 'session'"
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

    6行代码实现记忆增强：
    await cognee.remember("事实")
    await cognee.recall("查询")
    await cognee.forget(dataset="...")
    await cognee.improve(feedback)

    功能：
    - remember: 存储到知识图谱
    - recall: 查询记忆（自动路由）
    - forget: 删除数据
    - improve: 持续改进
    """

    def __init__(self, db_path: str | Path = None):
        from core.config import get_config_dir

        if db_path is None:
            db_path = get_config_dir() / "cognee_memory.db"

        self.db = CogneeDatabase(db_path)
        self._default_session = "default"
        self._extractors = []

        # 默认提取器：简单关键词
        self._add_default_extractors()

    def _add_default_extractors(self):
        """添加默认提取器"""
        import re

        def extract_entities(text: str) -> List[str]:
            """简单实体提取"""
            # 提取引号内容
            entities = re.findall(r'"([^"]+)"', text)
            # 提取技术术语
            tech_terms = re.findall(r'\b[A-Z][a-zA-Z]+\b', text)
            entities.extend(tech_terms)
            return list(set(entities))

        def extract_relations(text: str) -> List[Dict[str, str]]:
            """简单关系提取"""
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
        """
        存储到知识图谱

        等同于 cognee.remember()
        """
        # 提取实体和关系
        entities = []
        relations = []
        for extractor in self._extractors:
            result = extractor(content)
            if isinstance(result, list) and result:
                if isinstance(result[0], str):
                    entities.extend(result)
                elif isinstance(result[0], dict):
                    relations.extend(result)

        # 创建记忆
        memory = MemoryItem(
            content=content,
            memory_type=memory_type,
            session_id=session_id or self._default_session,
            entities=list(set(entities)),  # 去重
            relations=relations,
            embedding=hashlib.md5(content.encode()).hexdigest()[:32],
            metadata=metadata or {}
        )

        # 保存
        memory_id = self.db.save_memory(memory)

        # 关联实体
        for entity_name in memory.entities:
            self.db.save_entity(entity_name)
            self.db.link_memory_to_entity(memory_id, entity_name)

        return memory_id

    def recall(
        self,
        query: str,
        session_id: str = None,
        memory_type: MemoryType = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        查询记忆（自动路由）

        等同于 cognee.recall()
        混合搜索：内容匹配 + 实体关联
        """
        # 搜索记忆
        memories = self.db.search_memories(
            query=query,
            memory_type=memory_type,
            session_id=session_id,
            limit=limit
        )

        # 更新访问统计并返回
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

        # 按相关性排序
        results.sort(key=lambda x: x["relevance"] * x["quality"], reverse=True)

        return results

    def _calculate_relevance(self, query: str, memory: MemoryItem) -> float:
        """计算相关性"""
        query_lower = query.lower()
        content_lower = memory.content.lower()

        # 词匹配
        query_words = set(query_lower.split())
        content_words = set(content_lower.split())
        word_match = len(query_words & content_words) / max(len(query_words), 1)

        # 实体匹配
        entity_match = 0
        for entity in memory.entities:
            if entity.lower() in query_lower:
                entity_match += 1
        entity_match = min(entity_match / max(len(memory.entities), 1), 1.0)

        return 0.6 * word_match + 0.4 * entity_match

    def forget(self, memory_id: str = None, session_id: str = None):
        """
        删除数据

        等同于 cognee.forget()
        """
        if memory_id:
            self.db.delete_memory(memory_id)
        elif session_id:
            self.db.delete_by_session(session_id)

    def improve(self, memory_id: str, is_helpful: bool, note: str = ""):
        """
        持续改进

        等同于 cognee.improve()
        """
        score_delta = 0.1 if is_helpful else -0.1
        self.db.add_feedback(
            memory_id=memory_id,
            feedback_type="helpfulness",
            score_delta=score_delta
        )

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
        return self.db.get_stats()


# 单例
_cognee_adapter: Optional[CogneeMemoryAdapter] = None


def get_cognee_memory() -> CogneeMemoryAdapter:
    """获取 Cognee 记忆适配器单例"""
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
