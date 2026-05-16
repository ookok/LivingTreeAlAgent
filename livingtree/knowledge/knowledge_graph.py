"""Graph-based knowledge representation using NetworkX.

This module provides a lightweight graph model for entities and their
relationships, with simple import/export support to NetworkX and Neo4j
style formats.

v2.5: Added LLM-based triplet extraction (Vector Graph RAG style)
for higher-quality entity linking and relation extraction.
"""

from __future__ import annotations

import hashlib
import re
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from pydantic import BaseModel, Field

import networkx as nx


class Entity(BaseModel):
    id: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class Triplet(BaseModel):
    """A (subject, predicate, object) triplet extracted from text."""
    subject: str
    predicate: str
    obj: str
    source_text: str = ""
    confidence: float = 1.0


class KnowledgeGraph:
    def __init__(self) -> None:
        self.graph = nx.Graph() if nx is not None else None  # type: ignore
        self.nodes_index: Dict[str, Entity] = {}
        self._triplets: List[Triplet] = []

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
        """Entity linking: string-match fallback + anchored multi-word lookup.

        For production, use extract_triplets() with an LLM function.
        """
        matches: List[str] = []
        text_lower = text.lower()
        # Sort entities by label length descending (prefer longer matches)
        sorted_entities = sorted(
            self.nodes_index.items(),
            key=lambda x: len(x[1].label or ""),
            reverse=True,
        )
        matched_positions: set[int] = set()
        for entity_id, ent in sorted_entities:
            label = (ent.label or "").lower()
            if not label or len(label) < 2:
                continue
            # Find all occurrences of label in text
            pos = 0
            while True:
                idx = text_lower.find(label, pos)
                if idx == -1:
                    break
                # Check if this position is already taken
                positions = set(range(idx, idx + len(label)))
                if not positions & matched_positions:
                    matches.append(entity_id)
                    matched_positions |= positions
                pos = idx + 1
        return matches

    # ── LLM Triplet Extraction (Vector Graph RAG style) ──

    def extract_triplets(
        self, text: str, llm_func=None,
    ) -> List[Triplet]:
        """Extract (subject, predicate, object) triplets from text.

        Uses LLM if llm_func provided, otherwise falls back to regex-based extraction.

        Args:
            text: Input text to extract triplets from.
            llm_func: Optional async function to call LLM.
        """
        if llm_func:
            return self._extract_triplets_llm(text, llm_func)
        return self._extract_triplets_regex(text)

    async def extract_triplets_async(
        self, text: str, llm_func,
    ) -> List[Triplet]:
        """Async version of extract_triplets."""
        return await self._extract_triplets_llm_async(text, llm_func)

    TRIPLET_EXTRACT_PROMPT = """Extract all knowledge triplets (subject, predicate, object) from the text.
Each triplet represents one factual relationship.

Format each triplet as: subject | predicate | object
Example: Einstein | developed | theory of relativity

Rules:
- Extract only factual relationships, not opinions or speculation
- Keep subjects and objects concise (1-5 words)
- Use standard, consistent predicate names

Text:
{text}

Triplets (one per line):"""

    def _extract_triplets_llm(self, text: str, llm_func) -> List[Triplet]:
        prompt = self.TRIPLET_EXTRACT_PROMPT.format(text=text[:3000])
        try:
            response = llm_func(prompt)
            content = response if isinstance(response, str) else response.get("content", str(response))
        except Exception as e:
            logger.warning(f"LLM triplet extraction failed: {e}")
            return self._extract_triplets_regex(text)
        return self._parse_triplets(content, text)

    async def _extract_triplets_llm_async(self, text: str, llm_func) -> List[Triplet]:
        import asyncio
        prompt = self.TRIPLET_EXTRACT_PROMPT.format(text=text[:3000])
        try:
            response = await llm_func(prompt)
            content = response if isinstance(response, str) else response.get("content", str(response))
        except Exception as e:
            logger.warning(f"LLM triplet extraction failed: {e}")
            return self._extract_triplets_regex(text)
        return self._parse_triplets(content, text)

    def _parse_triplets(self, content: str, source_text: str) -> List[Triplet]:
        triplets: List[Triplet] = []
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                triplets.append(Triplet(
                    subject=parts[0].strip(),
                    predicate=parts[1].strip(),
                    obj=parts[2].strip(),
                    source_text=source_text[:200],
                    confidence=0.9,
                ))
        logger.debug(f"Parsed {len(triplets)} triplets from LLM output")
        return triplets

    @staticmethod
    def _extract_triplets_regex(text: str) -> List[Triplet]:
        """Regex-based triplet extraction as fallback (no LLM needed)."""
        triplets: List[Triplet] = []
        patterns = [
            # Subject-verb-object: "X is Y" / "X was Y"
            (r'([A-Z][a-zA-Z]+(?:\s+[a-z]+){0,3})\s+(?:is|was|are|were)\s+(?:a|an|the)?\s+([A-Za-z][a-zA-Z]+(?:\s+[a-z]+){0,4})', "is a"),
            # "X belongs to Y" / "X consists of Y"
            (r'([A-Z][a-zA-Z]+(?:\s+[a-z]+){0,3})\s+(?:belongs to|consists of|includes|contains|comprises)\s+([A-Za-z][a-zA-Z]+(?:\s+[a-z]+){0,4})', "contains"),
            # "X developed Y" / "X created Y"
            (r'([A-Z][a-zA-Z]+(?:\s+[a-z]+){0,3})\s+(?:developed|created|invented|discovered|proposed|designed)\s+([A-Za-z][a-zA-Z]+(?:\s+[a-z]+){0,4})', "developed"),
            # "X used in Y" / "X applied to Y"
            (r'([A-Z][a-zA-Z]+(?:\s+[a-z]+){0,3})\s+(?:used in|applied to|employed in)\s+([A-Za-z][a-zA-Z]+(?:\s+[a-z]+){0,4})', "used in"),
            # "X causes Y" / "X leads to Y"
            (r'([A-Z][a-zA-Z]+(?:\s+[a-z]+){0,3})\s+(?:causes|leads to|results in|triggers)\s+([A-Za-z][a-zA-Z]+(?:\s+[a-z]+){0,4})', "causes"),
        ]

        for pattern, default_predicate in patterns:
            for match in re.finditer(pattern, text):
                subj = match.group(1).strip()
                obj = match.group(2).strip()
                if subj.lower() != obj.lower():
                    triplets.append(Triplet(
                        subject=subj, predicate=default_predicate, obj=obj,
                        source_text=text[:200], confidence=0.6,
                    ))

        return triplets

    def add_triplets_to_graph(
        self, triplets: List[Triplet],
    ) -> int:
        """Add extracted triplets as entities and edges in the graph.

        Returns the number of edges added.
        """
        count = 0
        for t in triplets:
            subj_id = self._entity_id(t.subject)
            obj_id = self._entity_id(t.obj)
            if subj_id not in self.nodes_index:
                self.add_entity(Entity(id=subj_id, label=t.subject))
            if obj_id not in self.nodes_index:
                self.add_entity(Entity(id=obj_id, label=t.obj))
            self.add_relation(subj_id, obj_id, t.predicate, {"confidence": t.confidence})
            self._triplets.append(t)
            count += 1
        logger.info(f"Added {count} triplets to KnowledgeGraph ({len(self.nodes_index)} entities)")
        return count

    @staticmethod
    def _entity_id(label: str) -> str:
        norm = label.lower().strip().replace(" ", "_")
        return hashlib.md5(norm.encode()).hexdigest()[:12]

    def get_triplets(self) -> List[Triplet]:
        return list(self._triplets)

    # Import/export helpers
    def export_to_networkx(self, path: str) -> None:
        if self.graph is None:
            return
        nx.write_gexf(self.graph, path)

    def import_from_networkx(self, path: str) -> None:
        self.graph = nx.read_gexf(path) if nx is not None else None

    # Neo4j-style adapters (stubs for demo)
    def to_neo4j(self, path: str) -> None:
        self.export_to_sqlite(path.replace(".neo4j", ".db").replace(".cypher", ".db"))

    def export_to_sqlite(self, path: str) -> None:
        import sqlite3, json
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, label TEXT, kind TEXT, properties TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS edges (source TEXT, target TEXT, relation TEXT, weight REAL)")
        for eid, ent in self.nodes_index.items():
            conn.execute("INSERT OR REPLACE INTO entities VALUES (?,?,?,?)",
                         (eid, ent.label or "", getattr(ent, 'kind', ''), json.dumps(getattr(ent, 'properties', {}), ensure_ascii=False)))
        for eid, ent in self.nodes_index.items():
            for rel_ent_id in getattr(ent, 'related', []):
                conn.execute("INSERT INTO edges VALUES (?,?,?,?)", (eid, rel_ent_id, "related", 1.0))
        for t in self._triplets:
            conn.execute("INSERT INTO edges VALUES (?,?,?,?)",
                         (self._entity_id(t.subject), self._entity_id(t.obj), t.predicate, t.confidence))
        conn.commit()
        conn.close()
        logger.info(f"KnowledgeGraph exported to SQLite: {path}")


