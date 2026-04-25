"""
实时自适应进化策略 - 修正版
根据进化状态动态调整算法参数和策略
Author: LivingTreeAI Team
Version: 2.0.0
"""

import numpy as np
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import random
import time


class AdaptationStrategy(Enum):
    """自适应策略"""
    ADAptive_MUTATION = "adaptive_mutation"
    ADAptive_CROSSOVER = "adaptive_crossover"
    ADAptive_POPULATION = "adaptive_population"
    ADAptive_SELECTION = "adaptive_selection"
    DIVERSITY_INJECTION = "diversity_injection"
    ELITISM_CONTROL = "elitism_control"


@dataclass
class EvolutionState:
    """进化状态快照"""
    generation: int
    best_fitness: float
    avg_fitness: float
    worst_fitness: float
    diversity: float
    improvement_rate: float
    stagnation_counter: int
    population_convergence: float
    fitness_variance: float
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class AdaptiveEvolutionEngine:
    """
    实时自适应进化引擎
    核心能力：
    - 实时监控进化状态
    - 自适应调整参数
    - 自动检测并处理停滞
    - 动态策略切换
    """

    def __init__(
        self,
        base_population_size: int = 100,
        min_population_size: int = 20,
        max_population_size: int = 200,
        base_mutation_rate: float = 0.1,
        base_crossover_rate: float = 0.7,
        adaptation_interval: int = 5,
        stagnation_threshold: int = 10,
        diversity_threshold: float = 0.15,
    ):
        self.base_population_size = base_population_size
        self.min_population_size = min_population_size
        self.max_population_size = max_population_size
        self.base_mutation_rate = base_mutation_rate
        self.base_crossover_rate = base_crossover_rate
        self.adaptation_interval = adaptation_interval
        self.stagnation_threshold = stagnation_threshold
        self.diversity_threshold = diversity_threshold

        self.current_population_size = base_population_size
        self.current_mutation_rate = base_mutation_rate
        self.current_crossover_rate = base_crossover_rate
        self.current_elite_ratio = 0.1

        self.state_history: List[EvolutionState] = []
        self.parameter_history: List[Dict[str, Any]] = []

        self._fitness_func: Optional[Callable[[np.ndarray], float]] = None

        self.population: List[np.ndarray] = []
        self.fitnesses: List[float] = []
        self.generation = 0

        self.strategy_weights = {
            AdaptationStrategy.ADAPTIVE_MUTATION: 1.0,
            AdaptationStrategy.ADAPTIVE_CROSSOVER: 1.0,
            AdaptationStrategy.DIVERSITY_INJECTION: 1.0,
            AdaptationStrategy.ELITISM_CONTROL: 1.0,
        }

    def set_fitness_function(self, func: Callable[[np.ndarray], float]) -> None:
        self._fitness_func = func

    def initialize_population(self, dim: int, gene_min: float = -10.0, gene_max: float = 10.0) -> None:
        self.population = []
        for _ in range(self.current_population_size):
            individual = np.random.uniform(gene_min, gene_max, dim)
            self.population.append(individual)
        self._evaluate_population()

    def _evaluate_population(self) -> None:
        if not self._fitness_func:
            raise ValueError("Fitness function not set")
        self.fitnesses = [self._fitness_func(ind) for ind in self.population]

    def evolve_generation(self) -> EvolutionState:
        """执行一代进化（带自适应）"""
        state = self._capture_state()
        self.state_history.append(state)

        if self.generation % self.adaptation_interval == 0 and self.generation > 0:
            self._adapt_parameters()

        selected = self._adaptive_selection()
        offspring = self._adaptive_crossover(selected)
        offspring = self._adaptive_mutation(offspring)
        offspring_fitnesses = [self._fitness_func(ind) for ind in offspring]
        self._environmental_selection(offspring, offspring_fitnesses)

        self.generation += 1
        return self._capture_state()

    def _capture_state(self) -> EvolutionState:
        if not self.fitnesses:
            return EvolutionState(
                generation=self.generation,
                best_fitness=0.0, avg_fitness=0.0, worst_fitness=0.0,
                diversity=1.0, improvement_rate=0.0,
                stagnation_counter=0, population_convergence=0.0,
                fitness_variance=0.0,
            )

        best = max(self.fitnesses)
        worst = min(self.fitnesses)
        avg = sum(self.fitnesses) / len(self.fitnesses)
        variance = float(np.var(self.fitnesses))

        improvement_rate = 0.0
        if len(self.state_history) >= 5:
            prev_best = self.state_history[-5].best_fitness
            if prev_best != 0:
                improvement_rate = (best - prev_best) / abs(prev_best)

        stagnation_counter = 0
        if len(self.state_history) >= 2:
            for i in range(len(self.state_history) - 1,
                           max(-1, len(self.state_history) - self.stagnation_threshold - 1), -1):
                if abs(self.state_history[i].best_fitness - best) < 1e-6:
                    stagnation_counter += 1
                else:
                    break

        diversity = self._calculate_diversity()
        population_convergence = self._calculate_convergence()

        return EvolutionState(
            generation=self.generation,
            best_fitness=best, avg_fitness=avg, worst_fitness=worst,
            diversity=diversity, improvement_rate=improvement_rate,
            stagnation_counter=stagnation_counter,
            population_convergence=population_convergence,
            fitness_variance=variance,
        )

    def _adapt_parameters(self) -> None:
        if len(self.state_history) < 2:
            return

        state = self.state_history[-1]
        self._adapt_mutation_rate(state)
        self._adapt_crossover_rate(state)
        self._adapt_elite_ratio(state)
        self._adapt_population_size(state)

        if state.diversity < self.diversity_threshold:
            self._inject_diversity()

        self.parameter_history.append({
            'generation': self.generation,
            'mutation_rate': self.current_mutation_rate,
            'crossover_rate': self.current_crossover_rate,
            'population_size': self.current_population_size,
            'elite_ratio': self.current_elite_ratio,
            'diversity': state.diversity,
            'stagnation': state.stagnation_counter,
        })

    def _adapt_mutation_rate(self, state: EvolutionState) -> None:
        if state.stagnation_counter >= self.stagnation_threshold:
            self.current_mutation_rate = min(self.current_mutation_rate * 1.5, 0.5)
        elif state.diversity < self.diversity_threshold:
            self.current_mutation_rate = min(self.current_mutation_rate * 1.3, 0.5)
        elif state.population_convergence > 0.8 and state.improvement_rate > 0.01:
            self.current_mutation_rate = max(self.current_mutation_rate * 0.8, 0.01)
        else:
            self.current_mutation_rate = (
                0.9 * self.current_mutation_rate + 0.1 * self.base_mutation_rate
            )

    def _adapt_crossover_rate(self, state: EvolutionState) -> None:
        if state.diversity < self.diversity_threshold:
            self.current_crossover_rate = min(self.current_crossover_rate * 1.1, 0.95)
        elif state.diversity > 0.5 and state.improvement_rate > 0.01:
            self.current_crossover_rate = max(self.current_crossover_rate * 0.95, 0.3)
        else:
            self.current_crossover_rate = (
                0.9 * self.current_crossover_rate + 0.1 * self.base_crossover_rate
            )

    def _adapt_elite_ratio(self, state: EvolutionState) -> None:
        if state.improvement_rate > 0.01:
            self.current_elite_ratio = min(self.current_elite_ratio * 1.1, 0.3)
        elif state.stagnation_counter >= self.stagnation_threshold:
            self.current_elite_ratio = max(self.current_elite_ratio * 0.8, 0.05)

    def _adapt_population_size(self, state: EvolutionState) -> None:
        if state.stagnation_counter >= self.stagnation_threshold and state.diversity < self.diversity_threshold:
            self.current_population_size = min(
                int(self.current_population_size * 1.2), self.max_population_size)
            self._resize_population()
        elif state.population_convergence > 0.9 and state.improvement_rate < 0.001:
            self.current_population_size = max(
                int(self.current_population_size * 0.8), self.min_population_size)
            self._resize_population()

    def _inject_diversity(self) -> None:
        n_inject = max(1, int(self.current_population_size * 0.1))
        paired = list(zip(self.population, self.fitnesses))
        paired.sort(key=lambda x: x[1])
        dim = len(self.population[0])
        for i in range(n_inject):
            if i < len(paired):
                random_ind = np.random.uniform(-10, 10, dim)
                paired[i] = (random_ind, self._fitness_func(random_ind))
        self.population = [p[0] for p in paired]
        self.fitnesses = [p[1] for p in paired]

    def _resize_population(self) -> None:
        current_size = len(self.population)
        dim = len(self.population[0]) if self.population else 10

        if self.current_population_size > current_size:
            for _ in range(self.current_population_size - current_size):
                ind = np.random.uniform(-10, 10, dim)
                self.population.append(ind)
                self.fitnesses.append(self._fitness_func(ind))
        elif self.current_population_size < current_size:
            paired = list(zip(self.population, self.fitnesses))
            paired.sort(key=lambda x: x[1], reverse=True)
            paired = paired[:self.current_population_size]
            self.population = [p[0] for p in paired]
            self.fitnesses = [p[1] for p in paired]

    def _adaptive_selection(self) -> List[np.ndarray]:
        diversity = self._calculate_diversity()
        selected = []

        if diversity < 0.2:
            tournament_size = 5
            for _ in range(self.current_population_size):
                candidates = random.sample(list(zip(self.population, self.fitnesses)), tournament_size)
                winner = max(candidates, key=lambda x: x[1])
                selected.append(winner[0].copy())
        else:
            total_fitness = sum(f for f in self.fitnesses if f > 0)
            if total_fitness == 0:
                probabilities = [1.0 / len(self.fitnesses)] * len(self.fitnesses)
            else:
                probabilities = [f / total_fitness for f in self.fitnesses]
            indices = list(range(len(self.population)))
            selected_indices = np.random.choice(indices, size=self.current_population_size, p=probabilities)
            selected = [self.population[i].copy() for i in selected_indices]

        return selected

    def _adaptive_crossover(self, parents: List[np.ndarray]) -> List[np.ndarray]:
        offspring = []
        for i in range(0, len(parents) - 1, 2):
            if random.random() < self.current_crossover_rate:
                child1, child2 = self._simulated_binary_crossover(parents[i], parents[i + 1])
                offspring.extend([child1, child2])
            else:
                offspring.extend([parents[i].copy(), parents[i + 1].copy()])
        return offspring

    def _adaptive_mutation(self, individuals: List[np.ndarray]) -> List[np.ndarray]:
        mutated = []
        for ind in individuals:
            mutated_ind = ind.copy()
            for j in range(len(ind)):
                if random.random() < self.current_mutation_rate:
                    u = random.random()
                    delta = 0.0
                    if u <= 0.5:
                        delta = (2.0 * u) ** (1.0 / 21.0) - 1.0
                    else:
                        delta = 1.0 - (2.0 * (1.0 - u)) ** (1.0 / 21.0)
                    mutated_ind[j] += delta * 20.0
                    mutated_ind[j] = np.clip(mutated_ind[j], -10.0, 10.0)
            mutated.append(mutated_ind)
        return mutated

    def _environmental_selection(self, offspring: List[np.ndarray],
                                  offspring_fitnesses: List[float]) -> None:
        combined = list(zip(self.population, self.fitnesses)) + list(zip(offspring, offspring_fitnesses))
        combined.sort(key=lambda x: x[1], reverse=True)
        n_elite = max(1, int(self.current_population_size * self.current_elite_ratio))
        elite = combined[:n_elite]
        remaining = combined[n_elite:]
        n_remaining = self.current_population_size - n_elite
        if len(remaining) >= n_remaining:
            selected_remaining = random.sample(remaining, n_remaining)
        else:
            selected_remaining = remaining
        final = elite + selected_remaining
        self.population = [f[0] for f in final]
        self.fitnesses = [f[1] for f in final]

    def _simulated_binary_crossover(self, parent1: np.ndarray,
                                    parent2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        child1 = parent1.copy()
        child2 = parent2.copy()
        eta = 20.0
        for i in range(len(parent1)):
            if random.random() < 0.5:
                u = random.random()
                beta = 0.0
                if u <= 0.5:
                    beta = (2.0 * u) ** (1.0 / (eta + 1.0))
                else:
                    beta = (1.0 / (2.0 * (1.0 - u))) ** (1.0 / (eta + 1.0))
                child1[i] = 0.5 * ((1.0 + beta) * parent1[i] + (1.0 - beta) * parent2[i])
                child2[i] = 0.5 * ((1.0 - beta) * parent1[i] + (1.0 + beta) * parent2[i])
                child1[i] = np.clip(child1[i], -10.0, 10.0)
                child2[i] = np.clip(child2[i], -10.0, 10.0)
        return child1, child2

    def _calculate_diversity(self) -> float:
        if len(self.population) < 2:
            return 1.0
        total_diff = 0.0
        count = 0
        sample_size = min(20, len(self.population))
        indices = random.sample(range(len(self.population)), sample_size)
        for i in range(sample_size):
            for j in range(i + 1, sample_size):
                diff = np.linalg.norm(self.population[indices[i]] - self.population[indices[j]])
                total_diff += diff
                count += 1
        return total_diff / count if count > 0 else 1.0

    def _calculate_convergence(self) -> float:
        if not self.fitnesses or len(self.fitnesses) < 2:
            return 0.0
        best = max(self.fitnesses)
        avg = sum(self.fitnesses) / len(self.fitnesses)
        if best == 0:
            return 0.0
        return avg / best

    def run_evolution(self, max_generations: int = 100,
                      target_fitness: Optional[float] = None) -> Dict[str, Any]:
        history = []
        for gen in range(max_generations):
            state = self.evolve_generation()
            history.append(state)
            if target_fitness and state.best_fitness >= target_fitness:
                break
            if state.stagnation_counter >= self.stagnation_threshold * 2:
                break
        return {
            'generations': self.generation,
            'best_fitness': max(self.fitnesses) if self.fitnesses else 0.0,
            'history': history,
            'parameter_history': self.parameter_history,
        }

    def get_best_individual(self) -> Tuple[np.ndarray, float]:
        if not self.fitnesses:
            raise ValueError("Population not initialized")
        best_idx = int(np.argmax(self.fitnesses))
        return self.population[best_idx], self.fitnesses[best_idx]
