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
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
from loguru import logger
from pydantic import BaseModel, Field

try:
    import networkx as nx  # ensure optional availability
except Exception:  # pragma: no cover
    nx = None  # type: ignore


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


__all__ = ["KnowledgeGraph", "Entity", "Triplet"]
