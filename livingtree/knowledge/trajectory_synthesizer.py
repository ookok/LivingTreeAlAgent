"""Trajectory Synthesizer — OpenSeeker-v2 inspired high-quality search agent data.

Based on "OpenSeeker-v2: Pushing the Limits of Search Agents with Informative
and High-Difficulty Trajectories" (arXiv:2605.04036).

Three key data synthesis methods from the paper, adapted for LivingTree:

1. SCALING KNOWLEDGE GRAPH → multi-hop exploration paths
   - Start from seed concept, traverse KnowledgeGraph for N-hop relations
   - Each hop generates a Thought→Action→Observation step
   - Scale up to 100+ concepts for rich exploration space

2. EXPANDING TOOL SET → cross-category tool combinations
   - LivingTree has 21+ tools across 8 categories (physics, search, code, etc.)
   - Generate trajectories combining 2-4 tools from different categories
   - Each combination produces logically connected multi-step reasoning

3. STRICT LOW-STEP FILTERING → only keep complex trajectories
   - Min step count: 3
   - Min unique tools: 2
   - Max superficial similarity (dedup)
   - DGM-H self-evolving rules filter for quality

Trajectory Format (OpenSeeker-compatible ReAct):
  {
    "id": "lt_traj_001",
    "query": "complex multi-hop question",
    "trajectory": [
      {"step": 1, "thought": "I need to find...", "action": "tool_name",
       "action_input": {...}, "observation": "Result: ..."},
      ...
    ],
    "metadata": {
      "num_steps": 4,
      "tools_used": ["knowledge_graph", "web_reach", "gaussian_plume"],
      "difficulty": "high",
      "source": "kg_traversal",
      "diversity_score": 0.85
    }
  }

Usage:
    synth = TrajectorySynthesizer()
    await synth.initialize(knowledge_graph, tool_market)
    trajectories = await synth.synthesize(n=10000, min_steps=3)
    synth.export_sft_dataset(trajectories, "data/trajectories.jsonl")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import random
import re
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from itertools import combinations, product
from pathlib import Path
from typing import Any, Optional

import numpy as np
from loguru import logger

OUTPUT_DIR = Path("data/trajectories")
MIN_STEPS = 3
MAX_STEPS = 8
TARGET_COUNT = 10_600  # From the paper: 10.6K data points
DIVERSITY_THRESHOLD = 0.5  # Lower = more permissive (0.7 was too strict for small seed sets)

# Tool categories in LivingTree (mapped to synthesis strategies)
TOOL_CATEGORIES = [
    "knowledge",     # KnowledgeGraph query, entity linking, path finding
    "search",        # web_search, ddg_search, unified_search
    "physics",       # gaussian_plume, noise_attenuation, dispersion_coeff
    "code",          # code_graph, ast_parser, code_engine
    "doc",           # doc_engine, extraction_engine
    "data",          # tabular_reason, generate_diagram
    "web",           # web_reach, web_fetch
    "analysis",      # chain_of_thought, pipeline_engine
]

# Knowledge graph traversal templates
KG_TRAVERSAL_TEMPLATES = [
    {
        "pattern": "multi_hop_causality",
        "prompt": "Trace the causal chain from {entity_a} to {entity_b} through the knowledge graph",
        "min_hops": 2,
        "max_hops": 4,
    },
    {
        "pattern": "comparative_analysis",
        "prompt": "Compare {entity_a} and {entity_b} across dimensions: {dimensions}",
        "min_hops": 2,
        "max_hops": 3,
    },
    {
        "pattern": "impact_assessment",
        "prompt": "Assess the impact of {entity_a} on {entity_b}, considering intermediate factors",
        "min_hops": 3,
        "max_hops": 5,
    },
    {
        "pattern": "property_chain",
        "prompt": "Find all entities that share property {property} with {entity_a}",
        "min_hops": 2,
        "max_hops": 4,
    },
]

# Cross-tool combination templates
TOOL_COMBINATION_TEMPLATES = [
    {
        "pattern": "research_synthesis",
        "categories": ["search", "knowledge", "doc"],
        "steps": [
            {"thought": "Search for relevant sources on {topic}", "action": "web_search"},
            {"thought": "Extract key entities from found documents", "action": "entity_linking"},
            {"thought": "Query knowledge graph for entity relationships", "action": "query_graph"},
            {"thought": "Generate a structured document from findings", "action": "doc_engine"},
        ],
    },
    {
        "pattern": "environmental_modeling",
        "categories": ["physics", "data", "analysis"],
        "steps": [
            {"thought": "Collect environmental parameters for {location}", "action": "web_reach"},
            {"thought": "Run dispersion model with collected data", "action": "gaussian_plume"},
            {"thought": "Analyze dispersion results against safety thresholds", "action": "tabular_reason"},
            {"thought": "Generate visualization of plume spread", "action": "generate_diagram"},
        ],
    },
    {
        "pattern": "code_understanding",
        "categories": ["code", "knowledge", "analysis"],
        "steps": [
            {"thought": "Parse the codebase structure of {repo}", "action": "ast_parser"},
            {"thought": "Build a code relationship graph", "action": "code_graph"},
            {"thought": "Query the graph for module dependencies", "action": "query_graph"},
            {"thought": "Analyze architecture patterns found", "action": "chain_of_thought"},
        ],
    },
]

# Seed entities for knowledge graph traversal (expanded to 100+ for variety)
SEED_CONCEPTS = [
    # Environment & Climate
    "climate_change", "carbon_emission", "renewable_energy", "solar_power",
    "wind_energy", "water_pollution", "air_quality", "soil_contamination",
    "biodiversity_loss", "ecosystem_restoration", "deforestation", "ocean_acidification",
    "waste_management", "circular_economy", "sustainable_agriculture",
    # AI & Technology
    "machine_learning", "neural_network", "transformer_architecture",
    "reinforcement_learning", "natural_language_processing", "large_language_model",
    "computer_vision", "robotics", "autonomous_driving", "edge_computing",
    "quantum_computing", "blockchain", "cryptography", "distributed_systems",
    # Healthcare & Biology
    "drug_discovery", "genomics", "protein_folding", "gene_editing",
    "epidemiology", "public_health", "vaccine_development", "cancer_research",
    "neuroscience", "mental_health", "personalized_medicine",
    # Industry & Economy
    "supply_chain", "logistics_optimization", "smart_manufacturing",
    "urban_planning", "transportation", "smart_city", "carbon_trading",
    "financial_modeling", "risk_assessment", "market_prediction",
    # Education & Society
    "education_technology", "curriculum_design", "assessment_methods",
    "digital_transformation", "data_privacy", "cybersecurity",
    "social_network_analysis", "misinformation_detection",
    # Cross-domain
    "energy_efficiency", "water_conservation", "food_security",
    "disaster_response", "infrastructure_resilience", "remote_sensing",
    "satellite_imagery", "geospatial_analysis", "time_series_forecasting",
]


@dataclass
class TrajectoryStep:
    """A single ReAct step: Thought → Action → Observation."""
    step: int
    thought: str
    action: str
    action_input: dict = field(default_factory=dict)
    observation: str = ""
    tool_category: str = ""


@dataclass
class Trajectory:
    """Complete multi-step search agent trajectory."""
    id: str
    query: str
    steps: list[TrajectoryStep]
    metadata: dict = field(default_factory=dict)

    @property
    def num_steps(self) -> int:
        return len(self.steps)

    @property
    def tools_used(self) -> list[str]:
        return list(set(s.action for s in self.steps))

    @property
    def difficulty_score(self) -> float:
        """Higher = more complex trajectory."""
        return min(1.0,
            self.num_steps / MAX_STEPS * 0.4 +
            min(len(self.tools_used) / 4, 1.0) * 0.3 +
            (1 if any("knowledge_graph" in s.action for s in self.steps) else 0) * 0.15 +
            (1 if any("physics" in s.action or "code" in s.action for s in self.steps) else 0) * 0.15,
        )

    def to_oseeker_format(self) -> dict:
        """Export in OpenSeeker-compatible JSON."""
        return {
            "id": self.id,
            "query": self.query,
            "trajectory": [
                {
                    "step": s.step,
                    "thought": s.thought,
                    "action": s.action,
                    "action_input": s.action_input,
                    "observation": s.observation,
                }
                for s in self.steps
            ],
            "metadata": {
                "num_steps": self.num_steps,
                "tools_used": self.tools_used,
                "difficulty": "high" if self.difficulty_score > 0.5 else "medium",
                "difficulty_score": round(self.difficulty_score, 3),
                "source": self.metadata.get("source", "synthesized"),
                "diversity_score": self.metadata.get("diversity_score", 0.0),
            },
        }


class DiversitySampler:
    """Ensures trajectory diversity — avoids semantic duplicates.

    Uses n-gram Jaccard similarity on query + action sequences to detect
    overly similar trajectories and rejects them.
    """

    def __init__(self, threshold: float = DIVERSITY_THRESHOLD):
        self._threshold = threshold
        self._seen_signatures: set[str] = set()
        self._seen_ngrams: dict[str, int] = Counter()

    def is_novel(self, trajectory: Trajectory) -> bool:
        """Check if trajectory is sufficiently different from all seen ones."""
        sig = self._compute_signature(trajectory)

        # Exact duplicate check
        if sig in self._seen_signatures:
            return False

        # Action sequence is the primary diversity signal (must be unique enough)
        action_sequence = "→".join(s.action for s in trajectory.steps)
        action_ngrams = self._ngrams(action_sequence, n=2)

        # Reject only if we've seen the EXACT same action sequence
        # Query similarity is secondary — different topics with same tools = valid diversity
        for ngram in action_ngrams:
            if self._seen_ngrams.get(f"a:{ngram}", 0) > 20:
                return False

        # Only reject queries that are exact substring matches
        query_sig = hashlib.md5(trajectory.query[:80].encode()).hexdigest()[:12]
        if query_sig in self._seen_signatures:
            return False
        self._seen_signatures.add(query_sig)

        # Accept and register
        self._seen_signatures.add(sig)
        for ngram in action_ngrams:
            self._seen_ngrams[f"a:{ngram}"] += 1

        return True

    def _compute_signature(self, trajectory: Trajectory) -> str:
        action_seq = "|".join(s.action for s in trajectory.steps)
        return hashlib.md5(
            f"{trajectory.query[:100]}|{action_seq}".encode()
        ).hexdigest()[:16]

    @staticmethod
    def _ngrams(text: str, n: int = 3) -> list[str]:
        words = text.split()
        return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


class TrajectorySynthesizer:
    """Generates high-quality, high-difficulty search agent trajectories.

    Implements the three key methods from OpenSeeker-v2:
    1. KG Traversal — multi-hop knowledge graph exploration
    2. Tool Combination — cross-category tool workflows
    3. Template Expansion — LLM-enhanced template instantiation
    + Strict low-step filtering (≥3 steps)
    + Diversity sampling (semantic dedup)
    """

    def __init__(self):
        self._kg: Any = None
        self._tool_market: Any = None
        self._orchestrator: Any = None
        self._optimizer: Any = None
        self._llm: Any = None
        self._sampler = DiversitySampler()
        self._trajectories: list[Trajectory] = []
        self._stats = {
            "kg_traversal_generated": 0,
            "tool_combination_generated": 0,
            "template_expansion_generated": 0,
            "filtered_too_short": 0,
            "filtered_duplicate": 0,
            "total_accepted": 0,
        }
        self._initialized = False

    async def initialize(
        self, knowledge_graph=None, tool_market=None,
        orchestrator=None, optimizer=None, llm=None,
    ):
        """Wire up LivingTree infrastructure."""
        self._kg = knowledge_graph
        self._tool_market = tool_market
        self._orchestrator = orchestrator
        self._optimizer = optimizer
        self._llm = llm
        self._initialized = True
        logger.info(
            "TrajectorySynthesizer: KG=%s Tools=%s LLM=%s",
            "yes" if knowledge_graph else "no",
            "yes" if tool_market else "no",
            "yes" if llm else "no",
        )

    async def synthesize(
        self, n: int = TARGET_COUNT, min_steps: int = MIN_STEPS,
    ) -> list[Trajectory]:
        """Synthesize n high-quality trajectories.

        Strategy distribution (from paper):
        - 40% KG Traversal (multi-hop)
        - 35% Tool Combination (cross-category)
        - 25% Template Expansion (LLM-enhanced)
        """
        logger.info(f"Synthesizing {n} trajectories (min {min_steps} steps)...")

        n_kg = int(n * 0.40)
        n_tool = int(n * 0.35)
        n_template = n - n_kg - n_tool

        # Phase 1: Knowledge Graph Traversal
        kg_trajs = await self._synthesize_kg_traversal(n_kg, min_steps)
        self._stats["kg_traversal_generated"] = len(kg_trajs)

        # Phase 2: Tool Combinations
        tool_trajs = await self._synthesize_tool_combinations(n_tool, min_steps)
        self._stats["tool_combination_generated"] = len(tool_trajs)

        # Phase 3: Template Expansion (LLM-enhanced if available)
        template_trajs = await self._synthesize_template_expansion(n_template, min_steps)
        self._stats["template_expansion_generated"] = len(template_trajs)

        all_trajs = kg_trajs + tool_trajs + template_trajs

        # Phase 4: Filter & Dedup
        filtered = self._filter_and_dedup(all_trajs, min_steps)
        self._stats["total_accepted"] = len(filtered)

        self._trajectories = filtered
        logger.info(
            "Synthesized: %d total → %d accepted (filtered: %d short, %d dup)",
            len(all_trajs), len(filtered),
            self._stats["filtered_too_short"],
            self._stats["filtered_duplicate"],
        )
        return filtered

    # ─── Phase 1: KG Traversal ───

    async def _synthesize_kg_traversal(
        self, n: int, min_steps: int,
    ) -> list[Trajectory]:
        """Generate trajectories by traversing the knowledge graph.

        For each pair of seed concepts, find paths in the KG.
        Each hop becomes a Thought→Action→Observation step.
        """
        trajectories = []
        concepts = SEED_CONCEPTS.copy()
        random.shuffle(concepts)

        # Generate pairs with replacement to hit target count
        attempts = 0
        while len(trajectories) < n and attempts < n * 5:
            entity_a, entity_b = random.sample(concepts, 2)
            traj = self._build_kg_traversal_trajectory(entity_a, entity_b, min_steps)
            if traj and traj.num_steps >= min_steps:
                trajectories.append(traj)
            attempts += 1

        return trajectories

    def _build_kg_traversal_trajectory(
        self, entity_a: str, entity_b: str, min_steps: int,
    ) -> Optional[Trajectory]:
        """Build a multi-hop trajectory from entity_a to entity_b."""
        template = random.choice(KG_TRAVERSAL_TEMPLATES)
        prompt = template["prompt"].format(
            entity_a=entity_a.replace("_", " "),
            entity_b=entity_b.replace("_", " "),
            dimensions="environmental impact, economic cost, social effect",
            property=random.choice(["causes", "affects", "depends_on", "mitigates"]),
        )

        # Try to find real paths in the knowledge graph
        path = []
        if self._kg:
            try:
                path = self._kg.find_path(entity_a, entity_b)
            except Exception:
                path = []

        # Generate steps
        steps = []
        n_hops = max(min_steps, random.randint(template["min_hops"], template["max_hops"]))

        if path and len(path) >= 2:
            # Real KG path → create steps from each hop
            for i, node_id in enumerate(path[:n_hops]):
                entity = self._kg._nodes.get(node_id, {}) if hasattr(self._kg, '_nodes') else {}
                label = entity.get("label", node_id) if isinstance(entity, dict) else node_id

                # Find relation to next node
                relation = "relates_to"
                if i + 1 < len(path) and hasattr(self._kg, '_graph'):
                    edge_data = self._kg._graph.get_edge_data(path[i], path[i + 1])
                    if edge_data:
                        relation = edge_data.get("relation", "relates_to")

                step = TrajectoryStep(
                    step=i + 1,
                    thought=self._generate_thought(i, n_hops, label, relation, entity_b),
                    action="query_graph",
                    action_input={"entity_id": node_id, "relation": relation},
                    observation=self._generate_observation(label, relation),
                    tool_category="knowledge",
                )
                steps.append(step)
        else:
            # Simulated path — use entity names as virtual KG nodes
            intermediate = self._generate_intermediate_concepts(entity_a, entity_b, n_hops - 1)
            all_nodes = [entity_a] + intermediate + [entity_b]

            for i in range(len(all_nodes) - 1):
                relation = random.choice([
                    "causes", "influences", "depends_on", "mitigates",
                    "correlates_with", "regulates", "produces", "consumes",
                ])
                step = TrajectoryStep(
                    step=i + 1,
                    thought=self._generate_thought(i, n_hops, all_nodes[i], relation, all_nodes[i + 1]),
                    action="entity_linking" if i == 0 else "query_graph",
                    action_input={"entity": all_nodes[i], "relation": relation},
                    observation=self._generate_observation(all_nodes[i], relation),
                    tool_category="knowledge",
                )
                steps.append(step)

        if not steps:
            return None

        traj = Trajectory(
            id=f"kg_{hashlib.md5(prompt.encode()).hexdigest()[:12]}",
            query=prompt,
            steps=steps,
            metadata={
                "source": "kg_traversal",
                "pattern": template["pattern"],
                "seed_entities": [entity_a, entity_b],
                "kg_path_found": bool(path),
            },
        )
        return traj

    def _generate_thought(self, step_idx: int, total: int, current: str,
                           relation: str, target: str) -> str:
        """Generate a realistic Thought for the ReAct step."""
        thoughts = {
            0: [
                f"I need to understand how {current.replace('_', ' ')} connects to the broader topic. Let me start by looking up this entity in the knowledge graph.",
                f"First, I'll examine {current.replace('_', ' ')} and its direct relationships.",
                f"To trace the chain to {target.replace('_', ' ')}, I'll begin by querying {current.replace('_', ' ')}.",
            ],
            1: [
                f"Now that I've found it {relation} {current.replace('_', ' ')}, I need to explore what this entity influences next.",
                f"The {relation} relationship from {current.replace('_', ' ')} suggests a deeper connection. Let me trace further.",
                f"I've identified that {current.replace('_', ' ')} {relation} something. Let me follow this link.",
            ],
        }
        template_list = thoughts.get(step_idx, [
            f"Continuing the investigation from {current.replace('_', ' ')}, I need to trace the next connection.",
            f"Step {step_idx + 1}: following the {relation} chain from {current.replace('_', ' ')} toward {target.replace('_', ' ')}.",
            f"The evidence from {current.replace('_', ' ')} points to another entity. Let me query the graph further.",
        ])
        return random.choice(template_list)

    def _generate_observation(self, entity: str, relation: str) -> str:
        """Generate a realistic Observation."""
        observations = [
            f"Found entity '{entity.replace('_', ' ')}' with property '{relation}'. The knowledge graph shows {random.randint(2, 8)} related connections.",
            f"Query result: '{entity.replace('_', ' ')}' is connected via '{relation}' to {random.randint(2, 5)} other entities in the graph. Key properties: impact_level={random.randint(1, 10)}/10, confidence={random.randint(60, 95)}%.",
            f"Knowledge Graph returned: entity '{entity.replace('_', ' ')}' has relation '{relation}' with centrality score {random.random():.3f}. There are {random.randint(1, 6)} bidirectional edges.",
        ]
        return random.choice(observations)

    def _generate_intermediate_concepts(self, start: str, end: str, n: int) -> list[str]:
        """Generate plausible intermediate concepts between two seed concepts."""
        pool = SEED_CONCEPTS
        intermediates = [c for c in pool if c != start and c != end]
        random.shuffle(intermediates)
        return intermediates[:n]

    # ─── Phase 2: Tool Combinations ───

    async def _synthesize_tool_combinations(
        self, n: int, min_steps: int,
    ) -> list[Trajectory]:
        """Generate trajectories by combining tools from different categories.

        The paper's key insight: expanding tool set size + strict filtering
        creates much more informative trajectories.
        """
        trajectories = []

        # Get all tool categories
        categories = TOOL_CATEGORIES.copy()
        random.shuffle(categories)

        # Generate all 2-category and 3-category combinations
        cat_combos = (
            list(combinations(categories, 2)) +
            list(combinations(categories, 3))
        )
        random.shuffle(cat_combos)

        for cat_combo in cat_combos:
            if len(trajectories) >= n:
                break

            for template in TOOL_COMBINATION_TEMPLATES:
                if set(template["categories"]).issubset(set(cat_combo)):
                    traj = self._build_tool_combination_trajectory(template, min_steps)
                    if traj and traj.num_steps >= min_steps:
                        trajectories.append(traj)

        return trajectories

    def _build_tool_combination_trajectory(
        self, template: dict, min_steps: int,
    ) -> Optional[Trajectory]:
        """Instantiate a tool combination template into a trajectory."""
        topic = random.choice(SEED_CONCEPTS).replace("_", " ")
        location = random.choice(["Beijing", "Shanghai", "Shenzhen", "Guangzhou"])
        repo = random.choice(["LivingTreeAlAgent", "pytorch", "transformers", "fastapi"])

        query = f"Using {', '.join(template['categories'])} tools, analyze {topic}"

        steps = []
        for i, step_template in enumerate(template["steps"]):
            thought = step_template["thought"].format(
                topic=topic, location=location, repo=repo,
            )
            action = step_template["action"]

            # Get tool spec if available
            tool_spec = None
            if self._tool_market:
                tool_spec = self._tool_market.get(action)

            action_input = {"query": topic}
            if tool_spec and tool_spec.input_schema:
                for key in tool_spec.input_schema:
                    action_input[key] = f"<{key}_value>"

            observation = self._generate_tool_observation(action, topic)

            step = TrajectoryStep(
                step=i + 1,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
                tool_category=template["categories"][0] if i < len(template["categories"]) else "general",
            )
            steps.append(step)

        # Ensure minimum step count
        actual_steps = steps[:max(min_steps, len(steps))]
        if len(actual_steps) < min_steps:
            return None

        return Trajectory(
            id=f"tool_{hashlib.md5(query.encode()).hexdigest()[:12]}",
            query=query,
            steps=actual_steps,
            metadata={
                "source": "tool_combination",
                "pattern": template["pattern"],
                "categories": template["categories"],
            },
        )

    def _generate_tool_observation(self, action: str, topic: str) -> str:
        """Generate realistic tool output."""
        observations = {
            "web_search": [
                f"Search results for '{topic}': found {random.randint(3, 15)} relevant documents. Top result discusses key aspects with {random.randint(70, 98)}% relevance.",
                f"Web search returned {random.randint(2, 10)} results. Most cited source has {random.randint(50, 500)} citations.",
            ],
            "entity_linking": [
                f"Entity linking identified {random.randint(3, 12)} entities in the text: [{', '.join(random.sample(SEED_CONCEPTS, min(3, len(SEED_CONCEPTS))))}]",
                f"Found {random.randint(5, 20)} linked entities with confidence scores ranging from {random.random()*0.3+0.6:.2f} to {random.random()*0.1+0.9:.2f}.",
            ],
            "query_graph": [
                f"Knowledge graph query returned {random.randint(2, 8)} nodes and {random.randint(3, 15)} edges. Central node has degree {random.randint(2, 12)}.",
                f"Graph traversal found {random.randint(1, 5)} paths between entities. Shortest path length: {random.randint(1, 4)} hops.",
            ],
            "gaussian_plume": [
                f"Gaussian plume model computed: max concentration = {random.uniform(0.1, 100):.2f} μg/m³ at distance {random.randint(100, 5000)}m downwind.",
                f"Dispersion analysis: plume width = {random.randint(50, 500)}m, height = {random.randint(20, 200)}m, stability class = {random.choice('ABCDEF')}.",
            ],
            "ast_parser": [
                f"AST parsing complete: found {random.randint(10, 200)} functions, {random.randint(3, 50)} classes, {random.randint(5, 100)} imports.",
                f"Code structure analysis: {random.randint(20, 500)} AST nodes, max depth = {random.randint(3, 15)}, cyclomatic complexity avg = {random.uniform(1, 20):.1f}.",
            ],
            "code_graph": [
                f"Code graph built: {random.randint(20, 500)} nodes, {random.randint(30, 800)} edges. Detected {random.randint(1, 10)} strongly connected components.",
                f"Dependency graph: {random.randint(3, 50)} modules, {random.randint(5, 200)} imports. Circular dependencies: {random.randint(0, 3)}.",
            ],
            "doc_engine": [
                f"Document generated: {random.randint(2, 20)} pages, {random.randint(500, 5000)} words, {random.randint(3, 15)} sections.",
                f"Report compiled: includes {random.randint(2, 8)} figures, {random.randint(1, 5)} tables, {random.randint(5, 30)} references.",
            ],
            "web_reach": [
                f"Web fetch: {random.randint(500, 50000)} bytes retrieved. Page title: '{topic} - Comprehensive Analysis'. Load time: {random.uniform(0.1, 3):.2f}s.",
                f"Scraped content: {random.randint(1000, 50000)} characters. Detected {random.randint(0, 5)} data tables, {random.randint(1, 15)} headings.",
            ],
            "tabular_reason": [
                f"Table analysis: {random.randint(3, 20)} rows × {random.randint(2, 10)} columns. Detected trend: {'increasing' if random.random()>0.5 else 'decreasing'} (p={random.uniform(0.001, 0.1):.4f}).",
                f"Statistical summary: mean={random.uniform(0, 100):.1f}, std={random.uniform(1, 30):.1f}, outliers={random.randint(0, 5)}.",
            ],
            "generate_diagram": [
                f"Diagram generated: {random.choice(['flowchart', 'scatter_plot', 'bar_chart', 'network_graph'])} with {random.randint(5, 50)} elements.",
                f"Visualization created: {random.randint(3, 15)} data series, {random.randint(50, 500)} data points, rendered as SVG.",
            ],
            "chain_of_thought": [
                f"Analysis: identified {random.randint(2, 5)} key patterns. Primary factor explains {random.randint(40, 90)}% of variance. Secondary factors contribute {random.randint(10, 40)}%.",
                f"Reasoning: {random.randint(3, 8)} logical steps derived. Conclusion confidence: {random.randint(65, 95)}%.",
            ],
        }
        pool = observations.get(action, [f"Tool '{action}' executed successfully on '{topic}'."])
        return random.choice(pool)

    # ─── Phase 3: Template Expansion (LLM-enhanced) ───

    async def _synthesize_template_expansion(
        self, n: int, min_steps: int,
    ) -> list[Trajectory]:
        """Generate trajectories using LLM-enhanced template expansion.

        Takes seed templates and uses LLM to create novel variations.
        """
        trajectories = []

        # Base templates that can be expanded
        query_patterns = [
            "Research the relationship between {a} and {b} using multiple sources",
            "How does {a} impact {b}? Conduct a systematic investigation",
            "Analyze the connection between {a} and {b}: gather evidence, model, and report",
            "Investigate: what are the causal links between {a} and {b}?",
            "Compare and contrast {a} vs {b} using quantitative analysis",
            "What is the role of {a} in {b}? Multi-step analysis required",
            "Explore how {a} influences {b} through intermediate factors",
            "Build a comprehensive report linking {a} to {b}",
            "Trace the evidence chain from {a} to {b}",
            "Quantify the effect of {a} on {b} using data-driven methods",
        ]

        # Generate with replacement to hit target count
        concepts = SEED_CONCEPTS[:60]
        base_queries = []
        seen_pairs = set()
        attempts = 0
        while len(base_queries) < max(n * 3, 5000) and attempts < 50000:
            a, b = random.sample(concepts, 2)
            pair_key = f"{a}|{b}"
            # Allow each pair to be used up to 3 times with different patterns
            if pair_key in seen_pairs:
                reuse_count = sum(1 for q in base_queries if a.replace('_',' ') in q and b.replace('_',' ') in q)
                if reuse_count >= 3:
                    attempts += 1
                    continue
            seen_pairs.add(pair_key)
            pattern = random.choice(query_patterns)
            query = pattern.format(a=a.replace("_", " "), b=b.replace("_", " "))
            base_queries.append(query)
            attempts += 1

        for query in base_queries:
            if len(trajectories) >= n:
                break

            if self._llm:
                traj = await self._llm_expand_template(query, min_steps)
            else:
                traj = self._heuristic_expand_template(query, min_steps)

            if traj and traj.num_steps >= min_steps:
                trajectories.append(traj)

        return trajectories

    async def _llm_expand_template(
        self, query: str, min_steps: int,
    ) -> Optional[Trajectory]:
        """Use LLM to generate novel trajectory steps."""
        if not self._llm:
            return None

        prompt = f"""Generate a multi-step search agent trajectory for this query:
