"""Context Biology — context as a living, evolving organism.

Beyond engineering discipline: context has DNA, metabolism, hormones, and dreams.

🧬 Context DNA — lineage tracing, mutation tracking, inheritance
🌿 Context Photosynthesis — measure context efficiency (improvement/token)
💉 Context Hormones — system-wide state signals that modulate context behavior
🧪 Context Metabolism — hot/cold context, energy budget, decay rates
🫂 Context Symbiosis — co-evolving context artifacts, dependency graphs
🏰 Context Memory Palace — spatial knowledge organization
🌌 Context Dreams — idle-time context recombination → emergent insights
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
# 🧬 Context DNA — lineage, mutation, inheritance
# ═══════════════════════════════════════════════════════

class MutationType(str, Enum):
    REFINEMENT = "refinement"     # Human/feedback-driven improvement
    CROSSOVER = "crossover"       # Two contexts merged
    DREAM = "dream"               # Idle-time recombination
    HORMONAL = "hormonal"         # System-state induced change
    ANTIBODY = "antibody"         # Security-driven hardening


@dataclass
class ContextGene:
    """A single gene in a context artifact — a rule, pattern, or instruction."""
    gene_id: str
    content: str                 # The actual context text
    parent_gene_id: str = ""     # Which gene this mutated from
    mutation_type: MutationType = MutationType.REFINEMENT
    fitness: float = 0.5          # Success rate
    born_at: float = field(default_factory=time.time)
    generation: int = 0
    mutation_count: int = 0


@dataclass
class ContextGenome:
    """Complete genetic makeup of a context artifact."""
    artifact_name: str
    genes: list[ContextGene] = field(default_factory=list)
    lineage: list[str] = field(default_factory=list)  # Ancestor context names
    generation: int = 0
    created_at: float = field(default_factory=time.time)
    dna_hash: str = ""

    def mutate(self, gene_idx: int, new_content: str,
               mutation_type: MutationType = MutationType.REFINEMENT) -> ContextGene:
        """Mutate a gene — create new gene inheriting from parent."""
        parent = self.genes[gene_idx]
        child = ContextGene(
            gene_id=f"{parent.gene_id}_mut{parent.mutation_count + 1}",
            content=new_content,
            parent_gene_id=parent.gene_id,
            mutation_type=mutation_type,
            generation=self.generation + 1,
            mutation_count=parent.mutation_count + 1,
        )
        self.genes[gene_idx] = child
        self.generation += 1
        return child

    def crossover(self, other: ContextGenome, ratio: float = 0.5) -> ContextGenome:
        """Breed two genomes — create hybrid context."""
        child_genes = []
        max_len = max(len(self.genes), len(other.genes))

        for i in range(max_len):
            if i < len(self.genes) and i < len(other.genes):
                # Blend genes
                a, b = self.genes[i].content, other.genes[i].content
                blended = a[:int(len(a) * ratio)] + b[int(len(b) * ratio):]
                child_genes.append(ContextGene(
                    gene_id=f"hybrid_{i}",
                    content=blended,
                    parent_gene_id=f"{self.genes[i].gene_id}+{other.genes[i].gene_id}",
                    mutation_type=MutationType.CROSSOVER,
                    generation=max(self.generation, other.generation) + 1,
                ))
            elif i < len(self.genes):
                child_genes.append(self.genes[i])
            else:
                child_genes.append(other.genes[i])

        return ContextGenome(
            artifact_name=f"{self.artifact_name}×{other.artifact_name}",
            genes=child_genes,
            lineage=self.lineage + [other.artifact_name],
            generation=child_genes[0].generation if child_genes else 0,
        )

    def lineage_report(self) -> str:
        """Git-blame-like lineage trace for this context."""
        lines = [f"🧬 Context DNA: {self.artifact_name} (gen {self.generation})"]
        lines.append(f"   Lineage: {' → '.join(self.lineage[:10])}")
        for gene in self.genes:
            parent = gene.parent_gene_id[:10] if gene.parent_gene_id else "ORIGIN"
            age = time.time() - gene.born_at
            lines.append(
                f"  Gene {gene.gene_id[:12]}: fitness={gene.fitness:.2f} "
                f"parent={parent} type={gene.mutation_type.value} "
                f"age={age:.0f}s mutations={gene.mutation_count}"
            )
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# 🌿 Context Photosynthesis — efficiency measurement
# ═══════════════════════════════════════════════════════

class ContextPhotosynthesis:
    """Measure: how much improvement per token of context investment?

    Photosynthesis efficiency = Δsuccess_rate / context_tokens_invested
    Like plants: CO₂ + sunlight → sugar. Context: tokens + feedback → success.

    This tells us which context artifacts are "efficient" and which are
    parasitic (consume tokens without improving outcomes).
    """

    def __init__(self):
        self._measurements: dict[str, list[dict]] = defaultdict(list)

    def measure(self, context_name: str, tokens_used: int,
                success_rate_before: float, success_rate_after: float) -> float:
        """Measure photosynthetic efficiency of a context artifact.

        Returns efficiency score: higher = better return on context investment.
        """
        delta = success_rate_after - success_rate_before
        efficiency = delta / max(1, tokens_used / 100)  # Normalize per 100 tokens

        self._measurements[context_name].append({
            "tokens": tokens_used,
            "delta": delta,
            "efficiency": efficiency,
            "timestamp": time.time(),
        })

        if efficiency < 0:
            logger.warning(
                f"ContextPhotosynthesis: {context_name} is PARASITIC "
                f"(efficiency={efficiency:.3f}, made things WORSE)"
            )
        elif efficiency > 0.1:
            logger.info(
                f"ContextPhotosynthesis: {context_name} is HIGHLY EFFICIENT "
                f"(efficiency={efficiency:.3f})"
            )

        return efficiency

    def rank_by_efficiency(self) -> list[dict]:
        """Rank context artifacts by photosynthetic efficiency."""
        ranked = []
        for name, measures in self._measurements.items():
            if measures:
                avg_eff = sum(m["efficiency"] for m in measures) / len(measures)
                avg_delta = sum(m["delta"] for m in measures) / len(measures)
                ranked.append({
                    "context": name,
                    "efficiency": round(avg_eff, 4),
                    "avg_improvement": round(avg_delta, 4),
                    "measurements": len(measures),
                    "type": "photosynthetic" if avg_eff > 0 else "parasitic",
                })
        ranked.sort(key=lambda x: -x["efficiency"])
        return ranked

    def prune_parasites(self, threshold: float = 0.0) -> list[str]:
        """Identify context artifacts that should be removed (parasitic)."""
        parasites = []
        for name, measures in self._measurements.items():
            if measures:
                avg_eff = sum(m["efficiency"] for m in measures) / len(measures)
                if avg_eff < threshold:
                    parasites.append(name)
        return parasites


# ═══════════════════════════════════════════════════════
# 💉 Context Hormones — system-wide state signals
# ═══════════════════════════════════════════════════════

class HormoneType(str, Enum):
    STRESS = "stress"        # High error rate → conservative, verify more
    GROWTH = "growth"        # New learning → exploratory, take risks
    SLEEP = "sleep"          # Idle time → consolidate, compress, archive
    FEAR = "fear"            # Security threat → lockdown, scan everything
    JOY = "joy"              # High success → reinforce, amplify patterns
    HUNGER = "hunger"        # Low data → seek new knowledge sources


@dataclass
class HormoneSignal:
    """A hormone signal that modulates context behavior system-wide."""
    hormone: HormoneType
    intensity: float          # 0 (none) to 1 (max)
    triggered_by: str         # What caused this hormone release
    effect: str               # How this changes context behavior
    timestamp: float = field(default_factory=time.time)
    duration_seconds: float = 300  # How long the hormone lasts


class ContextEndocrineSystem:
    """System-wide hormone signals that modulate all context behavior.

    Like the human endocrine system:
      - Adrenaline (stress) → fight-or-flight, conservative choices
      - Growth hormone → explore, learn, take risks
      - Melatonin (sleep) → consolidate, compress, archive
    """

    def __init__(self):
        self._active_hormones: dict[HormoneType, HormoneSignal] = {}
        self._history: list[HormoneSignal] = []

    def release(self, hormone: HormoneType, intensity: float,
                triggered_by: str) -> HormoneSignal:
        """Release a hormone into the system."""
        effects = {
            HormoneType.STRESS: "Conservative context: verify twice, reduce exploration, prefer safe models",
            HormoneType.GROWTH: "Exploratory context: increase mutation rate, try new skills, expand capability graph",
            HormoneType.SLEEP: "Consolidation context: compress memories, archive old context, defragment",
            HormoneType.FEAR: "Lockdown context: scan all inputs, restrict tool access, require verification",
            HormoneType.JOY: "Reinforcement context: increase confidence weights, promote successful patterns",
            HormoneType.HUNGER: "Seeking context: expand knowledge search, query external sources, learn aggressively",
        }

        signal = HormoneSignal(
            hormone=hormone,
            intensity=min(1.0, intensity),
            triggered_by=triggered_by,
            effect=effects.get(hormone, ""),
        )
        self._active_hormones[hormone] = signal
        self._history.append(signal)

        logger.info(
            f"Endocrine: {hormone.value.upper()} released "
            f"(intensity={intensity:.2f}) — {signal.effect[:80]}"
        )
        return signal

    def get_dominant_hormone(self) -> Optional[HormoneSignal]:
        """Get the most intense active hormone — shapes current behavior."""
        if not self._active_hormones:
            return None
        return max(self._active_hormones.values(), key=lambda h: h.intensity)

    def modulate_context(self, base_behavior: dict) -> dict:
        """Apply hormonal modulation to context behavior parameters."""
        dominant = self.get_dominant_hormone()
        if not dominant:
            return base_behavior

        modulated = dict(base_behavior)

        if dominant.hormone == HormoneType.STRESS:
            modulated["temperature"] = modulated.get("temperature", 0.7) * 0.5
            modulated["verify_steps"] = modulated.get("verify_steps", 2) + 2
            modulated["max_tokens"] = modulated.get("max_tokens", 4096) // 2

        elif dominant.hormone == HormoneType.GROWTH:
            modulated["temperature"] = modulated.get("temperature", 0.7) * 1.5
            modulated["exploration_rate"] = modulated.get("exploration_rate", 0.3) + 0.4
            modulated["mutation_rate"] = modulated.get("mutation_rate", 0.05) * 2

        elif dominant.hormone == HormoneType.SLEEP:
            modulated["compress_threshold"] = 0.3
            modulated["archive_age_seconds"] = 3600

        elif dominant.hormone == HormoneType.FEAR:
            modulated["security_scan_level"] = "maximum"
            modulated["allow_external_tools"] = False

        return modulated

    def decay_hormones(self) -> None:
        """Hormones naturally decay over time."""
        now = time.time()
        expired = [
            h for h, s in self._active_hormones.items()
            if now - s.timestamp > s.duration_seconds
        ]
        for h in expired:
            del self._active_hormones[h]

    def hormonal_state(self) -> dict:
        """Current hormonal profile of the system."""
        self.decay_hormones()
        return {
            "active_hormones": [
                {"hormone": h.value, "intensity": round(s.intensity, 2),
                 "trigger": s.triggered_by[:60]}
                for h, s in self._active_hormones.items()
            ],
            "dominant": self.get_dominant_hormone().hormone.value if self.get_dominant_hormone() else "none",
        }


# ═══════════════════════════════════════════════════════
# 🧪 Context Metabolism — hot/cold, energy budget
# ═══════════════════════════════════════════════════════

class ContextMetabolism:
    """Context has metabolic rates. Hot context = fast retrieval. Cold = archived.

    Metabolic budget = tokens consumed per query.
    Basal metabolic rate = minimum context needed for basic function.
    """

    def __init__(self, basal_rate: int = 200):  # 200 tokens minimum
        self.basal_rate = basal_rate
        self._hot_context: dict[str, dict] = {}     # Frequently used
        self._warm_context: dict[str, dict] = {}    # Occasionally used
        self._cold_context: dict[str, dict] = {}    # Rarely used, compressed
        self._total_tokens_burned = 0

    def feed(self, context_name: str, tokens: int) -> str:
        """Record context usage → adjust temperature."""
        self._total_tokens_burned += tokens

        # Promote to hotter tier
        if context_name in self._cold_context:
            entry = self._cold_context.pop(context_name)
            self._warm_context[context_name] = entry
        elif context_name in self._warm_context:
            self._warm_context[context_name]["use_count"] += 1
            if self._warm_context[context_name]["use_count"] > 5:
                entry = self._warm_context.pop(context_name)
                self._hot_context[context_name] = entry
        elif context_name in self._hot_context:
            self._hot_context[context_name]["use_count"] += 1
        else:
            self._warm_context[context_name] = {"use_count": 1, "tokens": tokens}

        # Cool unused context
        for name in list(self._hot_context.keys()):
            self._hot_context[name]["idle_cycles"] = self._hot_context[name].get("idle_cycles", 0) + 1
            if self._hot_context[name]["idle_cycles"] > 100:
                entry = self._hot_context.pop(name)
                self._warm_context[name] = entry
                entry["idle_cycles"] = 0

        return self._temperature_for(context_name)

    def _temperature_for(self, context_name: str) -> str:
        if context_name in self._hot_context:
            return "🔥 HOT"
        elif context_name in self._warm_context:
            return "🌡 WARM"
        return "❄ COLD"

    @property
    def metabolic_rate(self) -> float:
        """Tokens burned per unit time."""
        return self._total_tokens_burned

    def health_report(self) -> str:
        hot = len(self._hot_context)
        warm = len(self._warm_context)
        cold = len(self._cold_context)
        total = hot + warm + cold
        return (
            f"🧪 Metabolism: {self._total_tokens_burned} tokens burned | "
            f"🔥{hot} 🌡{warm} ❄{cold} | "
            f"Basal: {self.basal_rate} tokens"
        )


# ═══════════════════════════════════════════════════════
# 🫂 Context Symbiosis — co-evolving dependencies
# ═══════════════════════════════════════════════════════

@dataclass
class SymbioticPair:
    """Two context artifacts that work better together."""
    artifact_a: str
    artifact_b: str
    synergy_score: float = 0.5   # How much better they are together
    co_usage_count: int = 0


class ContextSymbiosis:
    """Track which context artifacts have symbiotic relationships.

    Like gut bacteria + human: each benefits from the other's presence.
    Separating symbiotic pairs degrades performance.
    """

    def __init__(self):
        self._pairs: dict[str, SymbioticPair] = {}
        self._sole_performance: dict[str, float] = {}

    def observe_co_usage(self, artifact_a: str, artifact_b: str,
                         success: bool) -> None:
        """Observe that two artifacts were used together."""
        key = "|".join(sorted([artifact_a, artifact_b]))
        if key not in self._pairs:
            self._pairs[key] = SymbioticPair(artifact_a, artifact_b)
        pair = self._pairs[key]
        pair.co_usage_count += 1
        # Success boosts synergy, failure reduces
        alpha = 1.0 / (pair.co_usage_count + 1)
        target = 1.0 if success else 0.0
        pair.synergy_score = (1 - alpha) * pair.synergy_score + alpha * target

    def find_symbionts(self, artifact: str) -> list[dict]:
        """Find all symbionts for a given artifact."""
        symbionts = []
        for key, pair in self._pairs.items():
            if artifact in (pair.artifact_a, pair.artifact_b) and pair.synergy_score > 0.6:
                partner = pair.artifact_a if artifact == pair.artifact_b else pair.artifact_b
                symbionts.append({
                    "partner": partner,
                    "synergy": round(pair.synergy_score, 2),
                    "co_usage": pair.co_usage_count,
                })
        return sorted(symbionts, key=lambda x: -x["synergy"])


# ═══════════════════════════════════════════════════════
# 🏰 Context Memory Palace — spatial knowledge organization
# ═══════════════════════════════════════════════════════

class ContextMemoryPalace:
    """Organize context spatially like a memory palace.

    Each "room" = a domain. Walking through rooms = traversing context.
    Spatial proximity = semantic relatedness.
    """

    ROOMS = [
        ("entrance", "入口大厅", "General queries, routing, intent"),
        ("library", "图书馆", "Knowledge retrieval, document analysis"),
        ("workshop", "工坊", "Code generation, tool execution"),
        ("garden", "花园", "Creative tasks, brainstorming, exploration"),
        ("observatory", "天文台", "Analysis, reasoning, deep thinking"),
        ("vault", "金库", "Security, compliance, sensitive operations"),
        ("dream_chamber", "梦境室", "Idle learning, consolidation, dreams"),
    ]

    def locate(self, query: str) -> str:
        """Find which room a query belongs to."""
        query_lower = query.lower()
        for room_id, room_name, description in self.ROOMS:
            keywords = description.lower().split(", ")
            if any(kw in query_lower for kw in keywords):
                return f"🏰 {room_name} ({room_id})"
        return "🏰 入口大厅 (entrance) — default"

    def navigate(self, from_room: str, to_room: str) -> list[str]:
        """Walk through memory palace — return room sequence."""
        room_ids = [r[0] for r in self.ROOMS]
        if from_room not in room_ids or to_room not in room_ids:
            return [from_room, to_room]

        start_idx = room_ids.index(from_room)
        end_idx = room_ids.index(to_room)
        step = 1 if end_idx > start_idx else -1
        path = room_ids[start_idx:end_idx + step:step]
        return [f"🏰 {dict(self.ROOMS)[r][1]}" for r in path]


# ═══════════════════════════════════════════════════════
# 🌌 Context Dreams — idle-time recombination
# ═══════════════════════════════════════════════════════

class ContextDreamer:
    """Recombine context artifacts during idle time → emergent insights.

    Like human dreams: random recombination of day's experiences
    sometimes produces novel connections.
    """

    def __init__(self):
        self._dream_log: list[dict] = []
        self._insights: list[str] = []

    def dream(self, genomes: list[ContextGenome]) -> dict:
        """Recombine random genomes → potentially novel hybrid."""
        if len(genomes) < 2:
            return {"dream_type": "empty", "insight": "Not enough context to dream"}

        # Pick two random genomes
        a, b = random.sample(genomes, 2)

        # Crossover with random ratio
        ratio = random.random()
        hybrid = a.crossover(b, ratio)

        # Measure novelty: how different is the hybrid from both parents?
        novelty = 1.0 - max(
            self._similarity(hybrid, a),
            self._similarity(hybrid, b),
        )

        dream = {
            "dream_type": "crossover" if novelty > 0.5 else "mutation",
            "parent_a": a.artifact_name,
            "parent_b": b.artifact_name,
            "hybrid_name": hybrid.artifact_name,
            "novelty": round(novelty, 3),
            "gene_count": len(hybrid.genes),
            "timestamp": time.time(),
            "insight": (
                f"Dream: combined '{a.artifact_name}' with '{b.artifact_name}' "
                f"→ hybrid '{hybrid.artifact_name}' (novelty={novelty:.2f})"
            ),
        }

        self._dream_log.append(dream)

        if novelty > 0.6:
            self._insights.append(dream["insight"])
            logger.info(f"ContextDreamer: INSIGHT! {dream['insight']}")

        return dream

    def _similarity(self, a: ContextGenome, b: ContextGenome) -> float:
        """How similar are two genomes?"""
        if not a.genes or not b.genes:
            return 0.5
        shared = sum(1 for ga in a.genes for gb in b.genes
                     if ga.content[:50] == gb.content[:50])
        return shared / max(1, max(len(a.genes), len(b.genes)))

    def dream_journal(self) -> str:
        """Render dream log."""
        lines = ["🌌 Context Dream Journal"]
        for dream in self._dream_log[-7:]:
            lines.append(
                f"  {dream['dream_type'].upper()}: {dream['parent_a']} × {dream['parent_b']} "
                f"→ novelty={dream['novelty']:.2f}"
            )
        if self._insights:
            lines.append(f"\n💡 Insights gained: {len(self._insights)}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# Unified Context Biology
# ═══════════════════════════════════════════════════════

class ContextBiology:
    """All context biology systems in one organism."""

    def __init__(self):
        self.dna = ContextGenome(artifact_name="root")
        self.photosynthesis = ContextPhotosynthesis()
        self.endocrine = ContextEndocrineSystem()
        self.metabolism = ContextMetabolism()
        self.symbiosis = ContextSymbiosis()
        self.palace = ContextMemoryPalace()
        self.dreamer = ContextDreamer()

    def full_cycle(self, query: str, context_used: list[str],
                   success: bool, tokens: int) -> dict:
        """One full biological cycle — all systems update."""
        results = {}

        # DNA: record gene fitness
        for name in context_used:
            gene = ContextGene(gene_id=f"gene_{name}", content=name)
            gene.fitness = 0.8 if success else 0.3
            self.dna.genes.append(gene)

        # Photosynthesis: measure efficiency
        for name in context_used:
            eff = self.photosynthesis.measure(
                name, tokens,
                success_rate_before=0.5,
                success_rate_after=0.8 if success else 0.4,
            )
            results[f"photo_{name}"] = round(eff, 4)

        # Hormones: release based on outcomes
        if not success:
            self.endocrine.release(HormoneType.STRESS, 0.6, f"Failed on query: {query[:50]}")
        elif tokens < 500:
            self.endocrine.release(HormoneType.JOY, 0.3, f"Efficient success on: {query[:50]}")

        # Metabolism: track token consumption
        for name in context_used:
            self.metabolism.feed(name, tokens // max(1, len(context_used)))

        # Symbiosis: track co-usage
        if len(context_used) >= 2:
            for i in range(len(context_used)):
                for j in range(i + 1, len(context_used)):
                    self.symbiosis.observe_co_usage(
                        context_used[i], context_used[j], success
                    )

        # Memory Palace: locate query
        location = self.palace.locate(query)
        results["location"] = location

        # Endocrine state
        results["hormones"] = self.endocrine.hormonal_state()
        results["metabolism"] = self.metabolism.health_report()

        return results


# ── Singleton ──

_bio: Optional[ContextBiology] = None


def get_context_biology() -> ContextBiology:
    global _bio
    if _bio is None:
        _bio = ContextBiology()
    return _bio
