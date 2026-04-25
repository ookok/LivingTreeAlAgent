"""
交叉遗传引擎 - 实现多种交叉策略
"""

from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import random
import numpy as np

from .population import Individual
from .evolution_config import EvolutionConfig


class CrossoverStrategy(Enum):
    """交叉策略"""
    SINGLE_POINT = "single_point"       # 单点交叉
    TWO_POINT = "two_point"            # 两点交叉
    MULTI_POINT = "multi_point"        # 多点交叉
    UNIFORM = "uniform"               # 均匀交叉
    ARITHMETIC = "arithmetic"         # 算术交叉
    BLX_ALPHA = "blx_alpha"            # BLX-α 交叉
    SIMULATED_BINARY = "sbx"           # 模拟二进制交叉 (SBX)


@dataclass
class CrossoverResult:
    """交叉结果"""
    parent1: Individual
    parent2: Individual
    offspring1: Individual
    offspring2: Individual
    crossover_points: List[int]
    success: bool = True


class CrossoverEngine:
    """
    交叉遗传引擎
    
    实现多种交叉策略，用于组合父母的优秀基因
    """
    
    def __init__(self, config: EvolutionConfig):
        self.config = config
        
    def crossover(self, parent1: Individual, parent2: Individual,
                 strategy: CrossoverStrategy = CrossoverStrategy.UNIFORM,
                 alpha: float = 0.5) -> CrossoverResult:
        """
        对两个个体进行交叉
        
        Args:
            parent1: 第一个父本
            parent2: 第二个父本
            strategy: 交叉策略
            alpha: 混合参数
            
        Returns:
            CrossoverResult: 交叉结果
        """
        # 根据策略进行交叉
        if strategy == CrossoverStrategy.SINGLE_POINT:
            offspring1_genes, offspring2_genes, points = self._single_point_crossover(
                parent1.genes, parent2.genes
            )
        elif strategy == CrossoverStrategy.TWO_POINT:
            offspring1_genes, offspring2_genes, points = self._two_point_crossover(
                parent1.genes, parent2.genes
            )
        elif strategy == CrossoverStrategy.MULTI_POINT:
            offspring1_genes, offspring2_genes, points = self._multi_point_crossover(
                parent1.genes, parent2.genes
            )
        elif strategy == CrossoverStrategy.UNIFORM:
            offspring1_genes, offspring2_genes, points = self._uniform_crossover(
                parent1.genes, parent2.genes
            )
        elif strategy == CrossoverStrategy.ARITHMETIC:
            offspring1_genes, offspring2_genes, points = self._arithmetic_crossover(
                parent1.genes, parent2.genes, alpha
            )
        elif strategy == CrossoverStrategy.BLX_ALPHA:
            offspring1_genes, offspring2_genes, points = self._blx_alpha_crossover(
                parent1.genes, parent2.genes, alpha
            )
        elif strategy == CrossoverStrategy.SIMULATED_BINARY:
            offspring1_genes, offspring2_genes, points = self._sbx_crossover(
                parent1.genes, parent2.genes
            )
        else:
            offspring1_genes, offspring2_genes, points = self._uniform_crossover(
                parent1.genes, parent2.genes
            )
            
        # 创建后代
        offspring1 = Individual(genes=offspring1_genes)
        offspring2 = Individual(genes=offspring2_genes)
        
        return CrossoverResult(
            parent1=parent1,
            parent2=parent2,
            offspring1=offspring1,
            offspring2=offspring2,
            crossover_points=points,
        )
    
    def crossover_population(self, parents: List[Individual],
                            strategy: CrossoverStrategy = CrossoverStrategy.UNIFORM) -> List[Individual]:
        """
        对种群进行批量交叉
        
        Args:
            parents: 父本列表
            strategy: 交叉策略
            
        Returns:
            后代列表
        """
        offspring = []
        
        # 随机配对
        random.shuffle(parents)
        
        for i in range(0, len(parents) - 1, 2):
            # 根据交叉率决定是否交叉
            if random.random() < self.config.crossover_rate:
                result = self.crossover(parents[i], parents[i + 1], strategy)
                offspring.append(result.offspring1)
                offspring.append(result.offspring2)
            else:
                # 不交叉直接复制
                offspring.append(parents[i].copy())
                offspring.append(parents[i + 1].copy())
                
        return offspring
    
    def _single_point_crossover(self, genes1: np.ndarray, genes2: np.ndarray) -> Tuple[np.ndarray, np.ndarray, List[int]]:
        """单点交叉"""
        point = random.randint(1, len(genes1) - 1)
        
        offspring1 = np.concatenate([genes1[:point], genes2[point:]])
        offspring2 = np.concatenate([genes2[:point], genes1[point:]])
        
        return offspring1, offspring2, [point]
    
    def _two_point_crossover(self, genes1: np.ndarray, genes2: np.ndarray) -> Tuple[np.ndarray, np.ndarray, List[int]]:
        """两点交叉"""
        points = sorted(random.sample(range(1, len(genes1)), 2))
        
        offspring1 = np.concatenate([
            genes1[:points[0]],
            genes2[points[0]:points[1]],
            genes1[points[1]:]
        ])
        offspring2 = np.concatenate([
            genes2[:points[0]],
            genes1[points[0]:points[1]],
            genes2[points[1]:]
        ])
        
        return offspring1, offspring2, points
    
    def _multi_point_crossover(self, genes1: np.ndarray, genes2: np.ndarray,
                              num_points: int = 3) -> Tuple[np.ndarray, np.ndarray, List[int]]:
        """多点交叉"""
        points = sorted(random.sample(range(1, len(genes1)), min(num_points, len(genes1) - 1)))
        
        offspring1_genes = []
        offspring2_genes = []
        current = 0
        use_parent1_for_offspring1 = True
        
        for point in points + [len(genes1)]:
            if use_parent1_for_offspring1:
                offspring1_genes.extend(genes1[current:point])
                offspring2_genes.extend(genes2[current:point])
            else:
                offspring1_genes.extend(genes2[current:point])
                offspring2_genes.extend(genes1[current:point])
            current = point
            use_parent1_for_offspring1 = not use_parent1_for_offspring1
            
        return np.array(offspring1_genes), np.array(offspring2_genes), points
    
    def _uniform_crossover(self, genes1: np.ndarray, genes2: np.ndarray,
                          swap_prob: float = 0.5) -> Tuple[np.ndarray, np.ndarray, List[int]]:
        """均匀交叉"""
        mask = np.random.random(len(genes1)) < swap_prob
        
        offspring1 = np.where(mask, genes1, genes2)
        offspring2 = np.where(mask, genes2, genes1)
        
        return offspring1, offspring2, list(np.where(mask)[0])
    
    def _arithmetic_crossover(self, genes1: np.ndarray, genes2: np.ndarray,
                             alpha: float = 0.5) -> Tuple[np.ndarray, np.ndarray, List[int]]:
        """算术交叉"""
        offspring1 = alpha * genes1 + (1 - alpha) * genes2
        offspring2 = (1 - alpha) * genes1 + alpha * genes2
        
        return offspring1, offspring2, list(range(len(genes1)))
    
    def _blx_alpha_crossover(self, genes1: np.ndarray, genes2: np.ndarray,
                           alpha: float = 0.5) -> Tuple[np.ndarray, np.ndarray, List[int]]:
        """BLX-α 交叉"""
        min_genes = np.minimum(genes1, genes2)
        max_genes = np.maximum(genes1, genes2)
        
        # 扩展区间
        extension = alpha * (max_genes - min_genes)
        lower = min_genes - extension
        upper = max_genes + extension
        
        offspring1 = np.random.uniform(lower, upper)
        offspring2 = np.random.uniform(lower, upper)
        
        # 确保在边界内
        offspring1 = np.clip(offspring1, self.config.gene_min, self.config.gene_max)
        offspring2 = np.clip(offspring2, self.config.gene_min, self.config.gene_max)
        
        return offspring1, offspring2, list(range(len(genes1)))
    
    def _sbx_crossover(self, genes1: np.ndarray, genes2: np.ndarray,
                      eta: float = 20.0) -> Tuple[np.ndarray, np.ndarray, List[int]]:
        """模拟二进制交叉 (SBX)"""
        size = len(genes1)
        offspring1 = np.zeros(size)
        offspring2 = np.zeros(size)
        
        for i in range(size):
            if random.random() < 0.5:
                if abs(genes1[i] - genes2[i]) > 1e-10:
                    if genes1[i] < genes2[i]:
                        y1, y2 = genes1[i], genes2[i]
                    else:
                        y1, y2 = genes2[i], genes1[i]
                        
                    # SBX 公式
                    rand = random.random()
                    beta = 1.0 + (2.0 * (y1 - self.config.gene_min) / (y2 - y1))
                    alpha = 2.0 - beta ** (-(eta + 1.0))
                    
                    if rand <= (1.0 / alpha):
                        betaq = (rand * alpha) ** (1.0 / (eta + 1.0))
                    else:
                        betaq = (1.0 / (2.0 - rand * alpha)) ** (1.0 / (eta + 1.0))
                        
                    child1 = 0.5 * ((y1 + y2) - betaq * (y2 - y1))
                    child2 = 0.5 * ((y1 + y2) + betaq * (y2 - y1))
                    
                    offspring1[i] = child1
                    offspring2[i] = child2
                else:
                    offspring1[i] = genes1[i]
                    offspring2[i] = genes2[i]
            else:
                offspring1[i] = genes1[i]
                offspring2[i] = genes2[i]
                
        # 确保在边界内
        offspring1 = np.clip(offspring1, self.config.gene_min, self.config.gene_max)
        offspring2 = np.clip(offspring2, self.config.gene_min, self.config.gene_max)
        
        return offspring1, offspring2, list(range(size))
