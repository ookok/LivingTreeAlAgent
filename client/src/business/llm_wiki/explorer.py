"""
Entity Explorer

实体探索器，支持可视化展示实体关系、遍历知识图谱等功能，集成DeepOnto本体推理。

作者: LivingTreeAI Team
日期: 2026-05-01
版本: 1.1.0
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    from deeponto.reasoner import DLReasoner
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False


@dataclass
class EntityNode:
    """实体节点"""
    id: str
    name: str
    type: str
    description: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


@dataclass
class RelationEdge:
    """关系边"""
    source: str
    target: str
    predicate: str
    confidence: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExplorationResult:
    """探索结果"""
    entity: EntityNode
    relations: List[RelationEdge] = field(default_factory=list)
    neighbors: List[EntityNode] = field(default_factory=list)
    depth: int = 1


class EntityExplorer:
    """
    实体探索器
    
    核心功能：
    - 实体详情展示
    - 关系图遍历
    - 多维度搜索
    - 路径查找
    """
    
    def __init__(self):
        """初始化实体探索器"""
        self._knowledge_graph = None
        self._entity_kb = None
        self._wiki_core = None
        
        self._init_dependencies()
        logger.info("EntityExplorer 初始化完成")
    
    def _init_dependencies(self):
        """初始化依赖模块"""
        try:
            from ..fusion_rag.knowledge_graph import DynamicKnowledgeGraph
            from ..entity_management import get_entity_knowledge_base
            from .wiki_core import WikiCore
            
            self._knowledge_graph = DynamicKnowledgeGraph()
            self._entity_kb = get_entity_knowledge_base()
            self._wiki_core = WikiCore()
            
            logger.info("依赖模块加载成功")
        except ImportError as e:
            logger.warning(f"依赖模块加载失败: {e}")
    
    async def explore(self, entity_id: str, depth: int = 2) -> ExplorationResult:
        """
        探索实体
        
        Args:
            entity_id: 实体ID
            depth: 探索深度
            
        Returns:
            ExplorationResult 探索结果
        """
        if not self._knowledge_graph:
            return ExplorationResult(
                entity=EntityNode(id=entity_id, name=entity_id, type="unknown"),
                relations=[],
                neighbors=[],
                depth=0,
            )
        
        # 获取实体信息
        entity = await self._knowledge_graph.get_entity(entity_id)
        
        if not entity:
            # 从实体知识库获取
            kb_results = self._entity_kb.search_entities(entity_id)
            if kb_results:
                kb_entity = kb_results[0].entity
                entity_info = EntityNode(
                    id=kb_entity.entity_id or entity_id,
                    name=kb_entity.canonical_name,
                    type=kb_entity.entity.entity_type.value,
                    description=kb_entity.description,
                    attributes=kb_entity.attributes,
                    score=kb_results[0].score,
                )
            else:
                entity_info = EntityNode(id=entity_id, name=entity_id, type="unknown")
        else:
            entity_info = EntityNode(
                id=entity.id,
                name=entity.name,
                type=entity.type,
                description=entity.description,
                attributes=entity.attributes,
                score=1.0,
            )
        
        # 获取关系
        relations = await self._knowledge_graph.traverse_relations(entity_id, depth)
        
        # 构建关系边和邻居节点
        relation_edges = []
        neighbors = []
        seen_neighbors = set()
        
        for rel_info in relations:
            for path_item in rel_info["path"]:
                neighbor_id = path_item["neighbor_id"]
                
                if neighbor_id not in seen_neighbors:
                    seen_neighbors.add(neighbor_id)
                    
                    # 获取邻居实体信息
                    neighbor = await self._knowledge_graph.get_entity(neighbor_id)
                    if neighbor:
                        neighbors.append(EntityNode(
                            id=neighbor.id,
                            name=neighbor.name,
                            type=neighbor.type,
                            description=neighbor.description,
                            attributes=neighbor.attributes,
                            score=rel_info["confidence"],
                        ))
                    
                    # 添加关系边
                    relation_edges.append(RelationEdge(
                        source=entity_id,
                        target=neighbor_id,
                        predicate=path_item["relation"],
                        confidence=rel_info["confidence"],
                    ))
        
        return ExplorationResult(
            entity=entity_info,
            relations=relation_edges,
            neighbors=neighbors,
            depth=depth,
        )
    
    async def search_entities(self, query: str, entity_type: Optional[str] = None, 
                             limit: int = 20) -> List[EntityNode]:
        """
        搜索实体
        
        Args:
            query: 搜索词
            entity_type: 实体类型过滤
            limit: 返回数量限制
            
        Returns:
            List 实体节点列表
        """
        results = []
        
        # 从知识图谱搜索
        if self._knowledge_graph:
            kg_results = await self._knowledge_graph.search_entities(query, entity_type)
            for entity in kg_results:
                results.append(EntityNode(
                    id=entity.id,
                    name=entity.name,
                    type=entity.type,
                    description=entity.description,
                    attributes=entity.attributes,
                    score=0.9,
                ))
        
        # 从实体知识库搜索
        if self._entity_kb:
            kb_results = self._entity_kb.search_entities(query)
            for result in kb_results:
                entity = result.entity
                # 去重
                if entity.entity_id and not any(r.id == entity.entity_id for r in results):
                    results.append(EntityNode(
                        id=entity.entity_id or entity.canonical_name,
                        name=entity.canonical_name,
                        type=entity.entity.entity_type.value,
                        description=entity.description,
                        attributes=entity.attributes,
                        score=result.score * 0.8,
                    ))
        
        # 按分数排序并限制数量
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
    
    async def find_path(self, start_id: str, end_id: str, max_depth: int = 3) -> Optional[List[str]]:
        """
        查找两个实体之间的路径
        
        Args:
            start_id: 起始实体ID
            end_id: 目标实体ID
            max_depth: 最大深度
            
        Returns:
            List 路径（实体ID列表）
        """
        if not self._knowledge_graph:
            return None
        
        return await self._knowledge_graph.find_path(start_id, end_id, max_depth)
    
    def get_entity_types(self) -> List[str]:
        """获取所有实体类型"""
        return [
            "person", "organization", "location", "tech_term", "concept",
            "product", "algorithm", "framework", "language", "event",
        ]
    
    async def get_entity_wiki_pages(self, entity_name: str) -> List[Dict[str, Any]]:
        """
        获取与实体相关的 Wiki 页面
        
        Args:
            entity_name: 实体名称
            
        Returns:
            List Wiki 页面列表
        """
        if not self._wiki_core:
            return []
        
        # 搜索包含实体名称的页面
        pages = self._wiki_core.search_pages(entity_name)
        
        return [{
            "id": page.id,
            "title": page.title,
            "summary": page.summary,
            "updated_at": page.updated_at,
        } for page in pages]
    
    def get_relation_types(self) -> List[str]:
        """获取所有关系类型"""
        return [
            "related_to", "works_at", "born_in", "created", "studied_at",
            "located_in", "produces", "founded_by", "created_by", "used_for",
            "based_on", "used_in", "developed_by", "contains",
        ]
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "knowledge_graph_available": self._knowledge_graph is not None,
            "entity_kb_available": self._entity_kb is not None,
            "wiki_core_available": self._wiki_core is not None,
        }
        
        if self._knowledge_graph:
            kg_stats = self._knowledge_graph.get_stats()
            stats.update({
                "total_entities": kg_stats.get("total_entities", 0),
                "total_relations": kg_stats.get("total_relations", 0),
            })
        
        if self._entity_kb:
            kb_stats = self._entity_kb.get_stats()
            stats["kb_total_entities"] = kb_stats.get("total_entities", 0)
        
        return stats


# 全局探索器实例
_explorer_instance = None

def get_entity_explorer() -> EntityExplorer:
    """获取全局实体探索器实例"""
    global _explorer_instance
    if _explorer_instance is None:
        _explorer_instance = EntityExplorer()
    return _explorer_instance