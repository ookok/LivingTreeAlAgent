"""
统一 RAG 流水线

合并增强自:
- engine.py FusionRAGEngine (门面/编排器)
- fusion_engine.py FusionEngine (结果融合)
- query_engine.py QueryEngine (查询/检索)
- triple_chain_engine.py TripleChainEngine (推理验证)

增强:
- 统一结果类型 RAGResult
- 共享嵌入工具（消除 DRY）
- 依赖注入架构（KnowledgeGraph/VectorStore 共享实例）
- 策略模式（速度优先/精度优先/平衡/仅缓存/LLM优先）
- 统一的流水线: Ingest → Embed → Retrieve → Fuse → Reason → Answer
"""

from __future__ import annotations
import logging
from typing import Optional, Dict, Any, List, Callable

from .types import (
    RAGResult, SearchHit, IngestResult,
    generate_embedding, generate_content_hash, extract_entities,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 检索策略
# ============================================================================

class RetrieveStrategy:
    """检索策略基类"""
    name: str = "base"

    def should_use_cache(self, query: str) -> bool:
        return True

    def should_use_llm(self, confidence: float) -> bool:
        return confidence < 0.5


class SpeedFirstStrategy(RetrieveStrategy):
    """速度优先：只用缓存"""
    name = "speed_first"

    def should_use_cache(self, query: str) -> bool:
        return True

    def should_use_llm(self, confidence: float) -> bool:
        return False


class AccuracyFirstStrategy(RetrieveStrategy):
    """精度优先：始终使用 LLM"""
    name = "accuracy_first"

    def should_use_cache(self, query: str) -> bool:
        return True

    def should_use_llm(self, confidence: float) -> bool:
        return True


class BalancedStrategy(RetrieveStrategy):
    """平衡策略：适中"""
    name = "balanced"

    def should_use_cache(self, query: str) -> bool:
        return True

    def should_use_llm(self, confidence: float) -> bool:
        return confidence < 0.8


class CacheOnlyStrategy(RetrieveStrategy):
    """纯缓存：不调用 LLM"""
    name = "cache_only"

    def should_use_cache(self, query: str) -> bool:
        return True

    def should_use_llm(self, confidence: float) -> bool:
        return False


class LLMFirstStrategy(RetrieveStrategy):
    """LLM优先：先调 LLM，缓存兜底"""
    name = "llm_first"

    def should_use_cache(self, query: str) -> bool:
        return False

    def should_use_llm(self, confidence: float) -> bool:
        return True


STRATEGIES = {
    "speed_first": SpeedFirstStrategy(),
    "accuracy_first": AccuracyFirstStrategy(),
    "balanced": BalancedStrategy(),
    "cache_only": CacheOnlyStrategy(),
    "llm_first": LLMFirstStrategy(),
}


# ============================================================================
# 统一 RAG 流水线
# ============================================================================

class RAGPipeline:
    """统一 RAG 流水线

    组合检索、融合、推理，替代独立的 FusionRAGEngine + FusionEngine +
    QueryEngine + TripleChainEngine。
    
    通过依赖注入共享 KnowledgeGraph 和 VectorStore 实例。
    """

    def __init__(
        self,
        strategy: str = "balanced",
        top_k: int = 10,
        vector_store: Any = None,
        knowledge_graph: Any = None,
        llm_executor: Optional[Callable] = None,
        exact_cache: Any = None,
        session_cache: Any = None,
    ):
        """
        Args:
            strategy: 检索策略名称 ("speed_first"|"accuracy_first"|"balanced"|"cache_only"|"llm_first")
            top_k: 最终返回结果数量
            vector_store: 向量存储实例（SmartVectorStore 兼容接口）
            knowledge_graph: 知识图谱实例（DynamicKnowledgeGraph 兼容接口）
            llm_executor: LLM 执行器 (messages, model, intent) -> Dict
            exact_cache: 精确缓存实例
            session_cache: 会话缓存实例
        """
        self.strategy = STRATEGIES.get(strategy, BalancedStrategy())
        self.top_k = top_k
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph
        self.llm_executor = llm_executor
        self.exact_cache = exact_cache
        self.session_cache = session_cache

        # 统计
        self.query_count = 0
        self.cache_hits = 0
        self.llm_calls = 0

        logger.info(f"RAGPipeline 初始化: strategy={self.strategy.name}, top_k={top_k}")

    # ========================================================================
    # 主查询接口
    # ========================================================================

    async def query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        depth: int = 3,
        use_reasoning: bool = True,
    ) -> RAGResult:
        """执行 RAG 查询

        流水线: 缓存检查 → 向量检索 → 图谱检索 → 数据库检索 → 融合 → LLM(可选) → 推理(可选)

        Args:
            query: 查询文本
            context: 附加上下文
            depth: 检索深度
            use_reasoning: 是否使用推理链

        Returns:
            RAGResult
        """
        self.query_count += 1
        query_embedding = generate_embedding(query)

        # L1: 精确缓存
        cache_result = await self._search_cache(query)
        if cache_result:
            self.cache_hits += 1
            return cache_result

        # L2: 向量检索
        vector_hits = await self._search_vector(query_embedding, self.top_k)

        # L3: 知识图谱检索
        graph_hits = await self._search_graph(query, depth)

        # L4: 数据库检索（LLM fallback）
        db_hits = []
        if self.strategy.should_use_llm(0.0):
            db_hits = await self._search_llm(query, context)

        # 融合各层结果
        fused = self._fuse_results(query, vector_hits, graph_hits, db_hits)

        # 构建结果
        result = RAGResult(
            content=fused.get("content", ""),
            sources=fused.get("sources", []),
            confidence=fused.get("confidence", 0.0),
            entities=fused.get("entities", []),
            search_hits=fused.get("hits", []),
        )

        # 可选推理链
        if use_reasoning and result.confidence < 0.9:
            result = self._apply_reasoning(result, query)

        return result

    async def ingest(
        self,
        data: str,
        data_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestResult:
        """摄入数据

        流水线: 分块 → 嵌入 → 存储到向量库 → 提取实体 → 添加到图谱
        """
        try:
            # 简单分块
            chunks = self._chunk_text(data)
            entities = extract_entities(data)

            result = IngestResult(
                success=True,
                document_id=generate_content_hash(data[:100]),
                entities_count=len(entities),
                chunks_count=len(chunks),
            )

            # 生成嵌入并存储
            if self.vector_store:
                for chunk in chunks:
                    emb = generate_embedding(chunk)
                    chunk_id = generate_content_hash(chunk)
                    try:
                        await self.vector_store.add([emb], [chunk_id], [{"content": chunk}])
                    except Exception as e:
                        logger.warning(f"Vector store add failed: {e}")

            # 添加实体到知识图谱
            if self.knowledge_graph and entities:
                for entity in entities:
                    try:
                        await self.knowledge_graph.add_entity({"name": entity})
                    except Exception as e:
                        logger.debug(f"KG add entity failed: {e}")

            result.message = f"Ingested {len(chunks)} chunks, {len(entities)} entities"
            return result

        except Exception as e:
            logger.error(f"Ingest failed: {e}")
            return IngestResult(success=False, message=str(e))

    # ========================================================================
    # 检索层（L1-L4）
    # ========================================================================

    async def _search_cache(self, query: str) -> Optional[RAGResult]:
        """L1: 精确缓存检索"""
        if not self.strategy.should_use_cache(query):
            return None

        # 尝试精确缓存
        if self.exact_cache:
            try:
                cached = await self.exact_cache.get(query) if callable(getattr(self.exact_cache, 'get', None)) else None
                if cached:
                    return RAGResult(
                        content=cached.get("content", ""),
                        confidence=0.95,
                        sources=cached.get("sources", []),
                    )
            except Exception:
                pass

        # 尝试会话缓存
        if self.session_cache:
            try:
                cached = await self.session_cache.get(query) if callable(getattr(self.session_cache, 'get', None)) else None
                if cached:
                    return RAGResult(
                        content=cached.get("content", ""),
                        confidence=0.85,
                        sources=cached.get("sources", []),
                    )
            except Exception:
                pass

        return None

    async def _search_vector(self, embedding: List[float], top_k: int) -> List[SearchHit]:
        """L2: 向量检索"""
        if not self.vector_store:
            return []

        try:
            results = await self.vector_store.search(embedding, top_k)
            return [
                SearchHit(
                    id=r.id if hasattr(r, 'id') else r.get('id', ''),
                    content=r.content if hasattr(r, 'content') else r.get('content', ''),
                    score=r.score if hasattr(r, 'score') else r.get('score', 0.0),
                    metadata=r.metadata if hasattr(r, 'metadata') else r.get('metadata', {}),
                    source_type="vector",
                    source_layer="L2",
                    embedding=r.embedding if hasattr(r, 'embedding') else None,
                )
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    async def _search_graph(self, query: str, depth: int) -> List[SearchHit]:
        """L3: 知识图谱检索"""
        if not self.knowledge_graph:
            return []

        try:
            entities = extract_entities(query)
            hits = []
            for entity in entities:
                try:
                    entity_data = await self.knowledge_graph.get_entity(entity) if callable(getattr(self.knowledge_graph, 'get_entity', None)) else None
                    if entity_data:
                        hits.append(SearchHit(
                            id=entity,
                            content=str(entity_data),
                            score=0.7,
                            source_type="graph",
                            source_layer="L3",
                            metadata={"entity": entity},
                        ))
                except Exception:
                    pass
            return hits
        except Exception as e:
            logger.warning(f"Graph search failed: {e}")
            return []

    async def _search_llm(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[SearchHit]:
        """L4: LLM 穿透检索"""
        if not self.llm_executor:
            return []

        try:
            messages = [{"role": "user", "content": query}]
            result = await self.llm_executor(messages, "auto", context)
            self.llm_calls += 1
            return [
                SearchHit(
                    id="llm_direct",
                    content=result.get("answer", result.get("content", "")),
                    score=0.6,
                    source_type="llm",
                    source_layer="L4",
                    metadata={"model": result.get("model", "unknown")},
                )
            ]
        except Exception as e:
            logger.warning(f"LLM search failed: {e}")
            return []

    # ========================================================================
    # 融合
    # ========================================================================

    def _fuse_results(
        self,
        query: str,
        vector_hits: List[SearchHit],
        graph_hits: List[SearchHit],
        llm_hits: List[SearchHit],
    ) -> dict:
        """多源结果融合（RRF + 加权）"""
        all_hits = vector_hits + graph_hits + llm_hits

        if not all_hits:
            return {
                "content": "",
                "sources": [],
                "confidence": 0.0,
                "entities": [],
                "hits": [],
            }

        # RRF (Reciprocal Rank Fusion) k=60
        rrf_scores: Dict[str, float] = {}
        for rank, hit in enumerate(all_hits):
            key = hit.id or generate_content_hash(hit.content)
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (60 + rank + 1)

        # 去重并按 RRF 分数排序
        seen_content = set()
        unique_hits = []
        for hit in sorted(all_hits, key=lambda h: rrf_scores.get(h.id or generate_content_hash(h.content), 0), reverse=True):
            content_key = generate_content_hash(hit.content)
            if content_key not in seen_content:
                seen_content.add(content_key)
                hit.score = rrf_scores.get(hit.id or content_key, hit.score)
                unique_hits.append(hit)

        # 选择 top_k
        top_hits = unique_hits[:self.top_k]
        top_scores = [h.score for h in top_hits]

        # 计算置信度
        confidence = sum(top_scores) / max(len(top_hits), 1) if top_scores else 0.0
        confidence = min(confidence, 1.0)

        # 合并内容
        content = "\n\n".join(h.content for h in top_hits[:3] if h.content)
        entities = extract_entities(content)

        return {
            "content": content,
            "sources": [
                {"id": h.id, "content": h.content[:200], "score": h.score,
                 "source_type": h.source_type, "source_layer": h.source_layer}
                for h in top_hits
            ],
            "confidence": confidence,
            "entities": [{"name": e} for e in entities],
            "hits": top_hits,
        }

    # ========================================================================
    # 推理
    # ========================================================================

    def _apply_reasoning(self, result: RAGResult, query: str) -> RAGResult:
        """应用推理链增强结果"""
        if not result.sources:
            return result

        steps = []
        evidence = []

        for i, source in enumerate(result.sources[:5]):
            steps.append({
                "step_id": i + 1,
                "content": source.get("content", "")[:200],
                "confidence": source.get("score", 0.5),
            })
            evidence.append({
                "doc_id": source.get("id", f"doc_{i}"),
                "title": source.get("source_type", "unknown"),
                "content_snippet": source.get("content", "")[:100],
                "source_type": source.get("source_type", ""),
                "confidence": source.get("score", 0.5),
            })

        result.reasoning_steps = steps
        result.evidences = evidence

        # 重新计算置信度（考虑证据链）
        if steps:
            avg_step_confidence = sum(s["confidence"] for s in steps) / len(steps)
            result.confidence = result.confidence * 0.7 + avg_step_confidence * 0.3

        return result

    # ========================================================================
    # 工具方法
    # ========================================================================

    def _chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 64) -> List[str]:
        """文本分块"""
        if not text:
            return []
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def get_stats(self) -> dict:
        return {
            "query_count": self.query_count,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": self.cache_hits / max(self.query_count, 1),
            "llm_calls": self.llm_calls,
            "strategy": self.strategy.name,
            "top_k": self.top_k,
        }


# ============================================================================
# 工厂函数
# ============================================================================

def create_rag_pipeline(
    strategy: str = "balanced",
    top_k: int = 10,
    vector_store: Any = None,
    knowledge_graph: Any = None,
    llm_executor: Optional[Callable] = None,
) -> RAGPipeline:
    """创建 RAG 流水线实例"""
    return RAGPipeline(
        strategy=strategy,
        top_k=top_k,
        vector_store=vector_store,
        knowledge_graph=knowledge_graph,
        llm_executor=llm_executor,
    )
