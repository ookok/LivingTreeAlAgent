"""Hypergraph Store — N-ary knowledge with precedence structure.

OKH-RAG (arXiv:2604.12185) 核心数据层：
  - 超边（Hyperedge）：N 个实体的高阶关系（超越传统三元组）
  - 优先约束（Precedence）：超边间的前后依赖关系
  - 序列推断（Sequence Inference）：从超图恢复交互轨迹

Integration:
  - KnowledgeGraph: 保持兼容（三元组作为 k=2 超边的特例）
  - multi_source_retrieve: 超图融合结果替换传统 RRF 排序
  - PlanValidator: 基于超图的步骤顺序校验
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import networkx as nx


# ═══ Data Types ═══


@dataclass
class Hyperedge:
    """A single N-ary hyperedge connecting multiple entities.

    Unlike traditional triples (s, p, o), a hyperedge can connect
    any number of entities with a relation type and properties.

    Example (环评):
      Hyperedge(
        entities=["GB3095-2012", "SO2", "24h_avg", "150μg/m³", "Class_II"],
        relation="emission_limit",
        properties={"effective_date": "2016-01-01"},
        precedence_before=["monitoring_plan"],
        precedence_after=["standard_selection"],
      )
    """
    id: str
    entities: list[str]                 # N entity IDs (N >= 2)
    relation: str                        # Relation type label
    properties: dict[str, Any] = field(default_factory=dict)
    # Precedence: which hyperedge IDs must come before/after this one
    precedence_before: list[str] = field(default_factory=list)
    precedence_after: list[str] = field(default_factory=list)
    weight: float = 1.0                  # Edge weight (relevance/confidence)
    source_doc: str = ""                 # Which document this edge came from
    timestamp: float = 0.0               # When the edge was created/observed


@dataclass
class HypergraphQueryResult:
    """Result of a hypergraph sequence inference query."""
    hyperedges: list[Hyperedge]          # Ordered sequence of hyperedges
    trajectory_score: float              # Overall sequence score (0-1)
    missing_links: list[str] = field(default_factory=list)  # Gaps in the chain
    confidence: float = 0.0
    reasoning_trace: str = ""


@dataclass
class EntityNode:
    """Node in the hypergraph representing a knowledge entity."""
    id: str
    label: str
    entity_type: str = "concept"         # concept, document, regulation, etc.
    properties: dict[str, Any] = field(default_factory=dict)


# ═══ Hypergraph Store ═══


class HypergraphStore:
    """N-ary hypergraph storage engine with precedence structure.

    Internally uses NetworkX bipartite graph:
      - Entity nodes (type='entity')
      - Hyperedge nodes (type='hyperedge')
      - Edges connect entities to the hyperedges they participate in
    """

    def __init__(self):
        self._graph = nx.Graph()
        self._entities: dict[str, EntityNode] = {}
        self._hyperedges: dict[str, Hyperedge] = {}
        # Precedence graph: hyperedge → hyperedge directed edges
        self._precedence_graph = nx.DiGraph()
        # Co-occurrence stats for transition model learning
        self._cooccurrence: dict[tuple[str, str], int] = defaultdict(int)
        self._edge_count = 0

    # ── Entity Management ──

    def add_entity(self, entity: EntityNode) -> str:
        """Add an entity node (idempotent). Returns entity id."""
        if entity.id in self._entities:
            existing = self._entities[entity.id]
            existing.properties.update(entity.properties)
            return entity.id
        self._entities[entity.id] = entity
        self._graph.add_node(entity.id, type="entity", label=entity.label, **entity.properties)
        return entity.id

    def get_entity(self, entity_id: str) -> EntityNode | None:
        return self._entities.get(entity_id)

    def entity_count(self) -> int:
        return len(self._entities)

    # ── Hyperedge Management ──

    def add_hyperedge(self, hyperedge: Hyperedge) -> str:
        """Add a hyperedge connecting N entities. Returns hyperedge id."""
        # Auto-generate ID if missing
        if not hyperedge.id:
            self._edge_count += 1
            hyperedge.id = f"he_{self._edge_count}"

        h_id = hyperedge.id
        self._hyperedges[h_id] = hyperedge

        # Add as a node in the bipartite graph
        self._graph.add_node(h_id, type="hyperedge", relation=hyperedge.relation, weight=hyperedge.weight)
        # Connect to all entity nodes
        for entity_id in hyperedge.entities:
            if entity_id not in self._entities:
                self._entities[entity_id] = EntityNode(id=entity_id, label=entity_id)
                self._graph.add_node(entity_id, type="entity", label=entity_id)
            self._graph.add_edge(h_id, entity_id, relation=hyperedge.relation)

        # Register in precedence graph
        self._precedence_graph.add_node(h_id, relation=hyperedge.relation)
        for before_id in hyperedge.precedence_before:
            self._precedence_graph.add_edge(h_id, before_id, type="before")
        for after_id in hyperedge.precedence_after:
            self._precedence_graph.add_edge(after_id, h_id, type="after")

        # Update co-occurrence for transition learning
        entities = hyperedge.entities
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                pair = tuple(sorted([entities[i], entities[j]]))
                self._cooccurrence[pair] += 1

        # ── Synaptic Plasticity: register as silent synapse ──
        try:
            from ..core.synaptic_plasticity import get_plasticity
            get_plasticity().register(h_id, initial_weight=hyperedge.weight)
        except ImportError:
            pass

        return h_id

    def get_hyperedge(self, h_id: str) -> Hyperedge | None:
        return self._hyperedges.get(h_id)

    def hyperedge_count(self) -> int:
        return len(self._hyperedges)

    # ── Query: Sequence Inference (OKH-RAG core) ──

    def infer_sequence(
        self,
        seed_entities: list[str],
        max_depth: int = 5,
        min_weight: float = 0.1,
    ) -> HypergraphQueryResult:
        """OKH-RAG sequence inference: recover the most-likely trajectory.

        Starting from seed entities, traverse the hypergraph following
        precedence constraints to build a coherent interaction sequence.

        Args:
            seed_entities: Starting entity IDs (from query decomposition)
            max_depth: Maximum trajectory length (hyperedges)
            min_weight: Minimum edge weight to include

        Returns:
            HypergraphQueryResult with ordered hyperedges and trajectory score
        """
        if not seed_entities:
            return HypergraphQueryResult(
                hyperedges=[], trajectory_score=0.0,
                missing_links=seed_entities, confidence=0.0,
                reasoning_trace="no seed entities",
            )

        visited: set[str] = set()
        frontier: set[str] = set(seed_entities)
        trajectory: list[Hyperedge] = []
        depth = 0

        while frontier and depth < max_depth:
            # Find hyperedges connected to frontier entities
            candidates: list[tuple[Hyperedge, float]] = []
            for entity_id in list(frontier):
                neighbors = list(self._graph.neighbors(entity_id))
                for neighbor_id in neighbors:
                    if neighbor_id in visited:
                        continue
                    he = self._hyperedges.get(neighbor_id)
                    if he and he.weight >= min_weight:
                        # Score: weight + entity overlap with frontier
                        overlap = len(set(he.entities) & frontier)
                        score = he.weight * (1.0 + 0.5 * overlap)
                        candidates.append((he, score))

            if not candidates:
                break

            # Select best hyperedge considering precedence
            best_he, best_score = max(candidates, key=lambda x: (
                self._precedence_score(x[0], trajectory),
                x[1],
            ))

            visited.add(best_he.id)
            # Expand frontier: add all entities in the selected hyperedge
            frontier.update(best_he.entities)
            frontier.difference_update(visited)
            trajectory.append(best_he)
            depth += 1

        # Score the trajectory
        traj_score = self._score_trajectory(trajectory)
        missing = self._find_missing_links(trajectory)

        # ── Synaptic LTP: strengthen activated hyperedges ──
        if trajectory and traj_score > 0.5:
            try:
                from ..core.synaptic_plasticity import get_plasticity
                sp = get_plasticity()
                for he in trajectory:
                    sp.strengthen(he.id, boost=traj_score)
            except ImportError:
                pass

        return HypergraphQueryResult(
            hyperedges=trajectory,
            trajectory_score=traj_score,
            missing_links=missing,
            confidence=traj_score if trajectory else 0.0,
            reasoning_trace=f"depth={depth}, frontiers={len(frontier)}",
        )

    def _precedence_score(
        self, he: Hyperedge, trajectory: list[Hyperedge],
    ) -> float:
        """Score a hyperedge by how well it respects precedence constraints.

        Returns 0.0-1.0 where 1.0 = perfect ordering, 0.0 = violates constraints.
        """
        if not trajectory:
            return 0.5  # Neutral for first step

        score = 0.5

        # Check: all precedence_after are satisfied (present in trajectory)
        if he.precedence_after:
            traj_ids = {h.id for h in trajectory}
            satisfied = sum(1 for a in he.precedence_after if a in traj_ids)
            score += 0.3 * (satisfied / len(he.precedence_after))

        # Check: no precedence_before is violated (already in trajectory)
        if he.precedence_before:
            traj_ids = {h.id for h in trajectory}
            violations = sum(1 for b in he.precedence_before if b in traj_ids)
            score -= 0.3 * (violations / max(len(he.precedence_before), 1))

        return max(0.0, min(1.0, score))

    def _score_trajectory(self, trajectory: list[Hyperedge]) -> float:
        """Score overall trajectory quality (0-1)."""
        if not trajectory:
            return 0.0
        if len(trajectory) == 1:
            return trajectory[0].weight

        # Average weight + precedence consistency
        avg_weight = sum(h.weight for h in trajectory) / len(trajectory)
        # Check if any precedence constraints are violated
        prec_ok = True
        seen_ids = set()
        for h in trajectory:
            for before_id in h.precedence_before:
                if before_id in seen_ids:
                    prec_ok = False
                    break
            seen_ids.add(h.id)
        precedence_bonus = 0.2 if prec_ok else -0.2

        return max(0.0, min(1.0, avg_weight + precedence_bonus))

    def _find_missing_links(self, trajectory: list[Hyperedge]) -> list[str]:
        """Find unsatisfied precedence dependencies."""
        seen_ids = {h.id for h in trajectory}
        missing = []
        for h in trajectory:
            for after_id in h.precedence_after:
                if after_id not in seen_ids:
                    missing.append(f"missing_after:{after_id}")
            for before_id in h.precedence_before:
                if before_id not in seen_ids:
                    missing.append(f"missing_before:{before_id}")
        return missing

    # ── Query: Entity-based retrieval ──

    def query_by_entities(
        self, entity_ids: list[str], max_edges: int = 10,
    ) -> list[Hyperedge]:
        """Find all hyperedges connected to given entities."""
        result_set: dict[str, Hyperedge] = {}
        for eid in entity_ids:
            if eid not in self._graph:
                continue
            for neighbor in self._graph.neighbors(eid):
                he = self._hyperedges.get(neighbor)
                if he and he.id not in result_set:
                    result_set[he.id] = he
        # Sort by weight descending, take top
        sorted_edges = sorted(result_set.values(), key=lambda h: -h.weight)
        return sorted_edges[:max_edges]

    def query_by_relation(
        self, relation: str, max_edges: int = 10,
    ) -> list[Hyperedge]:
        """Find all hyperedges of a given relation type."""
        result = [h for h in self._hyperedges.values() if h.relation == relation]
        result.sort(key=lambda h: -h.weight)
        return result[:max_edges]

    # ── Precedence chain traversal ──

    def get_precedence_chain(
        self, start_id: str, direction: str = "forward", max_depth: int = 5,
    ) -> list[Hyperedge]:
        """Traverse the precedence graph from a starting hyperedge.

        Args:
            start_id: Hyperedge ID to start from
            direction: 'forward' (before→after), 'backward' (after→before), 'both'
            max_depth: Max traversal depth

        Returns:
            Ordered list of hyperedges along the precedence chain
        """
        if start_id not in self._precedence_graph:
            return []

        chain: list[Hyperedge] = []
        visited: set[str] = set()
        frontier = [start_id]

        for _ in range(max_depth):
            if not frontier:
                break
            next_frontier = []
            for node_id in frontier:
                if node_id in visited:
                    continue
                visited.add(node_id)
                he = self._hyperedges.get(node_id)
                if he:
                    chain.append(he)
                # Get successors
                if direction in ("forward", "both"):
                    for succ in self._precedence_graph.successors(node_id):
                        if succ not in visited:
                            next_frontier.append(succ)
                if direction in ("backward", "both"):
                    for pred in self._precedence_graph.predecessors(node_id):
                        if pred not in visited:
                            next_frontier.append(pred)
            frontier = next_frontier

        return chain

    # ── Import/Export ──

    def to_networkx(self) -> nx.Graph:
        """Export the full hypergraph as a NetworkX graph."""
        return self._graph.copy()

    def stats(self) -> dict[str, Any]:
        return {
            "entity_count": len(self._entities),
            "hyperedge_count": len(self._hyperedges),
            "precedence_edge_count": self._precedence_graph.number_of_edges(),
            "relation_types": len({h.relation for h in self._hyperedges.values()}),
            "avg_entity_per_edge": (
                sum(len(h.entities) for h in self._hyperedges.values()) / max(len(self._hyperedges), 1)
            ),
        }


# ═══ Hypergraph → Document Conversion ═══

def hypergraph_to_documents(
    store: HypergraphStore, max_per_edge: int = 50,
) -> list[dict[str, Any]]:
    """Convert hypergraph edges to document-like dicts for KnowledgeBase ingestion.

    Each hyperedge becomes a structured document summarizing the N-ary relation.
    """
    docs = []
    for he_id, he in store._hyperedges.items():
        entity_labels = []
        for eid in he.entities:
            entity = store._entities.get(eid)
            label = entity.label if entity else eid
            entity_labels.append(label)
        relation_text = f"[{he.relation}] {' + '.join(entity_labels)}"
        if he.properties:
            relation_text += f" | props: {he.properties}"
        docs.append({
            "title": f"hyperedge:{he_id}",
            "content": relation_text[:max_per_edge],
            "tags": [he.relation, "hyperedge"],
            "metadata": {
                "hyperedge_id": he_id,
                "relation": he.relation,
                "entity_count": len(he.entities),
                "weight": he.weight,
                "source_doc": he.source_doc,
            },
        })
    return docs


__all__ = [
    "HypergraphStore", "Hyperedge", "EntityNode",
    "HypergraphQueryResult", "hypergraph_to_documents",
]
