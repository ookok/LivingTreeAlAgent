"""
增强记忆系统核心模块
Enhanced Memory System Core

基于Claude-Mem的理念，增强现有记忆系统，实现：
1. 跨会话持久记忆
2. 智能记忆压缩
3. 语义搜索能力
4. 渐进式记忆检索
"""

import json
import time
import hashlib
import sqlite3
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading
import re


class MemoryValue(Enum):
    """记忆价值等级"""
    LOW = 0       # 噪音信息
    MEDIUM = 1   # 一般信息
    HIGH = 2     # 重要事实
    CRITICAL = 3 # 核心知识


@dataclass
class MemoryItem:
    """记忆项"""
    id: str = ""
    content: str = ""         # 原始内容
    compressed_content: str = ""  # 压缩后的内容
    summary: str = ""          # 内容摘要
    keywords: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None  # 语义嵌入向量
    value_level: int = MemoryValue.MEDIUM.value
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    usage_count: int = 0
    tags: List[str] = field(default_factory=list)


@dataclass
class Session:
    """会话信息"""
    id: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    summary: str = ""
    memory_item_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EnhancedMemoryDatabase:
    """增强记忆数据库"""

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
                -- 记忆项表
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    compressed_content TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    keywords TEXT DEFAULT '[]',
                    embedding BLOB DEFAULT NULL,
                    value_level INTEGER DEFAULT 1,
                    created_at REAL DEFAULT 0,
                    last_accessed REAL DEFAULT 0,
                    usage_count INTEGER DEFAULT 0,
                    tags TEXT DEFAULT '[]'
                );

                -- 会话表
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    start_time REAL DEFAULT 0,
                    end_time REAL DEFAULT NULL,
                    summary TEXT DEFAULT '',
                    memory_item_ids TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}'
                );

                -- 索引
                CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_items(created_at);
                CREATE INDEX IF NOT EXISTS idx_memory_value ON memory_items(value_level DESC);
                CREATE INDEX IF NOT EXISTS idx_memory_usage ON memory_items(usage_count DESC);
                CREATE INDEX IF NOT EXISTS idx_session_start ON sessions(start_time);
            """)
            conn.commit()
        finally:
            conn.close()

    def _generate_id(self, *parts: str) -> str:
        """生成唯一ID"""
        raw = "|".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def save_memory_item(self, item: MemoryItem) -> str:
        """保存记忆项"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                if not item.id:
                    item.id = self._generate_id(item.content[:50], str(time.time()))

                # 序列化数据
                keywords_json = json.dumps(item.keywords)
                tags_json = json.dumps(item.tags)
                embedding_blob = None
                if item.embedding:
                    embedding_blob = json.dumps(item.embedding).encode()

                conn.execute("""
                    INSERT OR REPLACE INTO memory_items 
                    (id, content, compressed_content, summary, keywords, embedding, 
                     value_level, created_at, last_accessed, usage_count, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.id, item.content, item.compressed_content, item.summary,
                    keywords_json, embedding_blob, item.value_level, item.created_at,
                    item.last_accessed, item.usage_count, tags_json
                ))
                conn.commit()
                return item.id
            finally:
                conn.close()

    def get_memory_item(self, item_id: str) -> Optional[MemoryItem]:
        """获取记忆项"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                row = conn.execute(
                    "SELECT * FROM memory_items WHERE id = ?",
                    (item_id,)
                ).fetchone()
                if not row:
                    return None

                # 更新访问时间和使用次数
                conn.execute(
                    "UPDATE memory_items SET last_accessed = ?, usage_count = usage_count + 1 WHERE id = ?",
                    (time.time(), item_id)
                )
                conn.commit()

                return self._row_to_memory_item(row)
            finally:
                conn.close()

    def search_memory_items(
        self, 
        query: str,
        limit: int = 10,
        min_value: int = 0
    ) -> List[MemoryItem]:
        """搜索记忆项"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                # 提取关键词
                keywords = self._extract_keywords(query)
                if not keywords:
                    return []

                # 构建搜索条件
                # 优先匹配标签和关键词
                conditions = []
                params = []

                # 匹配标签
                conditions.append("tags LIKE ?")
                params.append(f"%{query}%")

                # 匹配关键词
                for keyword in keywords:
                    conditions.append("keywords LIKE ?")
                    params.append(f"%{keyword}%")

                # 匹配内容
                conditions.append("content LIKE ?")
                params.append(f"%{query}%")

                # 添加价值等级条件
                conditions.append("value_level >= ?")
                params.append(min_value)

                # 构建SQL语句
                where_clause = " OR ".join(conditions)

                # 准备排序参数
                order_params = [f"%{query}%", f"%{query}%", f"%{query}%"]
                # 合并所有参数
                all_params = params + order_params + [limit]

                rows = conn.execute(f"""
                    SELECT * FROM memory_items 
                    WHERE ({where_clause})
                    ORDER BY 
                        CASE 
                            WHEN tags LIKE ? THEN 3
                            WHEN keywords LIKE ? THEN 2
                            WHEN content LIKE ? THEN 1
                            ELSE 0
                        END DESC,
                        (value_level * 10 + usage_count) DESC
                    LIMIT ?
                """, all_params).fetchall()

                return [self._row_to_memory_item(row) for row in rows]
            finally:
                conn.close()

    def save_session(self, session: Session) -> str:
        """保存会话"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                if not session.id:
                    session.id = self._generate_id(str(time.time()))

                # 序列化数据
                memory_item_ids_json = json.dumps(session.memory_item_ids)
                metadata_json = json.dumps(session.metadata)

                conn.execute("""
                    INSERT OR REPLACE INTO sessions 
                    (id, start_time, end_time, summary, memory_item_ids, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session.id, session.start_time, session.end_time, session.summary,
                    memory_item_ids_json, metadata_json
                ))
                conn.commit()
                return session.id
            finally:
                conn.close()

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE id = ?",
                    (session_id,)
                ).fetchone()
                return self._row_to_session(row) if row else None
            finally:
                conn.close()

    def get_recent_sessions(self, limit: int = 5) -> List[Session]:
        """获取最近的会话"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?",
                    (limit,)
                ).fetchall()
                return [self._row_to_session(row) for row in rows]
            finally:
                conn.close()

    def _row_to_memory_item(self, row: sqlite3.Row) -> MemoryItem:
        """将数据库行转换为MemoryItem"""
        embedding = None
        if row[5]:
            try:
                embedding = json.loads(row[5].decode())
            except:
                pass

        return MemoryItem(
            id=row[0],
            content=row[1],
            compressed_content=row[2],
            summary=row[3],
            keywords=json.loads(row[4] or "[]"),
            embedding=embedding,
            value_level=row[6],
            created_at=row[7],
            last_accessed=row[8],
            usage_count=row[9],
            tags=json.loads(row[10] or "[]")
        )

    def _row_to_session(self, row: sqlite3.Row) -> Session:
        """将数据库行转换为Session"""
        return Session(
            id=row[0],
            start_time=row[1],
            end_time=row[2],
            summary=row[3],
            memory_item_ids=json.loads(row[4] or "[]"),
            metadata=json.loads(row[5] or "{}")
        )

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单实现：去除停用词后取高频词
        stopwords = {
            "的", "是", "在", "有", "和", "与", "了", "我", "你", "他",
            "她", "它", "这", "那", "个", "一", "不", "也", "都", "要",
            "就", "可以", "会", "能", "对", "但", "而", "或", "如果"
        }

        # 分词（简单按标点和空格分）
        words = re.findall(r"[\u4e00-\u9fa5]+|[A-Za-z]*", text)

        # 过滤和计数
        word_freq = {}
        for word in words:
            if len(word) >= 2 and word not in stopwords:
                word_freq[word] = word_freq.get(word, 0) + 1

        # 排序取top 10
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:10]]

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                return {
                    "memory_items": conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0],
                    "sessions": conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
                }
            finally:
                conn.close()


