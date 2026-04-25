"""
Cognee RAG 管道

完整的检索增强生成管道
支持知识图谱、向量检索、混合搜索
"""

from core.logger import get_logger
logger = get_logger('cognee_memory.rag_pipeline')

import asyncio
import json
import time
from typing import List, Dict, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .embedding import EmbeddingEngine, SemanticSearch, get_embedding_engine, get_semantic_search
from .multimodal_ingestion import MultimodalIngester, DataItem, get_multimodal_ingester


class RetrievalStrategy(Enum):
    """检索策略"""
    VECTOR = "vector"           # 向量检索
    KG = "knowledge_graph"      # 知识图谱
    HYBRID = "hybrid"           # 混合检索


@dataclass
class RAGConfig:
    """RAG 配置"""
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    vector_top_k: int = 5
    kg_top_k: int = 5
    final_top_k: int = 3
    min_similarity: float = 0.5
    rerank: bool = True
    max_context_length: int = 4000


@dataclass
class RetrievalResult:
    """检索结果"""
    content: str
    source: str  # vector, kg, text
    similarity: float
    metadata: Dict[str, Any]


@dataclass
class RAGContext:
    """RAG 上下文"""
    query: str
    retrieval_results: List[RetrievalResult]
    generated_answer: Optional[str] = None
    total_tokens: int = 0
    retrieval_time_ms: float = 0.0


class KnowledgeGraph:
    """知识图谱"""

    def __init__(self):
        self.entities: Dict[str, Dict[str, Any]] = {}
        self.relations: List[Dict[str, Any]] = []
        self.entity_memories: Dict[str, List[str]] = {}

    def add_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: str = "",
        properties: Optional[Dict[str, Any]] = None
    ):
        """添加实体"""
        self.entities[entity_id] = {
            "id": entity_id,
            "name": name,
            "type": entity_type,
            "properties": properties or {}
        }
        if entity_id not in self.entity_memories:
            self.entity_memories[entity_id] = []

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: Optional[Dict[str, Any]] = None
    ):
        """添加关系"""
        self.relations.append({
            "source": source_id,
            "target": target_id,
            "type": relation_type,
            "properties": properties or {}
        })

    def link_memory(self, entity_id: str, memory_content: str):
        """关联记忆"""
        if entity_id in self.entity_memories:
            self.entity_memories[entity_id].append(memory_content)

    def query_by_entity(
        self,
        entity_name: str,
        depth: int = 1
    ) -> List[Dict[str, Any]]:
        """
        按实体查询

        Args:
            entity_name: 实体名称
            depth: 查询深度

        Returns:
            List[Dict]: 相关的知识三元组
        """
        results = []

        # 查找实体
        for entity_id, entity in self.entities.items():
            if entity_name.lower() in entity["name"].lower():
                results.append({
                    "entity": entity,
                    "memories": self.entity_memories.get(entity_id, [])
                })

                # 查找关系
                for relation in self.relations:
                    if relation["source"] == entity_id:
                        target = self.entities.get(relation["target"])
                        if target:
                            results.append({
                                "source": entity,
                                "relation": relation,
                                "target": target
                            })

        return results

    def query_by_relation(
        self,
        relation_type: str
    ) -> List[Dict[str, Any]]:
        """按关系类型查询"""
        results = []
        for relation in self.relations:
            if relation["type"].lower() == relation_type.lower():
                source = self.entities.get(relation["source"])
                target = self.entities.get(relation["target"])
                if source and target:
                    results.append({
                        "source": source,
                        "relation": relation,
                        "target": target
                    })
        return results

    def get_context(self, query: str, top_k: int = 3) -> List[str]:
        """
        获取上下文

        Args:
            query: 查询
            top_k: 返回数量

        Returns:
            List[str]: 上下文字符串列表
        """
        contexts = []

        # 按实体查询
        entity_results = self.query_by_entity(query, depth=1)
        for result in entity_results[:top_k]:
            if "entity" in result:
                entity = result["entity"]
                ctx = f"{entity['name']}"
                if entity.get("type"):
                    ctx += f" ({entity['type']})"
                contexts.append(ctx)

                # 添加关联记忆
                for memory in result.get("memories", [])[:2]:
                    contexts.append(f"  - {memory[:100]}")

            if "relation" in result:
                rel = result["relation"]
                ctx = f"{result['source']['name']} {rel['type']} {result['target']['name']}"
                contexts.append(ctx)

        return contexts[:top_k]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "entities": self.entities,
            "relations": self.relations,
            "entity_memories": self.entity_memories
        }

    def from_dict(self, data: Dict[str, Any]):
        """从字典加载"""
        self.entities = data.get("entities", {})
        self.relations = data.get("relations", [])
        self.entity_memories = data.get("entity_memories", {})


