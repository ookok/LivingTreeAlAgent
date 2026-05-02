"""
SkillGraph — Compatibility Stub
==================================

功能已被 livingtree.core.memory.store 的 SimpleGraphDB 覆盖。
保留兼容接口供 skill_integration_service 过渡使用。
"""

from typing import Dict, List, Any, Optional


class SkillGraph:
    def __init__(self, **kwargs):
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[tuple] = []

    def add_node(self, node_id: str, label: str, properties: Dict[str, Any] = None):
        self._nodes[node_id] = {"id": node_id, "label": label, "properties": properties or {}}

    def add_edge(self, from_id: str, to_id: str, relation: str = "RELATED_TO"):
        self._edges.append((from_id, to_id, relation))

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self._nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> List[Dict[str, Any]]:
        neighbors = []
        for from_id, to_id, relation in self._edges:
            if from_id == node_id and to_id in self._nodes:
                neighbors.append({"node": self._nodes[to_id], "relation": relation})
            elif to_id == node_id and from_id in self._nodes:
                neighbors.append({"node": self._nodes[from_id], "relation": relation})
        return neighbors

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        results = []
        kw = keyword.lower()
        for node in self._nodes.values():
            if kw in node.get("label", "").lower():
                results.append(node)
        return results

    def count(self) -> int:
        return len(self._nodes)


def create_skill_graph(**kwargs) -> SkillGraph:
    return SkillGraph(**kwargs)


__all__ = ["SkillGraph", "create_skill_graph"]
