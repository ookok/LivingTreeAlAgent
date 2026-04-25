"""
知识库创新增强模块
==================

5条创新功能：
1. 语义去重引擎 (SemanticDeduplicator) - 基于向量相似度检测语义重复
2. 知识价值评估系统 (KnowledgeValueScorer) - 多维度评分机制
3. 主动学习触发器 (ActiveLearningTrigger) - 自动发现问题并生成知识
4. 知识图谱增强 (KnowledgeGraphEnhancer) - 自动关系提取和实体链接
5. 遗忘机制 + 强化复习 (ForgettingMechanism) - 类人类记忆的强化学习

Author: Hermes Desktop Team
"""

import asyncio
import hashlib
import json
import logging
import math
import re
import sqlite3
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 第一部分：语义去重引擎
# ══════════════════════════════════════════════════════════════════════════════

class SemanticDeduplicator:
    """
    语义去重引擎
    =============

    现有问题：MD5哈希只能检测完全相同的内容
    创新方案：基于向量嵌入 + 余弦相似度，检测语义相似的内容

    核心逻辑：
    1. 对内容进行向量化
    2. 计算余弦相似度
    3. 相似度 > 阈值（如0.85）→ 判定为重复

    适用场景：
    - 同一概念的不同表述
    - 同一问题的不同问法
    - 同一事实的不同描述
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, embedding_model: str = "qwen2.5:1.5b"):
        if self._initialized:
            return

        self.embedding_model = embedding_model
        self.cache_path = Path.home() / ".hermes-desktop" / "kb_semantic_cache"
        self.cache_path.mkdir(parents=True, exist_ok=True)

        # 相似度配置
        self.config = {
            "similarity_threshold": 0.85,      # 相似度阈值
            "min_text_length": 50,              # 最小文本长度
            "embedding_batch_size": 10,         # 批处理大小
            "use_llm_fallback": True,            # LLM兜底
        }

        # 向量缓存：doc_id → vector
        self._vector_cache: Dict[str, List[float]] = {}
        self._text_cache: Dict[str, str] = {}  # doc_id → text
        self._embedding_lock = threading.Lock()

        self._load_cache()
        self._initialized = True
        logger.info("[SemanticDedup] 语义去重引擎初始化完成")

    def _load_cache(self):
        """加载向量缓存"""
        cache_file = self.cache_path / "vectors.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._vector_cache = {k: v for k, v in data.items()}
            except Exception as e:
                logger.warning(f"[SemanticDedup] 加载缓存失败: {e}")

    def _save_cache(self):
        """保存向量缓存"""
        try:
            cache_file = self.cache_path / "vectors.json"
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self._vector_cache, f)
        except Exception as e:
            logger.warning(f"[SemanticDedup] 保存缓存失败: {e}")

    def _compute_text_hash(self, text: str) -> str:
        """计算文本哈希（快速预检）"""
        return hashlib.sha256(text.strip().encode()).hexdigest()[:16]

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        获取文本向量

        策略：
        1. 短文本 → 关键词哈希向量化（快速）
        2. 长文本 → LLM向量化（精确）
        """
        # 缓存检查
        text_hash = self._compute_text_hash(text)
        if text_hash in self._vector_cache:
            return self._vector_cache[text_hash]

        # 短文本：使用关键词哈希向量化
        if len(text) < 200:
            vector = self._keyword_hash_vector(text)
        else:
            # 长文本：使用 LLM 向量化
            vector = self._llm_embedding(text)

        if vector:
            with self._embedding_lock:
                self._vector_cache[text_hash] = vector
                # 限制缓存大小
                if len(self._vector_cache) > 10000:
                    # 删除最老的 50%
                    keys = list(self._vector_cache.keys())
                    for k in keys[:5000]:
                        del self._vector_cache[k]

        return vector

    def _keyword_hash_vector(self, text: str) -> List[float]:
        """
        关键词哈希向量化（快速方法）

        将文本分成词汇，映射到固定维度的向量空间
        使用词频和位置权重
        """
        # 中文分词（简单实现）
        words = self._tokenize(text)

        # 停用词
        stopwords = {"的", "了", "是", "在", "和", "与", "或", "以及", "等", "于", "对", "为", "有", "可", "这", "那"}

        # 词频统计
        word_freq = defaultdict(int)
        for i, w in enumerate(words):
            if w not in stopwords and len(w) > 1:
                # 位置权重：越靠前的词权重越高
                weight = 1.0 / (i + 1)
                word_freq[w] += weight

        # 固定维度向量（512维）
        dim = 512
        vector = [0.0] * dim

        # 将词哈希到向量空间
        for word, freq in word_freq.items():
            word_hash = int(hashlib.md5(word.encode()).hexdigest()[:8], 16)
            for i in range(4):  # 每个词影响4个维度
                idx = (word_hash + i) % dim
                vector[idx] += freq * (1 if i % 2 == 0 else -1)

        # L2归一化
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        # 移除标点
        text = re.sub(r"[^\w\s]", " ", text)
        # 分割
        words = re.findall(r"[\w]+", text)
        return words

    def _llm_embedding(self, text: str) -> Optional[List[float]]:
        """LLM向量化（精确方法）"""
        try:
            # 使用 Ollama 获取嵌入
            from core.ollama_client import OllamaClient
            client = OllamaClient()

            # Ollama 的 embeddings API
            response = client._session.post(
                f"{client._base_url}/api/embeddings",
                json={"model": self.embedding_model, "prompt": text[:1000]}
            )

            if response.status_code == 200:
                return response.json().get("embedding")

        except Exception as e:
            logger.warning(f"[SemanticDedup] LLM向量化失败: {e}")

        # 降级到关键词方法
        return self._keyword_hash_vector(text)

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """计算余弦相似度"""
        if len(v1) != len(v2):
            return 0.0

        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot / (norm1 * norm2)

    def is_duplicate(
        self,
        new_text: str,
        existing_texts: List[Tuple[str, str]],  # [(doc_id, text)]
        threshold: Optional[float] = None
    ) -> Tuple[bool, Optional[str], float]:
        """
        检查新文本是否与已有文本重复

        Args:
            new_text: 新文本
            existing_texts: 已有文本列表 [(doc_id, text)]
            threshold: 自定义阈值（默认使用配置）

        Returns:
            (is_duplicate, duplicate_doc_id, similarity_score)
        """
        if len(new_text) < self.config["min_text_length"]:
            return False, None, 0.0

        threshold = threshold or self.config["similarity_threshold"]
        new_vector = self._get_embedding(new_text)

        if not new_vector:
            return False, None, 0.0

        best_match = (None, 0.0)

        for doc_id, text in existing_texts:
            if len(text) < self.config["min_text_length"]:
                continue

            existing_vector = self._get_embedding(text)
            if not existing_vector:
                continue

            similarity = self._cosine_similarity(new_vector, existing_vector)

            if similarity > best_match[1]:
                best_match = (doc_id, similarity)

            if similarity >= threshold:
                return True, doc_id, similarity

        return False, best_match[0], best_match[1]

    def find_similar(
        self,
        text: str,
        candidates: List[Tuple[str, str]],
        top_k: int = 5,
        threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """
        查找相似文本

        Returns:
            [(doc_id, similarity_score), ...]
        """
        text_vector = self._get_embedding(text)
        if not text_vector:
            return []

        results = []
        for doc_id, candidate_text in candidates:
            if len(candidate_text) < self.config["min_text_length"]:
                continue

            cand_vector = self._get_embedding(candidate_text)
            if not cand_vector:
                continue

            similarity = self._cosine_similarity(text_vector, cand_vector)
            if similarity >= threshold:
                results.append((doc_id, similarity))

        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


# ══════════════════════════════════════════════════════════════════════════════
# 第二部分：知识价值评估系统
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class KnowledgeValueScore:
    """知识价值评分"""
    total_score: float           # 总分 0-100
    citation_score: float        # 引用次数得分 (30%)
    authority_score: float      # 来源权威性得分 (20%)
    recency_score: float        # 时效性得分 (20%)
    feedback_score: float       # 用户反馈得分 (30%)
    decay_factor: float         # 衰减因子

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total_score,
            "citation": self.citation_score,
            "authority": self.authority_score,
            "recency": self.recency_score,
            "feedback": self.feedback_score,
            "decay": self.decay_factor,
        }


