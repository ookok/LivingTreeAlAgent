"""
适者生存筛选器 - 实现多种选择策略
"""

from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import random
import numpy as np

from .population import Individual, Population
from .evolution_config import EvolutionConfig


class SelectionStrategy(Enum):
    """选择策略"""
    TOURNAMENT = "tournament"           # 锦标赛选择
    ROULETTE = "roulette"             # 轮盘赌选择
    RANK = "rank"                     # 排名选择
    BOLTZMANN = "boltzmann"           # 玻尔兹曼选择
    SUS = "sus"                       # 随机 universal 选择


@dataclass
class SelectionResult:
    """选择结果"""
    selected: List[Individual]
    survivors: List[Individual]
    selection_pressure: float


class SurvivalSelector:
    """
    适者生存筛选器
    
    实现多种选择策略，用于选择优秀个体进行繁殖
    """
    
    def __init__(self, config: EvolutionConfig):
        self.config = config
        
    def select(self, population: Population, 
              strategy: SelectionStrategy = SelectionStrategy.TOURNAMENT,
              temperature: float = 1.0) -> SelectionResult:
        """
        选择个体进行繁殖
        
        Args:
            population: 当前种群
            strategy: 选择策略
            temperature: 温度参数（用于玻尔兹曼选择）
            
        Returns:
            SelectionResult: 选择结果
        """
        if strategy == SelectionStrategy.TOURNAMENT:
            selected = self._tournament_selection(population)
        elif strategy == SelectionStrategy.ROULETTE:
            selected = self._roulette_selection(population)
        elif strategy == SelectionStrategy.RANK:
            selected = self._rank_selection(population)
        elif strategy == SelectionStrategy.BOLTZMANN:
            selected = self._boltzmann_selection(population, temperature)
        elif strategy == SelectionStrategy.SUS:
            selected = self._sus_selection(population)
        else:
            selected = self._tournament_selection(population)
            
        return SelectionResult(
            selected=selected,
            survivors=population.select_elite(self.config.elite_ratio),
            selection_pressure=self._calculate_pressure(selected, population),
        )
    
    def select_survivors(self, parents: List[Individual],
                         offspring: List[Individual]) -> List[Individual]:
        """
        选择幸存者（从父母和后代中选择）
        
        Args:
            parents: 父母个体
            offspring: 后代个体
            
        Returns:
            幸存者列表
        """
        combined = parents + offspring
        combined.sort(key=lambda x: x.fitness, reverse=True)
        
        # 保留精英 + 竞争获胜者
        elite_count = max(1, int(self.config.population_size * self.config.elite_ratio))
        survivors = combined[:elite_count]
        
        # 用锦标赛填充剩余名额
        remaining = self.config.population_size - elite_count
        while len(survivors) < self.config.population_size:
            tournament = random.sample(combined, min(self.config.tournament_size, len(combined)))
            winner = max(tournament, key=lambda x: x.fitness)
            if winner not in survivors:
                survivors.append(winner.copy())
                
        return survivors[:self.config.population_size]
    
    def _tournament_selection(self, population: Population, 
                             k: Optional[int] = None) -> List[Individual]:
        """锦标赛选择"""
        k = k or self.config.tournament_size
        selected = []
        
        for _ in range(len(population.individuals)):
            tournament = random.sample(
                population.individuals, 
                min(k, len(population.individuals))
            )
            winner = max(tournament, key=lambda x: x.fitness)
            selected.append(winner.copy())
            
        return selected
    
    def _roulette_selection(self, population: Population) -> List[Individual]:
        """轮盘赌选择"""
        fitnesses = [max(0, ind.fitness) for ind in population.individuals]
        total_fitness = sum(fitnesses)
        
        if total_fitness == 0:
            return random.sample(population.individuals, len(population.individuals))
            
        probabilities = [f / total_fitness for f in fitnesses]
        
        selected = []
        for _ in range(len(population.individuals)):
            r = random.random()
            cumulative = 0
            for i, p in enumerate(probabilities):
                cumulative += p
                if r <= cumulative:
                    selected.append(population.individuals[i].copy())
                    break
                    
        return selected
    
    def _rank_selection(self, population: Population) -> List[Individual]:
        """排名选择"""
        sorted_individuals = sorted(
            population.individuals, 
            key=lambda x: x.fitness
        )
        
        n = len(sorted_individuals)
        # 排名权重（线性排名）
        ranks = np.arange(1, n + 1)
        probabilities = ranks / ranks.sum()
        
        selected = []
        indices = np.random.choice(n, size=n, p=probabilities)
        for idx in indices:
            selected.append(sorted_individuals[idx].copy())
            
        return selected
    
    def _boltzmann_selection(self, population: Population, temperature: float) -> List[Individual]:
        """玻尔兹曼选择"""
        fitnesses = [ind.fitness for ind in population.individuals]
        
        # 计算概率
        exp_fitness = np.exp(np.array(fitnesses) / temperature)
        probabilities = exp_fitness / exp_fitness.sum()
        
        n = len(population.individuals)
        indices = np.random.choice(n, size=n, p=probabilities)
        
        return [population.individuals[i].copy() for i in indices]
    
    def _sus_selection(self, population: Population) -> List[Individual]:
        """随机 universal 选择 (SUS)"""
        fitnesses = [max(0, ind.fitness) for ind in population.individuals]
        total_fitness = sum(fitnesses)
        
        if total_fitness == 0:
            return random.sample(population.individuals, len(population.individuals))
            
        n = len(population.individuals)
        # 等间距选择点
        pointer_distance = total_fitness / n
        start = random.uniform(0, pointer_distance)
        pointers = [start + i * pointer_distance for i in range(n)]
        
        selected = []
        cumulative = 0
        idx = 0
        
        for pointer in pointers:
            cumulative += fitnesses[idx]
            while cumulative >= pointer and idx < n - 1:
                selected.append(population.individuals[idx].copy())
                break
            else:
                if len(selected) < n:
                    selected.append(population.individuals[idx].copy())
                    
        return selected
    
    def _calculate_pressure(self, selected: List[Individual],
                           population: Population) -> float:
        """计算选择压力"""
        if not selected or not population.individuals:
            return 1.0
            
        avg_selected = sum(s.fitness for s in selected) / len(selected)
        avg_population = population.average_fitness
        
        if avg_population == 0:
            return 1.0
            
        return avg_selected / avg_population
    
    def get_selection_diversity(self, selected: List[Individual]) -> float:
        """计算选择多样性"""
        if len(selected) < 2:
            return 0.0
            
        genes_matrix = np.array([ind.genes for ind in selected])
        diversity = np.mean(np.std(genes_matrix, axis=0))
        return float(diversity)
