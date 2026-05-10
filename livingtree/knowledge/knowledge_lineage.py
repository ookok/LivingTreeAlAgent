"""Knowledge Lineage — provenance tracking for all knowledge operations.

Inspired by OpenMetadata's data lineage: tracks where knowledge comes from,
how it transforms through the 12-organ pipeline, and where it propagates.

Records per lineage node:
  - source (ingestion, LLM output, user input, organ processing)
  - target (knowledge node, document, which organ consumed it)
  - operation (create, transform, merge, delete, route)
  - timestamp, organ, model, user

Generates lineage graphs for visual inspection and impact analysis.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

LINEAGE_FILE = Path(".livingtree/lineage.jsonl")
MAX_LINEAGE_NODES = 10000


class NodeType:
    INGESTION = "ingestion"       # file/audio/video pseudo-upload
    LLM_OUTPUT = "llm_output"     # model generated content
    USER_INPUT = "user_input"     # chat message
    ORGAN_ROUTE = "organ_route"   # routed through an organ
    KNOWLEDGE_STORE = "knowledge_store"  # stored in knowledge base
    TRANSFORM = "transform"       # processed/filtered/summarized
    MERGE = "merge"               # combined from multiple sources
    DELETE = "delete"             # removed


@dataclass
class LineageNode:
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    node_type: str = NodeType.ORGAN_ROUTE
    content_preview: str = ""           # first 100 chars
    source_entity: str = ""             # file path, URL, model name
    organ: str = ""                     # which organ processed it
    operation: str = ""                 # what was done
    timestamp: float = field(default_factory=time.time)
    parent_ids: list[str] = field(default_factory=list)
    child_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id, "type": self.node_type,
            "preview": self.content_preview[:100], "source": self.source_entity,
            "organ": self.organ, "operation": self.operation,
            "ts": int(self.timestamp), "parents": self.parent_ids,
            "children": self.child_ids, "meta": self.metadata,
        }


class KnowledgeLineage:
    """Lineage tracker for knowledge provenance.

    Usage:
        lineage = get_lineage()
        node = lineage.record(
            source="inbox/document.pdf", organ="lungs",
            operation="ingest→index", content="...",
            parent_id=None,
        )
        graph = lineage.build_graph(node.node_id, depth=3)
    """

    def __init__(self):
        self._nodes: dict[str, LineageNode] = {}
        self._index: defaultdict[str, list[str]] = defaultdict(list)  # source_entity → node_ids
        self._load()

    def _load(self):
        if LINEAGE_FILE.is_file():
            try:
                lines = LINEAGE_FILE.read_text(errors="replace").strip().split("\n")
                for line in lines[-MAX_LINEAGE_NODES:]:
                    d = __import__("json").loads(line)
                    node = LineageNode(**{k: d.get(k, "") for k in LineageNode.__dataclass_fields__ if k != "node_type"})
                    node.node_type = d.get("type", NodeType.ORGAN_ROUTE)
                    self._nodes[node.node_id] = node
                    self._index[node.source_entity].append(node.node_id)
            except Exception:
                pass

    def _save(self, node: LineageNode):
        try:
            LINEAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(LINEAGE_FILE, "a") as f:
                f.write(__import__("json").dumps(node.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.debug(f"Lineage save: {e}")

    def record(
        self, source: str, organ: str, operation: str,
        content: str = "", parent_id: str = "", node_type: str = "",
        metadata: dict = None,
    ) -> LineageNode:
        """Record a lineage event. Returns the created node."""
        node = LineageNode(
            node_type=node_type or NodeType.ORGAN_ROUTE,
            source_entity=source, organ=organ, operation=operation,
            content_preview=content[:100], metadata=metadata or {},
        )
        if parent_id and parent_id in self._nodes:
            node.parent_ids.append(parent_id)
            self._nodes[parent_id].child_ids.append(node.node_id)

        self._nodes[node.node_id] = node
        self._index[source].append(node.node_id)
        self._save(node)

        if len(self._nodes) > MAX_LINEAGE_NODES:
            self._prune_oldest()

        return node

    def _prune_oldest(self, keep: int = 8000):
        sorted_nodes = sorted(self._nodes.items(), key=lambda x: x[1].timestamp)
        to_remove = sorted_nodes[:len(sorted_nodes) - keep]
        for nid, _ in to_remove:
            self._nodes.pop(nid, None)

    def build_graph(self, node_id: str, depth: int = 5) -> dict:
        """Build upstream + downstream lineage graph from a node."""
        if node_id not in self._nodes:
            return {"nodes": [], "edges": [], "root": node_id}

        visited = set()
        nodes = {}
        edges = []

        def traverse_up(nid: str, d: int):
            if nid in visited or d <= 0 or nid not in self._nodes:
                return
            visited.add(nid)
            node = self._nodes[nid]
            nodes[nid] = node.to_dict()
            for pid in node.parent_ids:
                edges.append({"from": pid, "to": nid, "direction": "upstream"})
                traverse_up(pid, d - 1)

        def traverse_down(nid: str, d: int):
            if nid not in self._nodes:
                return
            node = self._nodes[nid]
            for cid in node.child_ids:
                if cid in visited or cid not in self._nodes:
                    continue
                visited.add(cid)
                child = self._nodes[cid]
                nodes[cid] = child.to_dict()
                edges.append({"from": nid, "to": cid, "direction": "downstream"})
                if d > 0:
                    traverse_down(cid, d - 1)

        traverse_up(node_id, depth)
        traverse_down(node_id, depth)

        return {
            "root": node_id,
            "nodes": list(nodes.values()),
            "edges": edges,
            "total_nodes": len(self._nodes),
        }

    def stats(self) -> dict:
        types = defaultdict(int)
        organs = defaultdict(int)
        for n in self._nodes.values():
            types[n.node_type] += 1
            organs[n.organ] += 1
        return {
            "total_nodes": len(self._nodes),
            "by_type": dict(types),
            "by_organ": dict(organs),
            "roots": len([n for n in self._nodes.values() if not n.parent_ids]),
            "leaves": len([n for n in self._nodes.values() if not n.child_ids]),
        }

    def render_html(self, root_id: str = "") -> str:
        """Render lineage graph as HTML."""
        graph = self.build_graph(root_id, depth=4) if root_id else {"nodes": [], "edges": []}
        st = self.stats()

        node_rows = ""
        for nd in sorted(graph.get("nodes", []), key=lambda x: -x.get("ts", 0))[:20]:
            organ = nd.get("organ", "?")
            source = nd.get("source", "")[:40]
            preview = nd.get("preview", "")[:60]
            node_rows += (
                f'<div style="padding:4px 8px;margin:2px 0;border-left:3px solid var(--accent);font-size:10px">'
                f'<b>{nd.get("type","?")}</b> → {organ} · {nd.get("operation","")}'
                f'<div style="color:var(--dim);font-size:9px">源: {source}</div>'
                f'<div style="color:var(--dim);font-size:9px">{preview}</div></div>'
            )

        return f'''<div class="card">
<h2>🔗 知识血缘 <span style="font-size:10px;color:var(--dim)">— OpenMetadata Lineage 风格</span></h2>
<div style="font-size:9px;color:var(--dim);display:flex;gap:12px;margin:4px 0">
  <span>节点 <b>{st["total_nodes"]}</b></span>
  <span>根 <b>{st["roots"]}</b></span>
  <span>叶 <b>{st["leaves"]}</b></span>
</div>
<div style="max-height:400px;overflow-y:auto">{node_rows or '<p style="color:var(--dim)">暂无血缘数据</p>'}</div>
<div style="font-size:9px;color:var(--dim);margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">
  {" ".join(f'<span>{t}:{c}</span>' for t,c in st.get("by_type",{}).items())}
</div></div>'''


_instance: Optional[KnowledgeLineage] = None


def get_lineage() -> KnowledgeLineage:
    global _instance
    if _instance is None:
        _instance = KnowledgeLineage()
    return _instance
