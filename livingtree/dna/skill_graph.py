"""SkillGraph — interconnected skill topology for intelligent routing.

Core insight from Heinrich (arscontexta): Skill Graphs > SKILL.md.
A graph of skills captures relationships that flat file lists cannot:
  - depends_on: tool A requires tool B to function
  - composes: tool A + tool B combine to achieve more
  - specializes: role X is a specialized version of role Y
  - conflicts_with: don't route these together

Used by SkillRouter to make context-aware routing decisions.
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

GRAPH_FILE = Path(".livingtree/skill_graph.json")


@dataclass
class SkillNode:
    name: str
    category: str = ""
    description: str = ""
    enabled: bool = True
    # Relationships (other node names)
    depends_on: list[str] = field(default_factory=list)
    composes_with: list[str] = field(default_factory=list)
    specializes: list[str] = field(default_factory=list)
    conflicts_with: list[str] = field(default_factory=list)
    # Metadata
    priority: int = 0
    cost: float = 0.0  # estimated token cost
    reliability: float = 1.0  # 0-1


class SkillGraph:
    """Directed graph of skills with relationship-aware traversal."""

    def __init__(self):
        self._nodes: dict[str, SkillNode] = {}
        self._adjacency: dict[str, set[str]] = defaultdict(set)  # name → {connected names}

    def add_node(self, node: SkillNode):
        self._nodes[node.name] = node

    def add_edge(self, from_name: str, to_name: str, relation: str = "depends_on"):
        """Connect two nodes with a relationship."""
        if from_name not in self._nodes or to_name not in self._nodes:
            return
        if relation == "depends_on":
            self._nodes[from_name].depends_on.append(to_name)
        elif relation == "composes_with":
            self._nodes[from_name].composes_with.append(to_name)
        elif relation == "specializes":
            self._nodes[from_name].specializes.append(to_name)
        elif relation == "conflicts_with":
            self._nodes[from_name].conflicts_with.append(to_name)
        self._adjacency[from_name].add(to_name)
        self._adjacency[to_name].add(from_name)

    def get_dependencies(self, name: str, recursive: bool = True) -> list[str]:
        """Get all dependencies of a skill node. BFS traversal."""
        node = self._nodes.get(name)
        if not node or not node.depends_on:
            return []

        if not recursive:
            return list(node.depends_on)

        visited = set()
        queue = deque(node.depends_on)
        while queue:
            dep = queue.popleft()
            if dep in visited:
                continue
            visited.add(dep)
            dep_node = self._nodes.get(dep)
            if dep_node:
                for d in dep_node.depends_on:
                    if d not in visited:
                        queue.append(d)
        return list(visited)

    def get_compositions(self, name: str) -> list[str]:
        """Get skills that compose well with this one."""
        node = self._nodes.get(name)
        return list(node.composes_with) if node else []

    def get_conflicts(self, name: str) -> list[str]:
        """Get skills that conflict with this one."""
        node = self._nodes.get(name)
        return list(node.conflicts_with) if node else []

    def get_specializations(self, name: str) -> list[str]:
        """Get more specialized versions of this skill."""
        result = []
        for n in self._nodes.values():
            if name in n.specializes:
                result.append(n.name)
        return result

    def get_neighborhood(self, name: str, depth: int = 2) -> list[tuple[str, int, str]]:
        """BFS: get all connected nodes within depth hops.
        Returns [(name, distance, first_edge_type), ...].
        """
        if name not in self._nodes:
            return []
        visited = {name}
        result = []
        queue = deque([(name, 0)])
        while queue:
            current, dist = queue.popleft()
            if dist >= depth:
                continue
            for neighbor in self._adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    edge_type = self._classify_edge(current, neighbor)
                    result.append((neighbor, dist + 1, edge_type))
                    queue.append((neighbor, dist + 1))
        return result

    def _classify_edge(self, a: str, b: str) -> str:
        a_node = self._nodes.get(a)
        if a_node:
            if b in a_node.depends_on:
                return "depends_on"
            if b in a_node.composes_with:
                return "composes_with"
            if b in a_node.conflicts_with:
                return "conflicts_with"
        b_node = self._nodes.get(b)
        if b_node and a in b_node.specializes:
            return "specializes"
        return "related"

    def find_path(self, from_name: str, to_name: str, max_depth: int = 6) -> list[str] | None:
        """BFS: find shortest path between two skills."""
        if from_name not in self._nodes or to_name not in self._nodes:
            return None
        queue = deque([[from_name]])
        visited = {from_name}
        while queue:
            path = queue.popleft()
            current = path[-1]
            if current == to_name:
                return path
            if len(path) >= max_depth:
                continue
            for neighbor in self._adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return None

    def get_clusters(self) -> dict[str, list[str]]:
        """Group nodes by category into clusters."""
        clusters = defaultdict(list)
        for node in self._nodes.values():
            clusters[node.category].append(node.name)
        return dict(clusters)

    def format_ascii(self, highlight: str = "", depth: int = 2) -> str:
        """Render the skill graph as ASCII art for TUI display."""
        if not self._nodes:
            return "[dim]No skills in graph[/dim]"

        lines = ["## 🕸 Skill Graph", ""]
        clusters = self.get_clusters()

        for cat, names in sorted(clusters.items()):
            lines.append(f"### {cat}")
            for name in sorted(names):
                node = self._nodes[name]
                marker = "★" if name == highlight else "●"
                hl = "bold #58a6ff" if name == highlight else ""
                close_hl = "" if name == highlight else ""

                deps = len(node.depends_on)
                comps = len(node.composes_with)
                extra = ""
                if deps:
                    extra += f" ⬇{deps}"
                if comps:
                    extra += f" ✦{comps}"

                lines.append(f"  {marker} {hl}{name}{close_hl}{extra} [dim]{node.description[:60]}[/dim]")

                # Show neighborhood if highlighted
                if name == highlight:
                    neighbors = self.get_neighborhood(name, depth)
                    for n, d, etype in neighbors:
                        indent = "  " * d
                        eicon = {"depends_on": "⬇", "composes_with": "✦", "conflicts_with": "✗", "specializes": "→"}.get(etype, "·")
                        lines.append(f"{indent}  {eicon} {n}")
            lines.append("")

        return "\n".join(lines)

    def save(self):
        try:
            data = {name: {
                "category": n.category, "description": n.description,
                "depends_on": n.depends_on, "composes_with": n.composes_with,
                "specializes": n.specializes, "conflicts_with": n.conflicts_with,
            } for name, n in self._nodes.items()}
            GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
            GRAPH_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"Save graph: {e}")

    def load(self):
        try:
            if GRAPH_FILE.exists():
                data = json.loads(GRAPH_FILE.read_text())
                for name, d in data.items():
                    self.add_node(SkillNode(
                        name=name, category=d.get("category", ""),
                        description=d.get("description", ""),
                        depends_on=d.get("depends_on", []),
                        composes_with=d.get("composes_with", []),
                        specializes=d.get("specializes", []),
                        conflicts_with=d.get("conflicts_with", []),
                    ))
                return True
        except Exception:
            pass
        return False


# ═══ Default skill graph ═══

def build_default_graph() -> SkillGraph:
    """Build a default skill graph from LivingTree's known tools/roles."""
    g = SkillGraph()

    # ── Physics models ──
    g.add_node(SkillNode("gaussian_plume", "physics", "高斯烟羽大气扩散模型"))
    g.add_node(SkillNode("dispersion_coeff", "physics", "扩散系数计算"))
    g.add_node(SkillNode("noise_attenuation", "physics", "噪声衰减模型"))

    g.add_edge("gaussian_plume", "dispersion_coeff", "depends_on")
    g.add_edge("noise_attenuation", "dispersion_coeff", "composes_with")

    # ── Code tools ──
    g.add_node(SkillNode("build_code_graph", "code", "构建代码知识图谱"))
    g.add_node(SkillNode("search_code", "code", "代码全文搜索"))
    g.add_node(SkillNode("blast_radius", "code", "变更影响分析"))

    g.add_edge("blast_radius", "build_code_graph", "depends_on")
    g.add_edge("search_code", "build_code_graph", "composes_with")

    # ── Knowledge ──
    g.add_node(SkillNode("search_knowledge", "knowledge", "知识库检索"))
    g.add_node(SkillNode("detect_knowledge_gaps", "knowledge", "知识缺口检测"))

    g.add_edge("detect_knowledge_gaps", "search_knowledge", "depends_on")

    # ── Cell training ──
    g.add_node(SkillNode("train_cell", "cell", "AI 细胞训练"))
    g.add_node(SkillNode("drill_train", "cell", "深度训练 (MS-SWIFT)"))
    g.add_node(SkillNode("absorb_codebase", "cell", "吸收代码模式"))

    g.add_edge("drill_train", "train_cell", "specializes")
    g.add_edge("absorb_codebase", "build_code_graph", "depends_on")

    # ── Generation ──
    g.add_node(SkillNode("generate_code", "gen", "AI 代码生成"))
    g.add_node(SkillNode("generate_report", "gen", "工业报告生成"))
    g.add_node(SkillNode("generate_diagram", "gen", "ASCII 图表生成"))

    g.add_edge("generate_report", "generate_code", "composes_with")
    g.add_edge("generate_report", "search_knowledge", "depends_on")

    # ── Search ──
    g.add_node(SkillNode("unified_search", "search", "多引擎聚合搜索"))
    g.add_node(SkillNode("web_fetch", "search", "网页内容抓取"))

    g.add_edge("web_fetch", "unified_search", "composes_with")

    # ── Roles ──
    g.add_node(SkillNode("环评专家", "role", "环境影响评价工程师"))
    g.add_node(SkillNode("代码审查", "role", "代码安全与性能审查"))
    g.add_node(SkillNode("数据分析师", "role", "数据洞察与可视化"))
    g.add_node(SkillNode("全栈工程师", "role", "全栈开发"))
    g.add_node(SkillNode("AI研究员", "role", "AI/ML 研究"))
    g.add_node(SkillNode("技术文档", "role", "技术文档编写"))

    g.add_edge("环评专家", "gaussian_plume", "depends_on")
    g.add_edge("环评专家", "generate_report", "composes_with")
    g.add_edge("数据分析师", "gaussian_plume", "composes_with")
    g.add_edge("全栈工程师", "generate_code", "composes_with")
    g.add_edge("代码审查", "search_code", "depends_on")
    g.add_edge("AI研究员", "drill_train", "composes_with")

    return g


# ═══ Global ═══

_graph: SkillGraph | None = None


def get_skill_graph() -> SkillGraph:
    global _graph
    if _graph is None:
        _graph = build_default_graph()
        if not _graph.load():
            _graph = build_default_graph()
    return _graph