class MemoryCompressor:
    """记忆压缩器"""

    @staticmethod
    def compress_content(content: str, max_length: int = 500) -> str:
        """
        压缩内容
        使用简单的摘要算法
        """
        if len(content) <= max_length:
            return content

        # 简单的摘要算法：提取关键句子
        sentences = re.split(r'[。！？.!?]', content)
        key_sentences = []
        total_length = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 优先选择包含关键词的句子
            if any(keyword in sentence for keyword in ["重要", "关键", "核心", "结论", "决定"]):
                if total_length + len(sentence) <= max_length:
                    key_sentences.append(sentence)
                    total_length += len(sentence) + 1  # +1 for punctuation

        # 如果不够，添加其他句子
        if total_length < max_length * 0.7:
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence or sentence in key_sentences:
                    continue
                if total_length + len(sentence) <= max_length:
                    key_sentences.append(sentence)
                    total_length += len(sentence) + 1

        return "。".join(key_sentences) + "。"

    @staticmethod
    def generate_summary(content: str, max_length: int = 100) -> str:
        """
        生成摘要
        """
        # 简单实现：提取第一句和最后一句
        sentences = re.split(r'[。！？.!?]', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return ""
        elif len(sentences) == 1:
            return sentences[0][:max_length]
        else:
            summary = sentences[0] + " " + sentences[-1]
            return summary[:max_length]


class VectorStore:
    """向量存储"""

    def __init__(self, store_path: str | Path):
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._embeddings = {}
        self._load_embeddings()

    def _load_embeddings(self):
        """加载嵌入向量"""
        try:
            embedding_file = self.store_path / "embeddings.json"
            if embedding_file.exists():
                with open(embedding_file, 'r', encoding='utf-8') as f:
                    self._embeddings = json.load(f)
        except Exception:
            pass

    def _save_embeddings(self):
        """保存嵌入向量"""
        try:
            embedding_file = self.store_path / "embeddings.json"
            with open(embedding_file, 'w', encoding='utf-8') as f:
                json.dump(self._embeddings, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_embedding(self, item_id: str, embedding: List[float]):
        """添加嵌入向量"""
        self._embeddings[item_id] = embedding
        self._save_embeddings()

    def get_embedding(self, item_id: str) -> Optional[List[float]]:
        """获取嵌入向量"""
        return self._embeddings.get(item_id)

    def search_similar(self, query_embedding: List[float], top_k: int = 5) -> List[Tuple[str, float]]:
        """
        搜索相似的记忆项
        返回 (item_id, 相似度) 列表
        """
        if not self._embeddings:
            return []

        similarities = []
        for item_id, embedding in self._embeddings.items():
            similarity = self._cosine_similarity(query_embedding, embedding)
            similarities.append((item_id, similarity))

        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class ProgressiveRetriever:
    """渐进式检索器"""

    def __init__(self, db: EnhancedMemoryDatabase, vector_store):
        self.db = db
        self.vector_store = vector_store

    def retrieve_context(
        self,
        query: str,
        max_tokens: int = 2000,
        include_summaries: bool = True,
        include_full_content: bool = False
    ) -> Dict[str, Any]:
        """
        渐进式检索上下文
        1. 先获取摘要级别的信息
        2. 根据需要获取详细信息
        """
        # 1. 搜索相关记忆项（优先使用语义搜索）
        try:
            # 语义搜索
            semantic_results = self.vector_store.search(query, top_k=10)
            semantic_item_ids = [result['item_id'] for result in semantic_results]

            # 获取记忆项
            memory_items = []
            for item_id in semantic_item_ids:
                item = self.db.get_memory_item(item_id)
                if item:
                    memory_items.append(item)

            # 如果语义搜索结果不足，使用关键词搜索补充
            if len(memory_items) < 10:
                keyword_results = self.db.search_memory_items(query, limit=10 - len(memory_items))
                memory_items.extend(keyword_results)
        except Exception:
            # 语义搜索失败时，使用关键词搜索
            memory_items = self.db.search_memory_items(query, limit=10)

        # 2. 使用令牌优化器优化检索
        from .token_optimizer import ProgressiveRetrievalOptimizer, ContextPrioritizer

        # 优先级排序
        prioritized_items = ContextPrioritizer.prioritize_items(memory_items, query)

        # 优化检索
        optimizer = ProgressiveRetrievalOptimizer(max_tokens=max_tokens)
        optimized_context = optimizer.optimize_retrieval(prioritized_items, query)

        return optimized_context


class EnhancedMemorySystem:
    """
    增强记忆系统

    功能：
    - 跨会话持久记忆
    - 智能记忆压缩
    - 语义搜索能力
    - 渐进式记忆检索
    """

    def __init__(self, db_path: str | Path = None, vector_store_path: str | Path = None):
        from core.config import get_config_dir

        if db_path is None:
            db_path = get_config_dir() / "enhanced_memory.db"
        if vector_store_path is None:
            vector_store_path = get_config_dir() / "vector_store"

        self.db = EnhancedMemoryDatabase(db_path)
        self.compressor = MemoryCompressor()
        from .embedding import EnhancedVectorStore
        self.vector_store = EnhancedVectorStore(vector_store_path)
        self.retriever = ProgressiveRetriever(self.db, self.vector_store)

        # 配置
        self.config = {
            "auto_compress": True,
            "max_content_length": 5000,
            "summary_length": 100,
            "embedding_dim": 128,  # 简化版，实际应使用真实的嵌入模型
        }

        # 当前会话
        self.current_session: Optional[Session] = None

    def start_session(self, metadata: Dict[str, Any] = None) -> str:
        """开始新会话"""
        self.current_session = Session(
            metadata=metadata or {}
        )
        return self.db.save_session(self.current_session)

    def end_session(self, summary: str = "") -> str:
        """结束当前会话"""
        if not self.current_session:
            return ""

        self.current_session.end_time = time.time()
        self.current_session.summary = summary
        return self.db.save_session(self.current_session)

    def add_memory(self, content: str, tags: List[str] = None) -> str:
        """添加记忆"""
        # 评估价值
        value_level = self._assess_value(content)

        # 压缩内容
        compressed_content = self.compressor.compress_content(content)
        summary = self.compressor.generate_summary(content)

        # 提取关键词
        keywords = self._extract_keywords(content)

        # 创建记忆项
        item = MemoryItem(
            content=content[:self.config["max_content_length"]],
            compressed_content=compressed_content,
            summary=summary,
            keywords=keywords,
            value_level=value_level.value,
            tags=tags or []
        )

        # 保存
        item_id = self.db.save_memory_item(item)

        # 生成并存储嵌入向量
        self.vector_store.add_item(item_id, content)

        # 添加到当前会话
        if self.current_session:
            self.current_session.memory_item_ids.append(item_id)
            self.db.save_session(self.current_session)

        return item_id

    def search_memory(self, query: str, limit: int = 10, use_semantic: bool = True) -> List[MemoryItem]:
        """搜索记忆"""
        if not use_semantic:
            return self.db.search_memory_items(query, limit=limit)

        # 语义搜索
        semantic_results = self.vector_store.search(query, top_k=limit)
        semantic_item_ids = [result['item_id'] for result in semantic_results]

        # 关键词搜索
        keyword_results = self.db.search_memory_items(query, limit=limit)
        keyword_item_ids = [item.id for item in keyword_results]

        # 合并结果，去重，优先语义搜索结果
        combined_item_ids = []
        seen_ids = set()

        # 先添加语义搜索结果
        for item_id in semantic_item_ids:
            if item_id not in seen_ids:
                combined_item_ids.append(item_id)
                seen_ids.add(item_id)

        # 再添加关键词搜索结果
        for item_id in keyword_item_ids:
            if item_id not in seen_ids and len(combined_item_ids) < limit:
                combined_item_ids.append(item_id)
                seen_ids.add(item_id)

        # 获取记忆项
        memory_items = []
        for item_id in combined_item_ids:
            item = self.db.get_memory_item(item_id)
            if item:
                memory_items.append(item)

        return memory_items

    def retrieve_context(
        self,
        query: str,
        max_tokens: int = 2000,
        include_full_content: bool = False
    ) -> Dict[str, Any]:
        """检索上下文"""
        return self.retriever.retrieve_context(
            query,
            max_tokens=max_tokens,
            include_full_content=include_full_content
        )

    def get_recent_sessions(self, limit: int = 5) -> List[Session]:
        """获取最近的会话"""
        return self.db.get_recent_sessions(limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        db_stats = self.db.get_stats()
        return {
            **db_stats,
            "config": self.config
        }

    def _assess_value(self, text: str) -> MemoryValue:
        """评估文本价值"""
        # 简单的价值评估
        text_lower = text.lower()

        # 高价值模式
        high_value_patterns = [
            r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}",  # 日期
            r"\d+[万千万亿]?元",  # 金额
            r"电话|手机|邮箱|地址|账号",  # 联系方式
            r"项目|产品|功能|版本|发布",  # 项目相关
            r"API|SDK|配置|参数|设置",  # 技术配置
            r"决策|策略|方案|计划|目标",  # 决策相关
        ]

        # 低价值模式
        low_value_patterns = [
            r"^(你好|谢谢|是的|不是|可能|也许)",  # 简单寒暄
            r"^(哈哈|嗯嗯|好的)$",  # 敷衍回复
            r"^那|那好吧|随便",  # 无意义回应
        ]

        # 检查低价值模式
        for pattern in low_value_patterns:
            if re.match(pattern, text.strip()):
                return MemoryValue.LOW

        # 检查高价值模式
        for pattern in high_value_patterns:
            if re.search(pattern, text):
                return MemoryValue.HIGH

        # 检查问题-答案对
        if "?" in text or "？" in text:
            return MemoryValue.MEDIUM

        return MemoryValue.LOW

    def _extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """提取关键词"""
        # 简单实现：去除停用词后取高频词
        stopwords = {
            "的", "是", "在", "有", "和", "与", "了", "我", "你", "他",
            "她", "它", "这", "那", "个", "一", "不", "也", "都", "要",
            "就", "可以", "会", "能", "对", "但", "而", "或", "如果"
        }

        # 分词（简单按标点和空格分）
        words = re.findall(r"[\u4e00-\u9fa5]+|[A-Za-z]\w*", text)

        # 过滤和计数
        word_freq = {}
        for word in words:
            if len(word) >= 2 and word not in stopwords:
                word_freq[word] = word_freq.get(word, 0) + 1

        # 排序取top
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:top_n]]


# 单例
_enhanced_memory_system: Optional[EnhancedMemorySystem] = None


def get_enhanced_memory_system() -> EnhancedMemorySystem:
    """获取增强记忆系统单例"""
    global _enhanced_memory_system
    if _enhanced_memory_system is None:
        _enhanced_memory_system = EnhancedMemorySystem()
    return _enhanced_memory_system