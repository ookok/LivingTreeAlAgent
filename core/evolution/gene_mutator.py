"""
基因突变器 - 实现多种突变策略
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import numpy as np
import random

from .population import Individual, Population
from .evolution_config import EvolutionConfig


class MutationStrategy(Enum):
    """突变策略"""
    GAUSSIAN = "gaussian"           # 高斯突变
    UNIFORM = "uniform"             # 均匀突变
    CREEP = "creep"                 # 爬坡突变
    BOUNDARY = "boundary"           # 边界突变
    NON_UNIFORM = "non_uniform"     # 非均匀突变
    ADAPTIVE = "adaptive"           # 自适应突变


@dataclass
class MutationResult:
    """突变结果"""
    original: np.ndarray
    mutated: np.ndarray
    mutation_points: List[int]
    mutation_strength: float
    success: bool = True


class GeneMutator:
    """
    基因突变器
    
    实现多种突变策略，用于产生遗传变异
    """
    
    def __init__(self, config: EvolutionConfig):
        self.config = config
        
    def mutate(self, individual: Individual, 
               strategy: MutationStrategy = MutationStrategy.GAUSSIAN,
               generation: int = 0) -> MutationResult:
        """
        对个体进行突变
        
        Args:
            individual: 要突变的个体
            strategy: 突变策略
            generation: 当前代数（用于非均匀突变）
            
        Returns:
            MutationResult: 突变结果
        """
        genes = individual.genes.copy()
        original = genes.copy()
        
        # 决定突变点位
        mutation_points = self._select_mutation_points()
        
        # 根据策略进行突变
        if strategy == MutationStrategy.GAUSSIAN:
            genes = self._gaussian_mutation(genes, mutation_points)
        elif strategy == MutationStrategy.UNIFORM:
            genes = self._uniform_mutation(genes, mutation_points)
        elif strategy == MutationStrategy.CREEP:
            genes = self._creep_mutation(genes, mutation_points)
        elif strategy == MutationStrategy.BOUNDARY:
            genes = self._boundary_mutation(genes, mutation_points)
        elif strategy == MutationStrategy.NON_UNIFORM:
            genes = self._non_uniform_mutation(genes, mutation_points, generation)
        elif strategy == MutationStrategy.ADAPTIVE:
            genes = self._adaptive_mutation(genes, mutation_points, individual.fitness)
        else:
            genes = self._gaussian_mutation(genes, mutation_points)
            
        # 确保在边界内
        genes = np.clip(genes, self.config.gene_min, self.config.gene_max)
        
        # 创建新个体
        mutated_individual = individual.copy()
        mutated_individual.genes = genes
        mutated_individual.mutations.append({
            'strategy': strategy.value,
            'points': mutation_points,
            'generation': generation,
        })
        
        return MutationResult(
            original=original,
            mutated=genes,
            mutation_points=mutation_points,
            mutation_strength=self.config.mutation_strength,
        )
    
    def mutate_population(self, population: Population,
                          strategy: MutationStrategy = MutationStrategy.GAUSSIAN,
                          generation: int = 0) -> List[Individual]:
        """
        对整个种群进行突变
        
        Args:
            population: 种群
            strategy: 突变策略
            generation: 当前代数
            
        Returns:
            突变后的个体列表
        """
        mutated = []
        
        for individual in population.individuals:
            # 根据突变率决定是否突变
            if random.random() < self.config.mutation_rate:
                result = self.mutate(individual, strategy, generation)
                mutated.append(individual.copy() if not result.success else 
                             self._create_mutated_individual(individual, result.mutated, generation))
            else:
                mutated.append(individual.copy())
                
        return mutated
    
    def _select_mutation_points(self) -> List[int]:
        """选择突变点位"""
        points = []
        for i in range(self.config.individual_dimensions):
            if random.random() < self.config.mutation_rate:
                points.append(i)
        return points if points else [random.randint(0, self.config.individual_dimensions - 1)]
    
    def _gaussian_mutation(self, genes: np.ndarray, points: List[int]) -> np.ndarray:
        """高斯突变"""
        for i in points:
            genes[i] += np.random.normal(0, self.config.mutation_strength)
        return genes
    
    def _uniform_mutation(self, genes: np.ndarray, points: List[int]) -> np.ndarray:
        """均匀突变"""
        for i in points:
            genes[i] = np.random.uniform(self.config.gene_min, self.config.gene_max)
        return genes
    
    def _creep_mutation(self, genes: np.ndarray, points: List[int]) -> np.ndarray:
        """爬坡突变（小步长变化）"""
        for i in points:
            delta = np.random.choice([-1, 1]) * self.config.mutation_strength * 0.1
            genes[i] += delta
        return genes
    
    def _boundary_mutation(self, genes: np.ndarray, points: List[int]) -> np.ndarray:
        """边界突变"""
        for i in points:
            genes[i] = np.random.choice([self.config.gene_min, self.config.gene_max])
        return genes
    
    def _non_uniform_mutation(self, genes: np.ndarray, points: List[int], 
                             generation: int) -> np.ndarray:
        """非均匀突变（随代数减小步长）"""
        b = 5  # 非均匀度参数
        for i in points:
            if random.random() < 0.5:
                delta = (self.config.gene_max - genes[i]) * (1 - random.random() ** (1 - generation / self.config.max_generations) ** b)
            else:
                delta = (genes[i] - self.config.gene_min) * (1 - random.random() ** (1 - generation / self.config.max_generations) ** b)
            genes[i] += delta
        return genes
    
    def _adaptive_mutation(self, genes: np.ndarray, points: List[int],
                          fitness: float) -> np.ndarray:
        """自适应突变（根据适应度调整步长）"""
        # 适应度越高，步长越小
        adaptive_strength = self.config.mutation_strength * (1 / (1 + fitness))
        for i in points:
            genes[i] += np.random.normal(0, adaptive_strength)
        return genes
    
    def _create_mutated_individual(self, original: Individual, 
                                  genes: np.ndarray,
                                  generation: int) -> Individual:
        """创建突变后的个体"""
        new_individual = original.copy()
        new_individual.genes = genes
        new_individual.age = 0  # 重置年龄
        new_individual.mutations.append({
            'strategy': 'default',
            'generation': generation,
        })
        return new_individual
    
    def get_mutation_diversity(self, population: Population) -> float:
        """计算种群突变多样性"""
        if len(population.individuals) < 2:
            return 0.0
            
        genes_matrix = np.array([ind.genes for ind in population.individuals])
        # 计算基因多样性（标准差的平均值）
        diversity = np.mean(np.std(genes_matrix, axis=0))
        return float(diversity)
