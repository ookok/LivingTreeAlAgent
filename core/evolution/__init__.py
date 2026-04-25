"""
Evolution Engine - 进化引擎
核心模块：基因突变、适者生存、交叉遗传、表观遗传、多目标优化、自适应进化
"""

from .gene_mutator import GeneMutator, MutationStrategy
from .survival_selector import SurvivalSelector, SelectionStrategy
from .crossover_engine import CrossoverEngine, CrossoverStrategy
from .evolution_logger import EvolutionLogger
from .evolution_config import EvolutionConfig
from .population import Population, Individual
from .nsga2_engine import NSGA2Engine, Individual as NSGAIndividual
from .adaptive_evolution import AdaptiveEvolutionEngine, EvolutionState, AdaptationStrategy
from .visual_evolution_engine import VisualEvolutionEngine, ParameterTuner, ABTestFramework, SelfDiagnosis, GeneType, Gene, Chromosome
from .epigenetic import EpigeneticEngine, LamarckianLearner, BaldwinianLearner

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
    'NSGA2Engine',
    'NSGAIndividual',
    'AdaptiveEvolutionEngine',
    'EvolutionState',
    'AdaptationStrategy',
    'VisualEvolutionEngine',
    'ParameterTuner',
    'ABTestFramework',
    'SelfDiagnosis',
    'GeneType',
    'Gene',
    'Chromosome',
    'EpigeneticEngine',
    'LamarckianLearner',
    'BaldwinianLearner',
]

__version__ = '2.1.0'
