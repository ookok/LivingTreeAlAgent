"""Unified Latent Capability Framework — all agent capabilities as vectors.

Tool descriptions, MCP server manifests, expert role definitions, skill rules,
prompt templates — all represented as latent embeddings in a single space.

What this enables:
  - Tool selection by vector similarity, not keyword matching
  - MCP server auto-discovery: query embedding → matching server capabilities
  - Expert role assignment: task embedding → best-fit role
  - Prompt template retrieval: context embedding → best template
  - Cross-modal capability composition: "find a tool AND an expert role for this task"
  - Evolutionary optimization: ALL capability vectors evolve through SkillDNA

Unified abstraction:
  Capability = embedding vector + type tag + fitness score + metadata
  Same retrieval, same evolution, same store for everything.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# Unified Capability Types
# ═══════════════════════════════════════════════════════

class CapabilityType(str, Enum):
    SKILL = "skill"           # Reasoning/execution rule
    TOOL = "tool"             # Python function / API endpoint
    MCP = "mcp"               # Model Context Protocol server
    ROLE = "role"             # Expert agent role definition
    PROMPT = "prompt"         # Prompt template
    KNOWLEDGE = "knowledge"   # Retrieved knowledge chunk
    VALIDATOR = "validator"   # Quality check rule


@dataclass
class LatentCapability:
    """Unified latent representation for ANY agent capability.

    Tools, MCPs, Roles, Prompts, Skills — all the same thing:
    a semantically meaningful point in capability space.
    """
    id: str
    type: CapabilityType
    embedding: list[float]
    # Lightweight metadata — just enough to instantiate the capability
    name: str = ""
    description: str = ""      # Brief for debugging, NOT used for retrieval
    payload: dict = field(default_factory=dict)  # Tool spec, MCP manifest, role template
    fitness: float = 0.5
    usage_count: int = 0
    generation: int = 0
    parent_ids: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    @property
    def dim(self) -> int:
        return len(self.embedding)

    def to_capability_prompt(self) -> str:
        """Compact LLM injection — minimal tokens, maximal info density."""
        return (
            f"[{self.type.value.upper()}] {self.name} "
            f"f={self.fitness:.2f} use={self.usage_count} "
            f"desc={self.description[:60]}"
        )

    def serialize(self) -> dict:
        return {
            "id": self.id, "type": self.type.value,
            "embedding": self.embedding,
            "name": self.name, "description": self.description,
            "payload": self.payload,
            "fitness": self.fitness, "usage_count": self.usage_count,
            "generation": self.generation, "parent_ids": self.parent_ids,
            "created_at": self.created_at,
        }

    @staticmethod
    def deserialize(data: dict) -> LatentCapability:
        return LatentCapability(**{**data, "type": CapabilityType(data["type"])})


# ═══════════════════════════════════════════════════════
# Capability Graph — all capabilities in one space
# ═══════════════════════════════════════════════════════

@dataclass
class CapabilityEdge:
    source_id: str
    target_id: str
    strength: float = 0.5
    relation: str = "composes"  # composes, specializes, contradicts, requires


class CapabilityGraph:
    """Unified graph for ALL capability types: tools, MCPs, roles, skills, prompts.

    Single retrieval interface. Single evolution pipeline.
    Cross-type composition: task embedding → best tool + best role + best prompt.
    """

    def __init__(self, dim: int = 128):
        self._caps: dict[str, LatentCapability] = {}
        self._edges: dict[str, list[CapabilityEdge]] = defaultdict(list)
        self._by_type: dict[CapabilityType, list[str]] = defaultdict(list)
        self.dim = dim

    # ── Registration ──

    def register(self, cap: LatentCapability) -> None:
        self._caps[cap.id] = cap
        self._by_type[cap.type].append(cap.id)

    def register_tool(self, name: str, description: str, embedding: list[float] = None,
                      tool_spec: dict = None) -> LatentCapability:
        """Register a tool as a capability vector."""
        emb = embedding or self._make_embedding(description)
        cap = LatentCapability(
            id=f"tool_{name}", type=CapabilityType.TOOL,
            embedding=emb, name=name, description=description,
            payload=tool_spec or {},
        )
        self.register(cap)
        return cap

    def register_mcp(self, server_name: str, manifest: dict,
                     embedding: list[float] = None) -> LatentCapability:
        """Register an MCP server as a capability vector."""
        desc = manifest.get("description", server_name)
        emb = embedding or self._make_embedding(
            desc + " " + " ".join(t.get("name", "") for t in manifest.get("tools", []))
        )
        cap = LatentCapability(
            id=f"mcp_{server_name}", type=CapabilityType.MCP,
            embedding=emb, name=server_name, description=desc,
            payload=manifest,
        )
        self.register(cap)
        return cap

    def register_role(self, role_name: str, role_template: str,
                      embedding: list[float] = None) -> LatentCapability:
        """Register an expert role as a capability vector."""
        emb = embedding or self._make_embedding(role_template)
        cap = LatentCapability(
            id=f"role_{role_name}", type=CapabilityType.ROLE,
            embedding=emb, name=role_name, description=role_template[:80],
            payload={"template": role_template},
        )
        self.register(cap)
        return cap

    # ── Cross-Type Retrieval ──

    def query(self, query_embedding: list[float], top_k: int = 5,
              cap_type: CapabilityType = None) -> list[LatentCapability]:
        """Find nearest capabilities of any (or specific) type."""
        candidates = (
            self._by_type.get(cap_type, []) if cap_type
            else list(self._caps.keys())
        )
        if not candidates:
            return []

        scored = [
            (self._cosine_sim(query_embedding, self._caps[cid].embedding), self._caps[cid])
            for cid in candidates if cid in self._caps
        ]
        scored.sort(key=lambda x: -x[0])
        return [cap for _, cap in scored[:top_k]]

    def query_all_types(self, query_embedding: list[float], top_k: int = 3) -> dict:
        """Retrieve best capabilities of EACH type for a task.

        Returns a complete "capability bundle" for the task:
          best tool + best MCP server + best role + best skill + best prompt.
        """
        bundle = {}
        for cap_type in CapabilityType:
            matches = self.query(query_embedding, top_k, cap_type)
            if matches:
                bundle[cap_type.value] = [m.name for m in matches]
        return bundle

    def compose_prompt(self, query_embedding: list[float]) -> str:
        """Build a compact, AI-optimized prompt from all capability types.

        The LLM gets ALL relevant capabilities injected in a minimal format.
        No verbose descriptions — only essential metadata.
        """
        lines = ["[Capability Context — auto-selected by latent similarity]"]

        for cap_type in [CapabilityType.TOOL, CapabilityType.ROLE, CapabilityType.SKILL, CapabilityType.VALIDATOR]:
            matches = self.query(query_embedding, top_k=2, cap_type=cap_type)
            if matches:
                lines.append(f"\n  {cap_type.value.upper()}S:")
                for cap in matches:
                    lines.append(f"    {cap.to_capability_prompt()}")

        return "\n".join(lines)

    # ── Edge Learning ──

    def learn_edge(self, source_id: str, target_id: str, strength: float = 0.5) -> None:
        """Learn a relationship between two capabilities.

        Called when the agent observes: "using tool X and role Y together works well."
        The edge strength grows with repeated co-usage.
        """
        if source_id in self._caps and target_id in self._caps:
            # Find existing edge or create new
            for edge in self._edges.get(source_id, []):
                if edge.target_id == target_id:
                    edge.strength = 0.8 * edge.strength + 0.2 * strength
                    return
            self._edges[source_id].append(
                CapabilityEdge(source_id, target_id, strength, "composes")
            )

    # ── Evolution ──

    def evolve_capabilities(self, n_generations: int = 2) -> int:
        """Evolve ALL capability types through one SkillDNA cycle."""
        evolved = 0
        for cap_type in CapabilityType:
            caps = [self._caps[cid] for cid in self._by_type[cap_type]
                    if self._caps[cid].usage_count > 0]
            if len(caps) >= 5:
                # Tournament select + crossover + mutate
                new_caps = self._evolve_type(caps, n_generations)
                for c in new_caps:
                    self.register(c)
                evolved += len(new_caps)
        return evolved

    def _evolve_type(self, population: list[LatentCapability],
                     generations: int) -> list[LatentCapability]:
        """Single-type genetic evolution."""
        new_caps = []
        population.sort(key=lambda c: -c.fitness)

        for gen in range(generations):
            elite_count = max(2, len(population) // 4)
            gen_pop = population[:elite_count]

            while len(gen_pop) < len(population):
                p1 = random.choice(population[:elite_count])
                p2 = random.choice(population)
                if p1.id == p2.id:
                    continue

                # Crossover
                alpha = random.random()
                child_emb = [
                    alpha * p1.embedding[i] + (1 - alpha) * p2.embedding[i]
                    for i in range(len(p1.embedding))
                ]

                # Mutate
                for i in range(len(child_emb)):
                    if random.random() < 0.05:
                        child_emb[i] += random.gauss(0, 0.05)

                # Normalize
                norm = math.sqrt(sum(x * x for x in child_emb))
                child_emb = [x / max(1e-9, norm) for x in child_emb]

                child = LatentCapability(
                    id=f"{p1.type.value}_ev_{gen}_{len(gen_pop)}",
                    type=p1.type,
                    embedding=child_emb,
                    name=f"{p1.name}-ev{gen}",
                    description=p1.description,
                    payload=p1.payload,
                    fitness=(p1.fitness + p2.fitness) / 2 * random.uniform(0.9, 1.1),
                    generation=p1.generation + 1,
                    parent_ids=[p1.id, p2.id],
                )
                gen_pop.append(child)
                new_caps.append(child)

            population = gen_pop

        return new_caps

    # ── Metrics ──

    @property
    def stats(self) -> dict:
        return {
            "total_capabilities": len(self._caps),
            "by_type": {t.value: len(ids) for t, ids in self._by_type.items()},
            "total_edges": sum(len(e) for e in self._edges.values()),
            "avg_fitness": round(
                sum(c.fitness for c in self._caps.values()) / max(1, len(self._caps)), 3
            ),
        }

    def save(self, path: str = ".livingtree/capability_graph.json") -> None:
        data = {
            "caps": {cid: c.serialize() for cid, c in self._caps.items()},
            "edges": {sid: [{"target": e.target_id, "strength": e.strength,
                             "relation": e.relation} for e in edges]
                      for sid, edges in self._edges.items()},
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

    @staticmethod
    def load(path: str = ".livingtree/capability_graph.json") -> CapabilityGraph:
        g = CapabilityGraph()
        try:
            p = Path(path)
            if p.exists():
                data = json.loads(p.read_text("utf-8"))
                for cid, cdata in data.get("caps", {}).items():
                    g._caps[cid] = LatentCapability.deserialize(cdata)
                    g._by_type[g._caps[cid].type].append(cid)
                for sid, edges in data.get("edges", {}).items():
                    g._edges[sid] = [CapabilityEdge(sid, e["target"], e["strength"], e["relation"])
                                     for e in edges]
        except Exception:
            pass
        return g

    # ── Internal ──

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(a[i] * b[i] for i in range(len(a)))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / max(1e-9, na * nb)

    def _make_embedding(self, text: str) -> list[float]:
        """Quick deterministic pseudo-embedding from text hash."""
        emb = [0.0] * self.dim
        for i, ch in enumerate(text):
            bucket = hash(f"{ch}{i}") % self.dim
            emb[bucket] += 1.0
        norm = math.sqrt(sum(x * x for x in emb))
        return [x / max(1e-9, norm) for x in emb] if norm > 0 else emb


# ═══════════════════════════════════════════════════════
# Bootstrap: Register project capabilities
# ═══════════════════════════════════════════════════════

def bootstrap_capability_graph(dim: int = 128) -> CapabilityGraph:
    """Create a pre-populated capability graph from project tools/roles/skills."""
    g = CapabilityGraph(dim)

    # Register known tools
    tools = {
        "knowledge_search": "Search knowledge base for relevant information",
        "code_analyze": "Analyze code structure and find patterns",
        "web_fetch": "Fetch content from a URL",
        "file_read": "Read file contents from filesystem",
        "skill_apply": "Apply a discovered skill to current task",
    }
    for name, desc in tools.items():
        g.register_tool(name, desc)

    # Register expert roles
    roles = {
        "architect": "Design system architecture, evaluate trade-offs, plan components",
        "reviewer": "Review code quality, find bugs, suggest improvements",
        "researcher": "Search knowledge, synthesize findings, summarize insights",
        "executor": "Execute tasks step by step, handle errors, report results",
    }
    for name, template in roles.items():
        g.register_role(name, template)

    # Register known MCP servers
    mcps = {
        "filesystem": {"description": "File system operations", "tools": [
            {"name": "read_file", "description": "Read file contents"},
            {"name": "write_file", "description": "Write file contents"},
            {"name": "list_directory", "description": "List directory contents"},
        ]},
        "web_search": {"description": "Web search and browsing", "tools": [
            {"name": "search", "description": "Search the web"},
            {"name": "fetch", "description": "Fetch web page content"},
        ]},
    }
    for name, manifest in mcps.items():
        g.register_mcp(name, manifest)

    return g


# ── Singleton ──

_graph: Optional[CapabilityGraph] = None


def get_capability_graph(dim: int = 128) -> CapabilityGraph:
    global _graph
    if _graph is None:
        _graph = bootstrap_capability_graph(dim)
    return _graph
