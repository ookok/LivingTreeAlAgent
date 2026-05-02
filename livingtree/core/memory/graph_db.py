"""
LivingTree — Entity-Relation Knowledge Graph
==============================================

Full migration from client/src/business/knowledge_graph.py
Uses networkx for graph operations.

Features:
- Entity CRUD with typed metadata
- Relation management with weighted edges
- Semantic search with scoring
- Path finding (shortest path via networkx)
- Transitive inference
- JSON export/import
- Matplotlib visualization (optional)
"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

try:
    import networkx as nx
except ImportError:
    nx = None

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None

logger = logging.getLogger(__name__)


class EntityType(Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    PROJECT = "project"
    MODULE = "module"
    FUNCTION = "function"
    CLASS = "class"
    CONCEPT = "concept"
    DOCUMENT = "document"
    TAG = "tag"


class RelationType(Enum):
    PART_OF = "part_of"
    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    USES = "uses"
    CONTAINS = "contains"
    RELATED_TO = "related_to"
    DEFINES = "defines"
    REFERENCES = "references"


@dataclass
class Entity:
    id: str
    name: str
    type: EntityType
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Relation:
    source_id: str
    target_id: str
    type: RelationType
    weight: float = 1.0
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)


class KnowledgeGraph:
    """
    Full entity-relation knowledge graph backed by networkx DiGraph.

    Core operations: add/update/delete entities, add relations,
    semantic search, path finding, transitive inference,
    visualization, JSON import/export.
    """

    def __init__(self):
        self._entities: Dict[str, Entity] = {}
        self._relations: List[Relation] = []
        self._graph = nx.DiGraph() if nx else None
        if self._graph is None:
            logger.warning("networkx not available — graph operations limited")
        logger.info("KnowledgeGraph initialized (%d entities)", 0)

    # ── Entity CRUD ────────────────────────────────────────

    def add_entity(self, id: str, name: str, type: EntityType,
                   description: str = "", **attributes) -> Entity:
        entity = Entity(id=id, name=name, type=type,
                        description=description, attributes=attributes)
        self._entities[id] = entity
        if self._graph is not None:
            self._graph.add_node(id, label=name, type=type.value)
        return entity

    def get_entity(self, id: str) -> Optional[Entity]:
        return self._entities.get(id)

    def update_entity(self, id: str, **kwargs):
        if id not in self._entities:
            raise ValueError(f"Entity not found: {id}")
        entity = self._entities[id]
        if "name" in kwargs:
            entity.name = kwargs["name"]
        if "description" in kwargs:
            entity.description = kwargs["description"]
        if "attributes" in kwargs:
            entity.attributes.update(kwargs["attributes"])
        entity.updated_at = datetime.now()
        if self._graph is not None:
            self._graph.nodes[id]["label"] = entity.name

    def delete_entity(self, id: str):
        if id not in self._entities:
            return
        self._relations = [r for r in self._relations
                           if r.source_id != id and r.target_id != id]
        del self._entities[id]
        if self._graph is not None:
            self._graph.remove_node(id)

    def list_entities(self) -> List[Entity]:
        return list(self._entities.values())

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    # ── Relations ──────────────────────────────────────────

    def add_relation(self, source_id: str, target_id: str,
                     type: RelationType, weight: float = 1.0,
                     description: str = "") -> Relation:
        if source_id not in self._entities:
            raise ValueError(f"Source entity not found: {source_id}")
        if target_id not in self._entities:
            raise ValueError(f"Target entity not found: {target_id}")
        relation = Relation(source_id=source_id, target_id=target_id,
                            type=type, weight=weight, description=description)
        self._relations.append(relation)
        if self._graph is not None:
            self._graph.add_edge(source_id, target_id,
                                 type=type.value, weight=weight)
        return relation

    def get_relations(self, entity_id: str) -> List[Relation]:
        return [r for r in self._relations
                if r.source_id == entity_id or r.target_id == entity_id]

    @property
    def relation_count(self) -> int:
        return len(self._relations)

    # ── Search ─────────────────────────────────────────────

    def search(self, query: str) -> List[Tuple[Entity, float]]:
        results = []
        for entity in self._entities.values():
            score = 0
            if query.lower() in entity.name.lower():
                score += 0.5
            if query.lower() in entity.description.lower():
                score += 0.3
            for value in entity.attributes.values():
                if query.lower() in str(value).lower():
                    score += 0.1
            if score > 0:
                results.append((entity, score))
        results.sort(key=lambda x: -x[1])
        return results

    def find_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        if self._graph is None:
            return None
        try:
            return nx.shortest_path(self._graph, source_id, target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_neighbors(self, entity_id: str) -> List[Entity]:
        neighbors = set()
        for relation in self._relations:
            if relation.source_id == entity_id:
                neighbors.add(relation.target_id)
            elif relation.target_id == entity_id:
                neighbors.add(relation.source_id)
        return [self._entities[n] for n in neighbors if n in self._entities]

    # ── Inference ──────────────────────────────────────────

    def infer_relations(self) -> List[Relation]:
        """Transitive inference: if A→B and B→C then A→C."""
        inferred = []
        for r1 in self._relations:
            for r2 in self._relations:
                if r1.target_id == r2.source_id:
                    exists = any(r.source_id == r1.source_id
                                 and r.target_id == r2.target_id
                                 for r in self._relations)
                    if not exists:
                        inferred.append(Relation(
                            source_id=r1.source_id,
                            target_id=r2.target_id,
                            type=RelationType.RELATED_TO,
                            weight=min(r1.weight, r2.weight) * 0.5,
                            description="Inferred by transitivity",
                        ))
        return inferred

    # ── Visualization ──────────────────────────────────────

    def visualize(self, output_path: Optional[str] = None):
        if not MATPLOTLIB_AVAILABLE or self._graph is None:
            logger.warning("Visualization skipped (matplotlib/networkx unavailable)")
            return
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(self._graph, k=0.15, iterations=20)
        node_colors = []
        for node in self._graph.nodes:
            entity = self._entities.get(node)
            if entity:
                if entity.type == EntityType.MODULE:
                    node_colors.append('#4a90d9')
                elif entity.type == EntityType.FUNCTION:
                    node_colors.append('#67c23a')
                elif entity.type == EntityType.CLASS:
                    node_colors.append('#e6a23c')
                else:
                    node_colors.append('#909399')
            else:
                node_colors.append('#909399')
        nx.draw(self._graph, pos, node_color=node_colors, node_size=1500,
                with_labels=True, font_size=8, font_color='white',
                edge_color='#d9d9d9', linewidths=2)
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()

    # ── Serialization ──────────────────────────────────────

    def export_to_json(self, file_path: str):
        data = {
            "entities": [
                {"id": e.id, "name": e.name, "type": e.type.value,
                 "description": e.description, "attributes": e.attributes}
                for e in self._entities.values()
            ],
            "relations": [
                {"source_id": r.source_id, "target_id": r.target_id,
                 "type": r.type.value, "weight": r.weight, "description": r.description}
                for r in self._relations
            ]
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Knowledge graph exported to %s", file_path)

    def import_from_json(self, file_path: str):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for ed in data.get("entities", []):
            self.add_entity(id=ed["id"], name=ed["name"],
                            type=EntityType(ed["type"]),
                            description=ed.get("description", ""),
                            **ed.get("attributes", {}))
        for rd in data.get("relations", []):
            self.add_relation(source_id=rd["source_id"], target_id=rd["target_id"],
                              type=RelationType(rd["type"]),
                              weight=rd.get("weight", 1.0),
                              description=rd.get("description", ""))
        logger.info("Knowledge graph imported from %s (%d entities, %d relations)",
                     file_path, self.entity_count, self.relation_count)


# ── Singleton ──────────────────────────────────────────────

_global_kg: Optional[KnowledgeGraph] = None


def get_knowledge_graph() -> KnowledgeGraph:
    global _global_kg
    if _global_kg is None:
        _global_kg = KnowledgeGraph()
    return _global_kg


__all__ = [
    "KnowledgeGraph", "Entity", "Relation",
    "EntityType", "RelationType",
    "get_knowledge_graph",
]
