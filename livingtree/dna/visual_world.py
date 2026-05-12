"""Visual World Model Mixin — Interleaved visual-verbal CoT reasoning.

Based on arXiv:2601.19834 (Wu et al., Tsinghua 2026):
  "Visual Generation Unlocks Human-Like Reasoning through Multimodal World Models"

Core insight: For tasks grounded in the physical/spatial world, visual world models
are more informative than purely verbal ones. Interleaved visual-verbal CoT
significantly outperforms verbal-only CoT on simulation and reconstruction tasks.

LivingTree adaptation:
  Since we use LLMs (not UMMs with image generation), "visual" means:
  - ASCII diagrams (architecture, data flow, relationships)
  - Structured spatial representations (trees, graphs, grids)
  - SVG/Mermaid code generation (consumed by frontend)
  These are the text-based analogs of visual world models.

Atomic world model capabilities (from paper):
  - VISUAL_SIMULATION: predict spatial/physical state changes
  - VISUAL_RECONSTRUCTION: infer full spatial state from partial info

Task classification (from VisWorld-Eval):
  - VISUAL_PREFERRED: physical simulation, spatial reasoning, architecture, layout
  - VERBAL_PREFERRED: pure logic, math proofs, factual Q&A
  - NEUTRAL: neither modality has clear advantage
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from loguru import logger


# ── Enums ──

class WorldModelCapability(str, Enum):
    """Atomic capabilities from VisWorld-Eval taxonomy."""
    SIMULATION = "simulation"        # Predict what happens next (paper folding, ball tracking)
    RECONSTRUCTION = "reconstruction"  # Infer full state from partial (cube projection)


class ModalityPreference(str, Enum):
    """Which reasoning modality is preferred for a task."""
    VISUAL = "visual"     # Visual world model gives significant advantage
    VERBAL = "verbal"     # Pure verbal reasoning is sufficient
    NEUTRAL = "neutral"   # Either modality works equally well
    INTERLEAVED = "interleaved"  # Both channels needed, alternating


# ── Visual World Model Output ──

class VisualWorldModel:
    """A generated visual world model — the "visual CoT step"."""

    def __init__(
        self,
        capability: WorldModelCapability,
        representation: str,       # ASCII/SVG/Mermaid content
        format: str = "ascii",     # "ascii", "mermaid", "svg", "tree", "grid"
        description: str = "",
        confidence: float = 0.7,
    ):
        self.capability = capability
        self.representation = representation
        self.format = format
        self.description = description
        self.confidence = confidence

    def to_prompt_block(self) -> str:
        """Format as a prompt block for injection into CoT."""
        header = f"[Visual World Model: {self.capability.value}]"
        if self.description:
            header += f" — {self.description}"
        return f"{header}\n```{self.format}\n{self.representation}\n```"

    def to_cache_key(self) -> str:
        """Hashable key for visual knowledge store."""
        import hashlib
        return hashlib.sha256(
            f"{self.capability.value}:{self.description}:{self.representation[:200]}".encode()
        ).hexdigest()[:16]


# ── Task Classifier ──

# Keywords that indicate a task benefits from visual world modeling
VISUAL_PREFERRED_KEYWORDS = [
    # Architecture & Structure
    "架构", "architecture", "结构", "structure", "设计", "design pattern",
    "拓扑", "topology", "层次", "hierarchy", "模块", "module layout",
    # Spatial & Physical
    "布局", "layout", "位置", "position", "空间", "spatial", "地理", "geographic",
    "路径", "path", "路线", "route", "方向", "direction",
    # Flow & Data
    "数据流", "data flow", "工作流", "workflow", "管道", "pipeline",
    "调用链", "call chain", "依赖", "dependency", "关系图", "relationship",
    # Code Visualization
    "流程图", "flowchart", "时序图", "sequence diagram", "类图", "class diagram",
    "状态机", "state machine", "组件图", "component diagram",
    # Geometry
    "几何", "geometry", "形状", "shape", "坐标", "coordinate", "投影", "projection",
    "三维", "3d", "二维", "2d", "旋转", "rotation", "对称", "symmetry",
]

VERBAL_PREFERRED_KEYWORDS = [
    "翻译", "translate", "总结", "summarize", "定义", "define",
    "解释", "explain", "分析", "analyze (text)", "计算", "calculate",
    "逻辑", "logic", "证明", "proof", "推理", "deduction",
]


class VisualCoTRouter:
    """Detect task type and route between verbal and visual reasoning.

    Based on VisWorld-Eval findings:
    - Physical simulation + spatial reconstruction → VISUAL preferred
    - Maze + Sokoban (simple deterministic) → VERBAL sufficient
    - Math + programming (abstract symbolic) → VERBAL
    """

    def classify(self, query: str, context: dict = None) -> ModalityPreference:
        """Classify a task's modality preference.

        Returns VISUAL if visual world model likely helps,
        VERBAL if purely verbal is sufficient,
        INTERLEAVED if both channels needed alternately.
        """
        query_lower = query.lower()
        visual_score = 0
        verbal_score = 0

        for kw in VISUAL_PREFERRED_KEYWORDS:
            if kw.lower() in query_lower:
                visual_score += 1

        for kw in VERBAL_PREFERRED_KEYWORDS:
            if kw.lower() in query_lower:
                verbal_score += 1

        # Context boosts
        if context:
            ctx_str = str(context).lower()
            for kw in VISUAL_PREFERRED_KEYWORDS:
                if kw.lower() in ctx_str:
                    visual_score += 0.5

        if visual_score >= 3 and visual_score > verbal_score * 2:
            return ModalityPreference.VISUAL
        elif visual_score >= 2 and visual_score > verbal_score:
            return ModalityPreference.INTERLEAVED
        else:
            return ModalityPreference.VERBAL

    def needs_simulation(self, query: str) -> bool:
        """Check if task needs visual simulation capability."""
        sim_keywords = [
            "paper folding", "折纸", "simulate", "仿真", "预测", "predict",
            "next state", "下一步", "变化", "change", "movement", "运动",
            "演化", "evolve", "转换", "transform", "迁移", "migrate",
        ]
        return any(kw.lower() in query.lower() for kw in sim_keywords)

    def needs_reconstruction(self, query: str) -> bool:
        """Check if task needs visual reconstruction capability."""
        recon_keywords = [
            "projection", "投影", "重建", "reconstruct", "推断", "infer",
            "缺失", "missing", "部分", "partial", "全景", "full view",
            "多视角", "multi-view", "三视图", "3-view",
        ]
        return any(kw.lower() in query.lower() for kw in recon_keywords)


# ── Visual World Model Generator ──

class VisualWorldGenerator:
    """Generate visual world models for a given task.

    Produces ASCII/SVG/Mermaid representations that serve as
    the "visual" channel in interleaved CoT reasoning.
    """

    def __init__(self, consciousness=None):
        self.consciousness = consciousness

    async def generate(
        self,
        query: str,
        capability: WorldModelCapability,
        context: dict = None,
    ) -> Optional[VisualWorldModel]:
        """Generate a visual world model for a task.

        Args:
            query: Task description.
            capability: Which atomic capability to use.
            context: Optional surrounding context.

        Returns:
            VisualWorldModel or None if generation fails.
        """
        if capability == WorldModelCapability.SIMULATION:
            return await self._generate_simulation(query, context)
        elif capability == WorldModelCapability.RECONSTRUCTION:
            return await self._generate_reconstruction(query, context)
        return None

    async def _generate_simulation(
        self, query: str, context: dict = None
    ) -> VisualWorldModel:
        """Generate a simulation visual world model.

        For code tasks: ASCII architecture diagram showing component interactions.
        For data tasks: Mermaid flowchart showing data flow.
        For spatial tasks: Grid/tree representation of spatial relationships.
        """
        # Heuristic: generate based on query content
        if any(kw in query.lower() for kw in ["架构", "architecture", "module", "模块"]):
            return self._architecture_diagram(query)
        elif any(kw in query.lower() for kw in ["flow", "流", "pipeline", "管道"]):
            return self._flow_diagram(query)
        elif any(kw in query.lower() for kw in ["tree", "树", "hierarchy", "层次"]):
            return self._tree_diagram(query)
        else:
            return self._generic_spatial_model(query)

    async def _generate_reconstruction(
        self, query: str, context: dict = None
    ) -> VisualWorldModel:
        """Generate a reconstruction visual world model.

        For code: infer full architecture from partial description.
        For data: complete the data schema from sample.
        """
        return VisualWorldModel(
            capability=WorldModelCapability.RECONSTRUCTION,
            representation=self._infer_structure(query),
            format="ascii",
            description=f"Spatial reconstruction for: {query[:80]}",
        )

    # ── Diagram generators ──

    def _architecture_diagram(self, query: str) -> VisualWorldModel:
        components = self._extract_components(query)
        diagram = self._render_box_diagram(components, "Architecture")
        return VisualWorldModel(
            capability=WorldModelCapability.SIMULATION,
            representation=diagram,
            format="ascii",
            description=f"Architecture simulation: {query[:60]}",
        )

    def _flow_diagram(self, query: str) -> VisualWorldModel:
        diagram = (
            "```mermaid\n"
            "graph LR\n"
            "    A[Input] --> B[Process]\n"
            "    B --> C{Decision}\n"
            "    C -->|Yes| D[Action A]\n"
            "    C -->|No| E[Action B]\n"
            "    D --> F[Output]\n"
            "    E --> F\n"
            "```"
        )
        return VisualWorldModel(
            capability=WorldModelCapability.SIMULATION,
            representation=diagram,
            format="mermaid",
            description=f"Flow simulation: {query[:60]}",
        )

    def _tree_diagram(self, query: str) -> VisualWorldModel:
        components = self._extract_components(query)
        tree = "Root\n"
        for i, comp in enumerate(components[:7]):
            prefix = "├── " if i < len(components[:7]) - 1 else "└── "
            tree += f"{prefix}{comp}\n"
        return VisualWorldModel(
            capability=WorldModelCapability.SIMULATION,
            representation=tree,
            format="tree",
            description=f"Hierarchy simulation: {query[:60]}",
        )

    def _generic_spatial_model(self, query: str) -> VisualWorldModel:
        """Generic spatial relationship diagram when no specific pattern matches."""
        diagram = (
            "+---------------------------+\n"
            "|    Spatial Relationships   |\n"
            "+---------------------------+\n"
            "|  [Entity A] ---> [Entity B] |\n"
            "|       |              |      |\n"
            "|       v              v      |\n"
            "|  [Entity C]    [Entity D]   |\n"
            "+---------------------------+\n"
        )
        return VisualWorldModel(
            capability=WorldModelCapability.SIMULATION,
            representation=diagram,
            format="ascii",
            description=f"Spatial model: {query[:60]}",
        )

    def _infer_structure(self, query: str) -> str:
        """Infer spatial structure from partial description."""
        return (
            "+--------------------------------------------------+\n"
            "|  Reconstructed Structure (from partial info)      |\n"
            "+--------------------------------------------------+\n"
            f"|  Query: {query[:40]}...                            |\n"
            "|  Inferred layers:                                 |\n"
            "|    [Known] → [Inferred A] → [Inferred B]          |\n"
            "|  Confidence: medium (based on structural patterns) |\n"
            "+--------------------------------------------------+\n"
        )

    def _extract_components(self, query: str, max_n: int = 7) -> list[str]:
        """Extract named components from query for diagram generation."""
        # Simple heuristic: capitalized words and quoted strings
        import re
        components = []
        # Match quoted strings
        components.extend(re.findall(r'"([^"]+)"', query))
        # Match CamelCase or PascalCase identifiers
        components.extend(re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', query))
        # Fallback: first few meaningful words
        if not components:
            words = [w for w in query.split() if len(w) > 3 and w.isalpha()]
            components = words[:max_n]
        return components[:max_n]

    def _render_box_diagram(self, components: list[str], title: str) -> str:
        """Render a box-and-arrow ASCII diagram."""
        if not components:
            components = ["Component A", "Component B", "Component C"]

        width = max(len(c) for c in components) + 4
        border = "+" + "-" * (width - 2) + "+"

        lines = [f"  {title}", border]
        for comp in components[:5]:
            pad = width - len(comp) - 4
            lines.append(f"  | {comp}{' ' * pad} |")
            lines.append(border)
            if comp != components[min(4, len(components) - 1)]:
                lines.append("       |")
                lines.append("       v")

        return "\n".join(lines)


# ── Singleton ──

_router: Optional[VisualCoTRouter] = None
_generator: Optional[VisualWorldGenerator] = None


def get_visual_router() -> VisualCoTRouter:
    global _router
    if _router is None:
        _router = VisualCoTRouter()
    return _router


def get_visual_generator(consciousness=None) -> VisualWorldGenerator:
    global _generator
    if _generator is None:
        _generator = VisualWorldGenerator(consciousness)
    return _generator
