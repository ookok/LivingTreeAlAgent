"""
种群管理 - 个体和种群数据结构
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
import numpy as np
import random


@dataclass
class Individual:
    """
    个体 - 进化算法中的单个解决方案
    
    Attributes:
        genes: 基因列表（解决方案参数）
        fitness: 适应度值（越高越好）
        age: 年龄（代数）
        mutations: 突变历史
        learned_adjustments: 学习调整
        metadata: 元数据
    """
    genes: np.ndarray
    fitness: float = 0.0
    age: int = 0
    mutations: List[Dict[str, Any]] = field(default_factory=list)
    learned_adjustments: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def id(self) -> str:
        """生成唯一ID"""
        return f"ind_{hash(tuple(self.genes)) % 100000:05d}"
    
    def copy(self) -> 'Individual':
        """创建深拷贝"""
        return Individual(
            genes=self.genes.copy(),
            fitness=self.fitness,
            age=self.age,
            mutations=self.mutations.copy(),
            learned_adjustments=self.learned_adjustments.copy() if self.learned_adjustments is not None else None,
            metadata=self.metadata.copy(),
        )
    
    def get_effective_genes(self) -> np.ndarray:
        """获取有效基因（考虑表观遗传调整）"""
        if self.learned_adjustments is not None:
            return self.genes + self.learned_adjustments
        return self.genes
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'genes': self.genes.tolist(),
            'fitness': self.fitness,
            'age': self.age,
            'mutations_count': len(self.mutations),
        }


@dataclass
class Population:
    """
    种群 - 进化算法中的个体集合
    
    Attributes:
        individuals: 个体列表
        generation: 当前代数
        config: 进化配置
        history: 历史记录
    """
    individuals: List[Individual] = field(default_factory=list)
    generation: int = 0
    config: Optional['EvolutionConfig'] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def size(self) -> int:
        """种群大小"""
        return len(self.individuals)
    
    @property
    def best(self) -> Optional[Individual]:
        """最优个体"""
        if not self.individuals:
            return None
        return max(self.individuals, key=lambda x: x.fitness)
    
    @property
    def average_fitness(self) -> float:
        """平均适应度"""
        if not self.individuals:
            return 0.0
        return sum(ind.fitness for ind in self.individuals) / len(self.individuals)
    
    @property
    def fitness_variance(self) -> float:
        """适应度方差"""
        if not self.individuals:
            return 0.0
        fitnesses = [ind.fitness for ind in self.individuals]
        return np.var(fitnesses)
    
    def initialize_random(self, config: 'EvolutionConfig'):
        """随机初始化种群"""
        self.config = config
        self.individuals = []
        
        for _ in range(config.population_size):
            genes = np.random.uniform(
                config.gene_min, 
                config.gene_max, 
                config.individual_dimensions
            )
            self.individuals.append(Individual(genes=genes))
            
    def initialize_from_seeds(self, seeds: List[np.ndarray]):
        """从种子初始化"""
        self.individuals = []
        
        for genes in seeds:
            self.individuals.append(Individual(genes=genes.copy()))
            
        # 填充随机个体
        if self.config:
            while len(self.individuals) < self.config.population_size:
                genes = np.random.uniform(
                    self.config.gene_min,
                    self.config.gene_max,
                    self.config.individual_dimensions
                )
                self.individuals.append(Individual(genes=genes))
                
    def select_elite(self, ratio: float) -> List[Individual]:
        """选择精英个体"""
        sorted_individuals = sorted(
            self.individuals, 
            key=lambda x: x.fitness, 
            reverse=True
        )
        elite_count = max(1, int(len(self.individuals) * ratio))
        return sorted_individuals[:elite_count]
    
    def add_history(self):
        """记录历史"""
        if self.history is None:
            self.history = []
            
        self.history.append({
            'generation': self.generation,
            'best_fitness': self.best.fitness if self.best else 0,
            'average_fitness': self.average_fitness,
            'variance': self.fitness_variance,
            'population_size': self.size,
        })
        
    def is_converged(self, threshold: float) -> bool:
        """检查是否收敛"""
        if len(self.history) < 5:
            return False
            
        recent_best = [h['best_fitness'] for h in self.history[-5:]]
        return max(recent_best) - min(recent_best) < threshold
    
    def is_stagnant(self, limit: int) -> bool:
        """检查是否停滞"""
        if len(self.history) < limit:
            return False
            
        recent_best = [h['best_fitness'] for h in self.history[-limit:]]
        return len(set([round(f, 6) for f in recent_best])) == 1
