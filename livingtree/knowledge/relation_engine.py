"""
Relation Calculus Engine — 关系演算引擎。

为 LivingTree 的关系图谱添加传递性推理、逆关系推导、对称性检测和一致性检查。
解决当前 4 层本体中关系是扁平的、缺乏推理能力的问题。

Usage:
    from livingtree.knowledge.relation_engine import RELATION_ENGINE
    engine = RELATION_ENGINE
    closure = engine.infer("kg:python-lang", "related_to")
    paths = engine.get_relation_paths("skill:code-generation", "skill:code-review")
"""
from __future__ import annotations

from collections import deque
from typing import Any

from loguru import logger
from pydantic import BaseModel


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
