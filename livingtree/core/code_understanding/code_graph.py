"""
代码图谱 (Code Graph)

将代码结构转换为图模型：
- 函数/类作为节点
- 调用/继承/导入作为边
- 支持图分析（连通分量、环检测、拓扑排序）
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class NodeType(Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    VARIABLE = "variable"


class EdgeType(Enum):
    CALLS = "calls"
    INHERITS = "inherits"
    IMPORTS = "imports"
    CONTAINS = "contains"


@dataclass
class CodeNode:
    node_id: str
    name: str
    node_type: NodeType
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0


class CodeGraph:

    def __init__(self, name: str = ""):
        self.name = name
        self._nodes: Dict[str, CodeNode] = {}
        self._edges: Dict[str, List[CodeEdge]] = {}

    def add_node(self, node: CodeNode) -> str:
        if node.node_id and node.node_id not in self._nodes:
            self._nodes[node.node_id] = node
            self._edges[node.node_id] = []
            return node.node_id

        node_id = f"node_{uuid.uuid4().hex[:8]}"
        node.node_id = node_id
        self._nodes[node_id] = node
        self._edges[node_id] = []
        return node_id

    def add_edge(self, source_id: str, target_id: str,
                 edge_type: EdgeType, weight: float = 1.0):
        edge = CodeEdge(source_id=source_id, target_id=target_id,
                        edge_type=edge_type, weight=weight)
        if source_id in self._edges:
            self._edges[source_id].append(edge)
        if target_id not in self._edges:
            self._edges[target_id] = []

    def get_node(self, node_id: str) -> Optional[CodeNode]:
        return self._nodes.get(node_id)

    def get_edges(self, node_id: str) -> List[CodeEdge]:
        return self._edges.get(node_id, [])

    def get_outgoing(self, node_id: str) -> List[CodeEdge]:
        return [e for e in self._edges.get(node_id, [])
                if e.source_id == node_id]

    def get_incoming(self, node_id: str) -> List[CodeEdge]:
        incoming = []
        for source_id, edges in self._edges.items():
            for edge in edges:
                if edge.target_id == node_id:
                    incoming.append(edge)
        return incoming

    def find_cycles(self) -> List[List[str]]:
        cycles = []
        visited = set()
        stack = []

        def dfs(node_id: str, path: List[str]):
            if node_id in stack:
                cycle_start = stack.index(node_id)
                cycle = stack[cycle_start:] + [node_id]
                if cycle not in cycles:
                    cycles.append(cycle)
                return
            if node_id in visited:
                return

            visited.add(node_id)
            stack.append(node_id)

            for edge in self._edges.get(node_id, []):
                dfs(edge.target_id, path + [node_id])

            stack.pop()

        for node_id in self._nodes:
            if node_id not in visited:
                dfs(node_id, [])

        return cycles

    def topological_sort(self) -> List[str]:
        in_degree = {node_id: 0 for node_id in self._nodes}
        for edges in self._edges.values():
            for edge in edges:
                if edge.target_id in in_degree:
                    in_degree[edge.target_id] += 1

        queue = [n for n, d in in_degree.items() if d == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            for edge in self._edges.get(node_id, []):
                target = edge.target_id
                if target in in_degree:
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        queue.append(target)

        return result

    def get_connected_components(self) -> List[Set[str]]:
        visited = set()
        components = []

        for node_id in self._nodes:
            if node_id in visited:
                continue

            component = set()
            queue = [node_id]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                for edge in self._edges.get(current, []):
                    if edge.target_id not in visited:
                        queue.append(edge.target_id)
                incoming = self.get_incoming(current)
                for edge in incoming:
                    if edge.source_id not in visited:
                        queue.append(edge.source_id)

            if component:
                components.append(component)

        return components

    def get_node_rankings(self) -> Dict[str, float]:
        rankings = {}

        for node_id in self._nodes:
            outgoing = len(self._edges.get(node_id, []))
            incoming = len(self.get_incoming(node_id))
            rankings[node_id] = incoming + outgoing * 0.5

        return rankings

    def get_stats(self) -> Dict[str, Any]:
        total_edges = sum(len(edges) for edges in self._edges.values())
        cycles = self.find_cycles()
        components = self.get_connected_components()

        return {
            "name": self.name,
            "nodes": len(self._nodes),
            "edges": total_edges,
            "density": (total_edges / max(len(self._nodes) *
                        (len(self._nodes) - 1), 1)),
            "cycles_count": len(cycles),
            "components_count": len(components),
            "node_counts": {
                nt.value: sum(1 for n in self._nodes.values()
                             if n.node_type == nt)
                for nt in NodeType},
        }


__all__ = [
    "NodeType", "EdgeType", "CodeNode", "CodeEdge",
    "CodeGraph",
]
