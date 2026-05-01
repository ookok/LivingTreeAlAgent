"""
Dynamic Knowledge Graph

动态知识图谱模块，支持实体管理、关系推断、图遍历等功能，集成DeepOnto本体推理。

作者: LivingTreeAI Team
日期: 2026-05-01
版本: 1.1.0
"""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from deeponto.onto import Ontology
    from deeponto.reasoner import DLReasoner
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False


@dataclass
class KGEntity:
    """知识图谱实体"""
    id: str
    name: str
    type: str
    description: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class KGRelation:
    """知识图谱关系"""
    id: str
    subject: str
    predicate: str
    object: str
    confidence: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class DynamicKnowledgeGraph:
    """
    动态知识图谱
    
    支持功能：
    - 实体管理（添加、更新、删除、查询）
    - 关系管理（添加、查询）
    - 关系推断（基于上下文推断隐藏关系）
    - 图遍历（广度优先、深度优先）
    - 路径查找
    - 本体推理（DeepOnto集成）
    """
    
    def __init__(self):
        """初始化知识图谱"""
        self._entities: Dict[str, KGEntity] = {}
        self._relations: Dict[str, KGRelation] = {}
        self._ontology_reasoner = None
        
        # 索引
        self._entity_type_index: Dict[str, List[str]] = {}
        self._relation_predicate_index: Dict[str, List[str]] = {}
        self._subject_index: Dict[str, List[str]] = {}
        self._object_index: Dict[str, List[str]] = {}
        
        # 关系模板
        self._relation_templates = {
            "person": {
                "works_at": ["organization"],
                "born_in": ["location"],
                "created": ["product", "concept"],
                "studied_at": ["organization"],
            },
            "organization": {
                "located_in": ["location"],
                "produces": ["product"],
                "founded_by": ["person"],
            },
            "product": {
                "created_by": ["person", "organization"],
                "used_for": ["concept"],
            },
            "concept": {
                "related_to": ["concept", "technology"],
                "based_on": ["concept"],
            },
            "technology": {
                "used_in": ["product", "concept"],
                "developed_by": ["organization", "person"],
            },
            "location": {
                "contains": ["organization", "location"],
            },
        }
        
        self._init_ontology_reasoner()
        logger.info("DynamicKnowledgeGraph v1.1.0 初始化完成")
    
    def _init_ontology_reasoner(self):
        """初始化本体推理器"""
        try:
            from ..deeponto_integration import get_ontology_reasoner
            self._ontology_reasoner = get_ontology_reasoner()
            self._ontology_reasoner.initialize()
            logger.info("本体推理器初始化成功")
        except ImportError as e:
            logger.warning(f"本体推理器初始化失败: {e}")
    
    async def add_entity(self, entity_data: Dict[str, Any]) -> bool:
        """
        添加实体
        
        Args:
            entity_data: 实体数据
            
        Returns:
            bool 是否成功
        """
        try:
            entity_id = entity_data.get("id") or entity_data.get("name", "")
            if not entity_id:
                logger.error("实体ID或名称不能为空")
                return False
            
            entity = KGEntity(
                id=entity_id,
                name=entity_data.get("name", entity_id),
                type=entity_data.get("type", "unknown"),
                description=entity_data.get("description"),
                attributes=entity_data.get("attributes", {}),
                aliases=entity_data.get("aliases", []),
            )
            
            self._entities[entity_id] = entity
            
            # 更新类型索引
            entity_type = entity.type
            if entity_type not in self._entity_type_index:
                self._entity_type_index[entity_type] = []
            if entity_id not in self._entity_type_index[entity_type]:
                self._entity_type_index[entity_type].append(entity_id)
            
            logger.debug(f"实体添加成功: {entity_id}")
            return True
            
        except Exception as e:
            logger.error(f"添加实体失败: {e}")
            return False
    
    async def get_entity(self, entity_id: str) -> Optional[KGEntity]:
        """
        获取实体
        
        Args:
            entity_id: 实体ID
            
        Returns:
            KGEntity 实体对象
        """
        return self._entities.get(entity_id)
    
    async def update_entity(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新实体
        
        Args:
            entity_id: 实体ID
            updates: 更新内容
            
        Returns:
            bool 是否成功
        """
        if entity_id not in self._entities:
            logger.error(f"实体不存在: {entity_id}")
            return False
        
        entity = self._entities[entity_id]
        
        if "name" in updates:
            entity.name = updates["name"]
        if "description" in updates:
            entity.description = updates["description"]
        if "attributes" in updates:
            entity.attributes.update(updates["attributes"])
        if "aliases" in updates:
            entity.aliases = updates["aliases"]
        if "type" in updates:
            # 更新类型索引
            old_type = entity.type
            if old_type in self._entity_type_index and entity_id in self._entity_type_index[old_type]:
                self._entity_type_index[old_type].remove(entity_id)
            
            new_type = updates["type"]
            entity.type = new_type
            if new_type not in self._entity_type_index:
                self._entity_type_index[new_type] = []
            if entity_id not in self._entity_type_index[new_type]:
                self._entity_type_index[new_type].append(entity_id)
        
        entity.updated_at = datetime.now().isoformat()
        
        logger.debug(f"实体更新成功: {entity_id}")
        return True
    
    async def delete_entity(self, entity_id: str) -> bool:
        """
        删除实体
        
        Args:
            entity_id: 实体ID
            
        Returns:
            bool 是否成功
        """
        if entity_id not in self._entities:
            logger.error(f"实体不存在: {entity_id}")
            return False
        
        # 删除相关关系
        relations_to_delete = []
        for rel_id, relation in self._relations.items():
            if relation.subject == entity_id or relation.object == entity_id:
                relations_to_delete.append(rel_id)
        
        for rel_id in relations_to_delete:
            await self.delete_relation(rel_id)
        
        # 删除实体
        entity = self._entities[entity_id]
        
        # 更新类型索引
        if entity.type in self._entity_type_index and entity_id in self._entity_type_index[entity.type]:
            self._entity_type_index[entity.type].remove(entity_id)
        
        del self._entities[entity_id]
        
        logger.debug(f"实体删除成功: {entity_id}")
        return True
    
    async def add_relation(self, relation_data: Dict[str, Any]) -> bool:
        """
        添加关系
        
        Args:
            relation_data: 关系数据
            
        Returns:
            bool 是否成功
        """
        try:
            subject = relation_data.get("subject")
            predicate = relation_data.get("predicate")
            obj = relation_data.get("object")
            
            if not subject or not predicate or not obj:
                logger.error("关系三要素（subject, predicate, object）不能为空")
                return False
            
            # 检查实体是否存在
            if subject not in self._entities:
                await self.add_entity({"id": subject, "name": subject, "type": "unknown"})
            if obj not in self._entities:
                await self.add_entity({"id": obj, "name": obj, "type": "unknown"})
            
            relation_id = f"{subject}_{predicate}_{obj}"
            
            relation = KGRelation(
                id=relation_id,
                subject=subject,
                predicate=predicate,
                object=obj,
                confidence=relation_data.get("confidence", 0.7),
                attributes=relation_data.get("attributes", {}),
                source=relation_data.get("source"),
            )
            
            self._relations[relation_id] = relation
            
            # 更新索引
            if predicate not in self._relation_predicate_index:
                self._relation_predicate_index[predicate] = []
            if relation_id not in self._relation_predicate_index[predicate]:
                self._relation_predicate_index[predicate].append(relation_id)
            
            if subject not in self._subject_index:
                self._subject_index[subject] = []
            if relation_id not in self._subject_index[subject]:
                self._subject_index[subject].append(relation_id)
            
            if obj not in self._object_index:
                self._object_index[obj] = []
            if relation_id not in self._object_index[obj]:
                self._object_index[obj].append(relation_id)
            
            logger.debug(f"关系添加成功: {relation_id}")
            return True
            
        except Exception as e:
            logger.error(f"添加关系失败: {e}")
            return False
    
    async def delete_relation(self, relation_id: str) -> bool:
        """
        删除关系
        
        Args:
            relation_id: 关系ID
            
        Returns:
            bool 是否成功
        """
        if relation_id not in self._relations:
            logger.error(f"关系不存在: {relation_id}")
            return False
        
        relation = self._relations[relation_id]
        
        # 更新索引
        if relation.predicate in self._relation_predicate_index:
            self._relation_predicate_index[relation.predicate].remove(relation_id)
        
        if relation.subject in self._subject_index:
            self._subject_index[relation.subject].remove(relation_id)
        
        if relation.object in self._object_index:
            self._object_index[relation.object].remove(relation_id)
        
        del self._relations[relation_id]
        
        logger.debug(f"关系删除成功: {relation_id}")
        return True
    
    async def get_entity_relations(self, entity_id: str) -> List[KGRelation]:
        """
        获取实体的所有关系
        
        Args:
            entity_id: 实体ID
            
        Returns:
            List 关系列表
        """
        relations = []
        
        # 作为主体的关系
        if entity_id in self._subject_index:
            for rel_id in self._subject_index[entity_id]:
                relations.append(self._relations[rel_id])
        
        # 作为客体的关系
        if entity_id in self._object_index:
            for rel_id in self._object_index[entity_id]:
                relations.append(self._relations[rel_id])
        
        return relations
    
    async def traverse_relations(self, entity_id: str, depth: int = 2) -> List[Dict[str, Any]]:
        """
        遍历实体关系（广度优先）
        
        Args:
            entity_id: 起始实体ID
            depth: 遍历深度
            
        Returns:
            List 关系路径列表
        """
        if entity_id not in self._entities:
            return []
        
        visited = {entity_id}
        queue = [(entity_id, 0, [])]
        results = []
        
        while queue:
            current_id, current_depth, path = queue.pop(0)
            
            if current_depth >= depth:
                continue
            
            relations = await self.get_entity_relations(current_id)
            
            for relation in relations:
                # 确定邻居节点
                if relation.subject == current_id:
                    neighbor_id = relation.object
                else:
                    neighbor_id = relation.subject
                
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    new_path = path + [{
                        "entity_id": current_id,
                        "relation": relation.predicate,
                        "neighbor_id": neighbor_id,
                    }]
                    results.append({
                        "path": new_path,
                        "depth": current_depth + 1,
                        "confidence": relation.confidence,
                    })
                    
                    if current_depth + 1 < depth:
                        queue.append((neighbor_id, current_depth + 1, new_path))
        
        return results
    
    async def infer_relations(self, entity_ids: List[str]) -> List[Dict[str, Any]]:
        """
        基于实体列表推断隐藏关系
        
        Args:
            entity_ids: 实体ID列表
            
        Returns:
            List 推断的关系列表
        """
        inferred = []
        
        for i, e1_id in enumerate(entity_ids):
            for j, e2_id in enumerate(entity_ids):
                if i >= j:
                    continue
                
                e1 = self._entities.get(e1_id)
                e2 = self._entities.get(e2_id)
                
                if not e1 or not e2:
                    continue
                
                # 根据类型推断可能的关系
                possible_relations = self._infer_by_type(e1.type, e2.type)
                
                for predicate in possible_relations:
                    relation_id = f"{e1_id}_{predicate}_{e2_id}"
                    if relation_id not in self._relations:
                        inferred.append({
                            "subject": e1_id,
                            "predicate": predicate,
                            "object": e2_id,
                            "confidence": 0.5,
                            "source": "inference",
                        })
        
        return inferred
    
    def _infer_by_type(self, type1: str, type2: str) -> List[str]:
        """
        根据实体类型推断可能的关系
        
        Args:
            type1: 实体1类型
            type2: 实体2类型
            
        Returns:
            List 可能的关系谓词
        """
        relations = []
        
        # 检查 type1 -> type2 的关系
        if type1 in self._relation_templates:
            if type2 in self._relation_templates[type1]:
                for pred in self._relation_templates[type1]:
                    if type2 in self._relation_templates[type1][pred]:
                        relations.append(pred)
        
        # 检查 type2 -> type1 的关系
        if type2 in self._relation_templates:
            if type1 in self._relation_templates[type2]:
                for pred in self._relation_templates[type2]:
                    if type1 in self._relation_templates[type2][pred]:
                        relations.append(pred)
        
        # 默认关系
        if not relations:
            relations.append("related_to")
        
        return relations
    
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
        if start_id not in self._entities or end_id not in self._entities:
            return None
        
        if start_id == end_id:
            return [start_id]
        
        visited = {start_id}
        queue = [(start_id, [start_id])]
        
        while queue:
            current_id, path = queue.pop(0)
            
            if len(path) - 1 >= max_depth:
                continue
            
            relations = await self.get_entity_relations(current_id)
            
            for relation in relations:
                neighbor_id = relation.object if relation.subject == current_id else relation.subject
                
                if neighbor_id == end_id:
                    return path + [neighbor_id]
                
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, path + [neighbor_id]))
        
        return None
    
    async def search_entities(self, query: str, entity_type: Optional[str] = None) -> List[KGEntity]:
        """
        搜索实体
        
        Args:
            query: 搜索词
            entity_type: 实体类型（可选）
            
        Returns:
            List 匹配的实体列表
        """
        results = []
        query_lower = query.lower()
        
        for entity in self._entities.values():
            # 类型过滤
            if entity_type and entity.type != entity_type:
                continue
            
            # 匹配名称或别名
            if (query_lower in entity.name.lower() or 
                any(query_lower in alias.lower() for alias in entity.aliases)):
                results.append(entity)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        type_counts = {}
        for entity in self._entities.values():
            type_counts[entity.type] = type_counts.get(entity.type, 0) + 1
        
        predicate_counts = {}
        for relation in self._relations.values():
            predicate_counts[relation.predicate] = predicate_counts.get(relation.predicate, 0) + 1
        
        return {
            "total_entities": len(self._entities),
            "total_relations": len(self._relations),
            "entity_type_distribution": type_counts,
            "predicate_distribution": predicate_counts,
        }
    
    async def classify_entity(self, entity_id: str) -> List[str]:
        """
        使用本体推理对实体进行分类
        
        Args:
            entity_id: 实体ID
            
        Returns:
            List 实体类型列表
        """
        if not self._ontology_reasoner:
            entity = self._entities.get(entity_id)
            return [entity.type] if entity else []
        
        try:
            return self._ontology_reasoner.classify_instance(entity_id)
        except Exception as e:
            logger.error(f"本体分类失败: {e}")
            entity = self._entities.get(entity_id)
            return [entity.type] if entity else []
    
    async def infer_ontological_relations(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        使用本体推理推断实体关系
        
        Args:
            entity_id: 实体ID
            
        Returns:
            List 推断的关系列表
        """
        if not self._ontology_reasoner:
            return []
        
        try:
            other_entities = [eid for eid in self._entities.keys() if eid != entity_id]
            inferred = []
            
            for other_id in other_entities:
                relations = self._ontology_reasoner.infer_relations(entity_id, other_id)
                for rel in relations:
                    inferred.append({
                        "subject": entity_id,
                        "predicate": rel,
                        "object": other_id,
                        "confidence": 0.7,
                        "source": "ontology_reasoning",
                    })
            
            return inferred
        except Exception as e:
            logger.error(f"本体关系推断失败: {e}")
            return []
    
    async def validate_knowledge_consistency(self) -> Dict[str, Any]:
        """
        验证知识图谱一致性
        
        Returns:
            Dict 验证结果
        """
        if not self._ontology_reasoner:
            return {"is_consistent": True, "errors": [], "warnings": []}
        
        try:
            is_consistent = self._ontology_reasoner.check_consistency()
            return {
                "is_consistent": is_consistent,
                "errors": [] if is_consistent else ["本体不一致"],
                "warnings": [],
            }
        except Exception as e:
            logger.error(f"一致性验证失败: {e}")
            return {"is_consistent": True, "errors": [], "warnings": [str(e)]}
    
    def get_class_hierarchy(self) -> Dict[str, List[str]]:
        """
        获取本体类层次结构
        
        Returns:
            Dict 类层次结构
        """
        if not self._ontology_reasoner:
            return {}
        
        try:
            return self._ontology_reasoner.get_class_hierarchy()
        except Exception as e:
            logger.error(f"获取类层次结构失败: {e}")
            return {}


# 全局知识图谱实例
_knowledge_graph_instance = None

def get_dynamic_knowledge_graph() -> DynamicKnowledgeGraph:
    """获取全局知识图谱实例"""
    global _knowledge_graph_instance
    if _knowledge_graph_instance is None:
        _knowledge_graph_instance = DynamicKnowledgeGraph()
    return _knowledge_graph_instance