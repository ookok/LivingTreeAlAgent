"""Latent Skill Graph — AI-native skill representation, retrieval, and evolution.

Key insight: Skills don't need to be human-readable. They need to be
maximally useful to LLMs. Latent representations achieve this:
  - Compressed semantic vectors instead of verbose text
  - Vector similarity retrieval instead of keyword matching
  - Evolutionary optimization in latent space

Three components:
  1. LatentSkill — compact embedding-based representation
  2. LatentGraph — skills connected by learned relationships
  3. SkillDNA — evolutionary optimization of latent skill vectors
"""

from __future__ import annotations

import hashlib
import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# Part 1: Latent Skill — pure vector representation
# ═══════════════════════════════════════════════════════

@dataclass
class LatentSkill:
    """A skill represented entirely as a latent vector.

    No human-readable text. Pure continuous representation.
    LLMs decode it through vector similarity + context injection.
    """
    id: str
    embedding: list[float]       # Dense latent representation (128-512 dims)
    task_domain: str = "general"  # "code", "reasoning", "planning", "search"
    fitness: float = 0.5          # Quality score [0, 1]
    usage_count: int = 0
    generation: int = 0           # Evolution generation
    parent_ids: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    @property
    def dim(self) -> int:
        return len(self.embedding)

    def similarity(self, other: LatentSkill) -> float:
        """Cosine similarity between two skills."""
        return cosine_sim(self.embedding, other.embedding)

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "embedding": self.embedding,
            "task_domain": self.task_domain,
            "fitness": self.fitness,
            "usage_count": self.usage_count,
            "generation": self.generation,
            "parent_ids": self.parent_ids,
            "created_at": self.created_at,
        }

    @staticmethod
    def deserialize(data: dict) -> LatentSkill:
        return LatentSkill(**data)


# ═══════════════════════════════════════════════════════
# Part 2: Latent Skill Graph — connected by learned relationships
# ═══════════════════════════════════════════════════════

@dataclass
class LatentEdge:
    """A learned relationship between two skills."""
    source_id: str
    target_id: str
    strength: float = 0.5        # How strongly related
    relation_type: str = "composes"  # "composes", "contradicts", "enhances", "specializes"


class LatentSkillGraph:
    """Skills as nodes, learned relationships as edges.

    Retrieval: query embedding → find nearest neighbors → traverse edges
    to find compositionally related skills.
    """

    def __init__(self, dim: int = 128):
        self._skills: dict[str, LatentSkill] = {}
        self._edges: dict[str, list[LatentEdge]] = defaultdict(list)
        self.dim = dim

    def add_skill(self, skill: LatentSkill) -> None:
        """Add a skill to the graph."""
        self._skills[skill.id] = skill

    def add_edge(self, source: str, target: str, strength: float = 0.5,
                 rel_type: str = "composes") -> None:
        """Learn a relationship between two skills."""
        if source in self._skills and target in self._skills:
            self._edges[source].append(LatentEdge(source, target, strength, rel_type))

    def query(self, query_embedding: list[float], top_k: int = 5) -> list[LatentSkill]:
        """Find nearest skills by vector similarity.

        Pure latent retrieval — no keywords, no text matching.
        """
        if not self._skills:
            return []

        scored = [
            (cosine_sim(query_embedding, skill.embedding), skill)
            for skill in self._skills.values()
        ]
        scored.sort(key=lambda x: -x[0])
        return [skill for _, skill in scored[:top_k]]

    def traverse(self, start_id: str, depth: int = 2) -> list[tuple[LatentSkill, float]]:
        """Traverse skill graph from a starting skill.

        Returns skills reachable within `depth` hops, with accumulated
        edge strength as relevance weight.
        """
        visited = {}
        queue = [(start_id, 1.0, 0)]

        while queue:
            current_id, weight, current_depth = queue.pop(0)

            if current_id in visited and visited[current_id] >= weight:
                continue
            visited[current_id] = weight

            if current_depth >= depth:
                continue

            for edge in self._edges.get(current_id, []):
                decayed_weight = weight * edge.strength * 0.8  # Decay per hop
                queue.append((edge.target_id, decayed_weight, current_depth + 1))

        return [
            (self._skills[sid], w)
            for sid, w in visited.items()
            if sid in self._skills and sid != start_id
        ]

    def to_prompt_injection(self, query_embedding: list[float], top_k: int = 3) -> str:
        """Compile retrieved skills into a compact prompt for LLM injection.

        The LLM gets latent skill information without verbose text.
        Format: structured key-value pairs optimized for LLM parsing.
        """
        nearest = self.query(query_embedding, top_k)
        if not nearest:
            return ""

        lines = ["[Latent Skills — contextually active]"]
        for i, skill in enumerate(nearest):
            # Compact representation: no human-readable description needed
            hash_short = skill.id[:8]
            lines.append(
                f"  SKILL_{i}: fitness={skill.fitness:.2f} "
                f"domain={skill.task_domain} gen={skill.generation} "
                f"usage={skill.usage_count} id={hash_short}"
            )

        return "\n".join(lines)

    @property
    def size(self) -> int:
        return len(self._skills)

    def snapshot(self) -> dict:
        return {
            "skills": {sid: s.serialize() for sid, s in self._skills.items()},
            "edges": {sid: [{"target": e.target_id, "strength": e.strength,
                             "type": e.relation_type} for e in edges]
                      for sid, edges in self._edges.items()},
        }

    @staticmethod
    def from_snapshot(data: dict) -> LatentSkillGraph:
        g = LatentSkillGraph()
        for sid, sdata in data.get("skills", {}).items():
            g._skills[sid] = LatentSkill.deserialize(sdata)
        for sid, edges in data.get("edges", {}).items():
            for edge in edges:
                g._edges[sid].append(LatentEdge(
                    sid, edge["target"], edge["strength"], edge.get("type", "composes")
                ))
        return g