class RAGPipeline:
    """
    Cognee RAG 管道

    完整流程：
    1. 数据摄入（多模态）
    2. 向量嵌入
    3. 知识图谱构建
    4. 混合检索
    5. 生成上下文
    """

    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()

        # 组件
        self.embedding_engine = get_embedding_engine()
        self.semantic_search = get_semantic_search(self.embedding_engine)
        self.ingester = get_multimodal_ingester()
        self.knowledge_graph = KnowledgeGraph()

        # 存储
        self.documents: Dict[str, DataItem] = {}
        self.chunks: List[Dict[str, Any]] = []

    async def ingest_data(
        self,
        source: str,
        source_type: str = "file"
    ) -> List[str]:
        """
        摄入数据

        Args:
            source: 数据源
            source_type: source 类型 (file, directory, text)

        Returns:
            List[str]: 摄入的 chunk ID 列表
        """
        chunk_ids = []

        if source_type == "file":
            item = await self.ingester.ingest_file(source)
            chunk_ids.extend(await self._process_item(item))

        elif source_type == "directory":
            items = await self.ingester.ingest_directory(source)
            for item in items:
                ids = await self._process_item(item)
                chunk_ids.extend(ids)

        elif source_type == "text":
            item = await self.ingester.ingest_text(source)
            chunk_ids.extend(await self._process_item(item))

        return chunk_ids

    async def _process_item(self, item: DataItem) -> List[str]:
        """处理数据项"""
        self.documents[item.item_id] = item

        chunk_ids = []
        for i, chunk in enumerate(item.chunks):
            chunk_id = f"{item.item_id}_chunk_{i}"

            # 添加到向量存储
            self.semantic_search.add_document(
                doc_id=chunk_id,
                content=chunk,
                metadata={
                    "item_id": item.item_id,
                    "source_type": item.source_type,
                    "source_path": item.source_path,
                    "chunk_index": i
                }
            )

            # 提取实体并添加到知识图谱
            entities = self._extract_entities(chunk)
            for entity in entities:
                self.knowledge_graph.add_entity(
                    entity_id=f"{chunk_id}_{entity['name']}",
                    name=entity["name"],
                    entity_type=entity.get("type", "")
                )
                self.knowledge_graph.link_memory(chunk_id, chunk)

            chunk_ids.append(chunk_id)
            self.chunks.append({
                "chunk_id": chunk_id,
                "content": chunk,
                "metadata": item.metadata
            })

        return chunk_ids

    def _extract_entities(self, text: str) -> List[Dict[str, str]]:
        """提取实体（简单实现）"""
        import re


        entities = []

        # 提取中文实体
        chinese_entities = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        for name in set(chinese_entities[:10]):  # 限制数量
            entities.append({"name": name, "type": "entity"})

        # 提取英文实体
        english_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        for name in set(english_entities[:10]):
            entities.append({"name": name, "type": "entity"})

        return entities

    async def retrieve(
        self,
        query: str,
        strategy: Optional[RetrievalStrategy] = None
    ) -> List[RetrievalResult]:
        """
        检索

        Args:
            query: 查询
            strategy: 检索策略

        Returns:
            List[RetrievalResult]: 检索结果
        """
        strategy = strategy or self.config.retrieval_strategy
        start_time = time.time()

        results = []

        # 向量检索
        if strategy in [RetrievalStrategy.VECTOR, RetrievalStrategy.HYBRID]:
            vector_results = self.semantic_search.search(
                query,
                top_k=self.config.vector_top_k,
                min_similarity=self.config.min_similarity
            )

            for result in vector_results:
                results.append(RetrievalResult(
                    content=result["content"],
                    source="vector",
                    similarity=result["similarity"],
                    metadata=result["metadata"]
                ))

        # 知识图谱检索
        if strategy in [RetrievalStrategy.KG, RetrievalStrategy.HYBRID]:
            kg_contexts = self.knowledge_graph.get_context(
                query,
                top_k=self.config.kg_top_k
            )

            for ctx in kg_contexts:
                results.append(RetrievalResult(
                    content=ctx,
                    source="kg",
                    similarity=0.8,  # 知识图谱不计算相似度
                    metadata={}
                ))

        # 去重和排序
        seen = set()
        unique_results = []
        for r in results:
            if r.content not in seen:
                seen.add(r.content)
                unique_results.append(r)

        # 重排序
        if self.config.rerank:
            unique_results.sort(key=lambda x: x.similarity, reverse=True)

        retrieval_time = (time.time() - start_time) * 1000

        return unique_results[:self.config.final_top_k]

    async def generate_context(
        self,
        query: str,
        max_length: Optional[int] = None
    ) -> str:
        """
        生成上下文

        Args:
            query: 查询
            max_length: 最大长度

        Returns:
            str: 上下文字符串
        """
        results = await self.retrieve(query)

        contexts = []
        total_length = 0
        max_length = max_length or self.config.max_context_length

        for result in results:
            ctx = f"[来源: {result.source}, 相似度: {result.similarity:.2f}]\n{result.content}\n"
            if total_length + len(ctx) > max_length:
                break
            contexts.append(ctx)
            total_length += len(ctx)

        return "\n".join(contexts)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_documents": len(self.documents),
            "total_chunks": len(self.chunks),
            "total_entities": len(self.knowledge_graph.entities),
            "total_relations": len(self.knowledge_graph.relations),
            "config": {
                "retrieval_strategy": self.config.retrieval_strategy.value,
                "vector_top_k": self.config.vector_top_k,
                "kg_top_k": self.config.kg_top_k
            }
        }


