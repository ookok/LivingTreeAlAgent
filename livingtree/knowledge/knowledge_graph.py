"""Graph-based knowledge representation using NetworkX.

This module provides a lightweight graph model for entities and their
relationships, with simple import/export support to NetworkX and Neo4j
style formats.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import networkx as nx
from pydantic import BaseModel, Field

try:
    import networkx as nx  # ensure optional availability
except Exception:  # pragma: no cover
    nx = None  # type: ignore


class Entity(BaseModel):
    id: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraph:
    def __init__(self) -> None:
        self.graph = nx.Graph() if nx is not None else None  # type: ignore
        self.nodes_index: Dict[str, Entity] = {}

    def add_entity(self, entity: Entity) -> None:
        if self.graph is None:
            return
        self.nodes_index[entity.id] = entity
        self.graph.add_node(entity.id, label=entity.label, **entity.properties)

    def add_relation(self, source_id: str, target_id: str, relation: str, properties: Optional[Dict[str, Any]] = None) -> None:
        if self.graph is None:
            return
        if properties is None:
            properties = {}
        self.graph.add_edge(source_id, target_id, relation=relation, **properties)

    def query_graph(self, filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        if self.graph is None:
            return []
        results: List[Dict[str, Any]] = []
        for n, data in self.graph.nodes(data=True):
            if all(data.get(k) == v for k, v in filter.items()):
                results.append({"id": n, "attributes": data})
        return results

    def find_path(self, start_id: str, end_id: str) -> List[str]:
        if self.graph is None:
            return []
        try:
            return nx.shortest_path(self.graph, source=start_id, target=end_id)
        except Exception:
            return []

    def get_subgraph(self, ids: List[str]) -> "nx.Graph":
        if self.graph is None:
            return nx.Graph()
        return self.graph.subgraph(ids).copy()

    def entity_linking(self, text: str) -> List[str]:
        # Simple heuristic: return entity IDs whose label appears in text
        matches: List[str] = []
        for entity_id, ent in self.nodes_index.items():
            if ent.label and ent.label in text:
                matches.append(entity_id)
        return matches

    # Import/export helpers
    def export_to_networkx(self, path: str) -> None:
        if self.graph is None:
            return
        nx.write_gexf(self.graph, path)

    def import_from_networkx(self, path: str) -> None:
        self.graph = nx.read_gexf(path) if nx is not None else None

    # Neo4j-style adapters (stubs for demo)
    def to_neo4j(self, path: str) -> None:
        logger = __import__('loguru').logger  # lazy import to avoid hard dep
        logger.info("Exporting to Neo4j is not implemented in this lightweight backend. Path: %s", path)


__all__ = ["KnowledgeGraph", "Entity"]
