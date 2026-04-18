"""
编译器式缓存 - Compiled Cache

核心理念：将"查询-答案"对预编译为结构化的中间表示，
而非像传统缓存那样每次从向量数据库重新检索。

三层缓存架构：
┌─────────────────────────────────────────────────────┐
│ L1: Exact Cache    - 精确匹配，O(1) 毫秒级响应       │
│ L2: Compiled Cache - 预编译的答案片段，知识复用       │
│ L3: Semantic Cache - 向量相似度，容忍语义变化        │
└─────────────────────────────────────────────────────┘

复利效应：每次查询都在让缓存变聪明
- 新查询与已有"编译答案"交叉引用
- 相似查询复用已有编译结果
- 好的答案被沉淀为新的 Wiki 页面
"""

import os
import json
import time
import hashlib
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from collections import OrderedDict
from dataclasses import dataclass, field

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None


@dataclass
class CompiledChunk:
    """
    预编译的知识片段
    这是 LLM Wiki 编译器模式的核心数据结构
    """
    id: str                          # 唯一标识
    content: str                     # 预编译的内容片段
    query_pattern: str              # 匹配的查询模式
    answer_template: str            # 答案模板
    referenced_page_ids: List[str]   # 引用的 Wiki 页面
    referenced_source_ids: List[str] # 引用的原材料
    confidence: float = 1.0         # 置信度
    usage_count: int = 0            # 使用次数
    last_used: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    embedding: List[float] = field(default_factory=list)  # 向量表示
    tags: List[str] = field(default_factory=list)

    # 复利相关
    compounding_score: float = 0.0  # 复利得分（每次使用累加）
    chain_id: Optional[str] = None   # 链条ID（关联的编译片段）

    def mark_used(self):
        """标记使用，累加复利得分"""
        self.usage_count += 1
        self.last_used = time.time()
        self.compounding_score += 0.1  # 每次使用增加0.1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "query_pattern": self.query_pattern,
            "answer_template": self.answer_template,
            "referenced_page_ids": self.referenced_page_ids,
            "referenced_source_ids": self.referenced_source_ids,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "last_used": self.last_used,
            "created_at": self.created_at,
            "compounding_score": self.compounding_score,
            "chain_id": self.chain_id,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CompiledChunk":
        return cls(
            id=d["id"],
            content=d["content"],
            query_pattern=d.get("query_pattern", ""),
            answer_template=d.get("answer_template", ""),
            referenced_page_ids=d.get("referenced_page_ids", []),
            referenced_source_ids=d.get("referenced_source_ids", []),
            confidence=d.get("confidence", 1.0),
            usage_count=d.get("usage_count", 0),
            last_used=d.get("last_used", time.time()),
            created_at=d.get("created_at", time.time()),
            compounding_score=d.get("compounding_score", 0.0),
            chain_id=d.get("chain_id"),
            tags=d.get("tags", [])
        )


@dataclass
class CacheEntry:
    """缓存条目"""
    query_hash: str
    query: str
    response: Any
    compiled_chunks: List[str]      # 引用的预编译片段ID
    wiki_pages_used: List[str]     # 引用的 Wiki 页面
    sources_used: List[str]        # 引用的原材料
    compiled_at: float
    expires_at: float
    hit_count: int = 0
    last_hit: float = 0

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def mark_hit(self):
        self.hit_count += 1
        self.last_hit = time.time()