# ═══════════════════════════════════════════════════════
# Part 3: SkillDNA — evolutionary optimization
# ═══════════════════════════════════════════════════════

class SkillDNA:
    """Evolutionary optimization of skill vectors in latent space.

    Genetic algorithm over latent skill representations:
      1. Initialize population of random latent vectors
      2. Evaluate fitness against real task outcomes
      3. Select top performers (tournament selection)
      4. Crossover: blend parent vectors
      5. Mutate: add Gaussian noise
      6. Repeat → skills evolve toward higher fitness

    No human ever sees or writes these representations.
    AI optimizes for AI — pure latent space evolution.
    """

    def __init__(self, graph: LatentSkillGraph, dim: int = 128,
                 population_size: int = 50, mutation_rate: float = 0.1):
        self.graph = graph
        self.dim = dim
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self._generation = 0

    def initialize_population(self, domain: str = "general", n: int = None) -> list[LatentSkill]:
        """Create initial random latent skill vectors."""
        n = n or self.population_size
        population = []
        for i in range(n):
            embedding = [random.gauss(0, 0.1) for _ in range(self.dim)]
            # Normalize to unit sphere
            norm = math.sqrt(sum(x * x for x in embedding))
            embedding = [x / max(1e-9, norm) for x in embedding]

            skill = LatentSkill(
                id=f"dna_{self._generation}_{i}_{random.randint(1000, 9999)}",
                embedding=embedding,
                task_domain=domain,
                generation=self._generation,
            )
            self.graph.add_skill(skill)
            population.append(skill)
        return population

    def evaluate_fitness(self, skill: LatentSkill, reward: float) -> None:
        """Update fitness based on real task outcome.

        Called after the skill was used in actual execution.
        reward > 0: skill helped, reward < 0: skill hurt.
        """
        alpha = 0.2  # Learning rate
        skill.fitness = (1 - alpha) * skill.fitness + alpha * (0.5 + 0.5 * min(1.0, max(-1.0, reward)))
        skill.usage_count += 1

    def evolve_generation(self, population: list[LatentSkill]) -> list[LatentSkill]:
        """Run one generation of evolution.

        1. Tournament selection (top 50%)
        2. Crossover (blend parents)
        3. Mutation (noise injection)
        4. Build new population
        """
        self._generation += 1

        # Sort by fitness
        population.sort(key=lambda s: -s.fitness)
        elite_count = max(2, len(population) // 5)  # Top 20% survive

        # Keep elites
        new_population = population[:elite_count]

        # Generate offspring until we reach population_size
        while len(new_population) < self.population_size:
            # Tournament selection: pick 2 parents
            parent1 = self._tournament_select(population)
            parent2 = self._tournament_select(population)

            # Crossover
            child_embedding = self._crossover(parent1.embedding, parent2.embedding)

            # Mutation
            child_embedding = self._mutate(child_embedding)

            # Normalize
            norm = math.sqrt(sum(x * x for x in child_embedding))
            child_embedding = [x / max(1e-9, norm) for x in child_embedding]

            child = LatentSkill(
                id=f"dna_{self._generation}_{len(new_population)}_{random.randint(1000, 9999)}",
                embedding=child_embedding,
                task_domain=parent1.task_domain,
                generation=self._generation,
                parent_ids=[parent1.id, parent2.id],
                fitness=(parent1.fitness + parent2.fitness) / 2 * random.uniform(0.9, 1.1),
            )
            self.graph.add_skill(child)
            new_population.append(child)

        logger.info(
            f"SkillDNA gen {self._generation}: "
            f"best_fitness={new_population[0].fitness:.3f}, "
            f"avg_fitness={sum(s.fitness for s in new_population)/len(new_population):.3f}, "
            f"population={len(new_population)}"
        )

        return new_population

    def _tournament_select(self, population: list[LatentSkill], k: int = 3) -> LatentSkill:
        """Tournament selection: pick k random, return best."""
        candidates = random.sample(population, min(k, len(population)))
        return max(candidates, key=lambda s: s.fitness)

    def _crossover(self, a: list[float], b: list[float]) -> list[float]:
        """Blend crossover: weighted average of parent vectors."""
        alpha = random.random()  # Random blend ratio
        return [alpha * a[i] + (1 - alpha) * b[i] for i in range(len(a))]

    def _mutate(self, embedding: list[float]) -> list[float]:
        """Gaussian mutation with adaptive rate."""
        return [
            x + (random.gauss(0, self.mutation_rate) if random.random() < self.mutation_rate else 0)
            for x in embedding
        ]

    @property
    def generation(self) -> int:
        return self._generation


# ═══════════════════════════════════════════════════════
# Part 4: Latent Skill Encoder — text → latent → execution
# ═══════════════════════════════════════════════════════

class LatentSkillEncoder:
    """Bridge between text queries and latent skill representations.

    Converts: user query → query embedding → latent skill retrieval →
    compact prompt injection → LLM execution → fitness feedback → evolution.

    This is the full cycle: text enters, latent skills picked, AI executes,
    fitness flows back to evolve skills for next time.
    """

    def __init__(self, dim: int = 128):
        self.graph = LatentSkillGraph(dim)
        self.dna = SkillDNA(self.graph, dim)
        self._population: list[LatentSkill] = []

    def warm_start(self) -> None:
        """Initialize skill population from seed domains."""
        domains = ["code", "reasoning", "planning", "search", "chat"]
        for domain in domains:
            seeds = self.dna.initialize_population(domain, n=10)
            self._population.extend(seeds)

    def encode(self, query: str) -> dict:
        """Encode a text query into latent skill retrieval.

        Args:
            query: User's natural language input.

        Returns:
            Dict with prompt injection and matched skills.
        """
        # Convert query to pseudo-embedding via hash trick
        # In production: use actual text encoder (e.g., sentence-transformers)
        query_emb = self._text_to_pseudo_embedding(query)

        # Retrieve nearest skills
        matched = self.graph.query(query_emb, top_k=3)

        # Build prompt injection
        injection = self.graph.to_prompt_injection(query_emb, top_k=3)

        return {
            "matched_skills": [s.id[:8] for s in matched],
            "best_fitness": matched[0].fitness if matched else 0.5,
            "prompt_injection": injection,
            "query_embedding_dim": len(query_emb),
        }

    def feedback(self, skill_id: str, reward: float) -> None:
        """Feed execution outcome back to evolve the skill.

        Positive reward = skill helped. Negative = skill hurt.
        This drives SkillDNA evolution — skills that help survive and reproduce.
        """
        skill = self.graph._skills.get(skill_id)
        if skill:
            self.dna.evaluate_fitness(skill, reward)

        # Auto-evolve every 100 evaluations
        if sum(s.usage_count for s in self._population) % 100 == 0 and self._population:
            self._population = self.dna.evolve_generation(self._population)

    def _text_to_pseudo_embedding(self, text: str) -> list[float]:
        """Quick pseudo-embedding via deterministic hashing.

        In production, replace with actual text encoder.
        This is sufficient for prototyping the full pipeline.
        """
        # Hash-based: each char contributes to a hash bucket
        dim = self.graph.dim
        embedding = [0.0] * dim

        for i, ch in enumerate(text):
            bucket = hash(ch + str(i)) % dim
            embedding[bucket] += 1.0

        # Normalize
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding


# ═══════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════

def cosine_sim(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(a[i] * b[i] for i in range(len(a)))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Singleton ──

_encoder: Optional[LatentSkillEncoder] = None


def get_latent_encoder(dim: int = 128) -> LatentSkillEncoder:
    global _encoder
    if _encoder is None:
        _encoder = LatentSkillEncoder(dim)
        _encoder.warm_start()
    return _encoder
