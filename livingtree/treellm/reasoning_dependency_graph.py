"""ReasoningDependencyGraph — Formal reasoning step dependency analysis.

Based on Tessera (Hu et al., 2026): "kernels within a single application exhibit
diverse resource demands, making them the most suitable granularity for aligning
computation with hardware capabilities."

Tessera maps GPU kernels → optimal GPUs via a Data Dependency Graph (DDG).
We map reasoning steps → optimal LLMs via a Reasoning Dependency Graph (RDG).

Key innovation over StrategicOrchestrator's implicit step dependencies:
  1. Explicit RDG with resource annotations per node
  2. Parallelism detection — which steps can run concurrently
  3. Critical path analysis — which chain determines total latency
  4. Optimal model assignment — kernel-to-GPU style step-to-model mapping
  5. Communication cost — the "data transfer" between model contexts

Architecture:
  RDG (graph of reasoning steps)
    │
  ResourceProfiler (what capabilities each step needs)
    │
  ParallelismDetector (which steps can run concurrently)
    │
  CriticalPathAnalyzer (what chain determines total latency)
    │
  OptimalScheduler (assigns models to steps minimizing cost×latency)

Integration:
  - Replaces StrategicOrchestrator's simple depends_on with formal graph
  - Feeds into ConcurrentStream for pipeline-aware execution
  - Provides detailed resource profiles to HolisticElection

Usage:
    rdg = get_reasoning_graph()
    graph = rdg.build_graph(task_description="Design auth system",
                             steps=[{...}, {...}])
    schedule = rdg.optimal_schedule(graph, available_models=["dp-pro", "dp-flash"])
    # schedule.parallel_groups = [[step1, step2], [step3], [step4]]
    # schedule.assignments = {step1: "dp-flash", step2: "dp-pro", ...}
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


class ResourceType(StrEnum):
    """Resource demands of a reasoning step — analogous to GPU kernel resource types."""
    REASONING = "reasoning"        # Deep logical analysis
    CODE_GEN = "code_gen"          # Code generation
    CODE_REVIEW = "code_review"    # Code review / critique
    SEARCH = "search"              # Information retrieval
    SUMMARIZE = "summarize"        # Summarization / synthesis
    TRANSLATE = "translate"        # Translation
    CREATIVE = "creative"          # Creative generation
    CLASSIFY = "classify"          # Classification / labeling
    VERIFY = "verify"              # Verification / fact-checking


@dataclass
class StepNode:
    """A single node in the Reasoning Dependency Graph.

    Analogous to a GPU kernel in Tessera's DDG — has specific resource
    requirements and data dependencies on other nodes.

    v2.4 — MoDA-Enhanced (arXiv:2603.15619): soft_depends_on enables
    content-dependent routing where a step can partially proceed without
    all upstream steps fully completing. soft_similarity_threshold
    controls how similar an upstream result must be to trigger routing.
    """
    step_id: str
    description: str
    resource_type: ResourceType = ResourceType.REASONING
    estimated_tokens: int = 1000
    estimated_latency_ms: float = 2000.0
    priority: int = 0
    depends_on: list[str] = field(default_factory=list)
    depended_by: list[str] = field(default_factory=list)
    soft_depends_on: list[str] = field(default_factory=list)
    soft_similarity_threshold: float = 0.3
    input_context_tokens: int = 0
    status: str = "pending"
    assigned_model: str = ""
    actual_result: str = ""

    @property
    def criticality(self) -> float:
        return min(1.0, (self.priority * 0.3 + self.estimated_tokens / 5000 * 0.4 +
                         len(self.depended_by) * 0.1 + 0.2))


@dataclass
class ReasoningGraph:
    """Complete Reasoning Dependency Graph for a task.

    The formal structure that enables optimal step-to-model scheduling —
    analogous to Tessera's DDG enabling kernel-to-GPU scheduling.
    """
    task_id: str
    task_description: str = ""
    nodes: dict[str, StepNode] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)  # (from_id, to_id)
    # Analysis results
    parallel_groups: list[list[str]] = field(default_factory=list)  # Waves of parallel steps
    critical_path: list[str] = field(default_factory=list)          # Longest dependency chain
    critical_path_latency_ms: float = 0.0
    total_parallelism: float = 1.0   # avg nodes per wave (higher = more parallel)
    max_depth: int = 0               # Max dependency depth
    created_at: float = field(default_factory=time.time)


@dataclass
class OptimalSchedule:
    """Optimal step-to-model assignment — analogous to Tessera's kernel-to-GPU mapping."""
    graph: ReasoningGraph
    assignments: dict[str, str] = field(default_factory=dict)    # step_id → model
    parallel_groups: list[list[str]] = field(default_factory=list)
    estimated_total_latency_ms: float = 0.0
    estimated_total_cost_yuan: float = 0.0
    estimated_total_tokens: int = 0
    schedule_strategy: str = "balanced"  # cost_optimal, latency_optimal, balanced
    communication_overhead_ms: float = 0.0  # Context transfer cost
    created_at: float = field(default_factory=time.time)


