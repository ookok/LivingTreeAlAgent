"""
NSGA-II 多目标进化优化引擎
实现 Deb 提出的非支配排序遗传算法 II

Author: LivingTreeAI Team
Version: 2.0.0
"""

import numpy as np
from typing import List, Callable, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import random
import math


@dataclass
class Individual:
    """个体（多目标）"""
    genes: np.ndarray
    objectives: List[float] = field(default_factory=list)
    rank: int = 0           # 非支配等级
    crowding_distance: float = 0.0
    dominated_set: List[int] = field(default_factory=list)
    domination_count: int = 0
    
    def __lt__(self, other: 'Individual') -> bool:
        """用于排序：先按 rank，再按 crowding distance"""
        if self.rank != other.rank:
            return self.rank < other.rank
        return self.crowding_distance > other.crowding_distance


class NSGA2Engine:
    """
    NSGA-II 多目标进化引擎
    
    核心特性：
    - 非支配排序
    - 拥挤度距离
    - 精英保留策略
    - 自适应交叉/变异
    """
    
    def __init__(
        self,
        population_size: int = 100,
        n_objectives: int = 2,
        gene_dim: int = 10,
        gene_min: float = -10.0,
        gene_max: float = 10.0,
        crossover_rate: float = 0.9,
        mutation_rate: float = 0.1,
        mutation_strength: float = 0.1,
    ):
        self.population_size = population_size
        self.n_objectives = n_objectives
        self.gene_dim = gene_dim
        self.gene_min = gene_min
        self.gene_max = gene_max
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.mutation_strength = mutation_strength
        
        self.population: List[Individual] = []
        self.generation = 0
        self.history: List[Dict[str, Any]] = []
        
        self._objectives_func: Optional[Callable[[np.ndarray], List[float]]] = None
        
    def set_objectives_function(self, func: Callable[[np.ndarray], List[float]]) -> None:
        """设置多目标函数"""
        self._objectives_func = func
        
    def initialize_population(self) -> None:
        """初始化种群"""
        self.population = []
        for _ in range(self.population_size):
            genes = np.random.uniform(self.gene_min, self.gene_max, self.gene_dim)
            ind = Individual(genes=genes)
            self.population.append(ind)
        self._evaluate_population()
        
    def _evaluate_population(self) -> None:
        """评估种群"""
        if not self._objectives_func:
            raise ValueError("Objectives function not set")
            
        for ind in self.population:
            ind.objectives = self._objectives_func(ind.genes)
            
    def run(self, max_generations: int = 100) -> Tuple[List[Individual], List[Dict]]:
        """
        运行 NSGA-II
        
        Returns:
            Pareto 前沿个体列表, 历史记录
        """
        self.initialize_population()
        
        for gen in range(max_generations):
            self.generation = gen
            
            # 1. 创建子代
            offspring = self._create_offspring()
            
            # 2. 评估子代
            for ind in offspring:
                ind.objectives = self._objectives_func(ind.genes)
                
            # 3. 合并父代和子代
            combined = self.population + offspring
            
            # 4. 非支配排序
            fronts = self._non_dominated_sort(combined)
            
            # 5. 选择新一代
            new_population = []
            for front in fronts:
                if len(new_population) + len(front) <= self.population_size:
                    new_population.extend(front)
                else:
                    # 按拥挤度排序，选最不拥挤的
                    self._calculate_crowding_distance(front)
                    front.sort(reverse=True)
                    remaining = self.population_size - len(new_population)
                    new_population.extend(front[:remaining])
                    break
                    
            self.population = new_population
            
            # 6. 记录历史
            pareto = self.get_pareto_front()
            self.history.append({
                'generation': gen,
                'pareto_size': len(pareto),
                'pareto_spread': self._calculate_spread(pareto),
                'best_objectives': [min(ind.objectives[i] for ind in pareto) for i in range(self.n_objectives)],
            })
            
        return self.get_pareto_front(), self.history
        
    def _create_offspring(self) -> List[Individual]:
        """创建子代"""
        offspring = []
        
        while len(offspring) < self.population_size:
            # 锦标赛选择
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()
            
            # 交叉
            if random.random() < self.crossover_rate:
                child1_genes, child2_genes = self._crossover(parent1.genes, parent2.genes)
            else:
                child1_genes = parent1.genes.copy()
                child2_genes = parent2.genes.copy()
                
            # 变异
            child1_genes = self._mutate(child1_genes)
            child2_genes = self._mutate(child2_genes)
            
            offspring.append(Individual(genes=child1_genes))
            if len(offspring) < self.population_size:
                offspring.append(Individual(genes=child2_genes))
                
        return offspring
        
    def _tournament_selection(self, tournament_size: int = 2) -> Individual:
        """锦标赛选择"""
        candidates = random.sample(self.population, tournament_size)
        return min(candidates)
        
    def _crossover(self, parent1: np.ndarray, parent2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """模拟二进制交叉 (SBX)"""
        child1 = np.zeros_like(parent1)
        child2 = np.zeros_like(parent2)
        
        eta = 20  # 分布指数
        
        for i in range(len(parent1)):
            if random.random() > 0.5:
                child1[i], child2[i] = parent1[i], parent2[i]
            else:
                u = random.random()
                if u <= 0.5:
                    beta = (2 * u) ** (1 / (eta + 1))
                else:
                    beta = (1 / (2 * (1 - u))) ** (1 / (eta + 1))
                    
                child1[i] = 0.5 * ((1 + beta) * parent1[i] + (1 - beta) * parent2[i])
                child2[i] = 0.5 * ((1 - beta) * parent1[i] + (1 + beta) * parent2[i])
                
                # 边界处理
                child1[i] = np.clip(child1[i], self.gene_min, self.gene_max)
                child2[i] = np.clip(child2[i], self.gene_min, self.gene_max)
                
        return child1, child2
        
    def _mutate(self, genes: np.ndarray) -> np.ndarray:
        """多项式变异"""
        mutated = genes.copy()
        
        for i in range(len(genes)):
            if random.random() < self.mutation_rate:
                u = random.random()
                eta = 20
                
                if u <= 0.5:
                    delta = (2 * u) ** (1 / (eta + 1)) - 1
                    mutated[i] = genes[i] + delta * (genes[i] - self.gene_min)
                else:
                    delta = 1 - (2 * (1 - u)) ** (1 / (eta + 1))
                    mutated[i] = genes[i] + delta * (self.gene_max - genes[i])
                    
                mutated[i] = np.clip(mutated[i], self.gene_min, self.gene_max)
                
        return mutated
        
    def _non_dominated_sort(self, population: List[Individual]) -> List[List[Individual]]:
        """非支配排序"""
        n = len(population)
        
        # 初始化
        for i in range(n):
            population[i].dominated_set = []
            population[i].domination_count = 0
            
        # 支配关系计算
        for i in range(n):
            for j in range(n):
                if i != j:
                    if self._dominates(population[i], population[j]):
                        population[i].dominated_set.append(j)
                    elif self._dominates(population[j], population[i]):
                        population[i].domination_count += 1
                        
        # 第一前沿
        fronts = []
        current_front = []
        
        for i in range(n):
            if population[i].domination_count == 0:
                population[i].rank = 0
                current_front.append(population[i])
                
        fronts.append(current_front)
        
        # 后续前沿
        front_idx = 0
        while front_idx < len(fronts):
            next_front = []
            
            for ind in fronts[front_idx]:
                for dominated_idx in ind.dominated_set:
                    dominated_ind = population[dominated_idx]
                    dominated_ind.domination_count -= 1
                    if dominated_ind.domination_count == 0:
                        dominated_ind.rank = front_idx + 1
                        next_front.append(dominated_ind)
                        
            if next_front:
                fronts.append(next_front)
            front_idx += 1
            
        return fronts
        
    def _dominates(self, ind1: Individual, ind2: Individual) -> bool:
        """判断 ind1 是否支配 ind2"""
        better_in_all = True
        better_in_at_least_one = False
        
        for i in range(self.n_objectives):
            if ind1.objectives[i] > ind2.objectives[i]:  # 假设最小化
                return False
            if ind1.objectives[i] < ind2.objectives[i]:
                better_in_at_least_one = True
                
        return better_in_at_least_one
        
    def _calculate_crowding_distance(self, front: List[Individual]) -> None:
        """计算拥挤度距离"""
        n = len(front)
        
        for ind in front:
            ind.crowding_distance = 0.0
            
        for obj_idx in range(self.n_objectives):
            # 按当前目标排序
            front.sort(key=lambda x: x.objectives[obj_idx])
            
            # 边界个体拥挤度设为无穷
            front[0].crowding_distance = float('inf')
            front[n-1].crowding_distance = float('inf')
            
            # 计算目标范围
            obj_min = front[0].objectives[obj_idx]
            obj_max = front[n-1].objectives[obj_idx]
            
            if obj_max == obj_min:
                continue
                
            # 计算中间个体的拥挤度
            for i in range(1, n - 1):
                front[i].crowding_distance += (
                    front[i+1].objectives[obj_idx] - front[i-1].objectives[obj_idx]
                ) / (obj_max - obj_min)
                
    def _calculate_spread(self, pareto: List[Individual]) -> float:
        """计算 Pareto 前沿的分布度"""
        if len(pareto) < 2:
            return 0.0
            
        distances = []
        for i in range(len(pareto) - 1):
            dist = sum(
                (pareto[i].objectives[j] - pareto[i+1].objectives[j]) ** 2
                for j in range(self.n_objectives)
            ) ** 0.5
            distances.append(dist)
            
        return sum(distances) / len(distances) if distances else 0.0
        
    def get_pareto_front(self) -> List[Individual]:
        """获取当前 Pareto 前沿"""
        fronts = self._non_dominated_sort(self.population)
        return fronts[0] if fronts else []
        
    def get_hypervolume(self, reference_point: List[float]) -> float:
        """
        计算超体积指标 (2D 简化版)
        
        Args:
            reference_point: 参考点（最差点）
        """
        pareto = self.get_pareto_front()
        
        if self.n_objectives != 2:
            raise NotImplementedError("Hypervolume only implemented for 2D")
            
        if len(pareto) < 2:
            return 0.0
            
        # 按第一个目标排序
        pareto.sort(key=lambda x: x.objectives[0])
        
        hypervolume = 0.0
        for i in range(len(pareto) - 1):
            width = pareto[i+1].objectives[0] - pareto[i].objectives[0]
            height = reference_point[1] - pareto[i].objectives[1]
            hypervolume += width * height
            
        # 最后一个点
        width = reference_point[0] - pareto[-1].objectives[0]
        height = reference_point[1] - pareto[-1].objectives[1]
        hypervolume += width * height
        
        return hypervolume
