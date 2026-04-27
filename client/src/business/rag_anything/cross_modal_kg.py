"""
跨模态知识图谱模块

支持多模态内容的知识图谱构建：
- 文本实体抽取
- 图像实体抽取
- 跨模态关系抽取
- 图谱存储和检索
"""

import time
import asyncio
from typing import List, Optional, Dict, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid


# ============ 图谱元素 ============

class EntityType(Enum):
    """实体类型"""
    TEXT = "text"           # 文本实体
    IMAGE = "image"         # 图像实体
    TABLE = "table"         # 表格实体
    EQUATION = "equation"   # 公式实体
    CONCEPT = "concept"     # 概念实体
    TOPIC = "topic"         # 主题实体


class RelationType(Enum):
    """关系类型"""
    CONTAINS = "contains"           # 包含
    DESCRIBES = "describes"         # 描述
    EXPLAINS = "explains"           # 解释
    SUPPORTS = "supports"           # 支持
    REFERS_TO = "refers_to"         # 引用
    SIMILAR_TO = "similar_to"       # 相似
    DERIVED_FROM = "derived_from"   # 派生
    PART_OF = "part_of"             # 组成


@dataclass
class Entity:
    """实体"""
    entity_id: str
    entity_type: EntityType
    name: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    embeddings: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Relation:
    """关系"""
    relation_id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrossModalLink:
    """跨模态链接"""
    link_id: str
    source_entity: str
    target_entity: str
    modality: Tuple[str, str]  # (源模态, 目标模态)
    confidence: float
    link_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============ 跨模态知识图谱 ============

