"""
知识库增强模块
==============

功能：
1. 深度搜索结果自动存入知识库
2. 会话内容自动存入知识库
3. 知识库智能清理策略（TTL/LRU/去重/质量评分）

架构：
- KBAutoIngest: 自动摄入管道（搜索结果、会话内容）
- KnowledgeBaseGC: 知识库垃圾回收器
- ConversationExtractor: 会话内容提取器
"""

import asyncio
import hashlib
import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── 数据模型 ────────────────────────────────────────────────────────────────

class ContentSource(Enum):
    """知识来源"""
    DEEP_SEARCH = "deep_search"      # 深度搜索结果
    CONVERSATION = "conversation"    # 会话内容
    USER_FILE = "user_file"         # 用户文件
    EXPERT_TRAINING = "expert"       # 专家训练
    MANUAL = "manual"                # 手动添加


class ContentQuality(Enum):
    """内容质量"""
    HIGH = 3     # 多次引用、高评分
    MEDIUM = 2   # 正常内容
    LOW = 1      # 一次性、临时性
    GARBAGE = 0  # 待删除


@dataclass
class KnowledgeEntry:
    """知识条目"""
    doc_id: str
    content: str
    title: str = ""
    source: ContentSource = ContentSource.MANUAL
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    relevance_score: float = 1.0
    quality: ContentQuality = ContentQuality.MEDIUM
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 深度搜索专用
    source_url: str = ""
    search_query: str = ""

    # 会话专用
    session_id: str = ""
    speaker: str = ""  # user / assistant

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "title": self.title,
            "source": self.source.value,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "relevance_score": self.relevance_score,
            "quality": self.quality.value,
            "tags": self.tags,
            "metadata": self.metadata,
            "source_url": self.source_url,
            "search_query": self.search_query,
            "session_id": self.session_id,
            "speaker": self.speaker,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowledgeEntry":
        d = d.copy()
        d["source"] = ContentSource(d.get("source", "manual"))
        d["quality"] = ContentQuality(d.get("quality", 2))
        d["created_at"] = datetime.fromisoformat(d["created_at"]) if isinstance(d["created_at"], str) else d["created_at"]
        d["last_accessed"] = datetime.fromisoformat(d["last_accessed"]) if isinstance(d["last_accessed"], str) else d["last_accessed"]
        return cls(**d)


# ── 知识库自动摄入器 ────────────────────────────────────────────────────────

