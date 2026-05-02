"""
KnowledgeGraph — Re-export from livingtree.core.memory.graph_db

Full migration complete. Import from new location.
"""

from livingtree.core.memory.graph_db import (
    KnowledgeGraph,
    Entity, Relation,
    EntityType, RelationType,
    get_knowledge_graph,
)

__all__ = [
    "KnowledgeGraph", "Entity", "Relation",
    "EntityType", "RelationType",
    "get_knowledge_graph",
]
