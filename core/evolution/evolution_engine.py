"""
Evolution Engine - 进化引擎主类
整合突变、选择、交叉形成完整的进化循环
"""

from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass

from .evolution_config import EvolutionConfig
from .population import Population, Individual
from .gene_mutator import GeneMutator, MutationStrategy
from .survival_selector import SurvivalSelector, SelectionStrategy
from .crossover_engine import CrossoverEngine, CrossoverStrategy
from .evolution_logger import EvolutionLogger


@dataclass
class EvolutionResult:
    """进化结果"""
    best_individual: Individual
    best_fitness: float
    generations: int
    converged: bool
    final_population: List[Individual]
    history: List[Dict[str, Any]]


class EvolutionEngine:
    """
    进化引擎主类
    
    整合所有进化组件，提供完整的进化算法实现
    """
    
    def __init__(self, config: Optional[EvolutionConfig] = None):
        self.config = config or EvolutionConfig()
        self.population = Population(config=self.config)
        self.logger = EvolutionLogger()
        
        # 初始化组件
        self.mutator = GeneMutator(self.config)
        self.selector = SurvivalSelector(self.config)
        self.crossover = CrossoverEngine(self.config)
        
        # 适应度函数
        self.fitness_function: Optional[Callable] = None
        
        # 回调函数
        self.on_generation: Optional[Callable[[int, Population], None]] = None
        
    def set_fitness_function(self, func: Callable[[np.ndarray], float]):
        """
        设置适应度函数
        
        Args:
            func: 接受基因数组，返回适应度值
        """
        self.fitness_function = func
        
    def run(self, fitness_func: Callable[[np.ndarray], float],
           initial_population: Optional[List[np.ndarray]] = None) -> EvolutionResult:
        """
        运行进化算法
        
        Args:
            fitness_func: 适应度函数
            initial_population: 初始种群（可选）
            
        Returns:
            EvolutionResult: 进化结果
        """
        self.fitness_function = fitness_func
        
        # 初始化种群
        if initial_population:
            self.population.initialize_from_seeds(initial_population)
        else:
            self.population.initialize_random(self.config)
            
        # 评估初始种群
        self._evaluate_population()
        
        # 开始进化
        self.logger.start_run()
        self.population.add_history()
        
        for generation in range(self.config.max_generations):
            # 1. 选择
            selection_result = self.selector.select(
                self.population,
                strategy=SelectionStrategy[self.config.selection_strategy.upper()]
            )
            
            # 2. 交叉
            offspring = self.crossover.crossover_population(
                selection_result.selected,
                strategy=CrossoverStrategy[self.config.crossover_strategy.upper()]
            )
            
            # 3. 变异
            mutated_offspring = self.mutator.mutate_population(
                Population(individuals=offspring),
                strategy=MutationStrategy.GAUSSIAN,
                generation=generation
            )
            
            # 4. 评估后代
            temp_population = Population(individuals=mutated_offspring)
            for ind in temp_population.individuals:
                ind.fitness = fitness_func(ind.genes)
                
            # 5. 选择幸存者
            survivors = self.selector.select_survivors(
                self.population.individuals,
                temp_population.individuals
            )
            
            # 6. 更新种群
            self.population.individuals = survivors
            self.population.generation = generation + 1
            
            # 7. 记录日志
            self.population.add_history()
            self.logger.log_generation(
                generation=generation,
                population_stats={
                    'best_fitness': self.population.best.fitness if self.population.best else 0,
                    'average_fitness': self.population.average_fitness,
                    'variance': self.population.fitness_variance,
                    'diversity': self.mutator.get_mutation_diversity(self.population),
                },
                mutation_count=len(mutated_offspring),
                crossover_count=len(offspring),
                selection_pressure=selection_result.selection_pressure,
            )
            
            # 8. 回调
            if self.on_generation:
                self.on_generation(generation, self.population)
                
            # 9. 检查终止条件
            if self.population.is_converged(self.config.convergence_threshold):
                break
                
            if self.population.is_stagnant(self.config.stagnation_limit):
                break
                
        # 保存日志
        self.logger.save_run()
        
        return EvolutionResult(
            best_individual=self.population.best,
            best_fitness=self.population.best.fitness if self.population.best else 0,
            generations=self.population.generation,
            converged=self.population.is_converged(self.config.convergence_threshold),
            final_population=self.population.individuals.copy(),
            history=self.population.history.copy(),
        )
    
    def _evaluate_population(self):
        """评估整个种群"""
        if not self.fitness_function:
            return
            
        for individual in self.population.individuals:
            individual.fitness = self.fitness_function(individual.genes)
            
    def evolve_single_generation(self) -> bool:
        """
        执行单代进化
        
        Returns:
            是否继续进化（False表示已终止）
        """
        if not self.fitness_function:
            return False
            
        generation = self.population.generation
        
        # 选择
        selection_result = self.selector.select(self.population)
        
        # 交叉
        offspring = self.crossover.crossover_population(selection_result.selected)
        
        # 变异
        mutated_offspring = self.mutator.mutate_population(
            Population(individuals=offspring),
            generation=generation
        )
        
        # 评估后代
        for ind in mutated_offspring:
            ind.fitness = self.fitness_function(ind.genes)
            
        # 选择幸存者
        survivors = self.selector.select_survivors(
            self.population.individuals,
            mutated_offspring
        )
        
        # 更新种群
        self.population.individuals = survivors
        self.population.generation += 1
        self.population.add_history()
        
        # 检查终止条件
        return not (self.population.is_converged(self.config.convergence_threshold) or
                   self.population.is_stagnant(self.config.stagnation_limit) or
                   self.population.generation >= self.config.max_generations)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取种群统计信息"""
        return {
            'generation': self.population.generation,
            'population_size': self.population.size,
            'best_fitness': self.population.best.fitness if self.population.best else 0,
            'average_fitness': self.population.average_fitness,
            'fitness_variance': self.population.fitness_variance,
            'diversity': self.mutator.get_mutation_diversity(self.population),
        }