class CrossModalKnowledgeGraph:
    """
    跨模态知识图谱
    
    支持文本、图像、表格、公式的统一知识表示
    """
    
    def __init__(self, embedding_dim: int = 768):
        self.embedding_dim = embedding_dim
        
        # 存储
        self.entities: Dict[str, Entity] = {}
        self.relations: Dict[str, Relation] = {}
        self.cross_modal_links: Dict[str, CrossModalLink] = {}
        
        # 索引
        self.entity_type_index: Dict[EntityType, Set[str]] = defaultdict(set)
        self.entity_name_index: Dict[str, Set[str]] = defaultdict(set)
        
        # 统计
        self.stats = {
            "total_entities": 0,
            "total_relations": 0,
            "total_cross_modal_links": 0,
            "by_type": defaultdict(int),
        }
    
    def add_entity(self, entity: Entity) -> str:
        """
        添加实体
        
        Args:
            entity: 实体对象
            
        Returns:
            str: 实体 ID
        """
        # 生成 ID
        if not entity.entity_id:
            entity.entity_id = f"entity_{uuid.uuid4().hex[:12]}"
        
        # 存储实体
        self.entities[entity.entity_id] = entity
        
        # 更新索引
        self.entity_type_index[entity.entity_type].add(entity.entity_id)
        for name_part in entity.name.split():
            self.entity_name_index[name_part.lower()].add(entity.entity_id)
        
        # 更新统计
        self.stats["total_entities"] += 1
        self.stats["by_type"][entity.entity_type.value] += 1
        
        return entity.entity_id
    
    def add_relation(self, relation: Relation) -> str:
        """
        添加关系
        
        Args:
            relation: 关系对象
            
        Returns:
            str: 关系 ID
        """
        if not relation.relation_id:
            relation.relation_id = f"rel_{uuid.uuid4().hex[:12]}"
        
        self.relations[relation.relation_id] = relation
        self.stats["total_relations"] += 1
        
        return relation.relation_id
    
    def add_cross_modal_link(
        self,
        source_entity: str,
        target_entity: str,
        source_modality: str,
        target_modality: str,
        confidence: float = 1.0,
        link_type: str = "reference",
    ) -> str:
        """
        添加跨模态链接
        
        Args:
            source_entity: 源实体 ID
            target_entity: 目标实体 ID
            source_modality: 源模态
            target_modality: 目标模态
            confidence: 置信度
            link_type: 链接类型
            
        Returns:
            str: 链接 ID
        """
        link_id = f"link_{uuid.uuid4().hex[:12]}"
        
        link = CrossModalLink(
            link_id=link_id,
            source_entity=source_entity,
            target_entity=target_entity,
            modality=(source_modality, target_modality),
            confidence=confidence,
            link_type=link_type,
        )
        
        self.cross_modal_links[link_id] = link
        self.stats["total_cross_modal_links"] += 1
        
        return link_id
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        return self.entities.get(entity_id)
    
    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        """按类型获取实体"""
        entity_ids = self.entity_type_index.get(entity_type, set())
        return [self.entities[eid] for eid in entity_ids if eid in self.entities]
    
    def get_related_entities(
        self,
        entity_id: str,
        relation_type: Optional[RelationType] = None,
    ) -> List[Tuple[Entity, Relation]]:
        """
        获取相关实体
        
        Args:
            entity_id: 实体 ID
            relation_type: 关系类型过滤
            
        Returns:
            List[(Entity, Relation)]: 相关实体和关系
        """
        results = []
        
        for relation in self.relations.values():
            if relation_type and relation.relation_type != relation_type:
                continue
            
            if relation.source_id == entity_id:
                target = self.entities.get(relation.target_id)
                if target:
                    results.append((target, relation))
            elif relation.target_id == entity_id:
                source = self.entities.get(relation.source_id)
                if source:
                    results.append((source, relation))
        
        return results
    
    def get_cross_modal_neighbors(
        self,
        entity_id: str,
        target_modality: Optional[str] = None,
    ) -> List[Tuple[Entity, CrossModalLink]]:
        """
        获取跨模态邻居
        
        Args:
            entity_id: 实体 ID
            target_modality: 目标模态过滤
            
        Returns:
            List[(Entity, CrossModalLink)]: 邻居实体和链接
        """
        results = []
        
        for link in self.cross_modal_links.values():
            if target_modality and link.modality[1] != target_modality:
                continue
            
            if link.source_entity == entity_id:
                target = self.entities.get(link.target_entity)
                if target:
                    results.append((target, link))
            elif link.target_entity == entity_id:
                source = self.entities.get(link.source_entity)
                if source:
                    results.append((source, link))
        
        return results
    
    def search_entities(
        self,
        query: str,
        entity_type: Optional[EntityType] = None,
        limit: int = 10,
    ) -> List[Entity]:
        """
        搜索实体
        
        Args:
            query: 查询字符串
            entity_type: 实体类型过滤
            limit: 返回数量限制
            
        Returns:
            List[Entity]: 匹配的实体
        """
        query_parts = query.lower().split()
        
        # 收集匹配的实体
        candidates = set()
        for part in query_parts:
            for name, entity_ids in self.entity_name_index.items():
                if part in name:
                    candidates.update(entity_ids)
        
        # 过滤和排序
        results = []
        for entity_id in candidates:
            entity = self.entities.get(entity_id)
            if not entity:
                continue
            
            if entity_type and entity.entity_type != entity_type:
                continue
            
            # 计算匹配分数
            score = sum(1 for part in query_parts if part in entity.name.lower())
            results.append((entity, score))
        
        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        
        return [e for e, _ in results[:limit]]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_entities": self.stats["total_entities"],
            "total_relations": self.stats["total_relations"],
            "total_cross_modal_links": self.stats["total_cross_modal_links"],
            "by_type": dict(self.stats["by_type"]),
        }
    
    def export_to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "entities": {
                eid: {
                    "entity_id": e.entity_id,
                    "entity_type": e.entity_type.value,
                    "name": e.name,
                    "description": e.description,
                    "properties": e.properties,
                    "metadata": e.metadata,
                }
                for eid, e in self.entities.items()
            },
            "relations": {
                rid: {
                    "relation_id": r.relation_id,
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "relation_type": r.relation_type.value,
                    "weight": r.weight,
                    "description": r.description,
                }
                for rid, r in self.relations.items()
            },
            "cross_modal_links": {
                lid: {
                    "link_id": l.link_id,
                    "source_entity": l.source_entity,
                    "target_entity": l.target_entity,
                    "modality": l.modality,
                    "confidence": l.confidence,
                    "link_type": l.link_type,
                }
                for lid, l in self.cross_modal_links.items()
            },
            "stats": self.get_stats(),
        }


