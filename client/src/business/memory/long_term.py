"""
Long-term Memory - 长期知识

存储知识图谱、Wiki知识和结构化长期数据，用于复杂推理和关系查询。

特性：
- 较高延迟访问（秒级）
- 大容量存储
- 支持知识图谱查询和推理
- 数据保留期：无限期（> 30天）

包含：
- KnowledgeGraphMemory: 知识图谱存储和推理
"""

import time
from typing import Dict, Any, Optional, List, Tuple
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


class KnowledgeGraphMemory:
    """知识图谱存储 - 用于复杂推理和关系查询"""
    
    def __init__(self):
        self._logger = logger.bind(component="KnowledgeGraphMemory")
        self._nodes: Dict[str, KnowledgeNode] = {}
        self._relations: List[KnowledgeRelation] = []
        
        # 集成统一知识图谱服务
        self._knowledge_graph_service = None
        self._init_knowledge_graph()
        
        self._logger.info("KnowledgeGraphMemory 初始化完成")
    
    def _init_knowledge_graph(self):
        """初始化知识图谱连接"""
        try:
            from .knowledge_graph_service import get_knowledge_graph_service
            self._knowledge_graph_service = get_knowledge_graph_service()
            self._logger.info("✓ 集成 UnifiedKnowledgeGraphService")
        except Exception as e:
            self._logger.warning(f"UnifiedKnowledgeGraphService 加载失败，使用内存存储: {e}")
    
    def query(self, query: str, context: Dict = None) -> Dict:
        """
        查询知识图谱
        
        Args:
            query: 查询内容
            context: 上下文
        
        Returns:
            查询结果
        """
        # 如果有统一知识图谱服务，优先使用
        if self._knowledge_graph_service:
            try:
                # 使用统一知识图谱服务的混合检索
                results = self._knowledge_graph_service.hybrid_retrieve(query, top_k=3)
                if results:
                    contents = [r.entity for r in results]
                    avg_confidence = sum(r.confidence for r in results) / len(results)
                    return {
                        "success": True,
                        "content": "\n".join(contents),
                        "confidence": avg_confidence,
                        "type": "knowledge_graph",
                        "source": "long_term",
                        "results": [
                            {"entity": r.entity, "score": r.score, "confidence": r.confidence}
                            for r in results
                        ]
                    }
            except Exception as e:
                self._logger.warning(f"统一知识图谱服务查询失败，回退到内存存储: {e}")
        
        # 内存存储查询（简单实现）
        if not self._nodes:
            return {"success": False, "content": "", "confidence": 0.0}
        
        query_lower = query.lower()
        
        # 查找匹配的节点
        matched_nodes = []
        for node in self._nodes.values():
            if query_lower in node.label.lower():
                matched_nodes.append(node)
        
        if matched_nodes:
            # 构建关系路径
            relations = []
            for node in matched_nodes:
                rels = self._get_relations_for_node(node.id)
                relations.extend(rels)
            
            content = self._format_result(matched_nodes, relations)
            
            return {
                "success": True,
                "content": content,
                "confidence": 0.6 + len(matched_nodes) * 0.1,
                "type": "knowledge_graph",
                "source": "long_term",
                "matched_nodes": [n.label for n in matched_nodes],
                "relation_count": len(relations)
            }
        
        return {"success": False, "content": "", "confidence": 0.0}
    
    def _get_relations_for_node(self, node_id: str) -> List[KnowledgeRelation]:
        """获取节点相关的关系"""
        return [r for r in self._relations if r.source_id == node_id or r.target_id == node_id]
    
    def _format_result(self, nodes: List[KnowledgeNode], relations: List[KnowledgeRelation]) -> str:
        """格式化查询结果"""
        parts = []
        
        for node in nodes:
            props = ", ".join(f"{k}: {v}" for k, v in node.properties.items())
            if props:
                parts.append(f"- {node.label} ({props})")
            else:
                parts.append(f"- {node.label}")
        
        if relations:
            parts.append("\n关系:")
            for rel in relations[:5]:
                source_label = self._nodes.get(rel.source_id, KnowledgeNode(id="", label="Unknown")).label
                target_label = self._nodes.get(rel.target_id, KnowledgeNode(id="", label="Unknown")).label
                parts.append(f"  {source_label} -{rel.relation_type}-> {target_label}")
        
        return "\n".join(parts)
    
    def store(self, content: str, **kwargs) -> str:
        """
        存储知识到图谱
        
        Args:
            content: 知识内容
            **kwargs: 包含 id, label, properties, relations 等
        
        Returns:
            存储的ID
        """
        entry_id = kwargs.get("id", f"kg_{int(time.time())}")
        label = kwargs.get("label", content[:50])
        properties = kwargs.get("properties", {})
        
        # 如果有外部知识图谱，优先使用
        if self._knowledge_graph:
            try:
                result = self._knowledge_graph.add_node(content, label, properties)
                return result.get("id", entry_id)
            except Exception as e:
                self._logger.warning(f"知识图谱存储失败，回退到内存存储: {e}")
        
        # 内存存储
        self._nodes[entry_id] = KnowledgeNode(
            id=entry_id,
            label=label,
            properties=properties
        )
        
        # 添加关系
        if "relations" in kwargs:
            for rel in kwargs["relations"]:
                self._relations.append(KnowledgeRelation(
                    source_id=entry_id,
                    target_id=rel.get("target_id", ""),
                    relation_type=rel.get("type", "related_to"),
                    properties=rel.get("properties", {})
                ))
        
        return entry_id
    
    def add_relation(self, source_id: str, target_id: str, relation_type: str, **kwargs):
        """添加关系"""
        if source_id not in self._nodes or target_id not in self._nodes:
            self._logger.warning("添加关系失败：节点不存在")
            return False
        
        self._relations.append(KnowledgeRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            properties=kwargs
        ))
        
        return True
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_nodes": len(self._nodes),
            "total_relations": len(self._relations),
            "using_external_graph": self._knowledge_graph is not None
        }


# 单例模式
_knowledge_graph_memory_instance = None

def get_knowledge_graph_memory() -> KnowledgeGraphMemory:
    """获取知识图谱存储实例"""
    global _knowledge_graph_memory_instance
    if _knowledge_graph_memory_instance is None:
        _knowledge_graph_memory_instance = KnowledgeGraphMemory()
    return _knowledge_graph_memory_instance


if __name__ == "__main__":
    print("=" * 60)
    print("Long-term Memory 测试")
    print("=" * 60)
    
    kg_mem = get_knowledge_graph_memory()
    
    # 添加一些测试知识
    ai_id = kg_mem.store("人工智能", label="人工智能", properties={"领域": "计算机科学", "创立时间": "1956年"})
    ml_id = kg_mem.store("机器学习", label="机器学习", properties={"领域": "人工智能"})
    dl_id = kg_mem.store("深度学习", label="深度学习", properties={"领域": "机器学习"})
    
    # 添加关系
    kg_mem.add_relation(ai_id, ml_id, "包含")
    kg_mem.add_relation(ml_id, dl_id, "包含")
    
    result = kg_mem.query("人工智能")
    print(f"知识图谱查询 '人工智能':")
    print(f"  成功: {result['success']}")
    print(f"  置信度: {result['confidence']:.2f}")
    print(f"  内容:\n{result['content']}")
    
    print("\n" + "=" * 60)