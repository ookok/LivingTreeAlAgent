"""
FusionRAG Core Engine

核心引擎模块，提供统一的 RAG 入口，集成 DeepOnto 本体推理能力。

作者: LivingTreeAI Team
日期: 2026-05-01
版本: 3.1.0
"""

import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    from deeponto.onto import Ontology
    from deeponto.reasoner import DLReasoner
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False


@dataclass
class RAGResult:
    """RAG 查询结果"""
    content: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: Optional[str] = None
    entities: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class IngestResult:
    """数据摄入结果"""
    success: bool
    document_id: str
    entities_count: int = 0
    relations_count: int = 0
    message: str = ""


class FusionRAGEngine:
    """
    FusionRAG 核心引擎
    
    提供统一的 RAG 入口，整合以下能力：
    - 多模态数据摄入
    - 知识图谱管理
    - 智能查询
    - 推理引擎
    - 本体推理（DeepOnto集成）
    """
    
    def __init__(self):
        """初始化 FusionRAG 引擎"""
        self._ingestor = None
        self._knowledge_graph = None
        self._query_engine = None
        self._reasoning_engine = None
        self._vector_store = None
        self._ontology_reasoner = None
        self._entity_embedding_service = None
        
        self._init_modules()
        logger.info("FusionRAG Engine v3.1.0 初始化完成")
    
    def _init_modules(self):
        """懒加载模块"""
        try:
            from .ingestor import MultiModalIngestor
            from .knowledge_graph import DynamicKnowledgeGraph
            from .query_engine import QueryEngine
            from .reasoning import ReasoningEngine
            from .smart_vector_store import get_smart_vector_store
            from ..deeponto_integration import get_ontology_reasoner, get_entity_embedding_service
            
            self._ingestor = MultiModalIngestor()
            self._knowledge_graph = DynamicKnowledgeGraph()
            self._query_engine = QueryEngine()
            self._reasoning_engine = ReasoningEngine()
            self._vector_store = get_smart_vector_store()
            
            self._ontology_reasoner = get_ontology_reasoner()
            self._ontology_reasoner.initialize()
            self._entity_embedding_service = get_entity_embedding_service()
            self._entity_embedding_service.initialize()
            
            logger.info("所有模块加载成功（含DeepOnto集成）")
        except ImportError as e:
            logger.warning(f"模块加载失败: {e}")
    
    async def ingest(self, data: Union[str, bytes], data_type: str = "text", 
                     metadata: Optional[Dict[str, Any]] = None) -> IngestResult:
        """
        摄入数据
        
        Args:
            data: 数据内容
            data_type: 数据类型 (text, pdf, image, audio, video)
            metadata: 元数据
            
        Returns:
            IngestResult 摄入结果
        """
        if not self._ingestor:
            return IngestResult(success=False, document_id="", message="Ingestor 未加载")
        
        return await self._ingestor.ingest(data, data_type, metadata)
    
    async def query(self, query: str, context: Optional[str] = None, 
                   depth: int = 3) -> RAGResult:
        """
        查询知识
        
        Args:
            query: 查询文本
            context: 上下文
            depth: 检索深度 (1-3)
            
        Returns:
            RAGResult 查询结果
        """
        if not self._query_engine:
            return RAGResult(content="Query Engine 未加载", confidence=0.0)
        
        return await self._query_engine.query(query, context, depth)
    
    async def reasoning_query(self, query: str, context: Optional[str] = None,
                             reasoning_type: str = "default") -> RAGResult:
        """
        带推理的查询
        
        Args:
            query: 查询文本
            context: 上下文
            reasoning_type: 推理类型 (default, step_by_step, creative)
            
        Returns:
            RAGResult 查询结果（包含推理过程）
        """
        if not self._reasoning_engine:
            return RAGResult(content="Reasoning Engine 未加载", confidence=0.0)
        
        return await self._reasoning_engine.reason(query, context, reasoning_type)
    
    async def add_entity(self, entity: Dict[str, Any]) -> bool:
        """
        添加实体到知识图谱
        
        Args:
            entity: 实体信息
            
        Returns:
            bool 是否成功
        """
        if not self._knowledge_graph:
            return False
        
        return await self._knowledge_graph.add_entity(entity)
    
    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        获取实体信息
        
        Args:
            entity_id: 实体ID
            
        Returns:
            Dict 实体信息
        """
        if not self._knowledge_graph:
            return None
        
        return await self._knowledge_graph.get_entity(entity_id)
    
    async def explore_relations(self, entity_id: str, depth: int = 2) -> List[Dict[str, Any]]:
        """
        探索实体关系
        
        Args:
            entity_id: 实体ID
            depth: 关系深度
            
        Returns:
            List 关系列表
        """
        if not self._knowledge_graph:
            return []
        
        return await self._knowledge_graph.traverse_relations(entity_id, depth)
    
    async def ontological_query(self, query: str, context: Optional[str] = None) -> RAGResult:
        """
        基于本体推理的查询
        
        Args:
            query: 查询文本
            context: 上下文
            
        Returns:
            RAGResult 查询结果（包含本体推理）
        """
        if not self._ontology_reasoner:
            return RAGResult(content="本体推理引擎未加载", confidence=0.0)
        
        result = RAGResult(content="", confidence=0.8)
        
        try:
            reasoning_result = self._ontology_reasoner.reason({"query": query, "context": context})
            result.content = "\n".join(reasoning_result.inferred_axioms)
            result.confidence = 0.85
            result.reasoning = "基于本体推理"
            result.entities = [{"id": e, "types": reasoning_result.instance_types.get(e, [])} 
                              for e in reasoning_result.instance_types.keys()]
            
            if reasoning_result.class_hierarchy:
                result.sources = [{"type": "ontology", "hierarchy": reasoning_result.class_hierarchy}]
            
            logger.info("本体推理查询完成")
        except Exception as e:
            logger.error(f"本体推理失败: {e}")
            result.content = f"本体推理失败: {str(e)}"
            result.confidence = 0.5
        
        return result
    
    async def semantic_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        语义搜索（基于实体嵌入）
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            List 语义相似结果
        """
        if not self._entity_embedding_service:
            return await self.search_similar(query, top_k)
        
        try:
            entities = self._extract_entities(query)
            if not entities:
                return await self.search_similar(query, top_k)
            
            results = []
            for entity in entities:
                similar = self._entity_embedding_service.find_similar_entities(entity, entities, top_k)
                for match in similar:
                    results.append({
                        "entity": match.entity_id,
                        "score": match.score,
                        "metadata": match.metadata
                    })
            
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]
        except Exception as e:
            logger.error(f"语义搜索失败: {e}")
            return await self.search_similar(query, top_k)
    
    def _extract_entities(self, text: str) -> List[str]:
        """从文本中提取实体"""
        if self._ontology_reasoner:
            try:
                return self._ontology_reasoner.infer_relations(text, "")
            except:
                pass
        
        import re
        return re.findall(r'\b[A-Z][a-z]+\b', text)
    
    async def search_similar(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        搜索相似内容
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            List 相似内容列表
        """
        if not self._vector_store:
            return []
        
        results = await self._vector_store.search(self._generate_embedding(query), top_k)
        return [{"content": r.content, "score": r.score, "metadata": r.metadata} for r in results]
    
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
    
    def get_stats(self) -> Dict[str, Any]:
        """获取引擎统计信息"""
        stats = {
            "version": "3.0.0",
            "modules": {
                "ingestor": self._ingestor is not None,
                "knowledge_graph": self._knowledge_graph is not None,
                "query_engine": self._query_engine is not None,
                "reasoning_engine": self._reasoning_engine is not None,
                "vector_store": self._vector_store is not None,
            },
        }
        
        if self._vector_store:
            stats["vector_store"] = self._vector_store.get_info()
        
        if self._knowledge_graph:
            stats["knowledge_graph"] = self._knowledge_graph.get_stats()
        
        return stats


# 全局引擎实例
_engine_instance = None

def get_fusion_rag_engine() -> FusionRAGEngine:
    """获取全局 FusionRAG 引擎实例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = FusionRAGEngine()
    return _engine_instance