# ============ 跨模态知识图谱构建器 ============

class CrossModalGraphBuilder:
    """
    跨模态知识图谱构建器
    
    从多模态内容构建知识图谱
    """
    
    def __init__(self, graph: Optional[CrossModalKnowledgeGraph] = None):
        self.graph = graph or CrossModalKnowledgeGraph()
        self.entity_mapping: Dict[str, str] = {}  # 原始 ID -> 图谱 ID
    
    async def build_from_multimodal_content(self, content) -> CrossModalKnowledgeGraph:
        """
        从多模态内容构建图谱
        
        Args:
            content: MultimodalContent 对象
            
        Returns:
            CrossModalKnowledgeGraph: 构建的知识图谱
        """
        # 1. 提取和添加文本实体
        if content.text:
            text_entities = self._extract_text_entities(content.text)
            for entity in text_entities:
                self.graph.add_entity(entity)
        
        # 2. 提取和添加图像实体
        for image in content.images:
            image_entity = self._extract_image_entity(image)
            entity_id = self.graph.add_entity(image_entity)
            self.entity_mapping[f"image:{image.image_id}"] = entity_id
        
        # 3. 提取和添加表格实体
        for table in content.tables:
            table_entity = self._extract_table_entity(table)
            entity_id = self.graph.add_entity(table_entity)
            self.entity_mapping[f"table:{table.table_id}"] = entity_id
        
        # 4. 提取和添加公式实体
        for equation in content.equations:
            eq_entity = self._extract_equation_entity(equation)
            entity_id = self.graph.add_entity(eq_entity)
            self.entity_mapping[f"equation:{equation.equation_id}"] = entity_id
        
        # 5. 建立关系
        self._build_text_relations(content)
        
        # 6. 建立跨模态链接
        self._build_cross_modal_links(content)
        
        return self.graph
    
    def _extract_text_entities(self, text_content) -> List[Entity]:
        """提取文本实体"""
        entities = []
        
        # 从标题提取主题实体
        for heading in text_content.headings:
            entity = Entity(
                entity_id=f"topic_{uuid.uuid4().hex[:12]}",
                entity_type=EntityType.TOPIC,
                name=heading,
                description=f"Topic from heading: {heading}",
            )
            entities.append(entity)
        
        # 从段落提取概念实体（简化实现）
        for i, para in enumerate(text_content.paragraphs[:5]):  # 只处理前 5 段
            words = para.split()
            if words:
                # 取前几个词作为实体名
                entity_name = " ".join(words[:5])
                entity = Entity(
                    entity_id=f"concept_{i}_{uuid.uuid4().hex[:12]}",
                    entity_type=EntityType.CONCEPT,
                    name=entity_name,
                    description=para[:200],
                )
                entities.append(entity)
        
        return entities
    
    def _extract_image_entity(self, image_content) -> Entity:
        """提取图像实体"""
        return Entity(
            entity_id=f"image_{image_content.image_id}",
            entity_type=EntityType.IMAGE,
            name=image_content.caption or f"Image {image_content.image_id}",
            description=image_content.description,
            properties={
                "entities": image_content.entities,
                "relationships": image_content.relationships,
            },
            metadata={
                "caption": image_content.caption,
            }
        )
    
    def _extract_table_entity(self, table_content) -> Entity:
        """提取表格实体"""
        return Entity(
            entity_id=f"table_{table_content.table_id}",
            entity_type=EntityType.TABLE,
            name=f"Table: {table_content.summary[:50]}",
            description=table_content.summary,
            properties={
                "headers": table_content.headers,
                "row_count": len(table_content.rows),
                "relations": table_content.logical_relations,
            },
        )
    
    def _extract_equation_entity(self, equation_content) -> Entity:
        """提取公式实体"""
        return Entity(
            entity_id=f"equation_{equation_content.equation_id}",
            entity_type=EntityType.EQUATION,
            name=f"Equation: {equation_content.latex[:30]}",
            description=equation_content.description,
            properties={
                "latex": equation_content.latex,
                "variables": equation_content.variables,
                "dependencies": equation_content.dependencies,
            },
        )
    
    def _build_text_relations(self, content):
        """构建文本内关系"""
        text_entities = self.graph.get_entities_by_type(EntityType.TEXT)
        topic_entities = self.graph.get_entities_by_type(EntityType.TOPIC)
        concept_entities = self.graph.get_entities_by_type(EntityType.CONCEPT)
        
        # 标题包含概念
        for topic in topic_entities:
            for concept in concept_entities:
                if concept.name in topic.description:
                    relation = Relation(
                        relation_id=f"rel_{uuid.uuid4().hex[:12]}",
                        source_id=topic.entity_id,
                        target_id=concept.entity_id,
                        relation_type=RelationType.CONTAINS,
                        description=f"{topic.name} contains {concept.name}",
                    )
                    self.graph.add_relation(relation)
        
        # 概念之间的关系
        for i, concept1 in enumerate(concept_entities):
            for concept2 in concept_entities[i+1:]:
                # 检查是否有相似词
                words1 = set(concept1.name.lower().split())
                words2 = set(concept2.name.lower().split())
                if words1 & words2:  # 有交集
                    relation = Relation(
                        relation_id=f"rel_{uuid.uuid4().hex[:12]}",
                        source_id=concept1.entity_id,
                        target_id=concept2.entity_id,
                        relation_type=RelationType.SIMILAR_TO,
                        weight=len(words1 & words2) / len(words1 | words2),
                    )
                    self.graph.add_relation(relation)
    
    def _build_cross_modal_links(self, content):
        """构建跨模态链接"""
        # 文本与图像的链接
        if content.text and content.images:
            text_entities = self.graph.get_entities_by_type(EntityType.CONCEPT)
            for image_entity in self.graph.get_entities_by_type(EntityType.IMAGE):
                # 检查图像描述是否与文本概念相关
                for text_entity in text_entities:
                    if any(word in image_entity.description.lower() 
                           for word in text_entity.name.lower().split()):
                        self.graph.add_cross_modal_link(
                            source_entity=text_entity.entity_id,
                            target_entity=image_entity.entity_id,
                            source_modality="text",
                            target_modality="image",
                            confidence=0.8,
                            link_type="references",
                        )
        
        # 文本与表格的链接
        if content.text and content.tables:
            text_entities = self.graph.get_entities_by_type(EntityType.CONCEPT)
            for table_entity in self.graph.get_entities_by_type(EntityType.TABLE):
                for text_entity in text_entities:
                    # 检查表格摘要是否与文本相关
                    if any(word in table_entity.description.lower()
                           for word in text_entity.name.lower().split()):
                        self.graph.add_cross_modal_link(
                            source_entity=text_entity.entity_id,
                            target_entity=table_entity.entity_id,
                            source_modality="text",
                            target_modality="table",
                            confidence=0.9,
                            link_type="contains_data",
                        )
        
        # 文本与公式的链接
        if content.text and content.equations:
            text_entities = self.graph.get_entities_by_type(EntityType.CONCEPT)
            for eq_entity in self.graph.get_entities_by_type(EntityType.EQUATION):
                for text_entity in text_entities:
                    # 检查公式变量是否在文本中
                    eq_vars = set(eq_entity.properties.get("variables", []))
                    text_words = set(text_entity.name.lower().split())
                    if eq_vars & text_words:
                        self.graph.add_cross_modal_link(
                            source_entity=text_entity.entity_id,
                            target_entity=eq_entity.entity_id,
                            source_modality="text",
                            target_modality="equation",
                            confidence=0.7,
                            link_type="defines_variable",
                        )


# ============ 导出 ============

__all__ = [
    "EntityType",
    "RelationType",
    "Entity",
    "Relation",
    "CrossModalLink",
    "CrossModalKnowledgeGraph",
    "CrossModalGraphBuilder",
]
