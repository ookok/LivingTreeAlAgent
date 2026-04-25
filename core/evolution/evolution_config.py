"""
进化配置 - Evolution Engine 配置管理
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import os


@dataclass
class EvolutionConfig:
    """
    进化引擎配置
    
    控制进化算法的各种参数
    """
    # === 种群配置 ===
    population_size: int = 50              # 种群大小
    individual_dimensions: int = 10        # 个体维度（参数数量）
    gene_min: float = -10.0                # 基因最小值
    gene_max: float = 10.0                 # 基因最大值
    
    # === 变异配置 ===
    mutation_rate: float = 0.1            # 变异率
    mutation_strength: float = 0.5         # 变异强度
    elite_ratio: float = 0.1               # 精英比例（保留最优个体）
    
    # === 交叉配置 ===
    crossover_rate: float = 0.7            # 交叉率
    crossover_strategy: str = "uniform"     # 交叉策略: uniform, single_point, multi_point
    
    # === 选择配置 ===
    selection_strategy: str = "tournament" # 选择策略: tournament, roulette, rank
    tournament_size: int = 3              # 锦标赛大小
    selection_pressure: float = 1.5       # 选择压力
    
    # === 进化配置 ===
    max_generations: int = 100            # 最大代数
    convergence_threshold: float = 1e-6   # 收敛阈值
    stagnation_limit: int = 20            # 停滞代数限制
    
    # === 表观遗传配置 ===
    epigenetic_enabled: bool = True       # 是否启用表观遗传
    lamarckian_rate: float = 0.3          # 拉马克比率（学习获得性状）
    baldwin_rate: float = 0.2             # 鲍德温比率（学习影响适应度）
    
    # === 环境配置 ===
    environment_variance: float = 0.1     # 环境变化方差
    non_stationary: bool = False          # 非平稳环境
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'EvolutionConfig':
        """从字典创建配置"""
        return cls(**{k: v for k, v in config.items() if k in cls.__annotations__})
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'population_size': self.population_size,
            'individual_dimensions': self.individual_dimensions,
            'gene_min': self.gene_min,
            'gene_max': self.gene_max,
            'mutation_rate': self.mutation_rate,
            'mutation_strength': self.mutation_strength,
            'elite_ratio': self.elite_ratio,
            'crossover_rate': self.crossover_rate,
            'crossover_strategy': self.crossover_strategy,
            'selection_strategy': self.selection_strategy,
            'tournament_size': self.tournament_size,
            'epigenetic_enabled': self.epigenetic_enabled,
            'non_stationary': self.non_stationary,
        }
    
    def validate(self) -> bool:
        """验证配置合法性"""
        if self.population_size < 2:
            return False
        if not (0 <= self.mutation_rate <= 1):
            return False
        if not (0 <= self.crossover_rate <= 1):
            return False
        if self.gene_min >= self.gene_max:
            return False
        return True
    
    @classmethod
    def fast_config(cls) -> 'EvolutionConfig':
        """快速配置（适用于简单问题）"""
        return cls(
            population_size=20,
            individual_dimensions=5,
            max_generations=50,
            mutation_rate=0.2,
        )
    
    @classmethod
    def robust_config(cls) -> 'EvolutionConfig':
        """稳健配置（适用于复杂问题）"""
        return cls(
            population_size=100,
            individual_dimensions=50,
            max_generations=200,
            mutation_rate=0.05,
            elite_ratio=0.2,
        )
