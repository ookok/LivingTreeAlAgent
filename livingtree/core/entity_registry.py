"""
Unified Entity Identifier (UEI) — 全局实体命名空间。

为 LivingTree 的 4 层本体系统（KnowledgeGraph / Glossary / SkillGraph / CodeGraph）
提供跨层 canonical ID 共享，解决同一概念在不同层中作为独立对象的问题。

Usage:
    from livingtree.core import ENTITY_REGISTRY
    reg = ENTITY_REGISTRY
    reg.register("kg", "python-lang", "Python", "entity")
    reg.link("kg:python-lang", "skill:code-generation", "related_to")
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field, ConfigDict


class EntityEntry(BaseModel):
    """Canonical entity entry in the unified registry."""

    id: str  # Canonical: "{namespace}:{key}"
    namespace: str  # kg, glossary, skill, code
    key: str  # Unique within namespace
    name: str  # Human-readable name
    entity_type: str = Field(alias="type")  # entity, term, skill, code — use alias for Pydantic
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    linked_entities: dict[str, str] = Field(default_factory=dict)  # entity_id → relation
    created_at: float = 0.0
    updated_at: float = 0.0

    model_config = ConfigDict(populate_by_name=True)


class EntityRegistry:
    """Unified namespace for all ontology entities across LivingTree layers."""

    def __init__(self, persist_path: str = ".livingtree/entities.json"):
        self._persist_path = persist_path
        self._entries: dict[str, EntityEntry] = {}
        self._load()
        if not self._entries:
            self._seed_defaults()
            self._save()

    # ── CRUD ──

    def register(
        self,
        namespace: str,
        key: str,
        name: str,
        entity_type: str = "entity",
        description: str = "",
        aliases: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EntityEntry:
        """Register or update an entity. Returns the EntityEntry."""
        entity_id = f"{namespace}:{key}"
        now = time.time()
        metadata = metadata or {}
        aliases = aliases or []

        if entity_id in self._entries:
            entry = self._entries[entity_id]
            entry.name = name
            entry.description = description
            entry.metadata = metadata
            entry.aliases = list(set(entry.aliases + aliases))
            entry.updated_at = now
        else:
            entry = EntityEntry(
                id=entity_id,
                namespace=namespace,
                key=key,
                name=name,
                type=entity_type,
                description=description,
                metadata=metadata,
                aliases=aliases,
                created_at=now,
                updated_at=now,
            )
            self._entries[entity_id] = entry

        self._save()
        logger.debug(f"Entity registered: {entity_id}")
        return entry

    def resolve(self, id_or_alias: str) -> EntityEntry | None:
        """Resolve by canonical ID or alias. Returns None if not found."""
        if id_or_alias in self._entries:
            return self._entries[id_or_alias]
        for entry in self._entries.values():
            if id_or_alias.lower() in (a.lower() for a in entry.aliases):
                return entry
        return None

    def get_by_namespace(self, namespace: str) -> list[EntityEntry]:
        """Get all entities in a namespace."""
        return [e for e in self._entries.values() if e.namespace == namespace]

    def link(self, source_id: str, target_id: str, relation: str = "related_to") -> bool:
        """Create bidirectional link between two entities."""
        src = self._entries.get(source_id)
        tgt = self._entries.get(target_id)
        if not src or not tgt:
            logger.warning(f"Link failed: {source_id} or {target_id} not found")
            return False
        src.linked_entities[target_id] = relation
        tgt.linked_entities[source_id] = relation
        src.updated_at = tgt.updated_at = time.time()
        self._save()
        return True

    def get_references(self, entity_id: str) -> dict[str, str]:
        """Get linked entities and their relations."""
        entry = self._entries.get(entity_id)
        return dict(entry.linked_entities) if entry else {}

    def list_all(self) -> list[EntityEntry]:
        """Return all registered entities."""
        return list(self._entries.values())

    def search(self, query: str) -> list[EntityEntry]:
        """Case-insensitive search by name and aliases."""
        q = query.lower()
        results = []
        for entry in self._entries.values():
            if q in entry.name.lower() or any(q in a.lower() for a in entry.aliases):
                results.append(entry)
        return results

    # ── Analytics ──

    def stats(self) -> dict[str, Any]:
        """Return registry statistics."""
        by_ns: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for e in self._entries.values():
            by_ns[e.namespace] = by_ns.get(e.namespace, 0) + 1
            by_type[e.entity_type] = by_type.get(e.entity_type, 0) + 1
        return {"total": len(self._entries), "by_namespace": by_ns, "by_type": by_type}

    def get_graph(self) -> dict[str, Any]:
        """Return graph structure for visualization: nodes + edges."""
        nodes = [{"id": e.id, "name": e.name, "namespace": e.namespace, "type": e.entity_type} for e in self._entries.values()]
        seen = set()
        edges = []
        for e in self._entries.values():
            for target_id, relation in e.linked_entities.items():
                edge_key = tuple(sorted([e.id, target_id]))
                if edge_key not in seen:
                    seen.add(edge_key)
                    edges.append({"source": e.id, "target": target_id, "relation": relation})
        return {"nodes": nodes, "edges": edges}

    # ── Persistence ──

    def _save(self) -> None:
        """Persist entries to JSON file."""
        os.makedirs(os.path.dirname(self._persist_path) or ".", exist_ok=True)
        data = []
        for entry in self._entries.values():
            d = entry.model_dump()
            d["created_at"] = entry.created_at
            d["updated_at"] = entry.updated_at
            data.append(d)
        with open(self._persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        """Load entries from JSON file."""
        if not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                entry = EntityEntry(**item)
                self._entries[entry.id] = entry
        except Exception as e:
            logger.warning(f"Failed to load entity registry: {e}")

    def _seed_defaults(self) -> None:
        """Seed 10 default entities across 4 layers with cross-layer links."""
        entities = [
            ("kg", "python-lang", "Python", "entity", "Python programming language", ["python", "py"]),
            ("kg", "llm-concept", "LLM", "entity", "Large Language Model", ["large language model", "大语言模型"]),
            ("glossary", "unit-test", "Unit Test", "term", "Unit testing methodology", ["单元测试", "单元测验"]),
            ("glossary", "monolith", "Monolith", "term", "Monolithic architecture pattern", ["单体架构", "巨石应用"]),
            ("skill", "code-generation", "Code Generation", "skill", "Generate code from requirements", ["代码生成"]),
            ("skill", "code-review", "Code Review", "skill", "Review code for quality and issues", ["代码审查"]),
            ("skill", "reasoning", "Reasoning", "skill", "Logical reasoning and analysis", ["推理"]),
            ("skill", "knowledge-search", "Knowledge Search", "skill", "Search knowledge base", ["知识搜索", "知识检索"]),
            ("code", "livingtree-main", "LivingTreeAlAgent", "code", "Main repository", ["lta", "livingtree"]),
            ("code", "treellm-router", "TreeLLM Router", "code", "Multi-provider LLM routing", ["treellm", "路由"]),
        ]
        for ns, key, name, etype, desc, aliases in entities:
            self.register(ns, key, name, etype, description=desc, aliases=aliases)

        # Cross-layer auto-links
        self.link("kg:python-lang", "skill:code-generation", "related_to")
        self.link("kg:llm-concept", "skill:reasoning", "related_to")
        logger.info(f"Seeded {len(entities)} default entities")


# Singleton
ENTITY_REGISTRY = EntityRegistry()


def get_entity_registry() -> EntityRegistry:
    """Get the global EntityRegistry singleton."""
    return ENTITY_REGISTRY
