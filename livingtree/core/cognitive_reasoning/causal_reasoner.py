"""
因果推理器 (Causal Reasoner)

基于因果图模型进行分析推理：
- 构建因果图 (Cause-Effect Graph)
- 原因分析和影响预测
- 干预模拟 (Do-Calculus)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .reasoning_coordinator import ReasoningResult

logger = logging.getLogger(__name__)


@dataclass
class CausalNode:
    name: str
    description: str = ""
    causes: Set[str] = field(default_factory=set)
    effects: Set[str] = field(default_factory=set)
    weight: float = 1.0


@dataclass
class CausalLink:
    source: str
    target: str
    strength: float = 0.5
    type: str = "direct"


class CausalReasoner:

    def __init__(self):
        self._graph: Dict[str, CausalNode] = {}
        self._links: List[CausalLink] = []

    def add_node(self, name: str, description: str = "", causes: List[str] = None,
                 effects: List[str] = None, weight: float = 1.0):
        node = CausalNode(
            name=name, description=description,
            causes=set(causes or []), effects=set(effects or []),
            weight=weight)
        self._graph[name] = node
        for cause in (causes or []):
            link = CausalLink(source=cause, target=name)
            self._links.append(link)

    def add_link(self, source: str, target: str, strength: float = 0.5):
        link = CausalLink(source=source, target=target, strength=strength)
        self._links.append(link)
        if source in self._graph:
            self._graph[source].effects.add(target)
        if target in self._graph:
            self._graph[target].causes.add(source)

    def reason(self, query: str, context: Dict[str, Any] = None) -> ReasoningResult:
        if not self._graph and not self._links:
            return ReasoningResult(
                task_id="causal_default",
                domain=None,
                engine="causal_reasoner",
                conclusion=f"因果图模型未构建，无法进行因果推理: {query[:100]}",
                reasoning_chain=["因果图为空"],
                confidence=0.0)

        cause_analysis = self._analyze_causes(query)
        effect_analysis = self._analyze_effects(query)

        conclusion = "因果推理分析：\n"
        if cause_analysis:
            conclusion += f"\n可能原因：{'; '.join(cause_analysis)}"
        if effect_analysis:
            conclusion += f"\n可能影响：{'; '.join(effect_analysis)}"

        chain = []
        if cause_analysis:
            chain.append(f"反向追溯 {len(cause_analysis)} 个原因")
        if effect_analysis:
            chain.append(f"正向推演 {len(effect_analysis)} 个影响")

        return ReasoningResult(
            task_id="causal_result",
            domain=None,
            engine="causal_reasoner",
            conclusion=conclusion,
            reasoning_chain=chain,
            confidence=0.7 if (cause_analysis or effect_analysis) else 0.2,
            metadata={
                "graph_size": len(self._graph),
                "link_count": len(self._links)})

    def _analyze_causes(self, query: str) -> List[str]:
        causes = []
        query_words = set(query.lower().split())
        for node in self._graph.values():
            node_words = set(
                (node.name + " " + node.description).lower().split())
            if query_words & node_words:
                for cause in node.causes:
                    causes.append(f"{cause} → {node.name}")
        return causes[:5]

    def _analyze_effects(self, query: str) -> List[str]:
        effects = []
        query_words = set(query.lower().split())
        for node in self._graph.values():
            node_words = set(
                (node.name + " " + node.description).lower().split())
            if query_words & node_words:
                for effect in node.effects:
                    effects.append(f"{node.name} → {effect}")
        return effects[:5]

    def _traverse_graph(self, start: str, direction: str = "forward",
                        depth: int = 3) -> List[str]:
        visited = set()
        result = []
        queue = [(start, 0)]

        while queue and depth >= 0:
            current, d = queue.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)
            if d > 0:
                result.append(current)

            if current in self._graph:
                neighbors = (self._graph[current].effects
                            if direction == "forward"
                            else self._graph[current].causes)
                for n in neighbors:
                    queue.append((n, d + 1))
            depth -= 1

        return result

    def get_graph_summary(self) -> Dict[str, Any]:
        return {
            "nodes": len(self._graph),
            "links": len(self._links),
            "node_names": list(self._graph.keys()),
            "density": (len(self._links) / max(len(self._graph) *
                        (len(self._graph) - 1), 1)) if self._graph else 0}


__all__ = ["CausalNode", "CausalLink", "CausalReasoner"]
