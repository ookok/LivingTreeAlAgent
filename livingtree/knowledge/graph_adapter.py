"""Graph Database Adapter — abstract interface for hypergraph persistence.

Decouples HypergraphStore from any specific storage backend.
Current default: NetworkX (in-memory) + JSON snapshots.
Future backends: NebulaGraph, Neo4j, JanusGraph, SQLite+WAL.

All HypergraphStore operations are abstracted through this interface.
Switching backends requires zero changes to business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GraphBackend(ABC):
    """Abstract graph storage backend.

    Implement this to add support for NebulaGraph, Neo4j, etc.
    Default implementation: NetworkXBackend (in-memory).
    """

    @abstractmethod
    def add_node(self, node_id: str, label: str, **properties) -> None:
        ...

    @abstractmethod
    def add_edge(self, source: str, target: str, relation: str, **properties) -> None:
        ...

    @abstractmethod
    def get_node(self, node_id: str) -> dict | None:
        ...

    @abstractmethod
    def get_neighbors(self, node_id: str) -> list[str]:
        ...

    @abstractmethod
    def node_count(self) -> int:
        ...

    @abstractmethod
    def edge_count(self) -> int:
        ...

    @abstractmethod
    def degree(self, node_id: str) -> int:
        ...

    @abstractmethod
    def has_node(self, node_id: str) -> bool:
        ...

    @abstractmethod
    def subgraph(self, node_ids: list[str]) -> Any:
        ...

    @abstractmethod
    def save(self, path: str) -> None:
        ...

    @abstractmethod
    def load(self, path: str) -> None:
        ...

    @abstractmethod
    def stats(self) -> dict[str, Any]:
        ...


class NetworkXBackend(GraphBackend):
    """Default in-memory backend using NetworkX. Suitable for <100K nodes."""

    def __init__(self):
        import networkx as nx
        self._graph = nx.Graph()
        self._node_labels: dict[str, str] = {}

    def add_node(self, node_id, label="", **props):
        self._graph.add_node(node_id, label=label, **props)
        self._node_labels[node_id] = label

    def add_edge(self, source, target, relation="", **props):
        self._graph.add_edge(source, target, relation=relation, **props)

    def get_node(self, node_id):
        if node_id not in self._graph:
            return None
        return {"id": node_id, "label": self._node_labels.get(node_id, ""),
                **dict(self._graph.nodes[node_id])}

    def get_neighbors(self, node_id):
        return list(self._graph.neighbors(node_id)) if node_id in self._graph else []

    def node_count(self):
        return self._graph.number_of_nodes()

    def edge_count(self):
        return self._graph.number_of_edges()

    def degree(self, node_id):
        return self._graph.degree(node_id) if node_id in self._graph else 0

    def has_node(self, node_id):
        return node_id in self._graph

    def subgraph(self, node_ids):
        return self._graph.subgraph(node_ids)

    def save(self, path):
        import networkx as nx
        nx.write_gexf(self._graph, path)

    def load(self, path):
        import networkx as nx
        self._graph = nx.read_gexf(path)
        self._node_labels = {n: self._graph.nodes[n].get("label", "")
                             for n in self._graph.nodes}

    def stats(self):
        return {
            "backend": "networkx",
            "nodes": self.node_count(),
            "edges": self.edge_count(),
        }


# ═══ Registry ═══

_BACKENDS: dict[str, type[GraphBackend]] = {
    "networkx": NetworkXBackend,
    # "nebula": NebulaBackend,     # Future
    # "neo4j": Neo4jBackend,       # Future
    # "sqlite_wal": SQLiteWALBackend, # Future
}


def get_backend(name: str = "networkx") -> GraphBackend:
    """Get a graph backend by name. Default: NetworkX."""
    backend_cls = _BACKENDS.get(name)
    if backend_cls is None:
        raise ValueError(f"Unknown graph backend: {name}. Available: {list(_BACKENDS.keys())}")
    return backend_cls()


def register_backend(name: str, backend_cls: type[GraphBackend]) -> None:
    """Register a new graph backend."""
    _BACKENDS[name] = backend_cls


__all__ = [
    "GraphBackend", "NetworkXBackend",
    "get_backend", "register_backend",
]