class CompiledCache:
    """
    编译器式缓存

    与传统语义缓存的区别：
    - 传统：query embedding → vector similarity → return cached response
    - 编译式：query → analyze pattern → find relevant CompiledChunks → compose answer

    复利效应实现：
    1. 每次查询后，将有价值的答案沉淀为新的 CompiledChunk
    2. CompiledChunk 被使用时，复利得分累加
    3. 高复利得分的 chunk 优先被使用
    4. 形成正向循环：使用越多 → 复利越高 → 越容易被使用
    """

    def __init__(
        self,
        persist_path: str = "~/.hermes-desktop/wiki_cache",
        memory_size: int = 1000,
        chunk_size: int = 512,
        ttl_seconds: int = 86400 * 7,  # 7天
        similarity_threshold: float = 0.85
    ):
        self.persist_path = Path(os.path.expanduser(persist_path))
        self.memory_size = memory_size
        self.chunk_size = chunk_size
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold

        # LRU 内存缓存
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # 预编译片段库
        self._compiled_chunks: Dict[str, CompiledChunk] = {}

        # 统计
        self._stats = {
            "total_queries": 0,
            "exact_hits": 0,
            "pattern_hits": 0,
            "semantic_hits": 0,
            "misses": 0,
            "compilations": 0,
            "compounding_bonus": 0.0
        }

        # 向量维度
        self._vector_dim = 384
        self._embeddings: Dict[str, List[float]] = {}

        # 初始化
        self._init_storage()
        self._load_state()

    def _init_storage(self):
        """初始化存储"""
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self.chunks_path = self.persist_path / "compiled_chunks.json"
        self.cache_path = self.persist_path / "cache_entries.json"
        self.stats_path = self.persist_path / "stats.json"

    def _load_state(self):
        """加载状态"""
        # 加载预编译片段
        if self.chunks_path.exists():
            try:
                with open(self.chunks_path, 'r', encoding='utf-8') as f:
                    chunks_data = json.load(f)
                    for chunk_data in chunks_data:
                        chunk = CompiledChunk.from_dict(chunk_data)
                        self._compiled_chunks[chunk.id] = chunk
                        if chunk_data.get("embedding"):
                            self._embeddings[chunk.id] = chunk_data["embedding"]
            except Exception as e:
                print(f"[CompiledCache] 加载预编译片段失败: {e}")

        # 加载缓存条目
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    for entry_data in cache_data:
                        entry = CacheEntry(
                            query_hash=entry_data["query_hash"],
                            query=entry_data["query"],
                            response=entry_data["response"],
                            compiled_chunks=entry_data.get("compiled_chunks", []),
                            wiki_pages_used=entry_data.get("wiki_pages_used", []),
                            sources_used=entry_data.get("sources_used", []),
                            compiled_at=entry_data["compiled_at"],
                            expires_at=entry_data["expires_at"],
                            hit_count=entry_data.get("hit_count", 0),
                            last_hit=entry_data.get("last_hit", 0)
                        )
                        self._cache[entry.query_hash] = entry
            except Exception as e:
                print(f"[CompiledCache] 加载缓存条目失败: {e}")

        # 加载统计
        if self.stats_path.exists():
            try:
                with open(self.stats_path, 'r', encoding='utf-8') as f:
                    self._stats = json.load(f)
            except Exception as e:
                print(f"[CompiledCache] 加载统计失败: {e}")

    def _save_state(self):
        """保存状态"""
        try:
            # 保存预编译片段
            chunks_data = [c.to_dict() for c in self._compiled_chunks.values()]
            with open(self.chunks_path, 'w', encoding='utf-8') as f:
                json.dump(chunks_data, f, ensure_ascii=False, indent=2)

            # 保存缓存条目
            cache_data = []
            for entry in self._cache.values():
                entry_dict = {
                    "query_hash": entry.query_hash,
                    "query": entry.query,
                    "response": entry.response,
                    "compiled_chunks": entry.compiled_chunks,
                    "wiki_pages_used": entry.wiki_pages_used,
                    "sources_used": entry.sources_used,
                    "compiled_at": entry.compiled_at,
                    "expires_at": entry.expires_at,
                    "hit_count": entry.hit_count,
                    "last_hit": entry.last_hit
                }
                cache_data.append(entry_dict)
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            # 保存统计
            with open(self.stats_path, 'w', encoding='utf-8') as f:
                json.dump(self._stats, f, ensure_ascii=False)
        except Exception as e:
            print(f"[CompiledCache] 保存状态失败: {e}")

    def _hash_query(self, query: str) -> str:
        """计算查询哈希"""
        return hashlib.md5(query.encode()).hexdigest()

    def _generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入"""
        import hashlib
        features = []
        for i in range(self._vector_dim):
            hash_input = f"{text}_{i}_feature"
            h = hashlib.md5(hash_input.encode()).hexdigest()
            val = int(h[:8], 16) / (16**8)
            features.append(val - 0.5)

        if HAS_NUMPY:
            vec = np.array(features, dtype=np.float64)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec.tolist()
        else:
            total = sum(f * f for f in features) ** 0.5
            if total > 0:
                features = [f / total for f in features]
            return features

    def _compute_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        return max(0.0, dot)

    def _extract_query_pattern(self, query: str) -> str:
        """提取查询模式（去除具体实体，保留结构）"""
        import re
        # 去除具体数字、日期、专有名词
        pattern = query
        pattern = re.sub(r'\d+', 'N', pattern)  # 数字
        pattern = re.sub(r'[\u4e00-\u9fa5]+', 'X', pattern)  # 中文词
        pattern = re.sub(r'[A-Z][a-z]+', 'Y', pattern)  # 英文专名
        pattern = re.sub(r'什么|怎么|如何|为什么|为何', 'Q', pattern)  # 疑问词
        return pattern

    def get(
        self,
        query: str,
        wiki_pages: List[Any] = None,
        sources: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取缓存结果

        Args:
            query: 查询文本
            wiki_pages: 可用的 Wiki 页面列表
            sources: 可用的原材料ID列表

        Returns:
            缓存结果或 None
        """
        with self._lock:
            self._stats["total_queries"] += 1
            query_hash = self._hash_query(query)

            # 1. 精确匹配 (L1)
            if query_hash in self._cache:
                entry = self._cache[query_hash]
                if not entry.is_expired():
                    entry.mark_hit()
                    self._cache.move_to_end(query_hash)
                    self._stats["exact_hits"] += 1

                    # 标记使用的 chunk
                    for chunk_id in entry.compiled_chunks:
                        if chunk_id in self._compiled_chunks:
                            self._compiled_chunks[chunk_id].mark_used()

                    return {
                        "response": entry.response,
                        "cache_hit": True,
                        "hit_type": "exact",
                        "compiled_chunks": entry.compiled_chunks,
                        "wiki_pages": entry.wiki_pages_used,
                        "confidence": 1.0
                    }
                else:
                    del self._cache[query_hash]

            # 2. 查询模式匹配 (L2)
            query_pattern = self._extract_query_pattern(query)
            pattern_matches = self._find_pattern_matches(query_pattern)

            if pattern_matches:
                best_chunk = pattern_matches[0]
                best_chunk.mark_used()
                self._stats["pattern_hits"] += 1
                self._stats["compounding_bonus"] += best_chunk.compounding_score

                return {
                    "response": best_chunk.answer_template,
                    "cache_hit": True,
                    "hit_type": "compiled",
                    "compiled_chunks": [best_chunk.id],
                    "wiki_pages": best_chunk.referenced_page_ids,
                    "confidence": best_chunk.confidence * best_chunk.compounding_score
                }

            # 3. 语义相似度匹配 (L3)
            if wiki_pages:
                semantic_matches = self._find_semantic_matches(query, wiki_pages)
                if semantic_matches:
                    best_match = semantic_matches[0]
                    if best_match[1] >= self.similarity_threshold:
                        self._stats["semantic_hits"] += 1
                        return {
                            "response": best_match[0].content,
                            "cache_hit": True,
                            "hit_type": "semantic",
                            "compiled_chunks": [],
                            "wiki_pages": [best_match[0].id],
                            "confidence": best_match[1]
                        }

            self._stats["misses"] += 1
            return None

    def _find_pattern_matches(self, pattern: str) -> List[CompiledChunk]:
        """查找模式匹配的预编译片段"""
        matches = []
        for chunk in self._compiled_chunks.values():
            chunk_pattern = self._extract_query_pattern(chunk.query_pattern)
            if pattern == chunk_pattern:
                # 按复利得分排序
                matches.append(chunk)

        # 按复利得分降序
        matches.sort(key=lambda c: c.compounding_score, reverse=True)
        return matches[:5]

    def _find_semantic_matches(
        self,
        query: str,
        wiki_pages: List[Any]
    ) -> List[Tuple[Any, float]]:
        """查找语义相似的 Wiki 页面"""
        if not wiki_pages:
            return []

        query_vec = self._generate_embedding(query)
        matches = []

        for page in wiki_pages:
            page_id = page.id if hasattr(page, 'id') else str(page)
            content = page.compiled_truth.summary if hasattr(page, 'compiled_truth') else str(page)

            # 生成页面内容的向量（如果已有则复用）
            if page_id in self._embeddings:
                page_vec = self._embeddings[page_id]
            else:
                page_vec = self._generate_embedding(content)
                self._embeddings[page_id] = page_vec

            similarity = self._compute_similarity(query_vec, page_vec)
            if similarity >= 0.5:
                matches.append((page, similarity))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:5]

    def set(
        self,
        query: str,
        response: Any,
        compiled_chunks: List[str] = None,
        wiki_pages: List[str] = None,
        sources: List[str] = None,
        confidence: float = 1.0,
        worth_compiling: bool = False,
        query_pattern: str = None
    ):
        """
        设置缓存

        Args:
            query: 查询文本
            response: 响应内容
            compiled_chunks: 使用的预编译片段
            wiki_pages: 引用的 Wiki 页面
            sources: 引用的原材料
            confidence: 置信度
            worth_compiling: 是否值得编译为新片段
            query_pattern: 查询模式
        """
        with self._lock:
            query_hash = self._hash_query(query)
            now = time.time()

            # LRU 淘汰
            if len(self._cache) >= self.memory_size:
                self._cache.popitem(last=False)

            # 创建缓存条目
            entry = CacheEntry(
                query_hash=query_hash,
                query=query,
                response=response,
                compiled_chunks=compiled_chunks or [],
                wiki_pages_used=wiki_pages or [],
                sources_used=sources or [],
                compiled_at=now,
                expires_at=now + self.ttl_seconds
            )
            self._cache[query_hash] = entry

            # 如果值得编译，创建新的预编译片段
            if worth_compiling or (compiled_chunks and len(compiled_chunks) > 2):
                self._create_compiled_chunk(
                    query=query,
                    response=response,
                    referenced_pages=wiki_pages or [],
                    referenced_sources=sources or [],
                    confidence=confidence,
                    query_pattern=query_pattern or query
                )

            self._stats["compilations"] += 1
            self._save_state()

    def _create_compiled_chunk(
        self,
        query: str,
        response: Any,
        referenced_pages: List[str],
        referenced_sources: List[str],
        confidence: float,
        query_pattern: str
    ):
        """创建预编译片段"""
        chunk_id = hashlib.md5(query.encode()).hexdigest()[:12]

        # 如果已存在，更新
        if chunk_id in self._compiled_chunks:
            chunk = self._compiled_chunks[chunk_id]
            chunk.usage_count += 1
            chunk.last_used = time.time()
            chunk.confidence = (chunk.confidence + confidence) / 2
        else:
            # 创建新片段
            response_str = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)

            chunk = CompiledChunk(
                id=chunk_id,
                content=response_str[:self.chunk_size],
                query_pattern=query_pattern or query,
                answer_template=response_str,
                referenced_page_ids=referenced_pages,
                referenced_source_ids=referenced_sources,
                confidence=confidence,
                embedding=self._generate_embedding(response_str[:500])
            )
            self._compiled_chunks[chunk_id] = chunk
            self._embeddings[chunk_id] = chunk.embedding

    def compile_good_answer(
        self,
        query: str,
        answer: str,
        referenced_pages: List[str],
        referenced_sources: List[str],
        reasoning_chain: List[str] = None
    ):
        """
        将好答案编译为预编译片段

        这是复利效应的核心：每次发现好答案，就让它变成未来查询的基础
        """
        with self._lock:
            chunk_id = hashlib.md5(f"{query}_{time.time()}".encode()).hexdigest()[:12]

            answer_str = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)

            # 提取标签
            tags = self._extract_tags(answer_str)

            chunk = CompiledChunk(
                id=chunk_id,
                content=answer_str[:self.chunk_size],
                query_pattern=self._extract_query_pattern(query),
                answer_template=answer_str,
                referenced_page_ids=referenced_pages,
                referenced_source_ids=referenced_sources,
                confidence=0.9,  # 新编译的置信度稍低
                tags=tags,
                chain_id=referenced_pages[0] if referenced_pages else None
            )

            self._compiled_chunks[chunk_id] = chunk
            self._embeddings[chunk_id] = chunk.embedding
            self._stats["compilations"] += 1
            self._save_state()

    def _extract_tags(self, text: str) -> List[str]:
        """提取标签"""
        import re
        tags = []
        # 提取 #标签
        tags.extend(re.findall(r'#(\w+)', text))
        # 提取中文关键词
        keywords = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
        tags.extend(keywords[:5])
        return list(set(tags))[:10]

    def get_compounding_insights(self) -> Dict[str, Any]:
        """获取复利洞察"""
        total_chunks = len(self._compiled_chunks)
        if total_chunks == 0:
            return {"message": "暂无预编译片段"}

        # 按复利得分排序
        sorted_chunks = sorted(
            self._compiled_chunks.values(),
            key=lambda c: c.compounding_score,
            reverse=True
        )

        return {
            "total_chunks": total_chunks,
            "total_usage": sum(c.usage_count for c in sorted_chunks),
            "top_chunks": [
                {
                    "id": c.id,
                    "content": c.content[:50] + "...",
                    "compounding_score": c.compounding_score,
                    "usage_count": c.usage_count
                }
                for c in sorted_chunks[:5]
            ],
            "avg_compounding_score": sum(c.compounding_score for c in sorted_chunks) / total_chunks,
            "cache_hit_rate": self._stats["exact_hits"] / max(self._stats["total_queries"], 1),
            "compilation_rate": self._stats["compilations"] / max(self._stats["total_queries"], 1)
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self._stats["total_queries"]
        return {
            **self._stats,
            "cache_size": len(self._cache),
            "compiled_chunks": len(self._compiled_chunks),
            "cache_hit_rate": self._stats["exact_hits"] / max(total, 1),
            "pattern_hit_rate": self._stats["pattern_hits"] / max(total, 1),
            "semantic_hit_rate": self._stats["semantic_hits"] / max(total, 1),
            "compounding_rate": self._stats["compounding_bonus"] / max(total, 1)
        }

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._compiled_chunks.clear()
            self._embeddings.clear()
            self._stats = {
                "total_queries": 0,
                "exact_hits": 0,
                "pattern_hits": 0,
                "semantic_hits": 0,
                "misses": 0,
                "compilations": 0,
                "compounding_bonus": 0.0
            }
            self._save_state()