# ── Relation Engine (merged from relation_engine.py) ──


class RelationRule(BaseModel):
    """Rule defining how a relation type behaves in reasoning."""

    relation: str
    transitive: bool = False  # A→B and B→C ⇒ A→C
    symmetric: bool = False  # A→B ⇒ B→A
    reflexive: bool = False  # Every entity has this to itself
    inverse: str | None = None  # Inverse relation name (e.g. "depends_on" → "required_by")


# Default relation rules for LivingTree
_DEFAULT_RULES: list[RelationRule] = [
    RelationRule(relation="depends_on", transitive=True, symmetric=False, reflexive=False, inverse="required_by"),
    RelationRule(relation="specializes", transitive=True, symmetric=False, reflexive=False, inverse="generalized_by"),
    RelationRule(relation="composes_with", transitive=False, symmetric=True, reflexive=False),
    RelationRule(relation="conflicts_with", transitive=False, symmetric=True, reflexive=False),
    RelationRule(relation="related_to", transitive=False, symmetric=True, reflexive=False),
]


class RelationEngine:
    """Reasoning engine for typed relations across ontology layers."""

    def __init__(
        self,
        knowledge_graph=None,
        skill_graph=None,
        entity_registry=None,
    ):
        self._kg = knowledge_graph
        self._sg = skill_graph
        self._er = entity_registry
        self._rules: dict[str, RelationRule] = {}
        self._graph: dict[str, dict[str, list[str]]] = {}  # entity → {relation → [targets]}
        self._deps_loaded = False

        # Register default rules
        for rule in _DEFAULT_RULES:
            self.register_rule(rule)

    def _ensure_dependencies(self) -> None:
        """Lazy-load graph sources."""
        if self._deps_loaded:
            return
        self._deps_loaded = True

        # Load from EntityRegistry
        if self._er is None:
            try:
                from livingtree.core.entity_registry import ENTITY_REGISTRY
                self._er = ENTITY_REGISTRY
            except ImportError:
                pass

        if self._er:
            try:
                for entry in self._er.list_all():
                    for target_id, relation in entry.linked_entities.items():
                        self.add_relation(entry.id, target_id, relation)
            except Exception as e:
                logger.debug(f"EntityRegistry edge load error: {e}")

    # ── Rule management ──

    def register_rule(self, rule: RelationRule) -> None:
        """Register a relation reasoning rule."""
        self._rules[rule.relation] = rule

    def add_relation(self, source: str, target: str, relation: str) -> None:
        """Add a directed edge to the internal graph."""
        if source not in self._graph:
            self._graph[source] = {}
        if relation not in self._graph[source]:
            self._graph[source][relation] = []
        if target not in self._graph[source][relation]:
            self._graph[source][relation].append(target)

        # Symmetric: add reverse edge
        rule = self._rules.get(relation)
        if rule and rule.symmetric and target != source:
            if target not in self._graph:
                self._graph[target] = {}
            if relation not in self._graph[target]:
                self._graph[target][relation] = []
            if source not in self._graph[target][relation]:
                self._graph[target][relation].append(source)

    # ── Reasoning ──

    def infer(self, source: str, relation: str | None = None) -> list[str]:
        """
        Compute the set of entities reachable from source via the given relation(s).
        If relation is None, infer across ALL relations.
        """
        self._ensure_dependencies()

        relations = [relation] if relation else list(self._rules.keys())
        visited: set[str] = {source}
        queue = deque([source])

        while queue:
            current = queue.popleft()
            for rel in relations:
                rule = self._rules.get(rel)
                for target in self._graph.get(current, {}).get(rel, []):
                    if target not in visited:
                        visited.add(target)
                        queue.append(target)
                        if rule and rule.transitive:
                            # Continue traversal along transitive relations
                            pass

        visited.discard(source)
        return sorted(visited)

    def derive_inverse(self, source: str, relation: str) -> list[str]:
        """Infer using the inverse relation (e.g., depends_on → required_by)."""
        rule = self._rules.get(relation)
        if not rule or not rule.inverse:
            return []
        return self.infer(source, rule.inverse)

    def get_closure(self, relations: list[str] | None = None) -> dict[str, list[str]]:
        """Compute transitive closure for all entities."""
        self._ensure_dependencies()
        relations = relations or list(self._rules.keys())
        transitive_rules = [r for r in relations if self._rules.get(r) and self._rules[r].transitive]

        closure: dict[str, list[str]] = {}
        for entity in self._graph:
            reachable = set()
            for rel in transitive_rules:
                reachable.update(self.infer(entity, rel))
            if reachable:
                closure[entity] = sorted(reachable)
        return closure

    def check_consistency(self, source: str, target: str, relation: str, max_depth: int = 5) -> dict[str, Any]:
        """
        Check for cycles, contradictions, and redundancies between two entities.

        Returns:
            {"cycles": list, "contradictions": list, "redundancies": list}
        """
        self._ensure_dependencies()
        result: dict[str, list] = {"cycles": [], "contradictions": [], "redundancies": []}

        # Cycle detection: does target (transitively) reach back to source?
        back_reachable = self.infer(target, relation)
        if source in back_reachable:
            result["cycles"].append(f"Cycle: {source} → ... → {target} → ... → {source}")

        # Contradiction: check if source conflicts_with target but also depends_on target
        for r, targets in self._graph.get(source, {}).items():
            if r == "conflicts_with" and target in targets:
                # Check if there's also a depends_on path
                for r2, t2 in self._graph.get(source, {}).items():
                    if r2 == "depends_on" and target in t2:
                        result["contradictions"].append(
                            f"Contradiction: {source} both depends_on and conflicts_with {target}"
                        )
                # Check transitive depends_on
                depends_reachable = set(self.infer(source, "depends_on"))
                if target in depends_reachable:
                    result["contradictions"].append(
                        f"Transitive contradiction: {source} transitively depends_on but directly conflicts_with {target}"
                    )

        # Redundancy: multiple paths via different relations with same meaning
        all_paths = self.get_relation_paths(source, target, max_depth)
        if len(all_paths) > 1:
            result["redundancies"].append(
                f"Redundancy: {len(all_paths)} paths between {source} and {target}"
            )

        return result

    def get_relation_paths(self, source: str, target: str, max_depth: int = 5) -> list[list[tuple[str, str]]]:
        """
        Find all paths from source to target using BFS.
        Each path is a list of (from_entity, relation) tuples.
        """
        self._ensure_dependencies()

        if source not in self._graph:
            return []

        paths: list[list[tuple[str, str]]] = []
        queue = deque([(source, [], {source})])  # (current, path, visited)

        while queue and len(paths) < 20:
            current, path, visited = queue.popleft()
            if len(path) >= max_depth:
                continue

            for rel, targets in self._graph.get(current, {}).items():
                for tgt in targets:
                    if tgt in visited:
                        continue
                    new_path = path + [(current, rel)]
                    if tgt == target:
                        paths.append(new_path + [(tgt, "")])
                    else:
                        new_visited = visited | {tgt}
                        queue.append((tgt, new_path, new_visited))

        return paths

    # ── Utilities ──

    def stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        self._ensure_dependencies()
        total_edges = sum(len(targets) for src in self._graph.values() for targets in src.values())
        by_type: dict[str, int] = {}
        for src in self._graph.values():
            for rel, targets in src.items():
                by_type[rel] = by_type.get(rel, 0) + len(targets)
        closure = self.get_closure()
        return {
            "total_relations": total_edges,
            "by_type": by_type,
            "transitive_pairs": sum(len(v) for v in closure.values()),
            "rules_registered": len(self._rules),
        }


# Singleton
RELATION_ENGINE = RelationEngine()


def get_relation_engine() -> RelationEngine:
    """Get the global RelationEngine singleton."""
    return RELATION_ENGINE


__all__ = ["KnowledgeGraph", "Entity", "Triplet", "RelationRule", "RelationEngine", "RELATION_ENGINE", "get_relation_engine"]
