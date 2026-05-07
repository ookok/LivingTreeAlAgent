"""ThinkingEvolution — LLM-driven genetic optimization over code/solutions.

Inspired by CogAlpha (§3.6): performs genetic-style optimization in natural
language space, where candidate solutions undergo mutation and crossover
operations expressed through textual prompts.

DGM-H integration: process-level metrics track token efficiency, strategy
success rates, and generation quality, feeding back into MetaMemory for
data-driven strategy selection instead of random choice.

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
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from loguru import logger
from pydantic import BaseModel, Field

from ..dna.meta_memory import get_meta_memory


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


@dataclass
class ThinkingProcessMetrics:
    """DGM-H process-level metrics for ThinkingEvolution.

    Tracks the efficiency of the evolutionary search process itself,
    not just the quality of the final solutions.
    """
    tokens_used: int = 0
    mutations: int = 0
    crossovers: int = 0
    recombinations: int = 0
    generations_run: int = 0
    candidates_evaluated: int = 0
    time_spent_ms: int = 0
    best_fitness_achieved: float = 0.0
    mutation_directions_used: list[str] = field(default_factory=list)

    @property
    def tokens_per_candidate(self) -> float:
        return round(self.tokens_used / max(self.candidates_evaluated, 1), 1)

    @property
    def fitness_improvement_per_gen(self) -> float:
        return round(self.best_fitness_achieved / max(self.generations_run, 1), 4)

    def to_dict(self) -> dict:
        return {
            "tokens_used": self.tokens_used,
            "mutations": self.mutations,
            "crossovers": self.crossovers,
            "recombinations": self.recombinations,
            "generations_run": self.generations_run,
            "candidates_evaluated": self.candidates_evaluated,
            "time_spent_ms": self.time_spent_ms,
            "best_fitness_achieved": self.best_fitness_achieved,
            "tokens_per_candidate": self.tokens_per_candidate,
            "fitness_improvement_per_gen": self.fitness_improvement_per_gen,
            "mutation_directions_used": self.mutation_directions_used,
        }


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
        self._process_metrics = ThinkingProcessMetrics()
        self._memory = get_meta_memory()

    # ── Core evolution operations ──

    async def mutate(self, candidate: EvolutionCandidate,
                     direction: str = "explore_alternatives",
                     temperature: float = 0.8) -> EvolutionCandidate:
        """Apply mutation to a candidate — slightly modify to introduce variability.

        Direction is now guided by MetaMemory success rates if not explicitly set.
        """
        if not direction:
            direction = self._memory.recommend_mutation_direction()

        self._process_metrics.mutations += 1
        self._process_metrics.mutation_directions_used.append(direction)

        if self.consciousness and hasattr(self.consciousness, 'chain_of_thought'):
            try:
                start = time.time()
                prompt = self._build_mutation_prompt(candidate, direction)
                mutated_text = await self.consciousness.chain_of_thought(
                    prompt, steps=3,
                    temperature=temperature,
                    max_tokens=4096,
                )
                elapsed_ms = int((time.time() - start) * 1000)
                tokens = len(prompt.split()) + len(mutated_text.split())
                self._process_metrics.tokens_used += tokens
                self._process_metrics.time_spent_ms += elapsed_ms

                new_candidate = EvolutionCandidate(
                    content=mutated_text,
                    source=f"mutation_{direction}",
                    parent_ids=[candidate.id],
                    mutation_count=candidate.mutation_count + 1,
                    generation=candidate.generation + 1,
                )

                self._memory.record("mutation", direction, "code",
                                    success=True, tokens_used=tokens,
                                    time_spent_ms=elapsed_ms,
                                    context={"temperature": temperature})
                logger.debug(f"Mutation: {candidate.id[:8]} → {new_candidate.id[:8]} ({direction})")
                return new_candidate
            except Exception as e:
                logger.warning(f"LLM mutation failed: {e}")
                self._memory.record("mutation", direction, "code",
                                    success=False, notes=str(e)[:100])

        # Heuristic mutation fallback
        return self._heuristic_mutate(candidate, direction)

    async def crossover(self, parent_a: EvolutionCandidate,
                        parent_b: EvolutionCandidate,
                        temperature: float = 0.9) -> EvolutionCandidate:
        """Crossover two candidates — combine their best traits into a hybrid."""
        self._process_metrics.crossovers += 1

        if self.consciousness and hasattr(self.consciousness, 'chain_of_thought'):
            try:
                start = time.time()
                prompt = self._build_crossover_prompt(parent_a, parent_b)
                crossed_text = await self.consciousness.chain_of_thought(
                    prompt, steps=4,
                    temperature=temperature,
                    max_tokens=4096,
                )
                elapsed_ms = int((time.time() - start) * 1000)
                tokens = len(prompt.split()) + len(crossed_text.split())
                self._process_metrics.tokens_used += tokens
                self._process_metrics.time_spent_ms += elapsed_ms
                new_candidate = EvolutionCandidate(
                    content=crossed_text,
                    source="crossover",
                    parent_ids=[parent_a.id, parent_b.id],
                    generation=max(parent_a.generation, parent_b.generation) + 1,
                )
                self._memory.record("crossover", "fuse_parents", "code",
                                    success=True, tokens_used=tokens,
                                    time_spent_ms=elapsed_ms)
                logger.debug(f"Crossover: {parent_a.id[:8]} + {parent_b.id[:8]} → {new_candidate.id[:8]}")
                return new_candidate
            except Exception as e:
                logger.warning(f"LLM crossover failed: {e}")
                self._memory.record("crossover", "fuse_parents", "code",
                                    success=False, notes=str(e)[:100])

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
        gens = generations or self.max_generations
        self._population = list(initial_candidates)
        self._current_generation = 0

        total_fitness = 0.0
        best_fitness = -float("inf")

        for gen in range(gens):
            self._current_generation = gen
            self._process_metrics.generations_run += 1

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
                self._process_metrics.candidates_evaluated += len(self._population)

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

            elites = self._population[:self.elite_size]
            for elite in elites:
                self.elite_pool.add(elite)

            if self._population:
                current_best = self._population[0].fitness
                best_fitness = max(best_fitness, current_best)
                if current_best > self._process_metrics.best_fitness_achieved:
                    self._process_metrics.best_fitness_achieved = current_best
                total_fitness = sum(c.fitness for c in self._population)

            new_population = list(elites)

            while len(new_population) < self.population_size:
                if random.random() < self.crossover_rate and len(self._population) >= 2:
                    parents = random.sample(self._population, min(2, len(self._population)))
                    child = await self.crossover(parents[0], parents[1]) if len(parents) == 2 else parents[0]
                    if random.random() < self.mutation_rate:
                        direction = self._memory.recommend_mutation_direction()
                        child = await self.mutate(child, direction=direction)
                else:
                    parent = random.choice(self._population)
                    direction = self._memory.recommend_mutation_direction()
                    child = await self.mutate(parent, direction=direction)

                child.generation = gen + 1
                new_population.append(child)

            self._population = new_population[:self.population_size]
            logger.info(f"Generation {gen + 1}/{gens}: pop={len(self._population)}, "
                        f"best={best_fitness:.4f}, elites={len(elites)}")

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

    @staticmethod
    def select_best_by_prompt_echo(candidates: list[EvolutionCandidate],
                                    prompt: str = "",
                                    system_prompt: str = "") -> tuple[int, EvolutionCandidate]:
        """PromptEcho: select best candidate by zero-cost prompt-output alignment.

        Ranks candidates by QualityScorer n-gram alignment between each
        candidate's content and the original prompt. No LLM call needed.
        Returns (index, best_candidate).
        """
        from .quality_scorer import get_quality_scorer
        scorer = get_quality_scorer()
        items = [{"output": c.content, "system": system_prompt, "prompt": prompt}
                 for c in candidates]
        best_idx, best_result = scorer.select_best(items)
        return best_idx, candidates[best_idx]

    @staticmethod
    def rank_by_prompt_echo(candidates: list[EvolutionCandidate],
                             prompt: str = "",
                             system_prompt: str = "") -> list[tuple[int, EvolutionCandidate, float]]:
        """PromptEcho: rank all candidates by quality score.

        Returns list of (index, candidate, score) sorted by score descending.
        """
        from .quality_scorer import get_quality_scorer
        scorer = get_quality_scorer()
        items = [{"output": c.content, "system": system_prompt, "prompt": prompt}
                 for c in candidates]
        results = scorer.evaluate_batch(items)
        ranked = [(i, candidates[i], results[i].overall_score)
                  for i in range(len(candidates))]
        ranked.sort(key=lambda x: x[2], reverse=True)
        return ranked

    def get_population_stats(self) -> dict[str, Any]:
        return {
            "population_size": len(self._population),
            "generation": self._current_generation,
            "elite_pool_size": len(self.elite_pool.candidates),
            "avg_fitness": sum(c.fitness for c in self._population) / max(len(self._population), 1),
            "best_fitness": max((c.fitness for c in self._population), default=0),
        }

    def get_process_metrics(self) -> dict[str, Any]:
        """DGM-H: return process-level efficiency metrics."""
        return self._process_metrics.to_dict()

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