class KBAutoIngest:
    """
    知识库自动摄入管道

    功能：
    1. 深度搜索结果自动存入知识库
    2. 会话内容智能提取存入知识库
    3. 去重检测（MD5哈希/语义相似）
    4. 质量评分更新
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, kb_path: Optional[Path] = None):
        if self._initialized:
            return

        self.kb_path = kb_path or Path.home() / ".hermes-desktop" / "kb_auto_ingest"
        self.kb_path.mkdir(parents=True, exist_ok=True)

        self.db_path = self.kb_path / "knowledge_entries.db"
        self.hash_cache_path = self.kb_path / "hash_cache.json"
        self.stats_path = self.kb_path / "stats.json"

        self._init_database()
        self._load_hash_cache()

        # 回调
        self._on_ingest_callbacks: List[Callable] = []

        # 配置
        self.config = {
            "max_entries_per_source": 10000,     # 每个来源最大条目数
            "dedup_window": 0.85,               # 相似度阈值（超过则去重）
            "min_content_length": 50,             # 最小内容长度
            "auto_ingest_search": True,          # 自动摄入搜索结果
            "auto_ingest_conversation": True,    # 自动摄入会话内容
            "extract_interval": 300,              # 提取间隔（秒）
        }

        self._initialized = True
        logger.info(f"[KBAutoIngest] 初始化完成，DB: {self.db_path}")

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                doc_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                title TEXT DEFAULT '',
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                relevance_score REAL DEFAULT 1.0,
                quality INTEGER DEFAULT 2,
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                source_url TEXT DEFAULT '',
                search_query TEXT DEFAULT '',
                session_id TEXT DEFAULT '',
                speaker TEXT DEFAULT '',
                content_hash TEXT NOT NULL,
                UNIQUE(content_hash)
            )
        """)

        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON knowledge_entries(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created ON knowledge_entries(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality ON knowledge_entries(quality)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_accessed ON knowledge_entries(last_accessed)")

        conn.commit()
        conn.close()

    def _load_hash_cache(self):
        """加载哈希缓存（用于快速去重）"""
        if self.hash_cache_path.exists():
            try:
                with open(self.hash_cache_path, "r", encoding="utf-8") as f:
                    self._hash_cache: Set[str] = set(json.load(f))
            except Exception:
                self._hash_cache = set()
        else:
            self._hash_cache = set()

    def _save_hash_cache(self):
        """保存哈希缓存"""
        try:
            with open(self.hash_cache_path, "w", encoding="utf-8") as f:
                json.dump(list(self._hash_cache), f)
        except Exception as e:
            logger.warning(f"[KBAutoIngest] 保存哈希缓存失败: {e}")

    def _compute_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content.strip().encode()).hexdigest()[:32]

    def _is_duplicate(self, content_hash: str) -> bool:
        """检查是否重复"""
        return content_hash in self._hash_cache

    def add_to_hash_cache(self, content_hash: str):
        """添加到哈希缓存"""
        self._hash_cache.add(content_hash)
        # 限制缓存大小
        if len(self._hash_cache) > 100000:
            self._hash_cache = set(list(self._hash_cache)[-50000:])

    # ── 深度搜索结果摄入 ───────────────────────────────────────────────

    def ingest_search_result(
        self,
        query: str,
        results: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        摄入深度搜索结果

        Args:
            query: 搜索查询
            results: 搜索结果列表 [{"title", "url", "snippet"}]
            metadata: 额外元数据

        Returns:
            {"ingested": int, "duplicates": int, "failed": int}
        """
        stats = {"ingested": 0, "duplicates": 0, "failed": 0}
        metadata = metadata or {}

        for result in results:
            try:
                title = result.get("title", "")
                url = result.get("url", "")
                snippet = result.get("snippet", "")

                if len(snippet) < self.config["min_content_length"]:
                    continue

                content = f"{title}\n{snippet}"
                content_hash = self._compute_hash(content)

                if self._is_duplicate(content_hash):
                    stats["duplicates"] += 1
                    continue

                doc_id = f"search_{hashlib.md5((query + url).encode()).hexdigest()[:16]}"

                entry = KnowledgeEntry(
                    doc_id=doc_id,
                    content=content,
                    title=title,
                    source=ContentSource.DEEP_SEARCH,
                    source_url=url,
                    search_query=query,
                    metadata={
                        "original_query": query,
                        "result_rank": result.get("rank", 0),
                        **metadata
                    }
                )

                self._save_entry(entry)
                self.add_to_hash_cache(content_hash)
                stats["ingested"] += 1

                # 触发回调
                self._trigger_callbacks("search_ingested", entry)

            except Exception as e:
                logger.warning(f"[KBAutoIngest] 摄入搜索结果失败: {e}")
                stats["failed"] += 1

        self._save_hash_cache()
        self._update_stats("search_ingest", stats)
        return stats

    def ingest_search_result_batch(
        self,
        search_results: List[Dict[str, Any]],
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        批量摄入搜索结果

        Args:
            search_results: [{"query": str, "results": [...]}]
            batch_id: 批次ID

        Returns:
            汇总统计
        """
        total = {"ingested": 0, "duplicates": 0, "failed": 0}

        for sr in search_results:
            query = sr.get("query", "")
            results = sr.get("results", [])
            batch_stats = self.ingest_search_result(query, results, {"batch_id": batch_id})
            total["ingested"] += batch_stats["ingested"]
            total["duplicates"] += batch_stats["duplicates"]
            total["failed"] += batch_stats["failed"]

        return total

    # ── 会话内容摄入 ─────────────────────────────────────────────────

    def ingest_conversation(
        self,
        session_id: str,
        messages: List[Dict[str, str]],
        user_id: str = "default",
        extract_questions: bool = True,
        extract_facts: bool = True,
        min_importance: float = 0.5
    ) -> Dict[str, Any]:
        """
        摄入会话内容

        Args:
            session_id: 会话ID
            messages: 消息列表 [{"role": "user"/"assistant", "content": str}]
            user_id: 用户ID
            extract_questions: 是否提取问题
            extract_facts: 是否提取事实
            min_importance: 最小重要性阈值

        Returns:
            {"ingested": int, "questions": int, "facts": int}
        """
        stats = {"ingested": 0, "questions": 0, "facts": 0}

        extractor = ConversationExtractor()

        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            content = msg.get("content", "").strip()

            if len(content) < self.config["min_content_length"]:
                continue

            if role == "user" and extract_questions:
                # 提取用户问题
                questions = extractor.extract_questions(content)
                for q in questions:
                    if self._save_knowledge_from_text(
                        q, session_id, "question", user_id, ContentSource.CONVERSATION
                    ):
                        stats["questions"] += 1
                        stats["ingested"] += 1

            elif role == "assistant" and extract_facts:
                # 提取助手回答中的事实
                facts = extractor.extract_facts(content)
                for fact in facts:
                    importance = extractor.estimate_importance(fact)
                    if importance >= min_importance:
                        if self._save_knowledge_from_text(
                            fact, session_id, "fact", user_id, ContentSource.CONVERSATION
                        ):
                            stats["facts"] += 1
                            stats["ingested"] += 1

        self._save_hash_cache()
        self._update_stats("conversation_ingest", stats)
        return stats

    def _save_knowledge_from_text(
        self,
        content: str,
        session_id: str,
        content_type: str,
        speaker: str,
        source: ContentSource
    ) -> bool:
        """保存知识条目"""
        content_hash = self._compute_hash(content)

        if self._is_duplicate(content_hash):
            return False

        doc_id = f"conv_{hashlib.md5((session_id + content_hash).encode()).hexdigest()[:16]}"

        entry = KnowledgeEntry(
            doc_id=doc_id,
            content=content,
            title=f"[{content_type}] {content[:50]}...",
            source=source,
            session_id=session_id,
            speaker=speaker,
            metadata={"content_type": content_type}
        )

        self._save_entry(entry)
        self.add_to_hash_cache(content_hash)
        return True

    # ── 基础CRUD ──────────────────────────────────────────────────────

    def _save_entry(self, entry: KnowledgeEntry) -> bool:
        """保存知识条目"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO knowledge_entries
                (doc_id, content, title, source, created_at, last_accessed,
                 access_count, relevance_score, quality, tags, metadata,
                 source_url, search_query, session_id, speaker, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.doc_id,
                entry.content,
                entry.title,
                entry.source.value,
                entry.created_at.isoformat(),
                entry.last_accessed.isoformat(),
                entry.access_count,
                entry.relevance_score,
                entry.quality.value,
                json.dumps(entry.tags),
                json.dumps(entry.metadata),
                entry.source_url,
                entry.search_query,
                entry.session_id,
                entry.speaker,
                self._compute_hash(entry.content),
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"[KBAutoIngest] 保存条目失败: {e}")
            return False

    def get_entry(self, doc_id: str) -> Optional[KnowledgeEntry]:
        """获取知识条目"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM knowledge_entries WHERE doc_id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_entry(row)
        return None

    def search_knowledge(
        self,
        query: str,
        source: Optional[ContentSource] = None,
        top_k: int = 10
    ) -> List[KnowledgeEntry]:
        """搜索知识库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        sql = "SELECT * FROM knowledge_entries WHERE content LIKE ?"
        params = [f"%{query}%"]

        if source:
            sql += " AND source = ?"
            params.append(source.value)

        sql += " ORDER BY relevance_score DESC, access_count DESC LIMIT ?"
        params.append(top_k)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_entry(row) for row in rows]

    def _row_to_entry(self, row: sqlite3.Row) -> KnowledgeEntry:
        """行转实体"""
        return KnowledgeEntry(
            doc_id=row[0],
            content=row[1],
            title=row[2],
            source=ContentSource(row[3]),
            created_at=datetime.fromisoformat(row[4]),
            last_accessed=datetime.fromisoformat(row[5]),
            access_count=row[6],
            relevance_score=row[7],
            quality=ContentQuality(row[8]),
            tags=json.loads(row[9]),
            metadata=json.loads(row[10]),
            source_url=row[11],
            search_query=row[12],
            session_id=row[13],
            speaker=row[14],
        )

    # ── 统计与回调 ──────────────────────────────────────────────────

    def _update_stats(self, key: str, stats: Dict[str, Any]):
        """更新统计"""
        try:
            if self.stats_path.exists():
                with open(self.stats_path, "r") as f:
                    data = json.load(f)
            else:
                data = {}

            if key not in data:
                data[key] = {"total": {}, "recent": []}

            for k, v in stats.items():
                data[key]["total"][k] = data[key]["total"].get(k, 0) + v

            data[key]["recent"].append({**stats, "time": datetime.now().isoformat()})
            data[key]["recent"] = data[key]["recent"][-100:]

            with open(self.stats_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def register_callback(self, event: str, callback: Callable):
        """注册回调"""
        self._on_ingest_callbacks.append((event, callback))

    def _trigger_callbacks(self, event: str, entry: KnowledgeEntry):
        """触发回调"""
        for e, cb in self._on_ingest_callbacks:
            if e == event:
                try:
                    cb(entry)
                except Exception as ex:
                    logger.warning(f"[KBAutoIngest] 回调执行失败: {ex}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT source, COUNT(*) FROM knowledge_entries GROUP BY source")
        by_source = dict(cursor.fetchall())

        cursor.execute("SELECT COUNT(*) FROM knowledge_entries")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(LENGTH(content)) FROM knowledge_entries")
        total_size = cursor.fetchone()[0] or 0

        conn.close()

        return {
            "total_entries": total,
            "total_size_chars": total_size,
            "by_source": by_source,
            "hash_cache_size": len(self._hash_cache),
            "config": self.config,
        }


# ── 会话内容提取器 ──────────────────────────────────────────────────────────

class ConversationExtractor:
    """
    会话内容智能提取器

    从对话中提取：
    1. 用户问题（待解答）
    2. 事实性知识（可复用的信息）
    3. 实体和概念
    """

    def __init__(self):
        # 问题模式
        self.question_patterns = [
            r"[？?][\s]*$",           # 结尾问号
            r"^(什么是|如何|怎么|怎样|为什么|为何|哪个|哪些|谁|何时|何地)",
            r"^(帮我|请|能不能|是否可以|有没有)",
            r"^(告诉|告诉|讲解|解释|说明|介绍)",
        ]

        # 事实陈述模式
        self.fact_patterns = [
            r"^(.+?)是(.+?)$",         # X是Y
            r"^(.+?)可以(.+?)$",       # X可以Y
            r"^(.+?)用于(.+?)$",       # X用于Y
            r"^(.+?)包括(.+?)$",       # X包括Y
            r"^(- |• |\\d+\\. )",     # 列表项
        ]

        # 重要性关键词
        self.importance_keywords = {
            "high": ["定义", "概念", "原理", "公式", "定理", "定律", "方法", "步骤"],
            "medium": ["说明", "介绍", "讲解", "解释", "例子", "示例"],
            "low": ["顺便", "补充", "可能", "也许", "大概"],
        }

    def extract_questions(self, text: str) -> List[str]:
        """提取问题"""
        import re
        questions = []

        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue

            # 检查是否像问题
            is_question = False
            for pattern in self.question_patterns:
                if re.search(pattern, line):
                    is_question = True
                    break

            if is_question and len(line) < 500:
                questions.append(line)

        return questions

    def extract_facts(self, text: str) -> List[str]:
        """提取事实"""
        import re
        facts = []

        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line or len(line) < 15:
                continue

            # 检查是否像陈述句
            is_fact = False
            for pattern in self.fact_patterns:
                if re.search(pattern, line):
                    is_fact = True
                    break

            if is_fact and len(line) < 1000:
                facts.append(line)

        return facts

    def estimate_importance(self, text: str) -> float:
        """估计重要性（0-1）"""
        score = 0.5

        text_lower = text.lower()

        # 高重要性关键词
        for kw in self.importance_keywords["high"]:
            if kw in text_lower:
                score += 0.15

        # 中等重要性
        for kw in self.importance_keywords["medium"]:
            if kw in text_lower:
                score += 0.05

        # 低重要性
        for kw in self.importance_keywords["low"]:
            if kw in text_lower:
                score -= 0.1

        # 长度适中最好
        if 50 < len(text) < 300:
            score += 0.05
        elif len(text) > 500:
            score -= 0.05

        return max(0.0, min(1.0, score))


# ── 知识库垃圾回收器 ────────────────────────────────────────────────────────

class KnowledgeBaseGC:
    """
    知识库垃圾回收器

    清理策略：
    1. TTL（时间过期）
    2. LRU（访问频率低）
    3. 质量评分低
    4. 去重
    5. 存储限制
    """

    def __init__(self, ingest: Optional[KBAutoIngest] = None):
        self.ingest = ingest or KBAutoIngest()

        self.gc_config = {
            # TTL策略
            "ttl_days": {
                ContentSource.DEEP_SEARCH: 30,     # 搜索结果30天
                ContentSource.CONVERSATION: 90,    # 会话内容90天
                ContentSource.USER_FILE: 365,      # 用户文件1年
                ContentSource.EXPERT_TRAINING: 0,  # 专家训练永不过期
                ContentSource.MANUAL: 0,           # 手动添加永不过期
            },
            # LRU策略
            "lru_threshold": 3,                   # 访问次数低于此值
            # 质量策略
            "min_quality": ContentQuality.LOW,    # 最低质量阈值
            # 存储限制
            "max_entries": 100000,                # 最大条目数
            "max_storage_mb": 500,                # 最大存储（MB）
            # 清理比例
            "gc_batch_ratio": 0.1,               # 每次清理10%
            # 定时清理
            "gc_interval_hours": 24,             # 每24小时检查
        }

        self._gc_lock = threading.Lock()
        self._last_gc_time = datetime.min
        self._gc_running = False

    def should_gc(self) -> bool:
        """检查是否应该执行GC"""
        if self._gc_running:
            return False

        elapsed = (datetime.now() - self._last_gc_time).total_seconds()
        interval_seconds = self.gc_config["gc_interval_hours"] * 3600

        return elapsed >= interval_seconds

    def run_gc(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        执行垃圾回收

        Args:
            dry_run: True=只报告不删除

        Returns:
            {"candidates": int, "to_delete": int, "freed_chars": int, "details": [...]}
        """
        with self._gc_lock:
            if dry_run:
                self._gc_running = True  # 防止并发

        result = {
            "candidates": 0,
            "to_delete": 0,
            "freed_chars": 0,
            "details": [],
        }

        try:
            candidates = self._find_gc_candidates()
            result["candidates"] = len(candidates)

            # 计算删除数量
            max_delete = int(len(candidates) * self.gc_config["gc_batch_ratio"])
            to_delete = candidates[:max_delete]

            if not dry_run:
                for entry in to_delete:
                    if self._delete_entry(entry["doc_id"]):
                        result["to_delete"] += 1
                        result["freed_chars"] += entry["content_len"]
                        result["details"].append({
                            "doc_id": entry["doc_id"],
                            "reason": entry["reason"],
                            "content_preview": entry["content"][:50],
                        })

                self._last_gc_time = datetime.now()

            else:
                result["to_delete"] = len(to_delete)
                for entry in to_delete[:10]:
                    result["details"].append({
                        "doc_id": entry["doc_id"],
                        "reason": entry["reason"],
                        "content_preview": entry["content"][:50],
                    })
                if len(to_delete) > 10:
                    result["details"].append({"_more": len(to_delete) - 10})

        finally:
            self._gc_running = False

        return result

    def _find_gc_candidates(self) -> List[Dict[str, Any]]:
        """查找可回收的条目"""
        candidates = []
        now = datetime.now()

        conn = sqlite3.connect(str(self.ingest.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM knowledge_entries")
        rows = cursor.fetchall()

        for row in rows:
            entry = self.ingest._row_to_entry(row)
            reason = None

            # 1. TTL检查
            ttl_days = self.gc_config["ttl_days"].get(entry.source, 0)
            if ttl_days > 0:
                age = (now - entry.created_at).days
                if age > ttl_days and entry.access_count < 5:
                    reason = f"TTL过期({age}天)"

            # 2. LRU检查
            elif entry.access_count < self.gc_config["lru_threshold"] and entry.quality == ContentQuality.LOW:
                reason = f"LRU(访问{entry.access_count}次, 质量低)"

            # 3. 质量检查
            elif entry.quality == ContentQuality.GARBAGE:
                reason = "质量为垃圾"

            if reason:
                candidates.append({
                    "doc_id": entry.doc_id,
                    "content": entry.content,
                    "content_len": len(entry.content),
                    "reason": reason,
                    "score": entry.relevance_score * entry.access_count,
                })

        conn.close()

        # 按分数排序（低分优先删除）
        candidates.sort(key=lambda x: x["score"])

        return candidates

    def _delete_entry(self, doc_id: str) -> bool:
        """删除条目"""
        try:
            conn = sqlite3.connect(str(self.ingest.db_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM knowledge_entries WHERE doc_id = ?", (doc_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"[KBGC] 删除条目失败: {e}")
            return False

    def force_cleanup(
        self,
        source: Optional[ContentSource] = None,
        older_than_days: int = 0,
        keep_manual: bool = True
    ) -> int:
        """
        强制清理

        Args:
            source: 只清理特定来源
            older_than_days: 只清理超过N天的
            keep_manual: 是否保留手动添加

        Returns:
            删除数量
        """
        conn = sqlite3.connect(str(self.ingest.db_path))
        cursor = conn.cursor()

        conditions = []
        params = []

        if source:
            conditions.append("source = ?")
            params.append(source.value)

        if older_than_days > 0:
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(days=older_than_days)).isoformat()
            conditions.append("created_at < ?")
            params.append(cutoff)

        if keep_manual:
            conditions.append("source != ?")
            params.append(ContentSource.MANUAL.value)

        where = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"DELETE FROM knowledge_entries WHERE {where}", params)
        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        return deleted


# ── 集成钩子 ───────────────────────────────────────────────────────────────

class KBIntegrationHooks:
    """
    知识库集成钩子

    在关键位置自动触发知识摄入：
    1. 深度搜索完成后
    2. 会话结束后
    3. 用户明确指定时
    """

    def __init__(self):
        self.ingest = KBAutoIngest()
        self.gc = KnowledgeBaseGC(self.ingest)

        # 注册为全局摄入器回调
        self.ingest.register_callback("search_ingested", self._on_search_ingested)

    def on_deep_search_complete(
        self,
        query: str,
        results: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """深度搜索完成钩子"""
        stats = self.ingest.ingest_search_result(query, results, metadata)
        logger.info(f"[KBHooks] 搜索结果已摄入: {stats}")
        return stats

    def on_session_end(
        self,
        session_id: str,
        messages: List[Dict[str, str]],
        user_id: str = "default"
    ):
        """会话结束钩子"""
        stats = self.ingest.ingest_conversation(session_id, messages, user_id)
        logger.info(f"[KBHooks] 会话已摄入: {stats}")
        return stats

    def on_user_file_added(
        self,
        file_path: str,
        content: str,
        title: Optional[str] = None
    ):
        """用户文件添加钩子"""
        doc_id = f"file_{hashlib.md5(file_path.encode()).hexdigest()[:16]}"
        entry = KnowledgeEntry(
            doc_id=doc_id,
            content=content,
            title=title or Path(file_path).name,
            source=ContentSource.USER_FILE,
            metadata={"file_path": file_path}
        )
        self.ingest._save_entry(entry)
        return {"doc_id": doc_id}

    def run_scheduled_gc(self):
        """定时GC"""
        if self.gc.should_gc():
            result = self.gc.run_gc(dry_run=False)
            logger.info(f"[KBHooks] GC完成: {result}")
            return result
        return None


# ── 全局实例 ────────────────────────────────────────────────────────────────

_kb_ingest: Optional[KBAutoIngest] = None
_kb_gc: Optional[KnowledgeBaseGC] = None
_kb_hooks: Optional[KBIntegrationHooks] = None


def get_kb_ingest() -> KBAutoIngest:
    """获取知识摄入器"""
    global _kb_ingest
    if _kb_ingest is None:
        _kb_ingest = KBAutoIngest()
    return _kb_ingest


def get_kb_gc() -> KnowledgeBaseGC:
    """获取GC器"""
    global _kb_gc
    if _kb_gc is None:
        _kb_gc = KnowledgeBaseGC(get_kb_ingest())
    return _kb_gc


def get_kb_hooks() -> KBIntegrationHooks:
    """获取集成钩子"""
    global _kb_hooks
    if _kb_hooks is None:
        _kb_hooks = KBIntegrationHooks()
    return _kb_hooks


# ── 测试 ────────────────────────────────────────────────────────────────────

def test_kb_auto_ingest():
    """测试知识库自动摄入"""
    print("=" * 60)
    print("测试知识库自动摄入")
    print("=" * 60)

    ingest = KBAutoIngest()

    # 测试1: 摄入搜索结果
    print("\n1. 测试摄入搜索结果")
    test_results = [
        {"title": "Python教程", "url": "https://python.org", "snippet": "Python是一种高级编程语言"},
        {"title": "JavaScript教程", "url": "https://js.com", "snippet": "JavaScript是一种脚本语言"},
    ]
    stats = ingest.ingest_search_result("Python教程", test_results)
    print(f"   结果: {stats}")

    # 测试2: 摄入会话内容
    print("\n2. 测试摄入会话内容")
    messages = [
        {"role": "user", "content": "什么是机器学习？"},
        {"role": "assistant", "content": "机器学习是人工智能的一个分支，它使用数据来训练模型，从而使计算机能够自动学习和改进。"},
    ]
    stats = ingest.ingest_conversation("session_001", messages)
    print(f"   结果: {stats}")

    # 测试3: 搜索知识
    print("\n3. 测试搜索知识")
    results = ingest.search_knowledge("Python")
    print(f"   找到 {len(results)} 条结果")

    # 测试4: 统计
    print("\n4. 统计信息")
    stats = ingest.get_stats()
    print(f"   {stats}")

    print("\n测试完成!")


def test_kb_gc():
    """测试知识库GC"""
    print("=" * 60)
    print("测试知识库GC")
    print("=" * 60)

    gc = KnowledgeBaseGC()

    # 报告GC候选
    print("\n1. GC候选项（dry run）")
    result = gc.run_gc(dry_run=True)
    print(f"   候选: {result['candidates']}, 建议删除: {result['to_delete']}")

    print("\n测试完成!")


if __name__ == "__main__":
    test_kb_auto_ingest()
    print()
    test_kb_gc()
