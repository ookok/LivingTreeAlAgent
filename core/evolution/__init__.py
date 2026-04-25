"""
Evolution Engine - 进化引擎
核心模块：基因突变、适者生存、交叉遗传、表观遗传
"""

from .gene_mutator import GeneMutator, MutationStrategy
from .survival_selector import SurvivalSelector, SelectionStrategy
from .crossover_engine import CrossoverEngine, CrossoverStrategy
from .evolution_logger import EvolutionLogger
from .evolution_config import EvolutionConfig
from .population import Population, Individual

__all__ = [
    'GeneMutator',
    'MutationStrategy',
    'SurvivalSelector',
    'SelectionStrategy',
    'CrossoverEngine',
    'CrossoverStrategy',
    'EvolutionLogger',
    'EvolutionConfig',
    'Population',
    'Individual',
]

__version__ = '0.1.0'
