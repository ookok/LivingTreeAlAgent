"""
统一知识图谱服务 (Unified Knowledge Graph Service)

整合现有知识图谱模块：
1. llm_wiki - EvoRAG集成版知识图谱
2. knowledge_graph - 概念节点和图存储

提供统一接口：
- 知识检索
- 知识推理
- 知识融合
- 知识进化
- 图查询
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class KnowledgeNode:
    """知识节点"""
    id: str
    label: str
    properties: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())


@dataclass
class KnowledgeRelation:
    """知识关系"""
    source_id: str
    target_id: str
    relation_type: str
    properties: Dict = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """检索结果"""
    entity: str
    score: float
    path: List[str] = field(default_factory=list)
    context: str = ""
    confidence: float = 0.0


class UnifiedKnowledgeGraphService:
    """统一知识图谱服务"""
    
    def __init__(self):
        self._logger = logger.bind(component="UnifiedKnowledgeGraphService")
        
        # 集成的知识图谱组件
        self._llm_wiki_integrator = None
        self._knowledge_graph_manager = None
        
        # 初始化组件
        self._init_components()
        
        # 内存存储（备用）
        self._nodes: Dict[str, KnowledgeNode] = {}
        self._relations: List[KnowledgeRelation] = []
        
        self._logger.info("统一知识图谱服务初始化完成")
    
    def _init_components(self):
        """初始化知识图谱组件"""
        # 1. 集成 LLMWikiKnowledgeGraphIntegratorV4（EvoRAG版）
        try:
            from business.llm_wiki.knowledge_graph_integrator_v4 import (
                LLMWikiKnowledgeGraphIntegratorV4
            )
            self._llm_wiki_integrator = LLMWikiKnowledgeGraphIntegratorV4()
            self._logger.info("✓ 集成 LLMWikiKnowledgeGraphIntegratorV4 (EvoRAG)")
        except Exception as e:
            self._logger.warning(f"LLMWikiKnowledgeGraphIntegratorV4 加载失败: {e}")
        
        # 2. 集成 KnowledgeGraphManager
        try:
            from business.knowledge_graph.knowledge_graph_manager import (
                KnowledgeGraphManager
            )
            self._knowledge_graph_manager = KnowledgeGraphManager()
            self._logger.info("✓ 集成 KnowledgeGraphManager")
        except Exception as e:
            self._logger.warning(f"KnowledgeGraphManager 加载失败: {e}")
    
    def hybrid_retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """
        混合检索 - 综合多个知识源
        
        Args:
            query: 查询内容
            top_k: 返回数量
        
        Returns:
            检索结果列表
        """
        results = []
        
        # 1. 使用 EvoRAG 混合检索
        if self._llm_wiki_integrator:
            try:
                evorag_results = self._llm_wiki_integrator.hybrid_retrieve(query, top_k=top_k)
                for i, result in enumerate(evorag_results[:top_k]):
                    if hasattr(result, 'entity'):
                        results.append(RetrievalResult(
                            entity=result.entity,
                            score=result.score if hasattr(result, 'score') else 0.7 - i * 0.1,
                            confidence=0.7
                        ))
                    else:
                        results.append(RetrievalResult(
                            entity=str(result),
                            score=0.6 - i * 0.05,
                            confidence=0.6
                        ))
            except Exception as e:
                self._logger.warning(f"EvoRAG检索失败: {e}")
        
        # 2. 使用 KnowledgeGraphManager
        if self._knowledge_graph_manager:
            try:
                kg_results = self._knowledge_graph_manager.search(query, limit=top_k)
                for result in kg_results:
                    results.append(RetrievalResult(
                        entity=result.get('label', str(result)),
                        score=result.get('score', 0.5),
                        confidence=0.5
                    ))
            except Exception as e:
                self._logger.warning(f"KnowledgeGraphManager检索失败: {e}")
        
        # 3. 内存存储检索
        memory_results = self._search_memory(query)
        results.extend(memory_results)
        
        # 排序并去重
        results = sorted(results, key=lambda x: x.score, reverse=True)[:top_k]
        
        return results
    
    def _search_memory(self, query: str) -> List[RetrievalResult]:
        """在内存存储中搜索"""
        results = []
        query_lower = query.lower()
        
        for node_id, node in self._nodes.items():
            if query_lower in node.label.lower():
                results.append(RetrievalResult(
                    entity=node.label,
                    score=0.4,
                    confidence=0.4,
                    context=str(node.properties)
                ))
        
        return results
    
    def reason_over_graph(self, query: str, max_depth: int = 3) -> Dict:
        """
        基于图谱的推理
        
        Args:
            query: 查询内容
            max_depth: 最大推理深度
        
        Returns:
            推理结果
        """
        if self._llm_wiki_integrator:
            try:
                return self._llm_wiki_integrator.reason_over_graph_evorag(query, top_k=3)
            except Exception as e:
                self._logger.warning(f"EvoRAG推理失败: {e}")
        
        return {
            "success": False,
            "message": "推理引擎不可用"
        }
    
    def add_node(self, label: str, **properties) -> str:
        """
        添加知识节点
        
        Args:
            label: 节点标签
            **properties: 节点属性
        
        Returns:
            节点ID
        """
        node_id = f"node_{int(time.time())}"
        
        # 添加到内存存储
        self._nodes[node_id] = KnowledgeNode(
            id=node_id,
            label=label,
            properties=properties
        )
        
        # 同步到 KnowledgeGraphManager
        if self._knowledge_graph_manager:
            try:
                self._knowledge_graph_manager.add_concept(label, properties)
            except Exception as e:
                self._logger.warning(f"同步到KnowledgeGraphManager失败: {e}")
        
        return node_id
    
    def add_relation(self, source_id: str, target_id: str, relation_type: str, **properties):
        """
        添加知识关系
        
        Args:
            source_id: 源节点ID
            target_id: 目标节点ID
            relation_type: 关系类型
            **properties: 关系属性
        
        Returns:
            是否成功
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            return False
        
        self._relations.append(KnowledgeRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            properties=properties
        ))
        
        return True
    
    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取节点"""
        return self._nodes.get(node_id)
    
    def get_relations(self, node_id: str) -> List[KnowledgeRelation]:
        """获取节点相关的关系"""
        return [r for r in self._relations 
                if r.source_id == node_id or r.target_id == node_id]
    
    def knowledge_fusion(self, sources: List[str]) -> Dict:
        """
        知识融合 - 从多个来源融合知识
        
        Args:
            sources: 来源列表
        
        Returns:
            融合结果
        """
        fused_knowledge = {
            "sources": sources,
            "merged_concepts": [],
            "conflicts": [],
            "summary": ""
        }
        
        # 简单融合：合并所有来源的知识
        all_results = []
        for source in sources:
            results = self.hybrid_retrieve(source, top_k=3)
            all_results.extend(results)
        
        # 去重并排序
        seen = set()
        unique_results = []
        for r in all_results:
            if r.entity not in seen:
                seen.add(r.entity)
                unique_results.append(r)
        
        fused_knowledge["merged_concepts"] = [r.entity for r in unique_results]
        fused_knowledge["summary"] = f"从{len(sources)}个来源融合了{len(unique_results)}个概念"
        
        return fused_knowledge
    
    def graph_query(self, query: str) -> Dict:
        """
        图查询接口
        
        Args:
            query: 图查询语言或自然语言
        
        Returns:
            查询结果
        """
        # 尝试使用不同的查询方式
        if self._knowledge_graph_manager:
            try:
                return self._knowledge_graph_manager.query(query)
            except Exception as e:
                self._logger.warning(f"图查询失败: {e}")
        
        # 简单实现：返回节点和关系
        return {
            "nodes": [{"id": k, "label": v.label} for k, v in self._nodes.items()],
            "relations": [
                {
                    "source": r.source_id,
                    "target": r.target_id,
                    "type": r.relation_type
                } for r in self._relations
            ]
        }
    
    async def hybrid_retrieve_async(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """异步混合检索"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.hybrid_retrieve, query, top_k)
    
    async def reason_over_graph_async(self, query: str, max_depth: int = 3) -> Dict:
        """异步图谱推理"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.reason_over_graph, query, max_depth)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_nodes": len(self._nodes),
            "total_relations": len(self._relations),
            "llm_wiki_integrated": self._llm_wiki_integrator is not None,
            "knowledge_graph_manager_integrated": self._knowledge_graph_manager is not None
        }


# 单例模式
_knowledge_graph_service_instance = None

def get_knowledge_graph_service() -> UnifiedKnowledgeGraphService:
    """获取统一知识图谱服务实例"""
    global _knowledge_graph_service_instance
    if _knowledge_graph_service_instance is None:
        _knowledge_graph_service_instance = UnifiedKnowledgeGraphService()
    return _knowledge_graph_service_instance


if __name__ == "__main__":
    print("=" * 60)
    print("统一知识图谱服务测试")
    print("=" * 60)
    
    kg_service = get_knowledge_graph_service()
    
    stats = kg_service.get_stats()
    print(f"统计信息:")
    print(f"  - 节点数: {stats['total_nodes']}")
    print(f"  - 关系数: {stats['total_relations']}")
    print(f"  - LLM Wiki集成: {'是' if stats['llm_wiki_integrated'] else '否'}")
    print(f"  - KnowledgeGraphManager集成: {'是' if stats['knowledge_graph_manager_integrated'] else '否'}")
    
    # 测试添加节点
    print("\n测试添加知识节点...")
    ai_id = kg_service.add_node("人工智能", domain="计算机科学", year=1956)
    ml_id = kg_service.add_node("机器学习", domain="人工智能")
    print(f"添加节点: AI={ai_id}, ML={ml_id}")
    
    # 测试添加关系
    kg_service.add_relation(ai_id, ml_id, "包含")
    print(f"添加关系: AI -包含-> ML")
    
    # 测试检索
    print("\n测试混合检索...")
    results = kg_service.hybrid_retrieve("人工智能")
    print(f"检索结果 ({len(results)}):")
    for i, result in enumerate(results):
        print(f"  {i+1}. {result.entity} (分数: {result.score:.2f})")
    
    # 测试推理
    print("\n测试图谱推理...")
    reason_result = kg_service.reason_over_graph("人工智能包含哪些领域")
    print(f"推理结果: {reason_result.get('success', False)}")
    
    # 测试知识融合
    print("\n测试知识融合...")
    fusion_result = kg_service.knowledge_fusion(["人工智能", "机器学习", "深度学习"])
    print(f"融合来源: {fusion_result['sources']}")
    print(f"融合概念数: {len(fusion_result['merged_concepts'])}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)