class CogneeRAGAdapter:
    """
    Cognee RAG 适配器

    整合所有功能，提供统一的 API
    """

    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self.pipeline = RAGPipeline(config)
        self._initialize()

    def _initialize(self):
        """初始化"""
        logger.info("[CogneeRAGAdapter] 初始化完成")

    async def add_knowledge(
        self,
        data: str,
        data_type: str = "text"
    ) -> bool:
        """
        添加知识

        Args:
            data: 数据
            data_type: data 类型 (text, file, directory)

        Returns:
            bool: 是否成功
        """
        try:
            await self.pipeline.ingest_data(data, data_type)
            return True
        except Exception as e:
            logger.info(f"[CogneeRAGAdapter] 添加知识失败: {e}")
            return False

    async def query(
        self,
        question: str,
        use_rag: bool = True
    ) -> Dict[str, Any]:
        """
        查询

        Args:
            question: 问题
            use_rag: 是否使用 RAG

        Returns:
            Dict: 结果，包含 answer, context, sources
        """
        if not use_rag:
            return {
                "answer": "",
                "context": "",
                "sources": [],
                "rag_used": False
            }

        # 检索
        results = await self.pipeline.retrieve(question)

        # 生成上下文
        context = await self.pipeline.generate_context(question)

        return {
            "answer": "",
            "context": context,
            "sources": [
                {
                    "content": r.content[:200],
                    "source": r.source,
                    "similarity": r.similarity
                }
                for r in results
            ],
            "rag_used": True
        }

    def get_memory_context(self, query: str, limit: int = 5) -> List[str]:
        """
        获取记忆上下文

        Args:
            query: 查询
            limit: 数量限制

        Returns:
            List[str]: 上下文列表
        """
        return self.pipeline.knowledge_graph.get_context(query, top_k=limit)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return self.pipeline.get_stats()


# 全局实例
_global_rag_adapter: Optional[CogneeRAGAdapter] = None


def get_cognee_rag() -> CogneeRAGAdapter:
    """获取 Cognee RAG 适配器"""
    global _global_rag_adapter
    if _global_rag_adapter is None:
        _global_rag_adapter = CogneeRAGAdapter()
    return _global_rag_adapter
