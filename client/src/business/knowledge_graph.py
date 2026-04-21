#!/usr/bin/env python3
"""
知识图谱 - NetworkX/Neo4j 风格实现
支持实体-关系建模、知识推理、路径查询
"""

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class EntityType(Enum):
    """实体类型"""
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    CONCEPT = "concept"
    EVENT = "event"
    OBJECT = "object"
    DOCUMENT = "document"


class RelationType(Enum):
    """关系类型"""
    BELONGS_TO = "belongs_to"
    PART_OF = "part_of"
    RELATED_TO = "related_to"
    CAUSED_BY = "caused_by"
    LEADS_TO = "leads_to"
    WORKS_FOR = "works_for"
    LOCATED_IN = "located_in"
    IS_A = "is_a"
    HAS = "has"
    USES = "uses"
    CREATED = "created"
    PARTICIPATED_IN = "participated_in"


@dataclass
class Entity:
    """实体"""
    entity_id: str
    name: str
    entity_type: EntityType
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "type": self.entity_type.value,
            "properties": self.properties,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Relation:
    """关系"""
    relation_id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    properties: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.relation_type.value,
            "weight": self.weight,
        }


class KnowledgeGraph:
    """
    知识图谱

    特性:
    1. 实体-关系建模
    2. 多步关系查询
    3. 路径发现
    4. 知识推理
    5. 可视化导出
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._entities: Dict[str, Entity] = {}
        self._relations: Dict[str, Relation] = {}
        self._adjacency: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        self._entity_names: Dict[str, str] = {}  # name -> entity_id
        self._next_entity_id = 1
        self._next_relation_id = 1

    def add_entity(
        self,
        name: str,
        entity_type: str,
        properties: Dict[str, Any] = None,
    ) -> str:
        """添加实体"""
        entity_id = f"entity_{self._next_entity_id:06d}"
        self._next_entity_id += 1

        entity = Entity(
            entity_id=entity_id,
            name=name,
            entity_type=EntityType(entity_type),
            properties=properties or {},
        )

        self._entities[entity_id] = entity
        self._entity_names[name.lower()] = entity_id

        return entity_id

    def add_relation(
        self,
        source: str,
        target: str,
        relation_type: str,
        properties: Dict[str, Any] = None,
        weight: float = 1.0,
    ) -> Optional[str]:
        """添加关系"""
        source_id = self._resolve_entity(source)
        target_id = self._resolve_entity(target)

        if not source_id or not target_id:
            return None

        relation_id = f"rel_{self._next_relation_id:06d}"
        self._next_relation_id += 1

        relation = Relation(
            relation_id=relation_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=RelationType(relation_type),
            properties=properties or {},
            weight=weight,
        )

        self._relations[relation_id] = relation
        self._adjacency[source_id][relation_type].append(relation_id)

        return relation_id

    def _resolve_entity(self, identifier: str) -> Optional[str]:
        """解析实体标识"""
        if identifier in self._entities:
            return identifier

        return self._entity_names.get(identifier.lower())

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        return self._entities.get(entity_id)

    def get_relations(
        self,
        entity_id: str,
        relation_type: str = None,
        direction: str = "out",
    ) -> List[Tuple[Entity, Relation]]:
        """获取实体的关系"""
        results = []

        if direction in ["out", "both"]:
            for rel_id in self._adjacency[entity_id].get(relation_type, []):
                rel = self._relations.get(rel_id)
                if rel:
                    target = self._entities.get(rel.target_id)
                    if target:
                        results.append((target, rel))

        if direction in ["in", "both"]:
            for rel in self._relations.values():
                if relation_type and rel.relation_type.value != relation_type:
                    continue
                if rel.target_id == entity_id:
                    source = self._entities.get(rel.source_id)
                    if source:
                        results.append((source, rel))

        return results

    def find_path(
        self,
        source: str,
        target: str,
        max_depth: int = 3,
    ) -> List[List[str]]:
        """查找路径"""
        source_id = self._resolve_entity(source)
        target_id = self._resolve_entity(target)

        if not source_id or not target_id:
            return []

        if source_id == target_id:
            return [[source_id]]

        paths = []
        queue = deque([(source_id, [source_id])])
        visited = {source_id}

        while queue and len(paths) < 10:
            current, path = queue.popleft()

            if len(path) > max_depth:
                continue

            for rel_id in self._adjacency[current].get(rel.relation_type.value, []):
                rel = self._relations.get(rel_id)
                if not rel:
                    continue

                neighbor = rel.target_id
                if neighbor == target_id:
                    paths.append(path + [neighbor])
                    continue

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return paths

    def query(
        self,
        start_entity: str,
        relation_chain: List[str],
    ) -> List[List[Tuple[Entity, Relation]]]:
        """
        查询 - 支持关系链

        Args:
            start_entity: 起始实体
            relation_chain: 关系类型链，如 ["works_for", "part_of"]

        Returns:
            查询结果
        """
        current_ids = [self._resolve_entity(start_entity)]
        if not current_ids:
            return []

        results = []

        for rel_type in relation_chain:
            next_ids = []
            step_results = []

            for entity_id in current_ids:
                neighbors = self.get_relations(entity_id, rel_type, "out")
                for neighbor, rel in neighbors:
                    step_results.append((neighbor, rel))
                    next_ids.append(neighbor.entity_id)

            current_ids = next_ids
            if not current_ids:
                break

        return [step_results] if step_results else []

    def infer(self, entity_id: str) -> Dict[str, List[str]]:
        """
        知识推理

        推断实体的相关实体和关系
        """
        inferences = {
            "same_type_entities": [],
            "common_neighbors": [],
            "transitive_relations": [],
        }

        entity = self._entities.get(entity_id)
        if not entity:
            return inferences

        for other in self._entities.values():
            if other.entity_id == entity_id:
                continue
            if other.entity_type == entity.entity_type:
                inferences["same_type_entities"].append(other.name)

        return inferences

    def get_subgraph(
        self,
        entity_id: str,
        depth: int = 2,
    ) -> Dict[str, Any]:
        """
        获取子图

        Args:
            entity_id: 中心实体
            depth: 深度

        Returns:
            子图数据
        """
        entities = set([entity_id])
        relations = set()

        current_level = set([entity_id])
        for _ in range(depth):
            next_level = set()
            for eid in current_level:
                for rel_id in self._adjacency[eid].get("related_to", []):
                    rel = self._relations.get(rel_id)
                    if rel:
                        relations.add(rel_id)
                        next_level.add(rel.target_id)
                        entities.add(rel.target_id)

            current_level = next_level

        return {
            "entities": [self._entities[eid].to_dict() for eid in entities if eid in self._entities],
            "relations": [self._relations[rid].to_dict() for rid in relations if rid in self._relations],
            "center": entity_id,
            "depth": depth,
        }

    def export_to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "name": self.name,
            "entities": [e.to_dict() for e in self._entities.values()],
            "relations": [r.to_dict() for r in self._relations.values()],
            "stats": self.get_stats(),
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        type_counts = defaultdict(int)
        for entity in self._entities.values():
            type_counts[entity.entity_type.value] += 1

        rel_counts = defaultdict(int)
        for rel in self._relations.values():
            rel_counts[rel.relation_type.value] += 1

        return {
            "total_entities": len(self._entities),
            "total_relations": len(self._relations),
            "entity_types": dict(type_counts),
            "relation_types": dict(rel_counts),
        }


class KnowledgeGraphQueryEngine:
    """知识图谱查询引擎"""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def natural_language_query(self, query: str) -> Dict[str, Any]:
        """
        自然语言查询

        简单实现，实际应用中应使用 NLP 模型
        """
        query = query.lower()

        if "谁" in query and "工作" in query:
            return self._query_who_works(query)
        elif "什么" in query and "是" in query:
            return self._query_what_is(query)
        elif "在哪" in query:
            return self._query_where_is(query)
        else:
            return {"type": "unknown", "query": query}

    def _query_who_works(self, query: str) -> Dict[str, Any]:
        """查询谁在某处工作"""
        results = []
        for entity in self.graph._entities.values():
            if entity.entity_type == EntityType.PERSON:
                works = self.graph.get_relations(entity.entity_id, "works_for", "out")
                for target, rel in works:
                    results.append({
                        "person": entity.name,
                        "organization": target.name,
                    })

        return {
            "type": "who_works",
            "results": results,
        }

    def _query_what_is(self, query: str) -> Dict[str, Any]:
        """查询什么是某物"""
        return {"type": "what_is", "results": []}

    def _query_where_is(self, query: str) -> Dict[str, Any]:
        """查询某物在哪里"""
        return {"type": "where_is", "results": []}


def test_knowledge_graph():
    """测试知识图谱"""
    print("=== 测试知识图谱 ===")

    kg = KnowledgeGraph(name="测试图谱")

    print("\n1. 测试添加实体")
    python_id = kg.add_entity("Python", "concept", {"description": "编程语言"})
    guido_id = kg.add_entity("Guido van Rossum", "person", {"nationality": "荷兰"})
    microsoft_id = kg.add_entity("Microsoft", "organization", {"type": "科技公司"})
    ai_id = kg.add_entity("人工智能", "concept", {"description": "AI"})
    print(f"  添加实体: Python ({python_id})")
    print(f"  添加实体: Guido ({guido_id})")
    print(f"  添加实体: Microsoft ({microsoft_id})")
    print(f"  添加实体: AI ({ai_id})")

    print("\n2. 测试添加关系")
    rel1 = kg.add_relation("Guido van Rossum", "Python", "created", weight=1.0)
    rel2 = kg.add_relation("Python", "AI", "related_to", weight=0.8)
    rel3 = kg.add_relation("Guido van Rossum", "Microsoft", "works_for", weight=0.5)
    rel4 = kg.add_relation("Microsoft", "AI", "related_to", weight=0.7)
    print(f"  添加关系: Guido 创建 Python")
    print(f"  添加关系: Python 相关于 AI")
    print(f"  添加关系: Guido 工作于 Microsoft")
    print(f"  添加关系: Microsoft 相关于 AI")

    print("\n3. 测试获取关系")
    relations = kg.get_relations("Guido van Rossum", direction="out")
    print(f"  Guido 的关系:")
    for entity, rel in relations:
        print(f"    - {rel.relation_type.value} -> {entity.name}")

    print("\n4. 测试路径发现")
    paths = kg.find_path("Guido van Rossum", "AI", max_depth=3)
    print(f"  从 Guido 到 AI 的路径:")
    for path in paths:
        entity_names = [kg._entities[eid].name for eid in path]
        print(f"    - {' -> '.join(entity_names)}")

    print("\n5. 测试推理")
    inferences = kg.infer(python_id)
    print(f"  Python 的推理:")
    print(f"    同类型实体: {inferences['same_type_entities']}")

    print("\n6. 测试统计")
    stats = kg.get_stats()
    print(f"  统计:")
    print(f"    总实体数: {stats['total_entities']}")
    print(f"    总关系数: {stats['total_relations']}")
    print(f"    实体类型: {stats['entity_types']}")

    print("\n7. 测试子图导出")
    subgraph = kg.get_subgraph("Guido van Rossum", depth=2)
    print(f"  子图:")
    print(f"    实体数: {len(subgraph['entities'])}")
    print(f"    关系数: {len(subgraph['relations'])}")

    print("\n8. 测试查询引擎")
    engine = KnowledgeGraphQueryEngine(kg)
    result = engine.natural_language_query("谁在工作中")
    print(f"  查询结果: {result}")

    print("\n知识图谱测试完成！")


if __name__ == "__main__":
    test_knowledge_graph()