# ═══ Reasoning Dependency Graph Engine ════════════════════════════


class ReasoningDependencyGraph:
    """Formal reasoning dependency analysis and optimal scheduling engine.

    Design: Implements Tessera's four-stage pipeline adapted for LLM orchestration:
      1. Graph Construction: build RDG from task description
      2. Resource Profiling: annotate each step with resource requirements
      3. Parallelism Detection: identify independent step groups (waves)
      4. Optimal Scheduling: assign steps to models minimizing cost×latency

    From Tessera: "extracting precise inter-kernel dependencies to ensure
    correctness, overlapping communication with computation."
    → For us: extracting precise inter-step dependencies, overlapping model
      calls with context pre-loading.
    """

    def __init__(self):
        self._graphs: dict[str, ReasoningGraph] = {}
        self._schedules: dict[str, OptimalSchedule] = {}
        self._stats = {"graphs_built": 0, "schedules_computed": 0}

    # ── Stage 1: Graph Construction ───────────────────────────────

    def build_graph(
        self, task_description: str, steps: list[dict[str, Any]] | None = None,
        auto_decompose: bool = False,
    ) -> ReasoningGraph:
        """Build the Reasoning Dependency Graph from task description.

        Args:
            task_description: Full task description.
            steps: Optional pre-defined steps (from execution planner).
            auto_decompose: If True and no steps provided, auto-decompose.

        Returns:
            ReasoningGraph with fully analyzed dependency structure.
        """
        import hashlib
        task_id = hashlib.md5(
            f"{task_description}{time.time()}".encode()
        ).hexdigest()[:10]

        graph = ReasoningGraph(
            task_id=task_id,
            task_description=task_description,
        )

        # Build nodes
        if steps:
            for s in steps:
                node = StepNode(
                    step_id=s.get("id", f"step_{len(graph.nodes)}"),
                    description=s.get("description", ""),
                    resource_type=self._infer_resource_type(
                        s.get("description", ""),
                        s.get("task_type", "general"),
                    ),
                    estimated_tokens=s.get("estimated_tokens", 1000),
                    priority=s.get("priority", 0),
                    depends_on=s.get("depends_on", []),
                )
                graph.nodes[node.step_id] = node

        elif auto_decompose:
            graph.nodes = self._auto_decompose(task_description)
        else:
            # Single node
            node = StepNode(
                step_id="step_0",
                description=task_description,
                resource_type=ResourceType.REASONING,
            )
            graph.nodes[node.step_id] = node

        # Build edges and reverse edges
        for node in graph.nodes.values():
            for dep_id in node.depends_on:
                if dep_id in graph.nodes:
                    graph.edges.append((dep_id, node.step_id))
                    graph.nodes[dep_id].depended_by.append(node.step_id)
                else:
                    logger.warning(
                        f"RDG: step '{node.step_id}' depends on unknown "
                        f"step '{dep_id}' — ignoring"
                    )

        # Compute input context tokens for each node
        for node in graph.nodes.values():
            node.input_context_tokens = sum(
                graph.nodes[dep_id].estimated_tokens
                for dep_id in node.depends_on
                if dep_id in graph.nodes
            )

        # Stage 2: Resource profiling
        self._profile_resources(graph)

        # Stage 3: Parallelism detection
        graph.parallel_groups = self._detect_parallelism(graph)

        # Stage 4: Critical path analysis
        graph.critical_path, graph.critical_path_latency_ms = (
            self._find_critical_path(graph)
        )
        graph.max_depth = self._compute_max_depth(graph)
        graph.total_parallelism = (
            len(graph.nodes) / max(len(graph.parallel_groups), 1)
        )

        self._graphs[task_id] = graph
        self._stats["graphs_built"] += 1

        logger.info(
            f"RDG: built graph '{task_id}' — {len(graph.nodes)} nodes, "
            f"{len(graph.edges)} edges, {len(graph.parallel_groups)} waves, "
            f"critical_path={graph.critical_path_latency_ms:.0f}ms, "
            f"parallelism={graph.total_parallelism:.1f}x"
        )

        return graph

    # ── Stage 2: Resource Profiling ───────────────────────────────

    @staticmethod
    def _infer_resource_type(description: str, task_type: str) -> ResourceType:
        """Infer what type of reasoning capability a step requires."""
        d = (description or "").lower()
        if task_type == "code":
            if any(k in d for k in ["review", "检查", "审核", "bug", "fix", "修复"]):
                return ResourceType.CODE_REVIEW
            return ResourceType.CODE_GEN
        if task_type == "search":
            return ResourceType.SEARCH
        if any(k in d for k in ["总结", "summary", "概括", "summarize"]):
            return ResourceType.SUMMARIZE
        if any(k in d for k in ["翻译", "translate"]):
            return ResourceType.TRANSLATE
        if any(k in d for k in ["验证", "检查", "verify", "check", "fact"]):
            return ResourceType.VERIFY
        if any(k in d for k in ["创意", "创作", "creative", "generate"]):
            return ResourceType.CREATIVE
        if any(k in d for k in ["分类", "classify", "label"]):
            return ResourceType.CLASSIFY
        return ResourceType.REASONING

    @staticmethod
    def _profile_resources(graph: ReasoningGraph) -> None:
        """Annotate each node with resource characteristics."""
        # Resource-type → capability keywords
        capability_map: dict[ResourceType, list[str]] = {
            ResourceType.REASONING: ["reasoning", "analysis", "deep", "推理"],
            ResourceType.CODE_GEN: ["code", "tool_call", "代码"],
            ResourceType.CODE_REVIEW: ["code", "analysis", "代码"],
            ResourceType.SEARCH: ["search", "knowledge", "搜索"],
            ResourceType.SUMMARIZE: ["chat", "summary", "摘要"],
            ResourceType.TRANSLATE: ["translate", "翻译"],
            ResourceType.CREATIVE: ["chat", "creative", "创意"],
            ResourceType.CLASSIFY: ["classify", "simple", "分类"],
            ResourceType.VERIFY: ["reasoning", "analysis", "fact"],
        }

        for node in graph.nodes.values():
            # Store as metadata for routing
            caps = capability_map.get(node.resource_type, ["general"])
            # Token estimation refinement based on resource type
            if node.estimated_tokens <= 1000:
                type_tokens = {
                    ResourceType.REASONING: 3000,
                    ResourceType.CODE_GEN: 2000,
                    ResourceType.CODE_REVIEW: 1500,
                    ResourceType.SEARCH: 1000,
                    ResourceType.SUMMARIZE: 800,
                    ResourceType.TRANSLATE: 800,
                    ResourceType.CREATIVE: 2000,
                    ResourceType.CLASSIFY: 500,
                    ResourceType.VERIFY: 1000,
                }
                node.estimated_tokens = type_tokens.get(node.resource_type, 1000)

    # ── Stage 3: Parallelism Detection ────────────────────────────

    @staticmethod
    def _detect_parallelism(graph: ReasoningGraph) -> list[list[str]]:
        """Detect which steps can run in parallel (independent waves).

        Uses Kahn's algorithm for topological sorting to find waves of
        independent nodes at each depth level.
        """
        # Compute in-degree for each node
        in_degree: dict[str, int] = {nid: 0 for nid in graph.nodes}
        for from_id, to_id in graph.edges:
            in_degree[to_id] = in_degree.get(to_id, 0) + 1

        # Initialize queue with zero in-degree nodes
        queue: deque[str] = deque(
            nid for nid, deg in in_degree.items() if deg == 0
        )

        waves: list[list[str]] = []
        processed: set[str] = set()

        while queue:
            wave: list[str] = []
            # All nodes currently in queue can run in parallel
            for _ in range(len(queue)):
                node_id = queue.popleft()
                if node_id in processed:
                    continue
                wave.append(node_id)
                processed.add(node_id)

                # Reduce in-degree of dependents
                node = graph.nodes.get(node_id)
                if node:
                    for dep_id in node.depended_by:
                        if dep_id in in_degree:
                            in_degree[dep_id] -= 1
                            if in_degree[dep_id] == 0:
                                queue.append(dep_id)

            if wave:
                waves.append(wave)

        # Any unprocessed nodes → cycle detected, add them as final wave
        remaining = [nid for nid in graph.nodes if nid not in processed]
        if remaining:
            waves.append(remaining)
            logger.warning(
                f"RDG: cycle detected in graph — {len(remaining)} nodes "
                f"added as final wave"
            )

        return waves

    # ── Stage 4: Critical Path Analysis ───────────────────────────

    @staticmethod
    def _find_critical_path(graph: ReasoningGraph) -> tuple[list[str], float]:
        """Find the longest dependency chain — determines minimum total latency.

        From Tessera: the critical path determines the throughput bottleneck.
        Steps NOT on the critical path can be parallelized more aggressively.
        """
        if not graph.nodes:
            return [], 0.0

        # Longest-path DP (DAG: topological order)
        topo_order = []
        in_degree = {nid: 0 for nid in graph.nodes}
        for from_id, to_id in graph.edges:
            in_degree[to_id] = in_degree.get(to_id, 0) + 1

        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        while queue:
            nid = queue.popleft()
            topo_order.append(nid)
            node = graph.nodes.get(nid)
            if node:
                for dep_id in node.depended_by:
                    if dep_id in in_degree:
                        in_degree[dep_id] -= 1
                        if in_degree[dep_id] == 0:
                            queue.append(dep_id)

        # DP: longest path ending at each node
        dist: dict[str, float] = {nid: graph.nodes[nid].estimated_latency_ms
                                   for nid in graph.nodes}
        prev: dict[str, str | None] = {nid: None for nid in graph.nodes}

        for nid in topo_order:
            node = graph.nodes.get(nid)
            if node is None:
                continue
            for dep_id in node.depended_by:
                if dep_id in dist and dep_id in graph.nodes:
                    new_dist = dist[nid] + graph.nodes[dep_id].estimated_latency_ms
                    if new_dist > dist.get(dep_id, 0):
                        dist[dep_id] = new_dist
                        prev[dep_id] = nid

        # Find endpoint with max distance
        if not dist:
            return [], 0.0
        end_id = max(dist, key=dist.get)
        max_latency = dist[end_id]

        # Reconstruct path backwards
        path = []
        current = end_id
        while current:
            path.append(current)
            current = prev.get(current)
        path.reverse()

        return path, max_latency

    @staticmethod
    def _compute_max_depth(graph: ReasoningGraph) -> int:
        """Compute maximum dependency depth."""
        if not graph.nodes:
            return 0
        depths: dict[str, int] = {}
        for nid in graph.nodes:
            node = graph.nodes[nid]
            if not node.depends_on:
                depths[nid] = 0
            else:
                depths[nid] = max(
                    (depths.get(d, 0) for d in node.depends_on if d in depths),
                    default=-1
                ) + 1
        return max(depths.values()) if depths else 0

    # ── Optimal Scheduling ────────────────────────────────────────

    def optimal_schedule(
        self, graph: ReasoningGraph,
        available_models: list[str] | None = None,
        strategy: str = "balanced",
        cost_budget: float = 1.0,
    ) -> OptimalSchedule:
        """Compute optimal step-to-model assignment.

        From Tessera: "policy planner derives workload-aware kernel scheduling
        policies that jointly consider kernel characteristics, communication
        overhead, and load balance."

        Args:
            graph: The constructed RDG.
            available_models: Available model names.
            strategy: "cost_optimal", "latency_optimal", "balanced".
            cost_budget: Maximum cost budget in yuan.

        Returns:
            OptimalSchedule with per-step model assignments.
        """
        schedule = OptimalSchedule(
            graph=graph,
            parallel_groups=graph.parallel_groups,
            schedule_strategy=strategy,
        )

        if not available_models:
            available_models = self._discover_models()

        if not graph.nodes:
            return schedule

        # Model capability → resource type mapping
        model_caps = self._model_capability_map(available_models)

        # Assign models to each node
        total_latency = 0.0
        total_cost = 0.0
        total_tokens = 0

        for wave_idx, wave in enumerate(graph.parallel_groups):
            wave_latency = 0.0  # Max latency in this wave (parallel)

            for step_id in wave:
                node = graph.nodes.get(step_id)
                if not node:
                    continue

                # Score each model for this step
                scores = []
                for model in available_models:
                    cap_score = self._capability_match(
                        model, node.resource_type, model_caps,
                    )
                    cost_score = self._cost_score(model, strategy)
                    latency_score = self._latency_score(model, node.estimated_tokens)

                    if strategy == "cost_optimal":
                        total = cap_score * 0.3 + cost_score * 0.5 + latency_score * 0.2
                    elif strategy == "latency_optimal":
                        total = cap_score * 0.3 + cost_score * 0.1 + latency_score * 0.6
                    else:  # balanced
                        total = cap_score * 0.4 + cost_score * 0.3 + latency_score * 0.3

                    scores.append((model, total))

                # Select best model
                if scores:
                    scores.sort(key=lambda x: -x[1])
                    best_model = scores[0][0]
                    schedule.assignments[step_id] = best_model
                    node.assigned_model = best_model

                    # Estimate cost
                    step_cost = self._estimate_cost(best_model, node.estimated_tokens)
                    total_cost += step_cost
                    total_tokens += node.estimated_tokens

                    # Latency in this wave = max of parallel steps
                    step_latency = node.estimated_latency_ms
                    wave_latency = max(wave_latency, step_latency)

            total_latency += wave_latency

        # Communication overhead: context transfer between waves
        schedule.communication_overhead_ms = (
            len(graph.parallel_groups) * 50.0  # ~50ms per inter-wave context switch
        )

        schedule.estimated_total_latency_ms = total_latency + schedule.communication_overhead_ms
        schedule.estimated_total_cost_yuan = round(min(total_cost, cost_budget), 4)
        schedule.estimated_total_tokens = total_tokens

        self._schedules[graph.task_id] = schedule
        self._stats["schedules_computed"] += 1

        logger.info(
            f"RDG schedule: {len(schedule.assignments)} steps assigned, "
            f"{len(graph.parallel_groups)} waves, "
            f"est.latency={schedule.estimated_total_latency_ms:.0f}ms, "
            f"est.cost=¥{schedule.estimated_total_cost_yuan:.4f}"
        )

        return schedule

    # ── Model Scoring Helpers ─────────────────────────────────────

    @staticmethod
    def _model_capability_map(available_models: list[str]) -> dict[str, list[str]]:
        """Build model → capability keywords map."""
        try:
            from .holistic_election import PROVIDER_CAPABILITIES
            return {
                m: PROVIDER_CAPABILITIES.get(m, ["general"])
                for m in available_models
            }
        except ImportError:
            return {m: ["general"] for m in available_models}

    @staticmethod
    def _capability_match(
        model: str, resource_type: ResourceType,
        model_caps: dict[str, list[str]],
    ) -> float:
        """How well does a model match a resource type?"""
        type_to_keywords: dict[ResourceType, list[str]] = {
            ResourceType.REASONING: ["推理", "reasoning", "分析", "analysis", "deep"],
            ResourceType.CODE_GEN: ["代码", "code", "代码"],
            ResourceType.CODE_REVIEW: ["代码", "code", "分析", "analysis"],
            ResourceType.SEARCH: ["搜索", "search", "知识", "knowledge"],
            ResourceType.SUMMARIZE: ["对话", "chat", "摘要", "summary", "快速", "fast"],
            ResourceType.TRANSLATE: ["翻译", "translate", "对话", "chat"],
            ResourceType.CREATIVE: ["创意", "creative"],
            ResourceType.CLASSIFY: ["分类", "classify", "简单", "simple", "快速", "fast"],
            ResourceType.VERIFY: ["推理", "reasoning", "分析", "analysis"],
        }
        keywords = type_to_keywords.get(resource_type, ["general"])
        caps = model_caps.get(model, ["general"])
        matches = sum(1 for k in keywords if any(k in c.lower() for c in caps))
        return min(1.0, 0.3 + matches * 0.15)

    @staticmethod
    def _cost_score(model: str, strategy: str) -> float:
        """Score a model by cost preference."""
        if strategy == "cost_optimal":
            cheap_keywords = ["flash", "free", "lite", "mini", "small", "turbo", "fast"]
            if any(k in model.lower() for k in cheap_keywords):
                return 1.0
            return 0.3
        elif strategy == "latency_optimal":
            return 0.5  # Don't care about cost
        # balanced
        cheap_keywords = ["flash", "free", "lite", "mini", "small"]
        if any(k in model.lower() for k in cheap_keywords):
            return 0.8
        return 0.4

    @staticmethod
    def _latency_score(model: str, estimated_tokens: int) -> float:
        """Score a model by latency characteristics."""
        fast_keywords = ["flash", "fast", "turbo", "lite", "mini", "small", "quick"]
        if any(k in model.lower() for k in fast_keywords):
            return 0.8
        if estimated_tokens > 3000:
            # Long tasks benefit from pro models (better quality per token)
            return 0.6
        return 0.4

    @staticmethod
    def _estimate_cost(model: str, tokens: int) -> float:
        """Estimate cost for a step."""
        base_cost_per_1k = 0.005  # Default
        cheap_keywords = ["flash", "free", "lite", "mini", "small", "turbo", "fast", "freebuff"]
        pro_keywords = ["pro", "max", "reasoning"]
        if any(k in model.lower() for k in cheap_keywords):
            base_cost_per_1k = 0.001
        elif any(k in model.lower() for k in pro_keywords):
            base_cost_per_1k = 0.02
        return base_cost_per_1k * (tokens / 1000)

    # ── Auto Decomposition ────────────────────────────────────────

    @staticmethod
    def _auto_decompose(task_description: str) -> dict[str, StepNode]:
        """Heuristic auto-decomposition when no steps provided."""
        desc = task_description or "analyze"
        desc_l = desc.lower()
        nodes: dict[str, StepNode] = {}

        # Detect multi-action patterns
        patterns = [
            (["首先", "然后", "最后"], ["定义", "分析", "总结"]),
            (["first", "then", "finally"], ["define", "analyze", "conclude"]),
            (["设计", "实现", "测试"], ["design", "implement", "test"]),
            (["design", "implement", "test"], ["design", "implement", "test"]),
            (["分析", "优化", "部署"], ["analyze", "optimize", "deploy"]),
        ]

        for triggers, actions in patterns:
            if any(t in desc_l for t in triggers):
                for i, action in enumerate(actions):
                    sid = f"auto_step_{i}"
                    deps = [f"auto_step_{i-1}"] if i > 0 else []
                    nodes[sid] = StepNode(
                        step_id=sid,
                        description=f"{action}: {task_description[:100]}",
                        depends_on=deps,
                        resource_type=ResourceType.REASONING if i < len(actions) - 1
                        else ResourceType.SUMMARIZE,
                        priority=len(actions) - i,
                    )
                return nodes

        # Single step
        nodes["auto_step_0"] = StepNode(
            step_id="auto_step_0",
            description=task_description,
            resource_type=ResourceType.REASONING,
        )
        return nodes

    # ── Model Discovery ───────────────────────────────────────────

    @staticmethod
    def _discover_models() -> list[str]:
        try:
            from .holistic_election import PROVIDER_CAPABILITIES
            return list(PROVIDER_CAPABILITIES.keys())
        except ImportError:
            return ["deepseek-pro", "deepseek-flash", "longcat-flash"]

    # ── MoDA Content-Dependent Routing ────────────────────────────

    def compute_soft_dependencies(
        self, graph: ReasoningGraph, similarity_threshold: float = 0.3,
    ) -> dict[str, list[str]]:
        """MoDA soft dependency detection via content similarity.

        Instead of hard depends_on edges, use content similarity to
        discover which upstream steps are likely relevant to each
        downstream step. Steps with similar descriptions are presumed
        to share information flow even without explicit edges.

        Args:
            graph: The ReasoningGraph to analyze.
            similarity_threshold: Minimum word overlap to create a soft edge.

        Returns:
            Dict mapping step_id → list of soft-dependency step_ids.
        """
        soft_edges: dict[str, list[str]] = {}
        node_list = list(graph.nodes.values())
        for node in node_list:
            soft_deps: list[str] = []
            n_words = set(node.description.lower().split())
            for other in node_list:
                if other.step_id == node.step_id:
                    continue
                o_words = set(other.description.lower().split())
                if not n_words or not o_words:
                    continue
                intersect = len(n_words & o_words)
                union = len(n_words | o_words)
                sim = intersect / max(union, 1)
                if sim > similarity_threshold:
                    soft_deps.append(other.step_id)
            if soft_deps:
                soft_edges[node.step_id] = soft_deps
                node.soft_depends_on = soft_deps
                node.soft_similarity_threshold = similarity_threshold
        return soft_edges

    def get_depth_routed_context(
        self, graph: ReasoningGraph, step_id: str, max_tokens: int = 4000,
    ) -> str:
        """MoDA depth-aware context routing for a reasoning step.

        Routes upstream results to the current step based on dependency
        depth: hard dependencies (depends_on) are routed at full weight,
        soft dependencies (similar content) at reduced weight, leveraging
        MoDA's principle of content-aware information preservation.

        Args:
            graph: The ReasoningGraph.
            step_id: Current step to route context to.
            max_tokens: Maximum context tokens to include.

        Returns:
            Routed context string with depth-weighted upstream results.
        """
        node = graph.nodes.get(step_id)
        if not node:
            return ""

        parts: list[str] = []
        token_budget = max_tokens

        hard_deps = [graph.nodes[d] for d in node.depends_on if d in graph.nodes]
        hard_deps.sort(key=lambda n: n.criticality, reverse=True)

        hard_budget = int(token_budget * 0.7)
        for dep in hard_deps:
            if hard_budget <= 0:
                break
            txt = dep.actual_result or dep.description
            allocation = min(hard_budget, min(800, len(txt)))
            parts.append(f"[depth:hard|{dep.step_id}|crit={dep.criticality:.1f}] {txt[:allocation]}")
            hard_budget -= allocation

        soft_deps = [graph.nodes[d] for d in node.soft_depends_on if d in graph.nodes]
        soft_deps.sort(key=lambda n: n.criticality, reverse=True)

        soft_budget = int(token_budget * 0.3)
        for dep in soft_deps:
            if soft_budget <= 0:
                break
            txt = dep.actual_result or dep.description
            allocation = min(soft_budget, min(400, len(txt)))
            parts.append(f"[depth:soft|{dep.step_id}] {txt[:allocation]}")
            soft_budget -= allocation

        return "\n---\n".join(parts) if parts else ""

    # ── Query Methods ─────────────────────────────────────────────

    def get_graph(self, task_id: str) -> ReasoningGraph | None:
        return self._graphs.get(task_id)

    def get_schedule(self, task_id: str) -> OptimalSchedule | None:
        return self._schedules.get(task_id)

    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "active_graphs": len(self._graphs),
            "active_schedules": len(self._schedules),
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_rdg: Optional[ReasoningDependencyGraph] = None
_rdg_lock = threading.Lock()


def get_reasoning_graph() -> ReasoningDependencyGraph:
    global _rdg
    if _rdg is None:
        with _rdg_lock:
            if _rdg is None:
                _rdg = ReasoningDependencyGraph()
    return _rdg


__all__ = [
    "ReasoningDependencyGraph", "ReasoningGraph", "StepNode",
    "OptimalSchedule", "ResourceType",
    "get_reasoning_graph",
]
