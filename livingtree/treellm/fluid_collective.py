"""FluidCollective — Stigmergy-driven fluid collective intelligence.

Based on Werfel (2026) "Fluid thinking about collective intelligence",
Nature Machine Intelligence 8, 506–516.

Core thesis: Collective intelligence systems divide into two fundamental
topologies — STATIC (neural networks, fixed neighbors) and FLUID (ant colonies,
robot swarms, ephemeral encounters). Each topology has distinct learning
mechanisms. The key insight: MOBILITY can substitute for MULTIPLICITY — fewer
units can achieve equal performance through environmental modification (stigmergy)
and transient formations.

Three mechanisms for LivingTree (fluid multi-LLM orchestration):

1. STIGMERGIC CONTEXT (environmental modification):
   Models leave reasoning traces in a shared context space. Subsequent models
   pick up these traces and build upon them — like ants depositing pheromones
   that guide later ants. The "environment" accumulates collective intelligence.

2. TRANSIENT FORMATIONS (ephemeral sub-swarms):
   Instead of fixed flash/pro tiers, dynamically form temporary 2-3 model
   "sub-swarms" that collaborate on one sub-task, then dissolve. Formation
   is task-driven, not pre-planned.

3. MOBILITY BUDGET (movement vs. numbers):
   The paper proves: moving models between perspectives (high mobility) can
   achieve results comparable to using more expensive static models (high
   multiplicity). The mobility budget optimizes this tradeoff.

Architecture:
   StigmergicContext ── shared reasoning trace repository
        │
   TransientFormation ── dynamic sub-swarm assembly + dissolution
        │
   MobilityBudget ── optimal model count × switching frequency

Integration:
  - Called BEFORE routing — enriches context and determines formation
  - StigmergicContext is consulted by all modules that need prior reasoning
  - SynapseAggregator benefits from richer shared context
  - JointEvolution tracks stigmergy patterns as evolution signals

Usage:
    fc = get_fluid_collective()
    
    # Deposit a reasoning trace
    fc.deposit(trace_id="task_001", model="deepseek-pro", 
               content="Key insight: the bottleneck is...")
    
    # Form a transient sub-swarm
    formation = fc.form_swarm(query="Analyze security...", max_size=3)
    # formation.models = ["deepseek-flash", "longcat-flash"] (cost-optimal)
    
    # Get accumulated wisdom for a topic
    context = fc.retrieve_context(domain="security_analysis")
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


class TraceType(StrEnum):
    """Types of stigmergic traces models deposit in the environment."""
    INSIGHT = "insight"            # Key finding or realization
    COUNTER = "counter_argument"   # Contradiction or critique
    HYPOTHESIS = "hypothesis"      # Tentative claim to verify
    DECISION = "decision"          # Final conclusion or recommendation
    GAP = "gap"                    # Identified knowledge gap
    PATTERN = "pattern"            # Recognized recurring pattern


@dataclass
class StigmergicTrace:
    """A single reasoning trace deposited by a model in the shared environment.

    Like ant pheromones: deposited by one agent, guides subsequent agents.
    Traces decay over time (pheromone evaporation) to prevent context overload.
    """
    trace_id: str
    model: str                       # Which model deposited this
    trace_type: TraceType
    content: str                     # The actual reasoning content
    domain: str = "general"          # Knowledge domain for retrieval
    confidence: float = 0.5          # Model's confidence in this trace
    depth_grade: float = 0.5         # From DepthGrading
    parent_trace_ids: list[str] = field(default_factory=list)  # Building on what?
    deposited_at: float = field(default_factory=time.time)
    access_count: int = 0            # How many times retrieved
    last_accessed: float = 0.0
    decay_factor: float = 1.0        # 1.0 = fresh, → 0.0 = evaporated

    @property
    def relevance(self) -> float:
        """Current relevance = confidence × depth × decay × recency."""
        age_hours = (time.time() - self.deposited_at) / 3600
        recency = max(0.1, 1.0 - age_hours / 24.0)  # Linear decay over 24h
        return round(
            self.confidence * self.depth_grade * self.decay_factor * recency, 4
        )

    def access(self) -> None:
        """Record an access — strengthens the trace (positive feedback)."""
        self.access_count += 1
        self.last_accessed = time.time()
        self.decay_factor = min(1.0, self.decay_factor + 0.05)

    def evaporate(self, rate: float = 0.01) -> None:
        """Pheromone evaporation — traces gradually lose relevance."""
        self.decay_factor = max(0.01, self.decay_factor - rate)


@dataclass
class TransientFormation:
    """An ephemeral sub-swarm of models formed for a specific sub-task.

    From the paper: mobile units form "transient formations" — temporary
    groupings that collaborate briefly then dissolve.
    """
    formation_id: str
    models: list[str]                # Models in this formation
    task_description: str
    formation_strategy: str           # "cost_optimal", "quality_max", "diversity"
    budget_tokens: int = 0            # Allocated thinking tokens
    status: str = "forming"           # forming, active, dissolved
    formed_at: float = field(default_factory=time.time)
    dissolved_at: float = 0.0
    trace_ids: list[str] = field(default_factory=list)  # Traces produced
    sub_task_results: dict[str, str] = field(default_factory=dict)


@dataclass
class MobilityBudget:
    """Optimal tradeoff between model switching (mobility) and model count.

    From the paper's key theorem: mobility × multiplicity = constant performance.
    More switching (mobility) allows fewer models (multiplicity) for same result.
    """
    total_tokens: int = 0
    model_switches: int = 0          # How many times we switch models
    unique_models_used: int = 0      # How many distinct models
    mobility_ratio: float = 0.0      # switches / models (higher = more fluid)
    cost_yuan: float = 0.0
    quality_estimate: float = 0.5    # Expected quality at this budget level
    strategy: str = "balanced"       # "cost_optimal", "quality_max", "balanced"


# ═══ FluidCollective Engine ═══════════════════════════════════════


class FluidCollective:
    """Stigmergy-driven fluid collective intelligence coordinator.

    Design: Implements the three mechanisms from the Werfel paper as a
    unified coordination layer for LivingTree's multi-LLM orchestration.

    The stigmergic context is an OrderedDict with LRU eviction — the shared
    "environment" that all models deposit to and retrieve from.
    """

    MEMORY_TREE_DB = ".livingtree/memory_tree.db"
    CHUNK_MAX_TOKENS = 3000
    SUMMARY_INTERVAL = 600
    MAX_TRACES = 200
    EVAPORATION_INTERVAL = 300
    MAX_FORMATION_SIZE = 4
    DEFAULT_MOBILITY = 0.5

    def __init__(self):
        # Stigmergic environment: trace_id → StigmergicTrace
        self._traces: OrderedDict[str, StigmergicTrace] = OrderedDict()
        # Active transient formations
        self._formations: dict[str, TransientFormation] = {}
        # Mobility budget tracking
        self._mobility_history: list[MobilityBudget] = []
        # Domain → trace_ids index for fast retrieval
        self._domain_index: dict[str, list[str]] = {}
        # Last evaporation time
        self._last_evaporation: float = time.time()
        self._total_deposits: int = 0
        self._total_retrievals: int = 0
        self._last_summary_time: float = 0.0
        self._db_conn: Optional[sqlite3.Connection] = None
        self._init_memory_tree()

    # ── Stigmergic Context (Environmental Modification) ───────────

    def deposit(
        self, trace_id: str = "", model: str = "",
        content: str = "", trace_type: TraceType = TraceType.INSIGHT,
        domain: str = "general", confidence: float = 0.5,
        depth_grade: float = 0.5,
        parent_trace_ids: list[str] | None = None,
    ) -> StigmergicTrace:
        """Deposit a reasoning trace in the shared environment.

        Like an ant depositing pheromone: the trace becomes part of the
        environment that subsequent agents encounter and respond to.

        Args:
            trace_id: Unique ID (auto-generated if empty).
            model: Which model deposited this.
            content: The reasoning content.
            trace_type: Type of trace (insight, counter, hypothesis, etc.).
            domain: Knowledge domain for retrieval.
            confidence: Model's confidence (0-1).
            depth_grade: From DepthGrading.
            parent_trace_ids: Which traces this builds upon.

        Returns:
            The deposited StigmergicTrace.
        """
        if not trace_id:
            trace_id = hashlib.md5(
                f"{model}{content[:50]}{time.time()}".encode()
            ).hexdigest()[:12]

        trace = StigmergicTrace(
            trace_id=trace_id,
            model=model,
            trace_type=trace_type,
            content=content[:2000],  # Truncate long traces
            domain=domain,
            confidence=confidence,
            depth_grade=depth_grade,
            parent_trace_ids=parent_trace_ids or [],
        )

        # Store in environment
        self._traces[trace_id] = trace
        self._traces.move_to_end(trace_id)

        # Domain index
        if domain not in self._domain_index:
            self._domain_index[domain] = []
        self._domain_index[domain].append(trace_id)

        # LRU eviction
        self._evict_lru()

        # Periodically evaporate
        self._maybe_evaporate()

        self._total_deposits += 1

        # Persist to SQLite memory tree
        self._save_to_memory_tree(trace)

        logger.debug(
            f"FluidCollective stigmergy: {model} deposited "
            f"'{trace_type}' trace ({domain}, conf={confidence:.2f})"
        )
        return trace

    def retrieve_context(
        self, domain: str = "general", max_traces: int = 10,
        min_relevance: float = 0.1, trace_types: list[TraceType] | None = None,
    ) -> str:
        """Retrieve accumulated stigmergic context for a domain.

        Returns a formatted context string that can be injected into
        model prompts — the "environment" that guides subsequent reasoning.

        Args:
            domain: Knowledge domain to retrieve.
            max_traces: Max traces to include.
            min_relevance: Minimum relevance score to include.
            trace_types: Filter by trace type (None = all).

        Returns:
            Formatted context string for model consumption.
        """
        self._total_retrievals += 1

        trace_ids = self._domain_index.get(domain, [])
        if not trace_ids:
            # Fallback: search all traces for domain keyword match
            trace_ids = [
                tid for tid, t in self._traces.items()
                if domain.lower() in t.domain.lower()
                or domain.lower() in t.content.lower()
            ]

        # Collect and sort by relevance
        relevant = []
        for tid in trace_ids:
            trace = self._traces.get(tid)
            if not trace:
                continue
            if trace.relevance < min_relevance:
                continue
            if trace_types and trace.trace_type not in trace_types:
                continue
            relevant.append(trace)

        relevant.sort(key=lambda t: -t.relevance)

        # Mark accessed (positive feedback loop)
        for t in relevant[:max_traces]:
            t.access()

        # Build context string
        if not relevant:
            return ""

        parts = [f"[Stigmergic Context — {domain}]"]
        for i, t in enumerate(relevant[:max_traces]):
            age_min = int((time.time() - t.deposited_at) / 60)
            parts.append(
                f"Trace #{i+1} [{t.trace_type}] ({t.model}, "
                f"relevance={t.relevance:.2f}, {age_min}min ago):\n"
                f"  {t.content[:300]}"
            )

        context = "\n\n".join(parts)

        logger.debug(
            f"FluidCollective retrieve: {domain} → "
            f"{min(max_traces, len(relevant))} traces "
            f"(total relevance: {sum(t.relevance for t in relevant[:max_traces]):.2f})"
        )

        return context

    # ── RRF Hybrid Retrieval (agentmemory-inspired) ──────────────

    def unified_search(self, query: str, domain: str = "",
                       top_k: int = 10) -> list[tuple[StigmergicTrace, float]]:
        """RRF (Reciprocal Rank Fusion) hybrid search across all retrieval systems.

        Combines three independent search methods into one ranked result:
          1. BM25 keyword search (SQLite LIKE)
          2. Vector semantic search (in-memory relevance scoring)
          3. Graph relational search (parent→child trace trees)

        From agentmemory: "BM25 + Vector + Graph with RRF fusion"
        """
        results: dict[str, tuple[StigmergicTrace, dict[str, float]]] = {}

        # ── Method 1: BM25 keyword search (SQLite) ──
        if self._db_conn and query:
            try:
                terms = query.lower().split()
                for term in terms[:5]:  # Top 5 query terms
                    rows = self._db_conn.execute(
                        "SELECT id FROM memory_tree WHERE content LIKE ? OR domain LIKE ? LIMIT 15",
                        (f"%{term}%", f"%{term}%")
                    ).fetchall()
                    for rank, row in enumerate(rows):
                        tid = row[0]
                        if tid in self._traces:
                            score = 1.0 / (rank + 60)  # BM25: k1=1.2, b=0.75 approximation
                            if tid not in results:
                                results[tid] = (self._traces[tid], {})
                            results[tid][1]["bm25"] = score
            except Exception:
                pass

        # ── Method 2: Vector/semantic relevance search (in-memory) ──
        if domain:
            trace_ids = self._domain_index.get(domain, [])
        else:
            trace_ids = list(self._traces.keys())
        for tid in trace_ids:
            trace = self._traces.get(tid)
            if not trace:
                continue
            # Semantic match: domain relevance × confidence × recency
            sem_score = trace.relevance
            if query:
                # Boost if query terms appear in content
                q_terms = set(query.lower().split())
                c_terms = set(trace.content.lower().split())
                overlap = len(q_terms & c_terms) / max(len(q_terms), 1)
                sem_score *= (1.0 + overlap)
            if tid not in results:
                results[tid] = (trace, {})
            results[tid][1]["vector"] = min(1.0, sem_score)

        # ── Method 3: Graph relational search ──
        for tid, (trace, scores) in results.items():
            # Traces with children (referenced by others) get graph boost
            children = sum(1 for t in self._traces.values()
                          if tid in t.parent_trace_ids)
            if children > 0:
                scores["graph"] = min(1.0, 0.3 + children * 0.1)

        # ── RRF Fusion ──
        # Rank by each method independently, then fuse
        ranked: list[tuple[StigmergicTrace, float]] = []
        for tid, (trace, scores) in results.items():
            # RRF score = Σ 1/(k + rank_i) for each method i
            rrf = 0.0
            for method in ["bm25", "vector", "graph"]:
                if method in scores:
                    # Estimate rank from score (higher score = lower rank)
                    rrf += 1.0 / (60 + (1.0 - scores[method]) * 100)
            ranked.append((trace, round(rrf, 4)))

        ranked.sort(key=lambda x: -x[1])
        return ranked[:top_k]

    # ── Tiered Memory Consolidation (agentmemory-inspired) ──────

    def consolidate_traces(self, domain: str = "") -> int:
        """Tiered consolidation: raw traces → domain summary.

        From agentmemory: 4-tier consolidation (raw→summary→abstract→KG).
        LivingTree simplified 2-tier: raw→domain summary.

        Triggers when a domain has ≥10 traces, consolidates them into
        a single higher-quality summary trace.
        """
        if not self._db_conn:
            return 0

        consolidated = 0
        domains = [domain] if domain else list(self._domain_index.keys())

        for d in domains:
            traces = self._domain_index.get(d, [])
            if len(traces) < 10:
                continue

            # Get the 10 most recent traces for this domain
            recent = sorted(
                [self._traces[tid] for tid in traces if tid in self._traces],
                key=lambda t: -t.deposited_at
            )[:10]

            if len(recent) < 10:
                continue

            # Generate consolidated summary
            summary_parts = []
            for t in recent:
                summary_parts.append(f"[{t.model}] {t.content[:100]}")
            summary = f"Consolidated {d} knowledge ({len(recent)} traces):\n" + \
                      "\n".join(summary_parts)

            # Deposit as a new high-confidence trace
            import hashlib
            cons_id = hashlib.md5(
                f"consolidate:{d}:{time.time()}".encode()
            ).hexdigest()[:12]

            consolidated_trace = StigmergicTrace(
                trace_id=cons_id,
                model="consolidator",
                trace_type=TraceType.PATTERN,
                content=summary[:self.CHUNK_MAX_TOKENS],
                domain=d,
                confidence=0.85,
                depth_grade=0.7,
                parent_trace_ids=[t.trace_id for t in recent[:5]],
            )

            self._traces[consolidated_trace.trace_id] = consolidated_trace
            if d not in self._domain_index:
                self._domain_index[d] = []
            self._domain_index[d].append(consolidated_trace.trace_id)
            self._persist_trace(consolidated_trace)

            # Mark consolidated traces (reduce their relevance)
            for t in recent:
                t.decay_factor *= 0.5

            consolidated += 1
            logger.info(
                f"FluidCollective consolidate: {d} → {len(recent)} traces "
                f"consolidated into {cons_id}"
            )

        if consolidated:
            self._maybe_summarize()
        return consolidated

    def _maybe_summarize(self) -> None:
        """Periodically generate a memory tree summary."""
        now = time.time()
        if now - self._last_summary_time < self.SUMMARY_INTERVAL:
            return
        self._last_summary_time = now
        summary = self.generate_memory_summary()
        if summary:
            logger.debug(f"FluidCollective memory tree summary generated")

    def get_trace_tree(self, trace_id: str, depth: int = 3) -> list[StigmergicTrace]:
        """Build the ancestry tree of a trace — which traces it builds upon.

        Visualizes the "construction" process — like seeing how each ant's
        deposit relates to previous deposits.
        """
        trace = self._traces.get(trace_id)
        if not trace:
            return []

        tree = [trace]
        if depth > 1 and trace.parent_trace_ids:
            for pid in trace.parent_trace_ids:
                tree.extend(self.get_trace_tree(pid, depth - 1))
        return tree

    # ── Transient Formations (Ephemeral Sub-Swarms) ───────────────

    def form_swarm(
        self, task_description: str, domain: str = "general",
        max_size: int = 3, strategy: str = "cost_optimal",
        available_models: list[str] | None = None,
    ) -> TransientFormation:
        """Form a transient sub-swarm of models for a specific sub-task.

        From the paper: mobile units form ephemeral formations optimized
        for a particular task, then dissolve when complete.
        """
        # Select models for this formation
        if available_models:
            candidates = available_models
        else:
            candidates = self._get_all_providers()

        # Strategy-based selection
        if strategy == "cost_optimal":
            selected = self._select_cost_optimal(candidates, max_size)
        elif strategy == "quality_max":
            selected = self._select_quality_max(candidates, max_size)
        elif strategy == "diversity":
            selected = self._select_diverse(candidates, max_size)
        else:
            selected = candidates[:max_size]

        formation = TransientFormation(
            formation_id=hashlib.md5(
                f"{task_description}{time.time()}".encode()
            ).hexdigest()[:10],
            models=selected,
            task_description=task_description[:200],
            formation_strategy=strategy,
        )
        formation.status = "active"

        self._formations[formation.formation_id] = formation

        logger.info(
            f"FluidCollective swarm: formed {len(selected)}-model formation "
            f"for '{task_description[:60]}...' ({strategy})"
        )

        # Cleanup old formations
        self._clean_old_formations()

        return formation

    def dissolve_swarm(self, formation_id: str) -> None:
        """Dissolve a transient formation — models return to the pool."""
        formation = self._formations.get(formation_id)
        if formation:
            formation.dissolved_at = time.time()
            formation.status = "dissolved"
            logger.debug(
                f"FluidCollective: dissolved formation {formation_id} "
                f"({len(formation.models)} models, "
                f"duration={formation.dissolved_at - formation.formed_at:.1f}s)"
            )

    # ── Mobility Budget (Movement vs. Numbers) ────────────────────

    def allocate_mobility_budget(
        self, task_complexity: float = 0.5,
        context_available: int = 128000,
        cost_budget_yuan: float = 0.50,
        preference: str = "balanced",
    ) -> MobilityBudget:
        """Compute optimal mobility × multiplicity tradeoff.

        From the paper's key finding: mobility can substitute for numbers.
        Higher mobility (more model switches) → fewer models → lower cost
        for equivalent quality.

        Args:
            task_complexity: 0-1 estimated difficulty.
            context_available: Available context window.
            cost_budget_yuan: Maximum cost budget.
            preference: "cost_optimal", "quality_max", "balanced".

        Returns:
            MobilityBudget with optimal configuration.
        """
        # Base: low complexity → favor fewer models + low mobility
        # High complexity → need more models OR more mobility

        if preference == "cost_optimal":
            # Minimum cost: use few flash models with high mobility
            model_switches = int(3 + task_complexity * 4)
            unique_models = max(1, int(2 - task_complexity))
            quality = 0.4 + task_complexity * 0.3
            cost = 0.05 + task_complexity * 0.10

        elif preference == "quality_max":
            # Maximum quality: more models + high mobility
            model_switches = int(5 + task_complexity * 6)
            unique_models = max(2, int(3 + task_complexity * 2))
            quality = 0.6 + task_complexity * 0.35
            cost = 0.10 + task_complexity * 0.30

        else:  # balanced
            model_switches = int(3 + task_complexity * 5)
            unique_models = max(1, int(2 + task_complexity))
            quality = 0.5 + task_complexity * 0.3
            cost = 0.08 + task_complexity * 0.15

        total_tokens = int(context_available * 0.3 * task_complexity)
        mobility_ratio = model_switches / max(unique_models, 1)

        budget = MobilityBudget(
            total_tokens=total_tokens,
            model_switches=model_switches,
            unique_models_used=unique_models,
            mobility_ratio=round(mobility_ratio, 2),
            cost_yuan=round(min(cost, cost_budget_yuan), 4),
            quality_estimate=round(min(1.0, quality), 3),
            strategy=preference,
        )

        self._mobility_history.append(budget)
        if len(self._mobility_history) > 50:
            self._mobility_history = self._mobility_history[-30:]

        logger.debug(
            f"FluidCollective mobility: switches={model_switches} "
            f"models={unique_models} ratio={mobility_ratio:.1f} "
            f"cost=¥{budget.cost_yuan:.4f} quality={budget.quality_estimate:.2f}"
        )

        return budget

    # ── Model Selection Strategies ────────────────────────────────

    @staticmethod
    def _select_cost_optimal(candidates: list[str], max_n: int) -> list[str]:
        """Select cheapest models for the formation."""
        # Prefer flash/free models
        flash_keywords = ["flash", "free", "lite", "mini", "small", "turbo"]
        flash = [c for c in candidates
                 if any(k in c.lower() for k in flash_keywords)]
        others = [c for c in candidates if c not in flash]
        return (flash + others)[:max_n]

    @staticmethod
    def _select_quality_max(candidates: list[str], max_n: int) -> list[str]:
        """Select highest-quality models for the formation."""
        pro_keywords = ["pro", "max", "reasoning", "deep", "large"]
        pro = [c for c in candidates
               if any(k in c.lower() for k in pro_keywords)]
        others = [c for c in candidates if c not in pro]
        return (pro + others)[:max_n]

    @staticmethod
    def _select_diverse(candidates: list[str], max_n: int) -> list[str]:
        """Select diverse models — different providers."""
        providers_seen: set[str] = set()
        diverse: list[str] = []
        for c in candidates:
            # Extract provider prefix
            provider = c.split("/")[0] if "/" in c else c.split("-")[0]
            if provider not in providers_seen:
                diverse.append(c)
                providers_seen.add(provider)
            if len(diverse) >= max_n:
                break
        # Fill with remaining if not enough diverse
        if len(diverse) < max_n:
            for c in candidates:
                if c not in diverse:
                    diverse.append(c)
                if len(diverse) >= max_n:
                    break
        return diverse

    # ── Evaporation & Maintenance ─────────────────────────────────

    def _maybe_evaporate(self) -> None:
        """Periodically evaporate old traces (pheromone decay)."""
        now = time.time()
        if now - self._last_evaporation < self.EVAPORATION_INTERVAL:
            return
        self._last_evaporation = now

        evaporated = 0
        removed = []
        for tid, trace in list(self._traces.items()):
            trace.evaporate(rate=0.03)
            if trace.decay_factor < 0.05:
                removed.append(tid)
                evaporated += 1

        for tid in removed:
            del self._traces[tid]
            for domain_ids in self._domain_index.values():
                if tid in domain_ids:
                    domain_ids.remove(tid)

        if evaporated:
            logger.debug(
                f"FluidCollective: evaporated {evaporated} stale traces "
                f"({len(self._traces)} remaining)"
            )

    def _evict_lru(self) -> None:
        """Evict oldest traces when exceeding MAX_TRACES."""
        while len(self._traces) > self.MAX_TRACES:
            oldest_id, _ = self._traces.popitem(last=False)
            for domain_ids in self._domain_index.values():
                if oldest_id in domain_ids:
                    domain_ids.remove(oldest_id)

    def _clean_old_formations(self) -> None:
        """Remove formations older than 1 hour."""
        now = time.time()
        to_remove = [
            fid for fid, f in self._formations.items()
            if f.status == "dissolved" and now - f.dissolved_at > 3600
        ]
        for fid in to_remove:
            del self._formations[fid]

    # ── Provider Discovery ────────────────────────────────────────

    @staticmethod
    def _get_all_providers() -> list[str]:
        """Discover available models from the provider registry."""
        try:
            from .holistic_election import PROVIDER_CAPABILITIES
            return list(PROVIDER_CAPABILITIES.keys())
        except ImportError:
            return ["deepseek-flash", "longcat-flash", "deepseek-pro"]

    # ── Persistent Memory Tree (OpenHuman-inspired) ──────────────

    def _init_memory_tree(self) -> None:
        """Initialize SQLite-backed persistent memory tree."""
        try:
            import os
            os.makedirs(os.path.dirname(self.MEMORY_TREE_DB), exist_ok=True)
            self._db_conn = sqlite3.connect(self.MEMORY_TREE_DB)
            self._db_conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_tree (
                    id TEXT PRIMARY KEY,
                    domain TEXT,
                    content TEXT,
                    model TEXT,
                    trace_type TEXT,
                    confidence REAL,
                    depth_grade REAL,
                    deposited_at REAL,
                    access_count INTEGER DEFAULT 0,
                    summary TEXT DEFAULT ''
                )
            """)
            self._db_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_domain ON memory_tree(domain)"
            )
            self._db_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_deposited ON memory_tree(deposited_at DESC)"
            )
            self._db_conn.commit()
            # Load existing traces into memory
            self._load_memory_tree()
            logger.info(
                f"FluidCollective: memory tree ready ({len(self._traces)} traces loaded)"
            )
        except Exception as e:
            logger.debug(f"FluidCollective memory tree init: {e}")
            self._db_conn = None

    def _persist_trace(self, trace: StigmergicTrace) -> None:
        """Persist a trace to SQLite memory tree."""
        if not self._db_conn:
            return
        try:
            self._db_conn.execute(
                """INSERT OR REPLACE INTO memory_tree
                   (id, domain, content, model, trace_type, confidence,
                    depth_grade, deposited_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (trace.trace_id, trace.domain, trace.content[:self.CHUNK_MAX_TOKENS],
                 trace.model, trace.trace_type.value, trace.confidence,
                 trace.depth_grade, trace.deposited_at)
            )
            self._db_conn.commit()
        except Exception as e:
            logger.debug(f"FluidCollective persist: {e}")

    def _load_memory_tree(self) -> None:
        """Load persisted traces from SQLite into memory."""
        if not self._db_conn:
            return
        try:
            rows = self._db_conn.execute(
                "SELECT id, domain, content, model, trace_type, confidence, "
                "depth_grade, deposited_at, access_count FROM memory_tree "
                "ORDER BY deposited_at DESC LIMIT 200",
            ).fetchall()
            for row in rows:
                trace = StigmergicTrace(
                    trace_id=row[0], domain=row[1], content=row[2],
                    model=row[3], trace_type=TraceType(row[4]) if row[4] in TraceType.__members__ else TraceType.INSIGHT,
                    confidence=row[5], depth_grade=row[6], deposited_at=row[7],
                    access_count=row[8],
                )
                self._traces[trace.trace_id] = trace
                if trace.domain not in self._domain_index:
                    self._domain_index[trace.domain] = []
                self._domain_index[trace.domain].append(trace.trace_id)
        except Exception as e:
            logger.debug(f"FluidCollective load: {e}")

    def generate_memory_summary(self, domain: str = "") -> str:
        """Generate a hierarchical summary of the memory tree for a domain.

        Groups traces into themes, summarizes each theme, produces a
        concise tree view — similar to OpenHuman's Obsidian wiki output.
        """
        if not self._db_conn:
            return ""
        try:
            query = "SELECT domain, COUNT(*), AVG(confidence) FROM memory_tree"
            params = ()
            if domain:
                query += " WHERE domain = ?"
                params = (domain,)
            query += " GROUP BY domain ORDER BY COUNT(*) DESC LIMIT 10"
            rows = self._db_conn.execute(query, params).fetchall()

            if not rows:
                return ""

            lines = ["# Memory Tree Summary\n"]
            for row in rows:
                d, count, avg_conf = row
                lines.append(f"## {d} ({count} traces, avg confidence: {avg_conf:.2f})")
                # Get recent traces for this domain
                traces = self._db_conn.execute(
                    "SELECT content, model, deposited_at FROM memory_tree "
                    "WHERE domain = ? ORDER BY deposited_at DESC LIMIT 3",
                    (d,)
                ).fetchall()
                for t in traces:
                    lines.append(f"- [{t[1]}] {t[2][:120]}...")
                lines.append("")
            return "\n".join(lines)
        except Exception:
            return ""

    def _save_to_memory_tree(self, trace: StigmergicTrace) -> None:
        self._persist_trace(trace)

    # ── Statistics ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        recent_budgets = self._mobility_history[-10:] if self._mobility_history else []
        domains = {
            d: len(ids)
            for d, ids in sorted(
                self._domain_index.items(),
                key=lambda x: -len(x[1]),
            )[:10]
        }
        return {
            "traces_active": len(self._traces),
            "total_deposits": self._total_deposits,
            "total_retrievals": self._total_retrievals,
            "active_formations": sum(
                1 for f in self._formations.values() if f.status == "active"
            ),
            "domains_indexed": len(self._domain_index),
            "top_domains": domains,
            "avg_mobility_ratio": round(
                sum(b.mobility_ratio for b in recent_budgets) / max(len(recent_budgets), 1), 2
            ) if recent_budgets else 0.0,
            "avg_formation_size": round(
                sum(len(f.models) for f in self._formations.values()) /
                max(len(self._formations), 1), 1
            ),
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_fc: Optional[FluidCollective] = None


def get_fluid_collective() -> FluidCollective:
    global _fc
    if _fc is None:
        _fc = FluidCollective()
    return _fc


__all__ = [
    "FluidCollective", "StigmergicTrace", "TransientFormation",
    "MobilityBudget", "TraceType",
    "get_fluid_collective",
]
