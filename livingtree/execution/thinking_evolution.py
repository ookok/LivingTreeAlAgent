"""ThinkingEvolution — LLM-driven genetic optimization over code/solutions.

Inspired by CogAlpha (§3.6): performs genetic-style optimization in natural
language space, where candidate solutions undergo mutation and crossover
operations expressed through textual prompts.

Agents:
- MutationAgent: slightly modifies a solution to introduce variability
- CrossoverAgent: combines two solutions to create a novel hybrid
- RecombinationAgent: merges N best traits into a single enhanced solution

Modes:
- mutation_only: diversify a single candidate
- crossover_only: fuse two candidates
- crossover_then_mutation: fuse then refine (most powerful)

Usage:
    evo = ThinkingEvolution(consciousness=pro_model)
    mutated = await evo.mutate(solution, direction="explore alternatives")
    crossed = await evo.crossover(parent_a, parent_b)
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from loguru import logger
from pydantic import BaseModel, Field


@dataclass
class EvolutionCandidate:
    """A single candidate solution in the evolutionary population."""
    id: str = ""
    content: str = ""
    source: str = "initial"
    generation: int = 0
    fitness: float = 0.0
    fitness_metrics: dict[str, float] = field(default_factory=dict)
    annotations: str = ""
    parent_ids: list[str] = field(default_factory=list)
    mutation_count: int = 0
    status: str = "active"

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(self.content.encode()[:200]).hexdigest()[:12]


class ElitePool(BaseModel):
    """Preserves top-performing candidates across generations.

    Maximum pool size limits memory; oldest entries are evicted.
    """
    max_size: int = 10
    candidates: list[dict[str, Any]] = Field(default_factory=list)

    def add(self, candidate: EvolutionCandidate) -> None:
        entry = {
            "id": candidate.id,
            "content": candidate.content,
            "source": candidate.source,
            "generation": candidate.generation,
            "fitness": candidate.fitness,
            "metrics": candidate.fitness_metrics,
            "annotations": candidate.annotations,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.candidates.append(entry)
        self.candidates.sort(key=lambda c: c["fitness"], reverse=True)
        if len(self.candidates) > self.max_size:
            self.candidates = self.candidates[:self.max_size]

    def get_top(self, n: int = 2) -> list[dict[str, Any]]:
        return self.candidates[:n]

    def get_best(self) -> Optional[dict[str, Any]]:
        return self.candidates[0] if self.candidates else None

    def get_by_source(self, source: str) -> list[dict[str, Any]]:
        return [c for c in self.candidates if c["source"] == source]


@dataclass
class EvolutionResult:
    """Result of an evolution step."""
    candidates: list[EvolutionCandidate]
    elite_pool: ElitePool
    generation: int
    total_fitness: float
    best_fitness: float
    avg_fitness: float
    diversity_score: float


class ThinkingEvolution:
    """LLM-driven genetic optimization engine for cognitive evolution.

    Inspired by CogAlpha §3.6 — Thinking Evolution performs genetic-style
    optimization in natural language space via LLM prompts.

    Uses DualModelConsciousness when available (pro for deep mutation
    reasoning, flash for quick crossover), falls back to heuristic ops.
    """

    def __init__(self, consciousness: Any = None, population_size: int = 32,
                 elite_size: int = 2, max_generations: int = 24,
                 mutation_rate: float = 0.3, crossover_rate: float = 0.5):
        self.consciousness = consciousness
        self.population_size = population_size
        self.elite_size = elite_size
        self.max_generations = max_generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_pool = ElitePool(max_size=20)
        self._current_generation = 0
        self._population: list[EvolutionCandidate] = []

    # ── Core evolution operations ──

    async def mutate(self, candidate: EvolutionCandidate,
                     direction: str = "explore_alternatives",
                     temperature: float = 0.8) -> EvolutionCandidate:
        """Apply mutation to a candidate — slightly modify to introduce variability.

        Args:
            candidate: The candidate to mutate
            direction: Guidance for the mutation:
                - "explore_alternatives": seek structurally different solutions
                - "optimize": improve the existing solution
                - "diversify": deliberately break from the current pattern
                - "simplify": reduce complexity while preserving function
            temperature: Creativity temperature (0.7-1.2 recommended)
        """
        if self.consciousness and hasattr(self.consciousness, 'chain_of_thought'):
            try:
                prompt = self._build_mutation_prompt(candidate, direction)
                mutated_text = await self.consciousness.chain_of_thought(
                    prompt, steps=3,
                    temperature=temperature,
                    max_tokens=4096,
                )
                new_candidate = EvolutionCandidate(
                    content=mutated_text,
                    source=f"mutation_{direction}",
                    parent_ids=[candidate.id],
                    mutation_count=candidate.mutation_count + 1,
                    generation=candidate.generation + 1,
                )
                logger.debug(f"Mutation: {candidate.id[:8]} → {new_candidate.id[:8]} ({direction})")
                return new_candidate
            except Exception as e:
                logger.warning(f"LLM mutation failed: {e}")

        # Heuristic mutation fallback
        return self._heuristic_mutate(candidate, direction)

    async def crossover(self, parent_a: EvolutionCandidate,
                        parent_b: EvolutionCandidate,
                        temperature: float = 0.9) -> EvolutionCandidate:
        """Crossover two candidates — combine their best traits into a hybrid.

        The LLM is prompted to identify complementary strengths from each
        parent and synthesize a novel solution that exceeds both.
        """
        if self.consciousness and hasattr(self.consciousness, 'chain_of_thought'):
            try:
                prompt = self._build_crossover_prompt(parent_a, parent_b)
                crossed_text = await self.consciousness.chain_of_thought(
                    prompt, steps=4,
                    temperature=temperature,
                    max_tokens=4096,
                )
                new_candidate = EvolutionCandidate(
                    content=crossed_text,
                    source="crossover",
                    parent_ids=[parent_a.id, parent_b.id],
                    generation=max(parent_a.generation, parent_b.generation) + 1,
                )
                logger.debug(f"Crossover: {parent_a.id[:8]} + {parent_b.id[:8]} → {new_candidate.id[:8]}")
                return new_candidate
            except Exception as e:
                logger.warning(f"LLM crossover failed: {e}")

        return self._heuristic_crossover(parent_a, parent_b)

    async def crossover_then_mutate(self, parent_a: EvolutionCandidate,
                                     parent_b: EvolutionCandidate,
                                     temperature: float = 0.9) -> EvolutionCandidate:
        """Most powerful mode: fuse two parents, then mutate the result."""
        crossed = await self.crossover(parent_a, parent_b, temperature)
        return await self.mutate(crossed, direction="optimize", temperature=temperature * 0.8)

    async def recombine(self, candidates: list[EvolutionCandidate],
                        temperature: float = 0.8) -> EvolutionCandidate:
        """Recombine N top candidates — merge best traits from multiple sources."""
        if len(candidates) < 2:
            return candidates[0] if candidates else EvolutionCandidate(content="")

        if self.consciousness and hasattr(self.consciousness, 'chain_of_thought'):
            try:
                prompt = self._build_recombination_prompt(candidates)
                result = await self.consciousness.chain_of_thought(
                    prompt, steps=3, temperature=temperature, max_tokens=4096,
                )
                return EvolutionCandidate(
                    content=result,
                    source="recombination",
                    parent_ids=[c.id for c in candidates],
                    generation=max(c.generation for c in candidates) + 1,
                )
            except Exception as e:
                logger.warning(f"LLM recombination failed: {e}")

        # Fallback: pick best and merge literally
        sorted_candidates = sorted(candidates, key=lambda c: c.fitness, reverse=True)
        merged = "\n".join(c.content[:500] for c in sorted_candidates[:3])
        return EvolutionCandidate(content=merged, source="recombination_heuristic")

    # ── Population evolution ──

    async def evolve_population(self, initial_candidates: list[EvolutionCandidate],
                                 generations: int | None = None,
                                 fitness_fn: Optional[Callable] = None,
                                 quality_check_fn: Optional[Callable] = None,
                                 ) -> EvolutionResult:
        """Evolve a population through multiple generations.

        Args:
            initial_candidates: Starting population
            generations: Number of generations (defaults to self.max_generations)
            fitness_fn: Async (candidate) -> float
            quality_check_fn: Async (candidate) -> bool

        Returns:
            EvolutionResult with final population and metrics
        """
        gens = generations or self.max_generations
        self._population = list(initial_candidates)
        self._current_generation = 0

        total_fitness = 0.0
        best_fitness = -float("inf")

        for gen in range(gens):
            self._current_generation = gen

            # Evaluate fitness
            if fitness_fn:
                for c in self._population:
                    try:
                        if inspect.iscoroutinefunction(fitness_fn):
                            c.fitness = await fitness_fn(c)
                        else:
                            c.fitness = fitness_fn(c)
                    except Exception:
                        c.fitness = 0.0
                self._population.sort(key=lambda c: c.fitness, reverse=True)

            # Quality check
            if quality_check_fn:
                surviving = []
                for c in self._population:
                    if inspect.iscoroutinefunction(quality_check_fn):
                        ok = await quality_check_fn(c)
                    else:
                        ok = quality_check_fn(c)
                    if ok:
                        surviving.append(c)
                self._population = surviving

            # Preserve elites
            elites = self._population[:self.elite_size]
            for elite in elites:
                self.elite_pool.add(elite)

            # Track stats
            if self._population:
                best_fitness = max(best_fitness, self._population[0].fitness)
                total_fitness = sum(c.fitness for c in self._population)

            # Generate new population through evolution
            new_population = list(elites)  # Elite preservation

            while len(new_population) < self.population_size:
                if random.random() < self.crossover_rate and len(self._population) >= 2:
                    parents = random.sample(self._population, min(2, len(self._population)))
                    child = await self.crossover(parents[0], parents[1]) if len(parents) == 2 else parents[0]
                    if random.random() < self.mutation_rate:
                        child = await self.mutate(child, direction=random.choice(
                            ["explore_alternatives", "optimize", "diversify"]))
                else:
                    parent = random.choice(self._population)
                    child = await self.mutate(parent, direction=random.choice(
                        ["explore_alternatives", "optimize", "diversify", "simplify"]))

                child.generation = gen + 1
                new_population.append(child)

            self._population = new_population[:self.population_size]
            logger.info(f"Generation {gen + 1}/{gens}: pop={len(self._population)}, "
                        f"best={best_fitness:.4f}, elites={len(elites)}")

        # Compute diversity score
        all_ids = set(c.id for c in self._population)
        diversity = len(all_ids) / max(len(self._population), 1)

        return EvolutionResult(
            candidates=self._population,
            elite_pool=self.elite_pool,
            generation=self._current_generation,
            total_fitness=total_fitness,
            best_fitness=best_fitness,
            avg_fitness=total_fitness / max(len(self._population), 1),
            diversity_score=diversity,
        )

    async def get_elite_solutions(self, n: int = 5) -> list[dict[str, Any]]:
        """Get top N elite solutions from the pool."""
        return self.elite_pool.get_top(n)

    def get_population_stats(self) -> dict[str, Any]:
        return {
            "population_size": len(self._population),
            "generation": self._current_generation,
            "elite_pool_size": len(self.elite_pool.candidates),
            "avg_fitness": sum(c.fitness for c in self._population) / max(len(self._population), 1),
            "best_fitness": max((c.fitness for c in self._population), default=0),
        }

    # ── Prompt builders ──

    def _build_mutation_prompt(self, candidate: EvolutionCandidate,
                                direction: str) -> str:
        direction_guidance = {
            "explore_alternatives": "探索结构上完全不同的替代方案。不要微调——尝试全新的思路。",
            "optimize": "在保持核心思路不变的前提下优化和改进这个方案。增强其性能、可读性或鲁棒性。",
            "diversify": "刻意打破当前模式。从完全不同的角度重新思考，即使看起来不太常规。",
            "simplify": "简化方案，去掉不必要的复杂度，同时保持核心功能不变。",
        }
        guidance = direction_guidance.get(direction, direction_guidance["optimize"])

        return (
            f"你是一个认知进化引擎。请对以下解决方案进行变异操作。\n\n"
            f"变异方向: {guidance}\n\n"
            f"当前方案:\n{candidate.content[:2000]}\n\n"
            f"来源: {candidate.source} | 适应度: {candidate.fitness:.4f}\n\n"
            f"请生成变异后的方案。输出完整的新方案代码/方案，保持原有语言和格式。"
        )

    def _build_crossover_prompt(self, parent_a: EvolutionCandidate,
                                 parent_b: EvolutionCandidate) -> str:
        return (
            "你是一个认知进化引擎。请将以下两个方案进行交叉操作，"
            "提取各自的优势并融合成一个新的、更强的方案。\n\n"
            f"方案A:\n{parent_a.content[:1500]}\n\n"
            f"方案B:\n{parent_b.content[:1500]}\n\n"
            "请分析两个方案的互补特性，然后生成融合后的新方案。"
            "输出完整的新方案，保持代码/方案格式。"
        )

    def _build_recombination_prompt(self, candidates: list[EvolutionCandidate]) -> str:
        parts = []
        for i, c in enumerate(candidates[:5]):
            parts.append(f"方案{i + 1} (适应度={c.fitness:.4f}):\n{c.content[:800]}")
        return (
            "你是一个认知进化引擎。请从以下多个方案中提取最佳特征，"
            "合成一个综合最优的方案。\n\n" +
            "\n\n".join(parts) +
            "\n\n请生成整合后的新方案。输出完整方案。"
        )

    # ── Heuristic fallbacks ──

    def _heuristic_mutate(self, candidate: EvolutionCandidate,
                          direction: str) -> EvolutionCandidate:
        content = candidate.content
        strategies = {
            "explore_alternatives": content + "\n\n# [MUTATED: alternative approach]\n# Consider a completely different structure...",
            "optimize": content + "\n\n# [MUTATED: optimization pass]\n# Performance and clarity improvements applied.",
            "diversify": f"# [DIVERGENT variant of {candidate.id[:8]}]\n{content[:100]}\n# ... radically different approach ...",
            "simplify": "\n".join(line for line in content.split("\n") if not line.strip().startswith("#")) if content else "# simplified",
        }
        new_content = strategies.get(direction, content)
        return EvolutionCandidate(
            content=new_content,
            source=f"mutation_heuristic_{direction}",
            parent_ids=[candidate.id],
            mutation_count=candidate.mutation_count + 1,
            generation=candidate.generation + 1,
        )

    def _heuristic_crossover(self, parent_a: EvolutionCandidate,
                              parent_b: EvolutionCandidate) -> EvolutionCandidate:
        lines_a = parent_a.content.split("\n")
        lines_b = parent_b.content.split("\n")
        split_a = len(lines_a) // 2
        split_b = len(lines_b) // 2
        crossed = "\n".join(lines_a[:split_a] + lines_b[split_b:])
        crossed += f"\n\n# [CROSSOVER: {parent_a.id[:8]} + {parent_b.id[:8]}]"
        return EvolutionCandidate(
            content=crossed,
            source="crossover_heuristic",
            parent_ids=[parent_a.id, parent_b.id],
            generation=max(parent_a.generation, parent_b.generation) + 1,
        )