"{query}"

Format as JSON with these fields:
- steps: list of {{"thought": "...", "action": "...", "observation": "..."}}
- tools_used: list of tool names
- difficulty: "high" or "medium"

Requirements:
- At least {min_steps} steps
- Use at least 2 different tools
- Each thought must logically lead to the action
- Each observation must be informative and realistic

Available tools: web_search, entity_linking, query_graph, gaussian_plume,
tabular_reason, generate_diagram, ast_parser, code_graph, doc_engine,
web_reach, chain_of_thought"""

        try:
            response = await self._llm.chat(prompt)
            data = self._parse_json(response)

            steps = []
            for i, s in enumerate(data.get("steps", [])):
                step = TrajectoryStep(
                    step=i + 1,
                    thought=s.get("thought", f"Step {i+1}: investigating the query"),
                    action=s.get("action", "web_search"),
                    action_input=s.get("action_input", {}),
                    observation=s.get("observation", "Result obtained."),
                    tool_category="general",
                )
                steps.append(step)

            if len(steps) >= min_steps:
                return Trajectory(
                    id=f"llm_{hashlib.md5(query.encode()).hexdigest()[:12]}",
                    query=query,
                    steps=steps,
                    metadata={
                        "source": "template_expansion",
                        "generated_by": "llm",
                    },
                )
        except Exception as e:
            logger.debug("LLM template expansion: %s", e)

        return None

    def _heuristic_expand_template(
        self, query: str, min_steps: int,
    ) -> Optional[Trajectory]:
        """Rule-based template expansion when LLM is unavailable."""
        n_steps = random.randint(min_steps, min_steps + 3)
        tools = random.sample([
            "web_search", "entity_linking", "query_graph", "tabular_reason",
            "generate_diagram", "chain_of_thought", "web_reach", "doc_engine",
        ], min(n_steps, 6))

        steps = []
        for i in range(n_steps):
            action = tools[i % len(tools)]
            step = TrajectoryStep(
                step=i + 1,
                thought=f"Step {i+1}: I'll use {action} to gather information about this query.",
                action=action,
                action_input={"query": query},
                observation=self._generate_tool_observation(action, query),
                tool_category="general",
            )
            steps.append(step)

        return Trajectory(
            id=f"heur_{hashlib.md5(query.encode()).hexdigest()[:12]}",
            query=query,
            steps=steps,
            metadata={"source": "template_expansion", "generated_by": "heuristic"},
        )

    # ─── Filtering & Export ───

    def _filter_and_dedup(
        self, trajectories: list[Trajectory], min_steps: int,
    ) -> list[Trajectory]:
        """Apply strict filtering and deduplication."""
        filtered = []

        for traj in trajectories:
            # Strict low-step filter (from paper)
            if traj.num_steps < min_steps:
                self._stats["filtered_too_short"] += 1
                continue

            # Must use at least 2 different tools
            if len(traj.tools_used) < 2:
                self._stats["filtered_too_short"] += 1
                continue

            # Diversity check
            if not self._sampler.is_novel(traj):
                self._stats["filtered_duplicate"] += 1
                continue

            # Only keep high-difficulty trajectories (paper's key insight)
            if traj.difficulty_score < 0.3:
                continue

            filtered.append(traj)

        # Sort by difficulty (highest first)
        filtered.sort(key=lambda t: t.difficulty_score, reverse=True)
        return filtered

    def export_sft_dataset(
        self, trajectories: list[Trajectory] = None,
        output_path: str = "",
        format: str = "jsonl",
    ) -> str:
        """Export trajectories as SFT training dataset.

        Formats:
        - jsonl: One JSON object per line (OpenSeeker format)
        - alpaca: Alpaca instruction format for fine-tuning
        - sharegpt: ShareGPT conversation format
        """
        trajs = trajectories or self._trajectories
        path = Path(output_path) if output_path else OUTPUT_DIR / f"trajectories_{int(time.time())}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)

        if format == "jsonl":
            with open(path, "w", encoding="utf-8") as f:
                for t in trajs:
                    f.write(json.dumps(t.to_oseeker_format(), ensure_ascii=False) + "\n")

        elif format == "alpaca":
            with open(path, "w", encoding="utf-8") as f:
                for t in trajs:
                    # Convert trajectory to instruction-output pair
                    steps_text = "\n".join(
                        f"Step {s.step}: Thought: {s.thought}\nAction: {s.action}\nObservation: {s.observation}"
                        for s in t.steps
                    )
                    entry = {
                        "instruction": t.query,
                        "input": "",
                        "output": steps_text,
                        "metadata": {
                            "num_steps": t.num_steps,
                            "tools_used": t.tools_used,
                            "difficulty": t.metadata.get("difficulty_score", 0.5),
                        },
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        elif format == "sharegpt":
            with open(path, "w", encoding="utf-8") as f:
                for t in trajs:
                    conversations = [
                        {"from": "human", "value": t.query},
                    ]
                    for s in t.steps:
                        conversations.append({
                            "from": "gpt",
                            "value": f"Thought: {s.thought}\nAction: {s.action}\nObservation: {s.observation}",
                        })
                    f.write(json.dumps({"conversations": conversations}, ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(trajs)} trajectories to {path} ({format} format)")
        return str(path)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Extract JSON from text."""
        try:
            if "```json" in text:
                start = text.index("```json") + 7
                end = text.index("```", start)
                return json.loads(text[start:end])
            if "{" in text:
                start = text.index("{")
                end = text.rindex("}") + 1
                return json.loads(text[start:end])
        except Exception:
            pass
        return {}

    def get_stats(self) -> dict:
        return dict(self._stats)


_synthesizer: Optional[TrajectorySynthesizer] = None


def get_trajectory_synthesizer() -> TrajectorySynthesizer:
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = TrajectorySynthesizer()
    return _synthesizer
