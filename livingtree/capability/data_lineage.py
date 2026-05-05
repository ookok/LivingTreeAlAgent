"""DataLineage — trace every number, fact, and claim back to its source.

    Like git blame for document data. When user changes one number,
    system traces forward to find all downstream sections that need
    recalculation, and traces backward to find the root cause.

    Lineage entry format:
        {
          id: "sec4.2.1_so2_rate",
          value: 1.2,
          unit: "kg/h",
          source: "sec3.1.2_pollution_source",
          source_value: 1.2,
          derivation: "direct_copy",
          derived_from: ["sec1.3_capacity", "sec3.1.1_process"],
          confidence: 0.92,
          last_verified_by: null,
          change_history: [...]
        }

    Usage:
        dl = get_data_lineage()
        dl.record("sec4.2.1", "so2_rate", 1.2, source="sec3.1.2")
        affected = dl.trace_forward("sec1.3_capacity")  # what depends on this?
        root = dl.trace_backward("sec4.2.1_so2_rate")    # where did this come from?
        dl.propagate("sec1.3_capacity", old=300, new=200)  # update all downstream
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

LINEAGE_FILE = Path(".livingtree/data_lineage.json")


@dataclass
class LineageNode:
    id: str                          # unique: "section_field" e.g. "sec4.2.1_so2_rate"
    section: str                     # which section
    field: str                       # what field name
    value: Any                       # current value
    unit: str = ""
    source: str = ""                 # parent lineage node id
    derivation: str = "direct_copy"  # direct_copy | computed | user_provided | learned | assumed
    derived_from: list[str] = field(default_factory=list)
    confidence: float = 0.5          # 0.0-1.0 how reliable
    description: str = ""
    change_history: list[dict] = field(default_factory=list)
    timestamp: float = 0.0


class DataLineage:
    """Document data lineage tracker with forward/backward tracing."""

    def __init__(self):
        LINEAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._nodes: dict[str, LineageNode] = {}
        self._load()

    def record(
        self,
        section: str,
        field: str,
        value: Any,
        unit: str = "",
        source: str = "",
        derivation: str = "direct_copy",
        derived_from: list[str] | None = None,
        confidence: float = 0.5,
        description: str = "",
    ) -> str:
        """Record a data point with its origin. Returns node id."""
        node_id = f"{section}_{field}".replace(" ", "_").lower()
        node = LineageNode(
            id=node_id, section=section, field=field,
            value=value, unit=unit, source=source,
            derivation=derivation, derived_from=derived_from or [],
            confidence=confidence, description=description,
            timestamp=time.time(),
        )
        # Record change if node already exists
        if node_id in self._nodes:
            old = self._nodes[node_id]
            if old.value != value:
                node.change_history = old.change_history + [{
                    "old_value": old.value, "new_value": value,
                    "timestamp": time.time(),
                }]
        self._nodes[node_id] = node
        self._maybe_save()
        return node_id

    def trace_forward(self, node_id: str) -> list[LineageNode]:
        """Find all nodes that depend on this one (downstream)."""
        result = []
        for node in self._nodes.values():
            if node.source == node_id or node_id in node.derived_from:
                result.append(node)
                # Recursively trace further
                result.extend(self.trace_forward(node.id))
        return result

    def trace_backward(self, node_id: str) -> list[LineageNode]:
        """Find all ancestor nodes this depends on."""
        node = self._nodes.get(node_id)
        if not node:
            return []
        result = []
        visited = set()

        def _trace(nid):
            if nid in visited:
                return
            visited.add(nid)
            n = self._nodes.get(nid)
            if not n:
                return
            result.append(n)
            if n.source:
                _trace(n.source)
            for dep in n.derived_from:
                _trace(dep)

        _trace(node_id)
        return result

    def propagate(self, node_id: str, new_value: Any) -> dict[str, list]:
        """Change a node's value and return all downstream nodes that need update.

        Returns {must_update: [...], should_check: [...], unchanged: [...]}
        """
        if node_id in self._nodes:
            old = self._nodes[node_id].value
            self._nodes[node_id].value = new_value
            self._nodes[node_id].change_history.append({
                "old_value": old, "new_value": new_value, "timestamp": time.time()
            })

        downstream = self.trace_forward(node_id)
        must_update = []
        should_check = []

        for node in downstream:
            if node.derivation == "direct_copy":
                node.value = new_value
                node.change_history.append({
                    "old_value": node.value, "new_value": new_value,
                    "timestamp": time.time(), "reason": f"propagated from {node_id}"
                })
                must_update.append(node)
            elif node.derivation in ("computed", "learned"):
                should_check.append(node)

        self._maybe_save()
        return {"must_update": must_update, "should_check": should_check, "total_affected": len(downstream)}

    def summary(self, section: str = "") -> dict:
        """Get lineage summary for a section or all."""
        nodes = [n for n in self._nodes.values() if not section or n.section == section]
        by_derivation = defaultdict(int)
        by_confidence = {"high": 0, "medium": 0, "low": 0}
        user_provided = 0

        for n in nodes:
            by_derivation[n.derivation] += 1
            if n.confidence >= 0.8:
                by_confidence["high"] += 1
            elif n.confidence >= 0.5:
                by_confidence["medium"] += 1
            else:
                by_confidence["low"] += 1
            if n.derivation == "user_provided":
                user_provided += 1

        return {
            "total_nodes": len(nodes),
            "by_derivation": dict(by_derivation),
            "by_confidence": by_confidence,
            "user_provided_pct": user_provided / max(len(nodes), 1) * 100,
            "leaf_nodes": len([n for n in nodes if not self.trace_forward(n.id)]),
            "root_nodes": len([n for n in nodes if not n.source and not n.derived_from]),
        }

    def _save(self):
        data = {}
        for nid, n in self._nodes.items():
            data[nid] = {
                "id": n.id, "section": n.section, "field": n.field,
                "value": n.value, "unit": n.unit, "source": n.source,
                "derivation": n.derivation, "derived_from": n.derived_from,
                "confidence": n.confidence, "description": n.description,
                "change_history": n.change_history[-10:], "timestamp": n.timestamp,
            }
        LINEAGE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if not LINEAGE_FILE.exists():
            return
        try:
            data = json.loads(LINEAGE_FILE.read_text(encoding="utf-8"))
            for nid, d in data.items():
                self._nodes[nid] = LineageNode(
                    id=d.get("id", ""), section=d.get("section", ""),
                    field=d.get("field", ""), value=d.get("value"),
                    unit=d.get("unit", ""), source=d.get("source", ""),
                    derivation=d.get("derivation", "direct_copy"),
                    derived_from=d.get("derived_from", []),
                    confidence=d.get("confidence", 0.5),
                    description=d.get("description", ""),
                    change_history=d.get("change_history", []),
                    timestamp=d.get("timestamp", 0),
                )
        except Exception:
            pass

    def _maybe_save(self):
        if len(self._nodes) % 20 == 0:
            self._save()


_dl: DataLineage | None = None


def get_data_lineage() -> DataLineage:
    global _dl
    if _dl is None:
        _dl = DataLineage()
    return _dl
