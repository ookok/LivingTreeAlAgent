"""
Smart Query Engine

智能查询引擎，支持多轮对话、查询重写、层次化检索等功能。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """查询结果"""
    content: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: Optional[str] = None
    entities: List[Dict[str, Any]] = field(default_factory=list)
    related_queries: List[str] = field(default_factory=list)


@dataclass
class SearchHit:
    """搜索命中"""
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_type: str = "vector"


class QueryEngine:
    """
    智能查询引擎
    
    核心功能：
    - 查询重写（扩展、改写、纠错）
    - 层次化检索（L1:关键词, L2:语义, L3:知识图谱）
    - 多轮对话上下文管理
    - 结果重排序
    """
    
    def __init__(self):
        """初始化查询引擎"""
        self._vector_store = None
        self._knowledge_graph = None
        self._entity_recognizer = None
        
        self._init_dependencies()
        logger.info("QueryEngine 初始化完成")
    
    def _init_dependencies(self):
        """初始化依赖模块"""
        try:
            from .smart_vector_store import get_smart_vector_store
            from .knowledge_graph import DynamicKnowledgeGraph
            from ..entity_management import get_entity_recognizer
            
            self._vector_store = get_smart_vector_store()
            self._knowledge_graph = DynamicKnowledgeGraph()
            self._entity_recognizer = get_entity_recognizer()
            
            logger.info("依赖模块加载成功")
        except ImportError as e:
            logger.warning(f"依赖模块加载失败: {e}")
    
    async def query(self, query: str, context: Optional[str] = None, 
                    depth: int = 3) -> QueryResult:
        """
        执行查询
        
        Args:
            query: 查询文本
            context: 上下文（多轮对话历史）
            depth: 检索深度 (1-3)
            
        Returns:
            QueryResult 查询结果
        """
        # 1. 查询重写
        rewritten_query = self._rewrite_query(query, context)
        logger.debug(f"原始查询: {query} -> 重写后: {rewritten_query}")
        
        # 2. 层次化检索
        hits = await self._hierarchical_search(rewritten_query, depth)
        
        # 3. 结果融合与重排序
        result = await self._fuse_results(hits, query)
        
        # 4. 生成相关查询建议
        result.related_queries = self._generate_related_queries(query, result.entities)
        
        return result
    
    def _rewrite_query(self, query: str, context: Optional[str] = None) -> str:
        """
        查询重写
        
        包括：
        - 同义词扩展
        - 上位词扩展
        - 拼写纠错
        - 上下文整合
        
        Args:
            query: 原始查询
            context: 上下文
            
        Returns:
            str 重写后的查询
        """
        rewritten = query
        
        # 同义词扩展
        synonyms = self._get_synonyms(query)
        if synonyms:
            rewritten = f"{query} {' '.join(synonyms)}"
        
        # 实体识别与扩展
        if self._entity_recognizer:
            result = self._entity_recognizer.recognize(query)
            for entity in result.entities:
                if entity.entity_type not in ["date", "number", "email", "phone", "url"]:
                    rewritten = f"{rewritten} {entity.text}"
        
        # 上下文整合
        if context:
            # 提取上下文中的关键词
            context_keywords = self._extract_keywords(context)
            if context_keywords:
                rewritten = f"{rewritten} {' '.join(context_keywords)}"
        
        return rewritten
    
    def _get_synonyms(self, query: str) -> List[str]:
        """获取同义词"""
        synonym_map = {
            "AI": ["人工智能", "artificial intelligence"],
            "机器学习": ["ML", "machine learning"],
            "深度学习": ["deep learning", "神经网络"],
            "编程": ["编码", "coding", "programming"],
            "代码": ["code", "程序"],
            "问题": ["疑问", "issue", "problem"],
            "如何": ["怎样", "怎么"],
            "什么": ["哪些", "哪种"],
        }
        
        synonyms = []
        for word, syns in synonym_map.items():
            if word in query:
                synonyms.extend(syns)
        
        return synonyms
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        stop_words = {"的", "是", "在", "有", "和", "了", "我", "你", "他", "她", "它", "这", "那"}
        
        words = text.split()
        keywords = [w for w in words if len(w) > 1 and w not in stop_words]
        
        return keywords[:5]  # 最多取5个关键词
    
    async def _hierarchical_search(self, query: str, depth: int) -> List[SearchHit]:
        """
        层次化检索
        
        L1: 关键词匹配（快速）
        L2: 语义相似度（向量检索）
        L3: 知识图谱推理
        
        Args:
            query: 查询文本
            depth: 检索深度
            
        Returns:
            List 搜索结果
        """
        hits = []
        
        # L1: 关键词匹配（始终执行）
        if depth >= 1:
            l1_hits = await self._keyword_search(query)
            hits.extend(l1_hits)
            logger.debug(f"L1 检索完成，找到 {len(l1_hits)} 条结果")
        
        # L2: 语义相似度检索
        if depth >= 2 and self._vector_store:
            l2_hits = await self._semantic_search(query)
            hits.extend(l2_hits)
            logger.debug(f"L2 检索完成，找到 {len(l2_hits)} 条结果")
        
        # L3: 知识图谱推理
        if depth >= 3 and self._knowledge_graph:
            l3_hits = await self._graph_search(query)
            hits.extend(l3_hits)
            logger.debug(f"L3 检索完成，找到 {len(l3_hits)} 条结果")
        
        return hits
    
    async def _keyword_search(self, query: str) -> List[SearchHit]:
        """关键词搜索（简化实现）"""
        return []
    
    async def _semantic_search(self, query: str, top_k: int = 10) -> List[SearchHit]:
        """语义相似度搜索"""
        if not self._vector_store:
            return []
        
        embedding = self._generate_embedding(query)
        results = await self._vector_store.search(embedding, top_k)
        
        hits = []
        for result in results:
            hits.append(SearchHit(
                content=result.content if hasattr(result, 'content') else str(result.metadata),
                score=result.score,
                metadata=result.metadata,
                source_type="vector",
            ))
        
        return hits
    
    async def _graph_search(self, query: str) -> List[SearchHit]:
        """知识图谱搜索"""
        hits = []
        
        if not self._knowledge_graph:
            return hits
        
        # 识别查询中的实体
        if self._entity_recognizer:
            result = self._entity_recognizer.recognize(query)
            for entity in result.entities:
                # 遍历实体关系
                relations = await self._knowledge_graph.traverse_relations(entity.text, depth=2)
                for rel in relations:
                    for path_item in rel["path"]:
                        neighbor_id = path_item["neighbor_id"]
                        neighbor = await self._knowledge_graph.get_entity(neighbor_id)
                        if neighbor:
                            hits.append(SearchHit(
                                content=neighbor.description or neighbor.name,
                                score=rel["confidence"],
                                metadata={
                                    "entity_id": neighbor.id,
                                    "entity_type": neighbor.type,
                                    "relation": path_item["relation"],
                                },
                                source_type="graph",
                            ))
        
        return hits
    
    def _generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入向量"""
        import re
        
        text = text.lower()
        words = re.findall(r'[\w]+', text)
        vec = [0.0] * 384
        
        for word in words:
            word_hash = hash(word) % 384
            vec[word_hash] += 1.0
        
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        
        return vec
    
    async def _fuse_results(self, hits: List[SearchHit], query: str) -> QueryResult:
        """
        融合搜索结果
        
        Args:
            hits: 搜索命中列表
            query: 查询文本
            
        Returns:
            QueryResult 融合后的结果
        """
        if not hits:
            return QueryResult(content="未找到相关信息", confidence=0.0)
        
        # 去重和重排序
        unique_hits = {}
        for hit in hits:
            key = hit.content[:100]
            if key not in unique_hits or hit.score > unique_hits[key].score:
                unique_hits[key] = hit
        
        sorted_hits = sorted(unique_hits.values(), key=lambda h: h.score, reverse=True)
        
        # 提取实体
        entities = []
        if self._entity_recognizer:
            result = self._entity_recognizer.recognize(query)
            for entity in result.entities:
                entities.append({
                    "text": entity.text,
                    "type": entity.entity_type.value,
                    "confidence": entity.confidence,
                })
        
        # 构建最终结果
        top_hits = sorted_hits[:3]
        content_parts = []
        sources = []
        
        for hit in top_hits:
            content_parts.append(hit.content)
            sources.append({
                "score": hit.score,
                "type": hit.source_type,
                "metadata": hit.metadata,
            })
        
        content = "\n\n".join(content_parts) if content_parts else "未找到相关信息"
        
        return QueryResult(
            content=content,
            sources=sources,
            confidence=sorted_hits[0].score if sorted_hits else 0.0,
            entities=entities,
        )
    
    def _generate_related_queries(self, query: str, entities: List[Dict[str, Any]]) -> List[str]:
        """
        生成相关查询建议
        
        Args:
            query: 当前查询
            entities: 识别到的实体
            
        Returns:
            List 相关查询列表
        """
        related = []
        
        # 基于实体生成相关查询
        for entity in entities:
            entity_text = entity.get("text", "")
            if entity_text:
                related.append(f"{entity_text} 是什么？")
                related.append(f"{entity_text} 的特点")
                related.append(f"{entity_text} 如何使用")
        
        # 基于疑问词生成相关查询
        question_words = ["什么", "如何", "为什么", "哪里", "谁", "何时"]
        for qw in question_words:
            if qw in query:
                # 尝试生成其他类型的问题
                for other_qw in question_words:
                    if other_qw != qw:
                        new_query = query.replace(qw, other_qw, 1)
                        if new_query != query:
                            related.append(new_query)
        
        # 去重并限制数量
        return list(set(related))[:5]


# 全局查询引擎实例
_query_engine_instance = None

def get_query_engine() -> QueryEngine:
    """获取全局查询引擎实例"""
    global _query_engine_instance
    if _query_engine_instance is None:
        _query_engine_instance = QueryEngine()
    return _query_engine_instance