class KnowledgeValueScorer:
    """
    知识价值评估系统
    ================

    多维度评分机制：

    | 维度         | 权重 | 说明                          |
    |-------------|------|-------------------------------|
    | 引用次数     | 30%  | 被重复使用的知识更值钱          |
    | 来源权威性   | 20%  | 学术论文 > 博客 > 论坛         |
    | 时效性       | 20%  | 旧知识自动降权                  |
    | 用户反馈     | 30%  | 👍/👎 投票机制                  |

    评分公式：
    score = w1*citation + w2*authority + w3*recency + w4*feedback - decay
    """

    _instance = None

    # 权威性权重
    AUTHORITY_WEIGHTS = {
        # 顶级来源
        "arxiv.org": 1.0,
        "nature.com": 1.0,
        "science.org": 1.0,
        "ieee.org": 1.0,
        "acm.org": 1.0,
        # 权威媒体
        "wikipedia.org": 0.9,
        "github.com": 0.8,
        "stackoverflow.com": 0.8,
        # 一般来源
        "baidu.com": 0.5,
        "zhihu.com": 0.5,
        "csdn.net": 0.5,
        # 低权威
        "blog.sina": 0.3,
        "tieba.baidu": 0.2,
    }

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.db_path = Path.home() / ".hermes-desktop" / "kb_value_scores"
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db_file = self.db_path / "scores.db"

        self._init_db()
        self._init_feedback_cache()

        # 评分配置
        self.config = {
            "weights": {
                "citation": 0.30,
                "authority": 0.20,
                "recency": 0.20,
                "feedback": 0.30,
            },
            "decay_rate": 0.001,       # 每天衰减
            "half_life_days": 180,      # 半衰期180天
            "citation_bonus": 10,       # 每次引用+10分
            "max_citation_bonus": 50,  # 最高50分
        }

        self._initialized = True
        logger.info("[ValueScorer] 知识价值评估系统初始化完成")

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_file))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS value_scores (
                doc_id TEXT PRIMARY KEY,
                citation_count INTEGER DEFAULT 0,
                authority_score REAL DEFAULT 0.5,
                last_cited_at TEXT,
                positive_votes INTEGER DEFAULT 0,
                negative_votes INTEGER DEFAULT 0,
                total_score REAL DEFAULT 50.0,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                vote_type TEXT NOT NULL,
                user_id TEXT DEFAULT 'anonymous',
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def _init_feedback_cache(self):
        """初始化反馈缓存"""
        self._feedback_cache: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"positive": 0, "negative": 0}
        )

    def _get_authority_score(self, source_url: str) -> float:
        """计算权威性得分"""
        if not source_url:
            return 0.5  # 默认中等权威

        for domain, score in self.AUTHORITY_WEIGHTS.items():
            if domain in source_url:
                return score

        return 0.5  # 未知来源默认0.5

    def _calculate_recency_score(self, created_at: datetime) -> float:
        """计算时效性得分"""
        days_old = (datetime.now() - created_at).days
        half_life = self.config["half_life_days"]

        # 指数衰减
        recency = math.exp(-0.693 * days_old / half_life)
        return recency * 100

    def _calculate_feedback_score(
        self,
        positive: int,
        negative: int
    ) -> float:
        """计算用户反馈得分"""
        total = positive + negative
        if total == 0:
            return 50.0  # 无反馈默认50

        # 威尔逊置信区间
        z = 1.96  # 95%置信
        phat = positive / total

        denominator = 1 + z**2 / total
        center = phat + z**2 / (2 * total)
        spread = z * math.sqrt((phat * (1 - phat) + z**2 / (4 * total)) / total)

        wilson_score = (center - spread) / denominator
        return wilson_score * 100

    def get_citation_score(self, citation_count: int) -> float:
        """计算引用次数得分"""
        # 对数增长，有上限
        bonus = min(
            self.config["citation_bonus"] * math.log2(citation_count + 1),
            self.config["max_citation_bonus"]
        )
        return 30 + bonus  # 基础30分

    def calculate_score(
        self,
        doc_id: str,
        citation_count: int,
        source_url: str,
        created_at: datetime,
        positive_votes: int = 0,
        negative_votes: int = 0
    ) -> KnowledgeValueScore:
        """计算知识价值评分"""
        # 各维度得分
        citation = self.get_citation_score(citation_count)
        authority = self._get_authority_score(source_url) * 100
        recency = self._calculate_recency_score(created_at)
        feedback = self._calculate_feedback_score(positive_votes, negative_votes)

        # 权重
        w = self.config["weights"]

        # 总分
        total = (
            w["citation"] * citation +
            w["authority"] * authority +
            w["recency"] * recency +
            w["feedback"] * feedback
        )

        # 衰减因子
        days_old = (datetime.now() - created_at).days
        decay = math.exp(-self.config["decay_rate"] * days_old)

        return KnowledgeValueScore(
            total_score=min(100, total),
            citation_score=citation,
            authority_score=authority,
            recency_score=recency,
            feedback_score=feedback,
            decay_factor=decay
        )

    def record_citation(self, doc_id: str):
        """记录一次引用"""
        conn = sqlite3.connect(str(self.db_file))
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        # 更新引用计数
        cursor.execute("""
            INSERT INTO value_scores (doc_id, citation_count, last_cited_at, updated_at)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                citation_count = citation_count + 1,
                last_cited_at = excluded.last_cited_at,
                updated_at = excluded.updated_at
        """, (doc_id, now, now))

        conn.commit()
        conn.close()

    def record_feedback(
        self,
        doc_id: str,
        vote_type: str,  # "positive" or "negative"
        user_id: str = "anonymous"
    ):
        """记录用户反馈"""
        conn = sqlite3.connect(str(self.db_file))
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        # 记录历史
        cursor.execute("""
            INSERT INTO feedback_history (doc_id, vote_type, user_id, created_at)
            VALUES (?, ?, ?, ?)
        """, (doc_id, vote_type, user_id, now))

        # 更新投票计数
        if vote_type == "positive":
            cursor.execute("""
                INSERT INTO value_scores (doc_id, positive_votes, updated_at)
                VALUES (?, 1, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    positive_votes = positive_votes + 1,
                    updated_at = excluded.updated_at
            """, (doc_id, now))
        else:
            cursor.execute("""
                INSERT INTO value_scores (doc_id, negative_votes, updated_at)
                VALUES (?, 1, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    negative_votes = negative_votes + 1,
                    updated_at = excluded.updated_at
            """, (doc_id, now))

        conn.commit()
        conn.close()

    def get_score(self, doc_id: str) -> Optional[KnowledgeValueScore]:
        """获取评分"""
        conn = sqlite3.connect(str(self.db_file))
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM value_scores WHERE doc_id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        # (doc_id, citation_count, authority_score, last_cited_at,
        #  positive_votes, negative_votes, total_score, updated_at)
        return KnowledgeValueScore(
            total_score=row[6],
            citation_score=self.get_citation_score(row[1]),
            authority_score=row[2] * 100,
            recency_score=50,  # 估算
            feedback_score=self._calculate_feedback_score(row[4], row[5]),
            decay_factor=1.0
        )

    def get_top_k(self, k: int = 10, min_score: float = 30) -> List[Tuple[str, float]]:
        """获取评分最高的K条知识"""
        conn = sqlite3.connect(str(self.db_file))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT doc_id, total_score
            FROM value_scores
            WHERE total_score >= ?
            ORDER BY total_score DESC
            LIMIT ?
        """, (min_score, k))

        results = cursor.fetchall()
        conn.close()

        return [(doc_id, score) for doc_id, score in results]


# ══════════════════════════════════════════════════════════════════════════════
# 第三部分：主动学习触发器
# ══════════════════════════════════════════════════════════════════════════════

class TriggerType(Enum):
    """触发类型"""
    FAQ_GENERATION = "faq_generation"          # 生成FAQ
    KNOWLEDGE_GAP = "knowledge_gap"            # 知识缺口
    USER_CORRECTION = "user_correction"        # 用户纠正
    REPEAT_QUESTION = "repeat_question"         # 重复问题
    LOW_QUALITY_RESPONSE = "low_quality"       # 低质量响应


@dataclass
class LearningTrigger:
    """学习触发器"""
    trigger_type: TriggerType
    query: str
    context: Dict[str, Any]
    suggested_action: str
    priority: int  # 1-5, 1最高
    created_at: datetime = field(default_factory=datetime.now)


class ActiveLearningTrigger:
    """
    主动学习触发器
    ==============

    监控用户行为，自动发现问题并生成知识：

    触发条件：
    1. 同一问题被问 N 次 → 生成 FAQ
    2. 搜索无结果 → 标记为知识缺口
    3. 用户纠正 AI → 记录为新知识
    4. AI 回答质量低 → 触发重新学习

    工作流程：
    1. 监听会话事件
    2. 收集触发条件
    3. 满足条件 → 生成学习任务
    4. 执行学习 → 更新知识库
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.trigger_path = Path.home() / ".hermes-desktop" / "active_learning"
        self.trigger_path.mkdir(parents=True, exist_ok=True)
        self.triggers_file = self.trigger_path / "triggers.json"
        self.stats_file = self.trigger_path / "stats.json"

        # 触发配置
        self.config = {
            "repeat_threshold": 3,           # 同一问题出现N次触发FAQ生成
            "no_result_threshold": 2,         # 无结果搜索N次触发知识缺口
            "correction_threshold": 1,        # 纠正1次就触发
            "low_quality_threshold": 3,       # 连续N次低质量触发学习
        }

        # 状态追踪
        self._query_history: Dict[str, int] = defaultdict(int)  # query → count
        self._no_result_queries: Set[str] = set()
        self._correction_history: List[Dict] = []
        self._pending_triggers: List[LearningTrigger] = []

        self._load_state()
        self._initialized = True
        logger.info("[ActiveLearning] 主动学习触发器初始化完成")

    def _load_state(self):
        """加载状态"""
        if self.triggers_file.exists():
            try:
                with open(self.triggers_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._query_history = defaultdict(int, data.get("query_history", {}))
                    self._no_result_queries = set(data.get("no_result_queries", []))
            except Exception:
                pass

        if self.stats_file.exists():
            try:
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    self._stats = json.load(f)
            except Exception:
                pass
        else:
            self._stats = {
                "faq_generated": 0,
                "gaps_marked": 0,
                "corrections_recorded": 0,
                "relearn_triggered": 0,
            }

    def _save_state(self):
        """保存状态"""
        try:
            with open(self.triggers_file, "w", encoding="utf-8") as f:
                json.dump({
                    "query_history": dict(self._query_history),
                    "no_result_queries": list(self._no_result_queries),
                }, f, ensure_ascii=False)

            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self._stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[ActiveLearning] 保存状态失败: {e}")

    def on_query(self, query: str, result_count: int = -1):
        """
        监听查询事件

        Args:
            query: 用户查询
            result_count: 返回结果数量，-1表示未知
        """
        # 1. 重复查询检查
        normalized_query = self._normalize_query(query)
        self._query_history[normalized_query] += 1

        if self._query_history[normalized_query] == self.config["repeat_threshold"]:
            trigger = LearningTrigger(
                trigger_type=TriggerType.FAQ_GENERATION,
                query=query,
                context={"count": self._query_history[normalized_query]},
                suggested_action=f"生成FAQ: {query}",
                priority=2
            )
            self._pending_triggers.append(trigger)
            self._stats["faq_generated"] += 1
            logger.info(f"[ActiveLearning] 触发FAQ生成: {query}")

        # 2. 无结果检查
        if result_count == 0:
            self._no_result_queries.add(normalized_query)

            no_result_count = sum(
                1 for q in self._no_result_queries
                if q == normalized_query
            )

            if no_result_count >= self.config["no_result_threshold"]:
                trigger = LearningTrigger(
                    trigger_type=TriggerType.KNOWLEDGE_GAP,
                    query=query,
                    context={"no_result_count": no_result_count},
                    suggested_action=f"标记知识缺口并尝试获取: {query}",
                    priority=1
                )
                self._pending_triggers.append(trigger)
                self._stats["gaps_marked"] += 1
                logger.info(f"[ActiveLearning] 标记知识缺口: {query}")

        self._save_state()

    def on_user_correction(self, original_text: str, corrected_text: str, context: Dict = None):
        """
        监听用户纠正事件

        Args:
            original_text: AI原始回答
            corrected_text: 用户纠正
            context: 额外上下文
        """
        trigger = LearningTrigger(
            trigger_type=TriggerType.USER_CORRECTION,
            query=f"{original_text} → {corrected_text}",
            context=context or {},
            suggested_action="记录纠正，更新知识库",
            priority=1
        )
        self._pending_triggers.append(trigger)
        self._stats["corrections_recorded"] += 1

        logger.info(f"[ActiveLearning] 记录用户纠正: {original_text[:50]}...")

    def on_low_quality_response(self, query: str, quality_score: float, reasons: List[str]):
        """
        监听低质量响应事件

        Args:
            query: 查询
            quality_score: 质量分数 (0-1)
            reasons: 低质量原因列表
        """
        key = f"lowq_{self._normalize_query(query)}"

        # 简化：直接触发
        trigger = LearningTrigger(
            trigger_type=TriggerType.LOW_QUALITY_RESPONSE,
            query=query,
            context={"quality_score": quality_score, "reasons": reasons},
            suggested_action=f"触发重新学习: {query}",
            priority=3
        )
        self._pending_triggers.append(trigger)
        self._stats["relearn_triggered"] += 1

    def _normalize_query(self, query: str) -> str:
        """标准化查询"""
        # 小写 + 去除空白
        return query.lower().strip()

    def get_pending_triggers(self, trigger_type: Optional[TriggerType] = None) -> List[LearningTrigger]:
        """获取待处理的触发器"""
        if trigger_type:
            return [t for t in self._pending_triggers if t.trigger_type == trigger_type]
        return self._pending_triggers

    def acknowledge_trigger(self, trigger: LearningTrigger):
        """确认并移除触发器"""
        if trigger in self._pending_triggers:
            self._pending_triggers.remove(trigger)

    def generate_faq_entry(self, query: str, answer: str) -> Dict[str, Any]:
        """
        生成FAQ条目

        用于将重复问题转化为FAQ知识
        """
        return {
            "type": "faq",
            "question": query,
            "answer": answer,
            "created_at": datetime.now().isoformat(),
            "source": "active_learning",
            "trigger_type": "repeat_question",
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "pending_triggers": len(self._pending_triggers),
            "tracked_queries": len(self._query_history),
            "marked_gaps": len(self._no_result_queries),
        }


# ══════════════════════════════════════════════════════════════════════════════
# 第四部分：知识图谱增强
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExtractedEntity:
    """提取的实体"""
    name: str
    type: str  # person/organization/location/concept/technology
    confidence: float
    mentions: List[str]  # 提及列表


@dataclass
class ExtractedRelation:
    """提取的关系"""
    source: str
    relation: str  # is_a/part_of/uses/requires/related_to
    target: str
    confidence: float


class KnowledgeGraphEnhancer:
    """
    知识图谱增强
    ===========

    自动从文本中提取：
    1. 实体（人名/机构/地点/概念/技术）
    2. 关系（是/属于/使用/需要/相关）

    增强知识库：
    - 自动链接相关知识
    - 发现隐含关系
    - 扩展知识网络
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.graph_path = Path.home() / ".hermes-desktop" / "kb_graph"
        self.graph_path.mkdir(parents=True, exist_ok=True)
        self.graph_file = self.graph_path / "entities_relations.json"

        # 实体/关系缓存
        self._entities: Dict[str, ExtractedEntity] = {}
        self._relations: List[ExtractedRelation] = []

        # ══════════════════════════════════════════════════════════════════════════════
        # 中文优化：扩展关系模式库（精确版）
        # ══════════════════════════════════════════════════════════════════════════════
        # 关系类型：is_a (属于/是), part_of (包含/组成), uses (使用/采用), 
        #           requires (需要/依赖), related_to (相关/关联)
        # 
        # 重要：使用精确捕获，避免 .+? 贪婪匹配
        # 格式：r"([^，,。；;]{2,10})关键词([^，,。；;]{2,10})"
        
        self._relation_patterns = {
            # is_a 关系 - 表示归属/类型（"X是Y"的X和Y）
            "is_a": [
                # 标准句式：取关键词前后的名词性短语
                r"([^，。；、\s]{2,10})是([^，。；、\s]{2,10})",           # X是Y
                r"([^，。；、\s]{2,10})属于([^，。；、\s]{2,10})",         # X属于Y
                # 古文/学术风格
                r"([^，。；、\s]{2,10})乃([^，。；、\s]{2,10})",            # X乃Y
                r"([^，。；、\s]{2,10})即([^，。；、\s]{2,10})",            # X即Y
                # 现代表述
                r"([^，。；、\s]{2,10})是一种?([^，。；、\s]{2,10})",      # X是一种Y
                r"([^，。；、\s]{2,10})归为([^，。；、\s]{2,10})",          # X归为Y
            ],
            
            # part_of 关系 - 表示包含/组成
            "part_of": [
                # 标准句式
                r"([^，。；、\s]{2,10})包括([^，。；、\s]{2,10})",          # X包括Y
                r"([^，。；、\s]{2,10})包含([^，。；、\s]{2,10})",          # X包含Y
                # 组成句式
                r"([^，。；、\s]{2,10})由([^，。；、\s]{2,10})组成",         # X由Y组成
                r"([^，。；、\s]{2,10})由([^，。；、\s]{2,10})构成",         # X由Y构成
                r"([^，。；、\s]{2,10})是([^，。；、\s]{2,10})的一部分",     # X是Y的一部分
                # 涵盖句式
                r"([^，。；、\s]{2,10})涵盖([^，。；、\s]{2,10})",          # X涵盖Y
            ],
            
            # uses 关系 - 表示使用/采用
            "uses": [
                # 标准句式
                r"([^，。；、\s]{2,10})使用([^，。；、\s]{2,10})",          # X使用Y
                r"([^，。；、\s]{2,10})采用([^，。；、\s]{2,10})",          # X采用Y
                # 技术应用
                r"([^，。；、\s]{2,10})运用([^，。；、\s]{2,10})",          # X运用Y
                r"([^，。；、\s]{2,10})应用([^，。；、\s]{2,10})",          # X应用Y
                r"([^，。；、\s]{2,10})基于([^，。；、\s]{2,10})",          # X基于Y
                r"([^，。；、\s]{2,10})借助([^，。；、\s]{2,10})",          # X借助Y
                # 工具/方法
                r"([^，。；、\s]{2,10})通过([^，。；、\s]{2,10})",           # X通过Y
                r"([^，。；、\s]{2,10})利用([^，。；、\s]{2,10})",          # X利用Y
            ],
            
            # requires 关系 - 表示需要/依赖
            "requires": [
                # 标准句式
                r"([^，。；、\s]{2,10})需要([^，。；、\s]{2,10})",         # X需要Y
                r"([^，。；、\s]{2,10})依赖([^，。；、\s]{2,10})",         # X依赖Y
                # 必要条件
                r"([^，。；、\s]{2,10})必须具备([^，。；、\s]{2,10})",       # X必须具备Y
                r"([^，。；、\s]{2,10})的前提是([^，。；、\s]{2,10})",      # X的前提是Y
                # 要求
                r"([^，。；、\s]{2,10})要求([^，。；、\s]{2,10})",          # X要求Y
                # 缺乏句式
                r"([^，。；、\s]{2,10})离不开([^，。；、\s]{2,10})",         # X离不开Y
            ],
            
            # related_to 关系 - 表示相关/关联
            "related_to": [
                # 标准句式
                r"([^，。；、\s]{2,10})与([^，。；、\s]{2,10})相关",        # X与Y相关
                r"([^，。；、\s]{2,10})和([^，。；、\s]{2,10})有关",        # X和Y有关
                # 连接词
                r"([^，。；、\s]{2,10})与([^，。；、\s]{2,10})有关联",       # X与Y有关联
                # 涉及
                r"([^，。；、\s]{2,10})涉及([^，。；、\s]{2,10})",          # X涉及Y
                r"([^，。；、\s]{2,10})关于([^，。；、\s]{2,10})",           # X关于Y
                r"([^，。；、\s]{2,10})针对([^，。；、\s]{2,10})",           # X针对Y
            ],
        }

        # ══════════════════════════════════════════════════════════════════════════════
        # 中文优化：扩展实体类型模式库
        # ══════════════════════════════════════════════════════════════════════════════
        # 实体类型：person(人名), organization(机构), location(地点), 
        #           technology(技术), concept(概念), product(产品), event(事件)
        # 优先级：精确匹配优先于模糊匹配
        
        self._entity_patterns = {
            # 人名识别 - 常见后缀词前的姓名
            "person": [
                # 动作执行者
                r"([^，。；、\s]{2,4})说",                         # XXX说
                r"([^，。；、\s]{2,4})认为",                        # XXX认为
                r"([^，。；、\s]{2,4})提出",                        # XXX提出
                r"([^，。；、\s]{2,4})指出",                        # XXX指出
                r"([^，。；、\s]{2,4})表示",                        # XXX表示
                r"([^，。；、\s]{2,4})称",                          # XXX称
                r"([^，。；、\s]{2,4})写道",                        # XXX写道
                # 学者/专家
                r"([^，。；、\s]{2,4})教授",                        # XXX教授
                r"([^，。；、\s]{2,4})博士",                        # XXX博士
                r"([^，。；、\s]{2,4})院士",                         # XXX院士
                r"([^，。；、\s]{2,4})专家",                        # XXX专家
                r"([^，。；、\s]{2,4})先生",                        # XXX先生
                r"([^，。；、\s]{2,4})女士",                         # XXX女士
                # 职位+姓名
                r"([^，。；、\s]{2,4})CEO",                         # XXX CEO
                r"([^，。；、\s]{2,4})创始人",                      # XXX创始人
                r"([^，。；、\s]{2,4})董事长",                      # XXX董事长
                r"([^，。；、\s]{2,4})总经理",                      # XXX总经理
            ],
            
            # 组织机构识别
            "organization": [
                # 正式机构
                r"(.{2,10})公司",                       # XXX公司
                r"(.{2,10})医院",                       # XXX医院
                r"(.{2,10})大学",                       # XXX大学
                r"(.{2,10})学院",                        # XXX学院
                r"(.{2,10})研究所",                      # XXX研究所
                r"(.{2,10})研究院",                      # XXX研究院
                r"(.{2,10})机构",                        # XXX机构
                r"(.{2,10})组织",                        # XXX组织
                # 政府机构
                r"(.{2,10})部",                          # XXX部 (教育部)
                r"(.{2,10})局",                          # XXX局 (公安局)
                r"(.{2,10})委员会",                      # XXX委员会
                r"(.{2,10})办公厅",                      # XXX办公厅
                r"(.{2,6})省人民政府",                   # XXX省人民政府
                r"(.{2,6})市人民政府",                   # XXX市人民政府
                # 企业类型
                r"(.{2,10})(集团|股份|科技|网络|信息|软件)公司",
                r"(.{2,10})(科技|网络|信息|软件|电子)有限公司",
                # 简称识别
                r"(.{2,6})(科学院|社科院|工程院)",      # XXX科学院
            ],
            
            # 地点位置识别
            "location": [
                # 行政区划
                r"在(.{2,6})的",                         # 在XXX的
                r"位于(.{2,10})",                        # 位于XXX
                r"(.{2,6})省",                          # XXX省
                r"(.{2,6})市",                          # XXX市
                r"(.{2,6})区",                          # XXX区
                r"(.{2,6})县",                          # XXX县
                # 地名后缀
                r"(.{2,10})(省|市|区|县|镇|村|街道)",  # XXX省/市/区...
                r"(.{2,10})地区",                        # XXX地区
                r"(.{2,10})开发区",                      # XXX开发区
                r"(.{2,10})工业园",                      # XXX工业园
                # 地标/场所
                r"(.{2,10})(机场|车站|港口|码头|高铁站)",
                r"(.{2,10})(机场|火车站|汽车站)",
                r"(.{2,10})大学城",                      # XXX大学城
            ],
            
            # 技术术语识别
            "technology": [
                # 技术名词
                r"使用(.{2,10})技术",                   # 使用XXX技术
                r"(.{2,10})算法",                        # XXX算法
                r"(.{2,10})模型",                        # XXX模型
                r"(.{2,10})框架",                        # XXX框架
                r"(.{2,10})系统",                        # XXX系统
                r"(.{2,10})平台",                        # XXX平台
                r"(.{2,10})协议",                        # XXX协议
                r"(.{2,10})标准",                        # XXX标准
                # IT/互联网技术
                r"(.{2,10})(AI|人工智能|机器学习|深度学习)",
                r"(.{2,10})(大数据|云计算|区块链|物联网)",
                r"(.{2,10})(Python|Java|C\+\+|JavaScript|Go|Rust)",
                r"(.{2,10})(神经网络|Transformer|BERT|GPT)",
                # 新兴技术
                r"(.{2,10})(5G|6G|元宇宙|虚拟现实|增强现实)",
                r"(.{2,10})(自动驾驶|智能家居|智慧城市)",
            ],
            
            # 概念/理论识别
            "concept": [
                # 抽象概念
                r"(.{2,10})原理",                        # XXX原理
                r"(.{2,10})概念",                        # XXX概念
                r"(.{2,10})方法",                        # XXX方法
                r"(.{2,10})理论",                        # XXX理论
                r"(.{2,10})思想",                        # XXX思想
                r"(.{2,10})学说",                        # XXX学说
                r"(.{2,10})定律",                        # XXX定律
                r"(.{2,10})法则",                        # XXX法则
                # 思维方法
                r"(.{2,10})思维",                        # XXX思维
                r"(.{2,10})逻辑",                        # XXX逻辑
                r"(.{2,10})策略",                        # XXX策略
                r"(.{2,10})模式",                        # XXX模式
                # 管理/经济概念
                r"(.{2,10})效应",                        # XXX效应
                r"(.{2,10})定律",                        # XXX定律
                r"(.{2,10})原则",                        # XXX原则
            ],
            
            # 产品/品牌识别 (新增)
            "product": [
                r"(.{2,10})(手机|电脑|平板|手表|耳机)", # XXX手机/电脑...
                r"(.{2,10})(汽车|电动车|自行车)",        # XXX汽车
                r"(.{2,10})(电视|冰箱|洗衣机|空调)",    # XXX电视
                r"(.{2,10})(App|应用|软件)",             # XXX App
                r"(.{2,10})(品牌|商标)",                 # XXX品牌
                # 手机型号
                r"(华为|苹果|三星|小米|OPPO|VIVO)(.{0,6})",
                # 芯片型号
                r"(骁龙|麒麟|A系列|M系列|酷睿|锐龙)(.{0,4})",
            ],
            
            # 事件/时间识别 (新增)
            "event": [
                # 历史事件
                r"(.{2,10})战争",                        # XXX战争
                r"(.{2,10})革命",                        # XXX革命
                r"(.{2,10})起义",                        # XXX起义
                r"(.{2,10})事件",                        # XXX事件
                # 会议/活动
                r"(.{2,10})会议",                        # XXX会议
                r"(.{2,10})峰会",                        # XXX峰会
                r"(.{2,10})论坛",                        # XXX论坛
                r"(.{2,10})展览",                        # XXX展览
                # 时间+事件
                r"(\d{4})(年)?(爆发|发生|举办|召开)(.{2,8})",
            ],
        }

        # ══════════════════════════════════════════════════════════════════════════════
        # 中文优化：停用词表（实体提取时排除）
        # ══════════════════════════════════════════════════════════════════════════════
        self._stop_words = {
            # 常见动词
            "是", "有", "在", "的", "了", "和", "与", "为", "对", "以", "于",
            "上", "下", "中", "内", "外", "前", "后", "大", "小", "多", "少",
            "好", "坏", "新", "旧", "高", "低", "长", "短", "快", "慢",
            # 常见连词
            "以及", "或者", "还是", "并且", "而且", "因此", "所以", "但是",
            "然而", "虽然", "但是", "如果", "因为", "所以", "既", "又",
            # 常见量词
            "个", "种", "类", "些", "点", "件", "条", "次", "期", "版",
            # 常见副词
            "很", "非常", "特别", "十分", "比较", "相当", "极", "太", "最",
            "更", "越", "还", "也", "都", "只", "仅", "就", "才", "已",
            # 无意义组合（实体提取时排除）
            "一个", "这个", "那个", "其他", "某些", "各种", "任何", "所有",
            "一些", "可以", "能够", "应该", "必须", "需要", "关于",
            "通过", "利用", "使用", "采用", "根据", "按照", "经过",
            "作为", "对于", "关于", "通过", "经过", "由于", "基于",
        }

        self._load_graph()
        self._initialized = True
        logger.info("[KGEnhancer] 知识图谱增强初始化完成")

    def _load_graph(self):
        """加载图谱数据"""
        if self.graph_file.exists():
            try:
                with open(self.graph_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 加载实体
                    for e_data in data.get("entities", []):
                        entity = ExtractedEntity(**e_data)
                        self._entities[entity.name] = entity
                    # 加载关系
                    for r_data in data.get("relations", []):
                        relation = ExtractedRelation(**r_data)
                        self._relations.append(relation)
            except Exception as e:
                logger.warning(f"[KGEnhancer] 加载图谱失败: {e}")

    def _save_graph(self):
        """保存图谱数据"""
        try:
            data = {
                "entities": [e.__dict__ for e in self._entities.values()],
                "relations": [r.__dict__ for r in self._relations],
            }
            with open(self.graph_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[KGEnhancer] 保存图谱失败: {e}")

    def extract_entities(self, text: str) -> List[ExtractedEntity]:
        """
        从文本中提取实体（中文优化版）
        
        优化点：
        1. 停用词过滤 - 排除常见无意义词
        2. 长度限制 - 中文2-15字，英文1-30字符
        3. 重复字符过滤 - 排除"啊啊啊"等无意义重复
        4. 数字过滤 - 排除纯数字
        5. 置信度微调 - 根据匹配模式精确度调整
        """
        entities = []

        # 预编译正则（避免重复编译）
        compiled_patterns = {}
        for entity_type, patterns in self._entity_patterns.items():
            compiled_patterns[entity_type] = [
                re.compile(p) for p in patterns
            ]

        for entity_type, compiled in compiled_patterns.items():
            for pattern in compiled:
                matches = pattern.finditer(text)
                for match in matches:
                    # 提取第一组捕获
                    name = match.group(1).strip()
                    
                    # ══════════════════════════════════════════════════════════════
                    # 中文优化：多维度过滤
                    # ══════════════════════════════════════════════════════════════
                    
                    # 1. 长度过滤：中文2-15字
                    if not (2 <= len(name) <= 15):
                        continue
                    
                    # 2. 停用词过滤
                    if name in self._stop_words:
                        continue
                    
                    # 3. 包含停用词开头/结尾（宽松）
                    if any(name.startswith(sw) or name.endswith(sw) for sw in ["的", "了", "是", "在", "有", "和", "与"]):
                        # 排除"XXX的"格式
                        if len(name) <= 4:
                            continue
                    
                    # 4. 重复字符过滤（如"啊啊啊"）
                    if len(set(name)) == 1 and len(name) > 2:
                        continue
                    
                    # 5. 纯数字过滤
                    if name.isdigit():
                        continue
                    
                    # 6. 排除常见无意义组合
                    skip_patterns = [
                        r"^\d+$",           # 纯数字
                        r"^[a-zA-Z]+$",      # 纯英文字母
                        r"^\s+$",           # 纯空白
                    ]
                    if any(re.match(p, name) for p in skip_patterns):
                        continue
                    
                    # ══════════════════════════════════════════════════════════════
                    # 计算置信度
                    # ══════════════════════════════════════════════════════════════
                    base_confidence = 0.7
                    
                    # 精确匹配加成
                    if len(name) >= 3 and len(name) <= 6:
                        base_confidence += 0.1
                    
                    # 特殊后缀加成（更精确的识别）
                    precise_suffixes = ["公司", "大学", "医院", "教授", "博士", 
                                       "算法", "模型", "系统", "平台", "协议"]
                    if any(name.endswith(suffix) for suffix in precise_suffixes):
                        base_confidence += 0.15
                    
                    # 人名加成
                    person_suffixes = ["说", "认为", "提出", "指出", "表示"]
                    if any(name.endswith(suffix) for suffix in person_suffixes):
                        # 人名不应以动词结尾，提取人名部分
                        for suffix in person_suffixes:
                            if name.endswith(suffix):
                                name = name[:-len(suffix)]
                                break
                        if len(name) >= 2:
                            base_confidence = 0.85
                    
                    # 确保名称有效
                    if len(name) >= 2:
                        entity = ExtractedEntity(
                            name=name,
                            type=entity_type,
                            confidence=min(base_confidence, 0.95),
                            mentions=[match.group(0)]
                        )
                        entities.append(entity)

        # 去重并合并 - 按名称合并相同实体
        merged: Dict[str, ExtractedEntity] = {}
        for e in entities:
            if e.name in merged:
                # 合并提及
                merged[e.name].mentions.extend(e.mentions)
                # 保留最高置信度
                if e.confidence > merged[e.name].confidence:
                    merged[e.name].confidence = e.confidence
                # 合并类型
                if e.type != merged[e.name].type:
                    merged[e.name].type = "concept"  # 模糊类型
            else:
                merged[e.name] = e

        return list(merged.values())

    def extract_relations(self, text: str) -> List[ExtractedRelation]:
        """
        从文本中提取关系（中文优化版）
        
        优化点：
        1. 预编译正则 - 避免重复编译
        2. 停用词过滤 - 排除无意义实体
        3. 长度过滤 - 排除过长/过短实体
        4. 重复过滤 - 排除同一关系重复提取
        5. 置信度调整 - 根据关系类型精确度
        """
        relations = []
        seen_relations = set()  # 去重集合
        
        # 预编译正则
        compiled_patterns = {}
        for rel_type, patterns in self._relation_patterns.items():
            compiled_patterns[rel_type] = [
                re.compile(p) for p in patterns
            ]

        # 关系类型置信度基础分
        relation_confidence = {
            "is_a": 0.75,       # "是"关系较明确
            "part_of": 0.70,    # "包括"关系
            "uses": 0.70,       # "使用"关系
            "requires": 0.70,   # "需要"关系
            "related_to": 0.65, # "相关"关系较模糊
        }

        for rel_type, compiled in compiled_patterns.items():
            for pattern in compiled:
                matches = pattern.finditer(text)
                for match in matches:
                    source = match.group(1).strip()
                    target = match.group(2).strip()
                    
                    # ══════════════════════════════════════════════════════════════
                    # 中文优化：关系过滤
                    # ══════════════════════════════════════════════════════════════
                    
                    # 1. 长度过滤
                    if not (2 <= len(source) <= 20 and 2 <= len(target) <= 20):
                        continue
                    
                    # 2. 停用词过滤
                    if source in self._stop_words or target in self._stop_words:
                        continue
                    
                    # 3. 纯数字/纯标点过滤
                    if (source.isdigit() or target.isdigit() or
                        not re.search(r'[\u4e00-\u9fa5a-zA-Z]', source) or
                        not re.search(r'[\u4e00-\u9fa5a-zA-Z]', target)):
                        continue
                    
                    # 4. 去重
                    rel_key = (source, rel_type, target)
                    if rel_key in seen_relations:
                        continue
                    seen_relations.add(rel_key)
                    
                    # 5. 计算置信度
                    base_conf = relation_confidence.get(rel_type, 0.65)
                    
                    # 精确匹配加成
                    if 3 <= len(source) <= 10 and 3 <= len(target) <= 10:
                        base_conf += 0.1
                    
                    # 特殊模式加成
                    if any(kw in match.group(0) for kw in ["由...组成", "由...构成", "是一种"]):
                        base_conf += 0.1
                    
                    relation = ExtractedRelation(
                        source=source,
                        relation=rel_type,
                        target=target,
                        confidence=min(base_conf, 0.9)
                    )
                    relations.append(relation)

        return relations

    def enhance_knowledge(
        self,
        doc_id: str,
        content: str,
        title: str = ""
    ) -> Dict[str, Any]:
        """
        增强知识条目

        1. 提取实体和关系
        2. 链接到已有知识
        3. 返回增强结果
        """
        # 提取
        entities = self.extract_entities(content)
        relations = self.extract_relations(content)

        # 添加到图谱
        for entity in entities:
            if entity.name not in self._entities:
                self._entities[entity.name] = entity

        for relation in relations:
            self._relations.append(relation)

        # 查找相关实体
        related_entities = []
        for entity in entities:
            related = self._find_related_entities(entity.name)
            related_entities.extend(related)

        # 保存
        self._save_graph()

        return {
            "doc_id": doc_id,
            "entities_extracted": len(entities),
            "relations_extracted": len(relations),
            "linked_entities": related_entities,
            "entity_types": {e.type: e.name for e in entities[:5]},
        }

    def _find_related_entities(self, entity_name: str) -> List[str]:
        """查找相关实体"""
        related = []

        # 查找关系
        for rel in self._relations:
            if rel.source == entity_name:
                related.append(rel.target)
            elif rel.target == entity_name:
                related.append(rel.source)

        # 查找共同出现的实体
        for name, entity in self._entities.items():
            if name != entity_name and any(entity_name in m for m in entity.mentions):
                related.append(name)

        return list(set(related))[:5]

    def find_paths(self, entity1: str, entity2: str, max_depth: int = 3) -> List[List[str]]:
        """查找两个实体之间的路径"""
        # BFS
        visited = {entity1}
        queue = [(entity1, [entity1])]

        while queue:
            current, path = queue.pop(0)

            if len(path) > max_depth:
                continue

            if current == entity2:
                return [path]

            for rel in self._relations:
                next_entity = None
                if rel.source == current and rel.target not in visited:
                    next_entity = rel.target
                elif rel.target == current and rel.source not in visited:
                    next_entity = rel.source

                if next_entity:
                    visited.add(next_entity)
                    queue.append((next_entity, path + [next_entity]))

        return []

    def get_entity_info(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """获取实体信息"""
        if entity_name not in self._entities:
            return None

        entity = self._entities[entity_name]
        relations = [r for r in self._relations if r.source == entity_name or r.target == entity_name]
        related = self._find_related_entities(entity_name)

        return {
            "name": entity.name,
            "type": entity.type,
            "confidence": entity.confidence,
            "mentions": entity.mentions,
            "relations": [(r.source, r.relation, r.target) for r in relations],
            "related_entities": related,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 第五部分：遗忘机制 + 强化复习
# ══════════════════════════════════════════════════════════════════════════════

class MemoryState(Enum):
    """记忆状态"""
    ACTIVE = "active"           # 活跃
    REVIEW_NEEDED = "review_needed"  # 需要复习
    DECAYING = "decaying"       # 衰减中
    FORGOTTEN = "forgotten"    # 已遗忘


@dataclass
class MemoryNode:
    """记忆节点"""
    doc_id: str
    content: str
    strength: float = 1.0       # 记忆强度 0-1
    last_accessed: datetime = field(default_factory=datetime.now)
    last_reviewed: datetime = field(default_factory=datetime.now)
    next_review: datetime = field(default_factory=datetime.now)
    review_count: int = 0
    state: MemoryState = MemoryState.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "content": self.content[:100],
            "strength": self.strength,
            "last_accessed": self.last_accessed.isoformat(),
            "last_reviewed": self.last_reviewed.isoformat(),
            "next_review": self.next_review.isoformat(),
            "review_count": self.review_count,
            "state": self.state.value,
        }


class ForgettingMechanism:
    """
    遗忘机制 + 强化复习
    ====================

    类比人类记忆的间隔重复算法：

    核心概念：
    1. 记忆强度 (strength): 知识被"记住"的程度
    2. 间隔复习 (spaced repetition): 随时间安排复习
    3. 强化 (reinforcement): 使用时增强记忆
    4. 遗忘 (forgetting): 不使用的知识逐渐遗忘

    算法：SM-2 变体
    - 每次访问 → strength += 0.1 (有上限)
    - 每次复习成功 → strength += 0.2
    - 每天衰减 → strength -= 0.001
    - strength < 0.2 → 标记为待删除

    复习策略：
    - 间隔 = base_interval * (2 ^ review_count)
    - 成功复习 → 延长间隔
    - 失败 → 重置间隔
    """

    _instance = None

    # 遗忘曲线参数
    DECAY_RATE = 0.001        # 每天衰减率
    STRENGTH_THRESHOLD = 0.2  # 低于此值标记为遗忘
    ACCESS_BONUS = 0.1        # 每次访问增加强度
    REVIEW_BONUS = 0.2        # 每次复习增加强度
    BASE_INTERVAL_HOURS = 24  # 基础复习间隔

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.memory_path = Path.home() / ".hermes-desktop" / "kb_memory"
        self.memory_path.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_path / "memory_nodes.json"

        # 记忆节点
        self._memory: Dict[str, MemoryNode] = {}

        # 复习队列
        self._review_queue: List[str] = []

        self._load_memory()
        self._initialized = True
        logger.info("[ForgettingMechanism] 遗忘机制初始化完成")

    def _load_memory(self):
        """加载记忆数据"""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for doc_id, node_data in data.items():
                        node_data = node_data.copy()
                        node_data["last_accessed"] = datetime.fromisoformat(node_data["last_accessed"])
                        node_data["last_reviewed"] = datetime.fromisoformat(node_data["last_reviewed"])
                        node_data["next_review"] = datetime.fromisoformat(node_data["next_review"])
                        node_data["state"] = MemoryState(node_data["state"])
                        self._memory[doc_id] = MemoryNode(**node_data)

                self._update_review_queue()
            except Exception as e:
                logger.warning(f"[ForgettingMechanism] 加载记忆失败: {e}")

    def _save_memory(self):
        """保存记忆数据"""
        try:
            data = {
                doc_id: {
                    **node.__dict__,
                    "last_accessed": node.last_accessed.isoformat(),
                    "last_reviewed": node.last_reviewed.isoformat(),
                    "next_review": node.next_review.isoformat(),
                    "state": node.state.value,
                }
                for doc_id, node in self._memory.items()
            }
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[ForgettingMechanism] 保存记忆失败: {e}")

    def register_knowledge(self, doc_id: str, content: str):
        """注册知识到记忆系统"""
        if doc_id in self._memory:
            return

        self._memory[doc_id] = MemoryNode(
            doc_id=doc_id,
            content=content,
            strength=1.0,
            state=MemoryState.ACTIVE
        )
        self._update_review_queue()
        self._save_memory()

    def on_access(self, doc_id: str):
        """知识被访问时调用 - 强化记忆"""
        if doc_id not in self._memory:
            return

        node = self._memory[doc_id]

        # 强化
        node.strength = min(1.0, node.strength + self.ACCESS_BONUS)
        node.last_accessed = datetime.now()

        # 状态更新
        if node.strength >= 0.5:
            node.state = MemoryState.ACTIVE

        # 更新复习时间
        self._update_next_review(node)

        self._save_memory()

    def record_review(
        self,
        doc_id: str,
        success: bool  # True=记住了, False=忘记了
    ):
        """记录复习结果"""
        if doc_id not in self._memory:
            return

        node = self._memory[doc_id]
        node.last_reviewed = datetime.now()
        node.review_count += 1

        if success:
            # 成功：强化 + 延长间隔
            node.strength = min(1.0, node.strength + self.REVIEW_BONUS)
            node.state = MemoryState.ACTIVE
        else:
            # 失败：减弱 + 缩短间隔
            node.strength = max(0, node.strength - 0.15)
            node.review_count = max(0, node.review_count - 1)

        # 更新下次复习时间
        self._update_next_review(node)

        # 检查遗忘
        if node.strength < self.STRENGTH_THRESHOLD:
            node.state = MemoryState.FORGOTTEN

        self._save_memory()

    def _update_next_review(self, node: MemoryNode):
        """更新下次复习时间"""
        # 间隔 = 基础间隔 * 2^(复习次数)
        interval_hours = self.BASE_INTERVAL_HOURS * (2 ** node.review_count)
        interval_hours = min(interval_hours, 30 * 24)  # 最多30天

        node.next_review = datetime.now() + timedelta(hours=interval_hours)

        if node.strength < 0.5:
            node.state = MemoryState.REVIEW_NEEDED

    def _update_review_queue(self):
        """更新复习队列"""
        now = datetime.now()

        # 按下次复习时间排序
        pending = [
            doc_id for doc_id, node in self._memory.items()
            if node.next_review <= now or node.state == MemoryState.REVIEW_NEEDED
        ]

        pending.sort(key=lambda d: self._memory[d].next_review)
        self._review_queue = pending

    def get_review_candidates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取待复习的知识"""
        self._update_review_queue()

        candidates = []
        for doc_id in self._review_queue[:limit]:
            node = self._memory[doc_id]
            candidates.append({
                "doc_id": doc_id,
                "content": node.content[:100],
                "strength": node.strength,
                "next_review": node.next_review.isoformat(),
                "review_count": node.review_count,
                "state": node.state.value,
            })

        return candidates

    def get_forgotten_knowledge(self) -> List[str]:
        """获取已遗忘的知识（待GC）"""
        return [
            doc_id for doc_id, node in self._memory.items()
            if node.state == MemoryState.FORGOTTEN
        ]

    def apply_decay(self):
        """应用每日衰减"""
        now = datetime.now()

        for doc_id, node in self._memory.items():
            # 计算自上次访问以来的衰减
            days_since_access = (now - node.last_accessed).total_seconds() / 86400
            decay = self.DECAY_RATE * days_since_access

            # 如果不是活跃使用的知识
            if node.review_count < 2:
                decay *= 2  # 低复习的知识衰减更快

            node.strength = max(0, node.strength - decay)

            # 更新状态
            if node.strength < self.STRENGTH_THRESHOLD:
                node.state = MemoryState.FORGOTTEN
            elif node.strength < 0.5:
                node.state = MemoryState.DECAYING
            elif node.strength >= 0.8:
                node.state = MemoryState.ACTIVE

        self._update_review_queue()
        self._save_memory()

        # 返回被遗忘的数量
        return len(self.get_forgotten_knowledge())

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        states = defaultdict(int)
        for node in self._memory.values():
            states[node.state.value] += 1

        return {
            "total": len(self._memory),
            "states": dict(states),
            "review_queue_size": len(self._review_queue),
            "forgotten_count": len(self.get_forgotten_knowledge()),
            "avg_strength": sum(n.strength for n in self._memory.values()) / max(1, len(self._memory)),
        }


# ══════════════════════════════════════════════════════════════════════════════
# 全局实例和便捷访问
# ══════════════════════════════════════════════════════════════════════════════

_semantic_dedup: Optional[SemanticDeduplicator] = None
_value_scorer: Optional[KnowledgeValueScorer] = None
_active_learner: Optional[ActiveLearningTrigger] = None
_kg_enhancer: Optional[KnowledgeGraphEnhancer] = None
_forgetting: Optional[ForgettingMechanism] = None


def get_semantic_dedup() -> SemanticDeduplicator:
    """获取语义去重器"""
    global _semantic_dedup
    if _semantic_dedup is None:
        _semantic_dedup = SemanticDeduplicator()
    return _semantic_dedup


def get_value_scorer() -> KnowledgeValueScorer:
    """获取价值评估器"""
    global _value_scorer
    if _value_scorer is None:
        _value_scorer = KnowledgeValueScorer()
    return _value_scorer


def get_active_learner() -> ActiveLearningTrigger:
    """获取主动学习器"""
    global _active_learner
    if _active_learner is None:
        _active_learner = ActiveLearningTrigger()
    return _active_learner


def get_kg_enhancer() -> KnowledgeGraphEnhancer:
    """获取知识图谱增强器"""
    global _kg_enhancer
    if _kg_enhancer is None:
        _kg_enhancer = KnowledgeGraphEnhancer()
    return _kg_enhancer


def get_forgetting_mechanism() -> ForgettingMechanism:
    """获取遗忘机制"""
    global _forgetting
    if _forgetting is None:
        _forgetting = ForgettingMechanism()
    return _forgetting


# ══════════════════════════════════════════════════════════════════════════════
# 统一知识库创新引擎
# ══════════════════════════════════════════════════════════════════════════════

class KnowledgeInnovationEngine:
    """
    知识库创新引擎

    整合5大创新模块的统一接口
    """

    def __init__(self):
        self.dedup = get_semantic_dedup()
        self.scorer = get_value_scorer()
        self.learner = get_active_learner()
        self.kg = get_kg_enhancer()
        self.forgetting = get_forgetting_mechanism()

    def process_knowledge(
        self,
        doc_id: str,
        content: str,
        source_url: str = "",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        处理知识条目（完整流程）

        1. 语义去重检查
        2. 价值评分
        3. 知识图谱增强
        4. 注册到记忆系统
        5. 主动学习触发检查
        """
        results = {}

        # 1. 语义去重
        is_dup, dup_id, similarity = self.dedup.is_duplicate(
            content,
            [(doc_id, c) for doc_id, c in [(doc_id, content)]]  # TODO: 从KB获取全部
        )
        results["is_duplicate"] = is_dup
        results["duplicate_id"] = dup_id
        results["similarity"] = similarity

        # 2. 价值评分
        score = self.scorer.calculate_score(
            doc_id=doc_id,
            citation_count=0,
            source_url=source_url,
            created_at=datetime.now()
        )
        results["value_score"] = score.to_dict()

        # 3. 知识图谱增强
        kg_result = self.kg.enhance_knowledge(doc_id, content)
        results["kg_enhancement"] = kg_result

        # 4. 注册到记忆系统
        self.forgetting.register_knowledge(doc_id, content)

        return results

    def on_knowledge_accessed(self, doc_id: str):
        """知识被访问"""
        # 强化记忆
        self.forgetting.on_access(doc_id)
        # 记录引用
        self.scorer.record_citation(doc_id)

    def on_user_feedback(
        self,
        doc_id: str,
        is_positive: bool
    ):
        """用户反馈"""
        vote_type = "positive" if is_positive else "negative"
        self.scorer.record_feedback(doc_id, vote_type)

    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有统计"""
        return {
            "value_scores": self.scorer.get_top_k(5),
            "active_learning": self.learner.get_stats(),
            "memory": self.forgetting.get_memory_stats(),
            "pending_triggers": len(self.learner.get_pending_triggers()),
        }


# ══════════════════════════════════════════════════════════════════════════════
# 测试
# ══════════════════════════════════════════════════════════════════════════════

def test_innovation_modules():
    """测试创新模块"""
    logger.info("=" * 60)
    logger.info("测试知识库创新模块")
    logger.info("=" * 60)

    # 1. 测试语义去重
    logger.info("\n1. 测试语义去重引擎")
    dedup = get_semantic_dedup()

    texts = [
        "Python是一种高级编程语言",
        "Python属于高级编程语言",
        "JavaScript是脚本语言",
    ]

    is_dup, dup_id, sim = dedup.is_duplicate(texts[1], [(f"doc_{i}", t) for i, t in enumerate(texts)])
    logger.info(f"   '{texts[1]}' 与已有文本重复: {is_dup}, 相似度: {sim:.3f}")

    # 2. 测试价值评估
    logger.info("\n2. 测试价值评估")
    scorer = get_value_scorer()
    score = scorer.calculate_score(
        doc_id="test_doc",
        citation_count=10,
        source_url="https://arxiv.org/paper/123",
        created_at=datetime.now() - timedelta(days=30)
    )
    logger.info(f"   评分: {score.total_score:.1f}, 引用: {score.citation_score:.1f}, 权威: {score.authority_score:.1f}")

    # 3. 测试主动学习
    logger.info("\n3. 测试主动学习")
    learner = get_active_learner()
    learner.on_query("如何学习Python", result_count=5)
    learner.on_query("如何学习Python", result_count=5)
    learner.on_query("如何学习Python", result_count=5)  # 触发FAQ
    logger.info(f"   待处理触发: {len(learner.get_pending_triggers())}")
    logger.info(f"   统计: {learner.get_stats()}")

    # 4. 测试知识图谱
    logger.info("\n4. 测试知识图谱")
    kg = get_kg_enhancer()
    result = kg.enhance_knowledge("test", "Python是一种编程语言, 使用Python可以开发网站")
    logger.info(f"   提取实体: {result['entities_extracted']}, 关系: {result['relations_extracted']}")

    # 5. 测试遗忘机制
    logger.info("\n5. 测试遗忘机制")
    forgetting = get_forgetting_mechanism()
    forgetting.register_knowledge("test_doc", "这是一段测试内容")
    forgetting.on_access("test_doc")
    stats = forgetting.get_memory_stats()
    logger.info(f"   记忆统计: {stats}")

    logger.info("\n" + "=" * 60)
    logger.info("测试完成!")


if __name__ == "__main__":
    test_innovation_modules()
