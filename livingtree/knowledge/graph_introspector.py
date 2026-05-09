"""Graph Introspector — interactive knowledge graph exploration & impact analysis.

Inspired by Lum1104/Understand-Anything (13.6k stars):
  "Graphs that teach > graphs that impress."
  - Multi-agent pipeline → analyze codebase into knowledge graph
  - Diff impact analysis → predict change propagation
  - Incremental updates → only re-analyze changed parts
  - Interactive exploration → search, navigate, query the graph
  - JSON-committed graph → version-controlled, team-shareable

Adapted to LivingTree's HypergraphStore + KnowledgeGraph ecosystem:
  1. Incremental Hypergraph Builder — only update changed entities/edges
  2. Impact Propagation Analyzer — predict change ripple effects
  3. Graph Export/Import — JSON format for commit/sharing
  4. Semantic Graph Search — find entities by meaning, not just ID
  5. Guided Architecture Tour — auto-generate walkthrough of graph topology
  6. Diff Overlay — compare two snapshots, show what changed

Integration points:
  - HypergraphStore → enhanced with incremental update + export
  - KnowledgeGraph → enhanced with diff + impact analysis
  - KnowledgeBase → graph-aware document ingestion
  - MCP server → expose graph queries as MCP tools
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


# ═══ Data Types ═══


@dataclass
class GraphDiff:
    """Difference between two graph snapshots."""
    added_entities: list[str]
    removed_entities: list[str]
    modified_entities: list[str]     # Properties changed
    added_hyperedges: list[str]
    removed_hyperedges: list[str]
    modified_hyperedges: list[str]
    timestamp: float = field(default_factory=time.time)

    @property
    def total_changes(self) -> int:
        return (len(self.added_entities) + len(self.removed_entities)
                + len(self.modified_entities) + len(self.added_hyperedges)
                + len(self.removed_hyperedges) + len(self.modified_hyperedges))

    def summary(self) -> str:
        return (
            f"Graph diff: +{len(self.added_entities)}/-{len(self.removed_entities)} "
            f"entities, +{len(self.added_hyperedges)}/-{len(self.removed_hyperedges)} "
            f"edges ({self.total_changes} total changes)"
        )


@dataclass
class ImpactPath:
    """A single impact propagation path through the graph."""
    source_entity: str
    affected_entities: list[str]     # Ordered chain of affected entities
    path_length: int
    total_impact_score: float        # Cumulative impact along the path
    relation_types: list[str]        # How entities are related along the path


@dataclass
class ImpactReport:
    """Complete impact analysis for a change."""
    changed_entity: str
    directly_affected: list[str]     # 1-hop neighbors
    propagation_paths: list[ImpactPath]  # Multi-hop impact chains
    total_affected_count: int        # Unique affected entities
    max_propagation_depth: int
    risk_level: str = "low"          # low/medium/high/critical
    summary: str = ""

    def to_context(self) -> str:
        lines = [
            f"## Impact Analysis: {self.changed_entity}",
            f"Risk: {self.risk_level.upper()}",
            f"Directly affected: {len(self.directly_affected)} entities",
            f"Propagation depth: {self.max_propagation_depth} hops",
            f"Total affected: {self.total_affected_count} entities",
        ]
        if self.propagation_paths:
            lines.append("Key impact chains:")
            for p in self.propagation_paths[:5]:
                chain = " → ".join(p.affected_entities[:5])
                lines.append(f"  {chain} (score={p.total_impact_score:.2f})")
        return "\n".join(lines)


@dataclass
class TourStep:
    """A single step in a guided architecture tour."""
    order: int
    entity_id: str
    entity_label: str
    why_here: str                  # Why this step is important
    relationships: list[str]        # What this connects to
    learning_points: list[str]      # Key concepts to understand


@dataclass
class GuidedTour:
    """A guided tour through the knowledge graph architecture."""
    title: str
    steps: list[TourStep]
    estimated_minutes: int
    target_audience: str = "developer"
    summary: str = ""


# ═══ Graph Introspector ═══


class GraphIntrospector:
    """Interactive exploration and analysis of LivingTree knowledge graphs.

    Understand-Anything concepts applied to LivingTree's graph ecosystem:
      - HypergraphStore: primary graph data
      - KnowledgeGraph: entity-relation triples
      - PrecedenceModel: transition information
      - KnowledgeBase: document-aware graph building
    """

    def __init__(self, store_dir: str = ".livingtree/graph_snapshots"):
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._snapshots: dict[str, dict] = {}
        self._diffs: list[GraphDiff] = []

    # ═══ Incremental Build ═══

    def snapshot(self, hypergraph_store=None, label: str = "") -> dict:
        """Take a snapshot of the current graph state.

        Understand-Anything analog: the JSON graph produced by the
        multi-agent pipeline, committed for sharing.
        """
        ts = time.strftime("%Y%m%d_%H%M%S")
        snap_id = f"{label}_{ts}" if label else ts

        snapshot_data = {"id": snap_id, "timestamp": time.time(), "label": label}

        if hypergraph_store:
            snapshot_data["entities"] = {
                eid: {
                    "label": e.label,
                    "type": e.entity_type,
                    "properties": e.properties,
                }
                for eid, e in hypergraph_store._entities.items()
            }
            snapshot_data["hyperedges"] = {
                hid: {
                    "relation": he.relation,
                    "entities": he.entities,
                    "precedence_before": he.precedence_before,
                    "precedence_after": he.precedence_after,
                    "weight": he.weight,
                    "source_doc": he.source_doc,
                }
                for hid, he in hypergraph_store._hyperedges.items()
            }
            snapshot_data["stats"] = hypergraph_store.stats()

        self._snapshots[snap_id] = snapshot_data

        # Save to disk (committable JSON — Understand-Anything pattern)
        path = self._store_dir / f"{snap_id}.json"
        path.write_text(json.dumps(snapshot_data, ensure_ascii=False, indent=2))

        logger.info(f"Graph snapshot: {snap_id} ({len(snapshot_data.get('entities', {}))} entities, "
                     f"{len(snapshot_data.get('hyperedges', {}))} edges)")
        return snapshot_data

    def incremental_update(
        self, hypergraph_store=None, changed_files: list[str] | None = None,
    ) -> GraphDiff | None:
        """Incrementally update only changed parts of the graph.

        Understand-Anything analog: post-commit hook that re-analyzes
        only changed files, patching the graph incrementally.
        """
        if not self._snapshots:
            return None

        # Get latest snapshot
        latest_id = sorted(self._snapshots.keys())[-1]
        latest = self._snapshots[latest_id]

        if not hypergraph_store:
            return None

        current_entities = {
            eid: {"label": e.label, "type": e.entity_type, "properties": e.properties}
            for eid, e in hypergraph_store._entities.items()
        }
        current_edges = {
            hid: {"relation": he.relation, "entities": he.entities}
            for hid, he in hypergraph_store._hyperedges.items()
        }

        prev_entities = latest.get("entities", {})
        prev_edges = latest.get("hyperedges", {})

        # Compute diff
        diff = self._compute_diff(
            prev_entities, current_entities,
            prev_edges, current_edges,
        )

        if diff.total_changes > 0:
            self._diffs.append(diff)
            logger.info(diff.summary())

        return diff

    @staticmethod
    def _compute_diff(
        prev_e: dict, curr_e: dict, prev_h: dict, curr_h: dict,
    ) -> GraphDiff:
        """Compute the diff between two graph snapshots."""
        prev_e_keys = set(prev_e.keys())
        curr_e_keys = set(curr_e.keys())
        prev_h_keys = set(prev_h.keys())
        curr_h_keys = set(curr_h.keys())

        added_e = list(curr_e_keys - prev_e_keys)
        removed_e = list(prev_e_keys - curr_e_keys)
        modified_e = []
        for key in prev_e_keys & curr_e_keys:
            if prev_e[key] != curr_e[key]:
                modified_e.append(key)

        added_h = list(curr_h_keys - prev_h_keys)
        removed_h = list(prev_h_keys - curr_h_keys)
        modified_h = []
        for key in prev_h_keys & curr_h_keys:
            if prev_h[key] != curr_h[key]:
                modified_h.append(key)

        return GraphDiff(
            added_entities=added_e, removed_entities=removed_e,
            modified_entities=modified_e, added_hyperedges=added_h,
            removed_hyperedges=removed_h, modified_hyperedges=modified_h,
        )

    # ═══ Impact Propagation Analysis ═══

    def analyze_impact(
        self, entity_id: str, hypergraph_store=None,
        max_depth: int = 3, max_paths: int = 10,
    ) -> ImpactReport | None:
        """Analyze ripple effects of changing an entity.

        Understand-Anything analog: diff impact analysis showing which
        parts of the system are affected by a change.

        Uses BFS through the hypergraph to trace impact propagation.
        """
        if not hypergraph_store or entity_id not in hypergraph_store._graph:
            return None

        # BFS from changed entity
        direct: list[str] = []
        paths: list[ImpactPath] = []
        visited: set[str] = {entity_id}
        frontier = [(entity_id, [entity_id], 1.0, [])]  # (node, path, score, relations)

        depth = 0
        while frontier and depth < max_depth:
            next_frontier = []
            for node, path, score, relations in frontier:
                if node in hypergraph_store._graph:
                    for neighbor in hypergraph_store._graph.neighbors(node):
                        if neighbor in visited:
                            continue
                        visited.add(neighbor)
                        if depth == 0:
                            direct.append(neighbor)
                        # Impact score decays with distance: 1/(d+1)
                        edge_weight = 1.0
                        he = hypergraph_store._hyperedges.get(neighbor)
                        if he:
                            edge_weight = he.weight
                        new_score = score * edge_weight / (depth + 1)
                        relation = he.relation if he else "unknown"
                        new_path = path + [neighbor]
                        new_relations = relations + [relation]
                        next_frontier.append((neighbor, new_path, new_score, new_relations))

                        if depth > 0 and len(paths) < max_paths:
                            paths.append(ImpactPath(
                                source_entity=entity_id,
                                affected_entities=list(new_path),
                                path_length=len(new_path) - 1,
                                total_impact_score=round(new_score, 3),
                                relation_types=list(new_relations),
                            ))
            frontier = next_frontier
            depth += 1

        total = len(direct) + sum(len(p.affected_entities) - 1 for p in paths)
        total_unique = len(visited) - 1  # Exclude source
        max_d = max((p.path_length for p in paths), default=1)

        # Risk level
        if total_unique > 20:
            risk = "critical"
        elif total_unique > 10:
            risk = "high"
        elif total_unique > 5:
            risk = "medium"
        else:
            risk = "low"

        return ImpactReport(
            changed_entity=entity_id,
            directly_affected=direct,
            propagation_paths=sorted(paths, key=lambda p: -p.total_impact_score),
            total_affected_count=total_unique,
            max_propagation_depth=max_d,
            risk_level=risk,
            summary=f"Changing {entity_id} affects {total_unique} entities across {max_d} hops (risk: {risk})",
        )

    # ═══ Semantic Graph Search ═══

    def search_by_meaning(
        self, query: str, hypergraph_store=None, top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """Find graph entities by semantic meaning, not just ID.

        Understand-Anything analog: fuzzy and semantic search across the graph.
        """
        if not hypergraph_store:
            return []

        query_words = set(query.lower().split())
        scored = []

        for eid, entity in hypergraph_store._entities.items():
            label = entity.label.lower()
            label_words = set(label.split())

            # Word overlap score
            overlap = len(query_words & label_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                scored.append((eid, score))
            else:
                # Partial substring match
                if any(qw in label for qw in query_words):
                    scored.append((eid, 0.3))

        # Boost by entity properties
        for i, (eid, score) in enumerate(scored):
            entity = hypergraph_store._entities.get(eid)
            if entity and entity.properties:
                props_str = str(entity.properties).lower()
                prop_overlap = sum(1 for qw in query_words if qw in props_str)
                score += prop_overlap * 0.1

        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    # ═══ Guided Architecture Tour ═══

    def generate_tour(
        self, hypergraph_store=None, target: str = "developer", max_steps: int = 12,
    ) -> GuidedTour | None:
        """Auto-generate a guided tour of the graph architecture.

        Understand-Anything analog: guided tours that teach the architecture
        in dependency order, walking through the system layer by layer.
        """
        if not hypergraph_store:
            return None

        hg = hypergraph_store
        steps: list[TourStep] = []

        # 1. Find entry points (entities with highest centrality)
        centralities = []
        for eid in hg._entities:
            degree = hg._graph.degree(eid) if eid in hg._graph else 0
            centralities.append((eid, degree))
        centralities.sort(key=lambda x: -x[1])

        tour_order = 0
        seen: set[str] = set()
        frontier = [eid for eid, _ in centralities[:3]]  # Top 3 most central

        while frontier and len(steps) < max_steps:
            eid = frontier.pop(0)
            if eid in seen or eid not in hg._entities:
                continue
            seen.add(eid)
            entity = hg._entities[eid]

            # Find related entities
            relations = []
            if eid in hg._graph:
                for neighbor in hg._graph.neighbors(eid):
                    he = hg._hyperedges.get(neighbor)
                    if he:
                        relations.append(f"{he.relation} → {neighbor[:30]}")
                    elif neighbor in hg._entities:
                        relations.append(f"related → {neighbor[:30]}")

            # Learning points
            learning = [f"{entity.label} is a {entity.entity_type} node"]
            degree = hg._graph.degree(eid) if eid in hg._graph else 0
            if degree > 5:
                learning.append(f"Hub node with {degree} connections")
            he_count = len(hg.query_by_entities([eid], max_edges=50))
            if he_count > 0:
                learning.append(f"Involved in {he_count} hypergraph relations")

            steps.append(TourStep(
                order=tour_order + 1,
                entity_id=eid,
                entity_label=entity.label,
                why_here=self._tour_why(eid, degree, he_count),
                relationships=relations[:5],
                learning_points=learning,
            ))
            tour_order += 1

            # Expand frontier with unvisited neighbors
            if eid in hg._graph:
                neighbors = [
                    n for n in hg._graph.neighbors(eid)
                    if n in hg._entities and n not in seen
                ]
                # Sort by degree for most-important-first
                neighbors.sort(
                    key=lambda n: hg._graph.degree(n) if n in hg._graph else 0,
                    reverse=True)
                frontier.extend(neighbors[:3])

        est_minutes = max(1, len(steps) * 2)

        return GuidedTour(
            title=f"LivingTree Knowledge Architecture Tour",
            steps=steps,
            estimated_minutes=est_minutes,
            target_audience=target,
            summary=(
                f"A {len(steps)}-step guided walkthrough starting from "
                f"the most central entities. Estimated: {est_minutes} minutes."
            ),
        )

    @staticmethod
    def _tour_why(entity_id: str, degree: int, he_count: int) -> str:
        if degree > 10:
            return f"Central hub — {degree} connections, critical for graph connectivity"
        if he_count > 5:
            return f"Knowledge nexus — participates in {he_count} hypergraph relations"
        if degree > 3:
            return f"Important bridge — connects {degree} related concepts"
        return "Foundational concept — understanding this unlocks related knowledge"

    # ═══ Graph Export ═══

    def export_json(self, hypergraph_store=None, path: str = "") -> dict:
        """Export the full graph as committable JSON.

        Understand-Anything analog: the JSON graph format committed
        for team sharing and version control.
        """
        if not hypergraph_store:
            return {}

        data = {
            "version": "1.0",
            "generated_at": time.time(),
            "stats": hypergraph_store.stats(),
            "entities": {},
            "hyperedges": {},
        }

        for eid, entity in hypergraph_store._entities.items():
            data["entities"][eid] = {
                "label": entity.label,
                "type": entity.entity_type,
                "properties": entity.properties,
                "degree": hypergraph_store._graph.degree(eid)
                if eid in hypergraph_store._graph else 0,
            }

        for hid, he in hypergraph_store._hyperedges.items():
            data["hyperedges"][hid] = {
                "relation": he.relation,
                "entities": he.entities,
                "weight": he.weight,
                "precedence": {
                    "before": he.precedence_before[:5],
                    "after": he.precedence_after[:5],
                },
                "source_doc": he.source_doc,
            }

        if path:
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))
            logger.info(f"Graph exported to {path} ({len(data['entities'])} entities)")

        return data

    def import_json(self, path: str, hypergraph_store=None) -> int:
        """Import a JSON graph into the hypergraph store.

        Returns:
            Number of entities imported.
        """
        data = json.loads(Path(path).read_text())
        if not hypergraph_store:
            return 0

        from .hypergraph_store import EntityNode, Hyperedge

        count = 0
        for eid, edata in data.get("entities", {}).items():
            hypergraph_store.add_entity(EntityNode(
                id=eid,
                label=edata.get("label", eid),
                entity_type=edata.get("type", "concept"),
                properties=edata.get("properties", {}),
            ))
            count += 1

        for hid, hdata in data.get("hyperedges", {}).items():
            hypergraph_store.add_hyperedge(Hyperedge(
                id=hid,
                entities=hdata.get("entities", []),
                relation=hdata.get("relation", "unknown"),
                weight=hdata.get("weight", 1.0),
                source_doc=hdata.get("source_doc", ""),
                precedence_before=hdata.get("precedence", {}).get("before", []),
                precedence_after=hdata.get("precedence", {}).get("after", []),
            ))

        logger.info(f"Graph imported: {count} entities, {len(data.get('hyperedges', {}))} edges")
        return count

    # ═══ Stats ═══

    def stats(self) -> dict[str, Any]:
        return {
            "snapshots": len(self._snapshots),
            "diffs_computed": len(self._diffs),
            "store_dir": str(self._store_dir),
            "total_changes_tracked": sum(d.total_changes for d in self._diffs),
        }


# ═══ Singleton ═══

_introspector: GraphIntrospector | None = None


def get_introspector() -> GraphIntrospector:
    global _introspector
    if _introspector is None:
        _introspector = GraphIntrospector()
    return _introspector


__all__ = [
    "GraphIntrospector", "GraphDiff", "ImpactReport", "ImpactPath",
    "GuidedTour", "TourStep", "get_introspector",
]
