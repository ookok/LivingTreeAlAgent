"""
Evolution Engine 测试文件
"""

import pytest
import numpy as np
from evolution import (
    EvolutionEngine,
    EvolutionConfig,
    GeneMutator,
    SurvivalSelector,
    CrossoverEngine,
    Population,
    Individual,
    MutationStrategy,
    SelectionStrategy,
    CrossoverStrategy,
)


class TestEvolutionConfig:
    """进化配置测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = EvolutionConfig()
        assert config.population_size == 50
        assert config.mutation_rate == 0.1
        assert config.validate()
        
    def test_fast_config(self):
        """测试快速配置"""
        config = EvolutionConfig.fast_config()
        assert config.population_size == 20
        assert config.max_generations == 50
        
    def test_robust_config(self):
        """测试稳健配置"""
        config = EvolutionConfig.robust_config()
        assert config.population_size == 100
        assert config.mutation_rate == 0.05


class TestPopulation:
    """种群测试"""
    
    def test_initialize_random(self):
        """测试随机初始化"""
        config = EvolutionConfig(population_size=10, individual_dimensions=5)
        pop = Population()
        pop.initialize_random(config)
        
        assert pop.size == 10
        assert len(pop.individuals[0].genes) == 5
        
    def test_select_elite(self):
        """测试精英选择"""
        pop = Population()
        pop.individuals = [
            Individual(genes=np.array([1, 2]), fitness=1.0),
            Individual(genes=np.array([2, 3]), fitness=3.0),
            Individual(genes=np.array([3, 4]), fitness=2.0),
        ]
        
        elite = pop.select_elite(0.33)
        assert len(elite) == 1
        assert elite[0].fitness == 3.0
        
    def test_best_individual(self):
        """测试最优个体"""
        pop = Population()
        pop.individuals = [
            Individual(genes=np.array([1]), fitness=1.0),
            Individual(genes=np.array([2]), fitness=5.0),
            Individual(genes=np.array([3]), fitness=3.0),
        ]
        
        assert pop.best.fitness == 5.0


class TestGeneMutator:
    """基因突变器测试"""
    
    def setup_method(self):
        self.config = EvolutionConfig()
        self.mutator = GeneMutator(self.config)
        
    def test_gaussian_mutation(self):
        """测试高斯突变"""
        individual = Individual(genes=np.array([1.0, 2.0, 3.0]))
        result = self.mutator.mutate(individual, MutationStrategy.GAUSSIAN)
        
        assert len(result.mutated) == 3
        assert len(result.mutation_points) > 0
        
    def test_uniform_mutation(self):
        """测试均匀突变"""
        individual = Individual(genes=np.array([1.0, 2.0, 3.0]))
        result = self.mutator.mutate(individual, MutationStrategy.UNIFORM)
        
        assert result.success
        
    def test_mutation_within_bounds(self):
        """测试突变在边界内"""
        for _ in range(100):
            individual = Individual(genes=np.random.uniform(-1, 1, 10))
            result = self.mutator.mutate(individual, MutationStrategy.GAUSSIAN)
            
            assert all(self.config.gene_min <= g <= self.config.gene_max 
                      for g in result.mutated)


class TestSurvivalSelector:
    """适者生存筛选器测试"""
    
    def setup_method(self):
        self.config = EvolutionConfig(population_size=10)
        self.selector = SurvivalSelector(self.config)
        
    def test_tournament_selection(self):
        """测试锦标赛选择"""
        pop = Population()
        pop.individuals = [
            Individual(genes=np.array([i]), fitness=float(i))
            for i in range(10)
        ]
        
        result = self.selector.select(pop, SelectionStrategy.TOURNAMENT)
        
        assert len(result.selected) == 10
        # 锦标赛选择应该偏向高适应度
        avg_fitness = sum(ind.fitness for ind in result.selected) / len(result.selected)
        assert avg_fitness > 4.0  # 应该高于平均值
        
    def test_roulette_selection(self):
        """测试轮盘赌选择"""
        pop = Population()
        pop.individuals = [
            Individual(genes=np.array([i]), fitness=float(i + 1))
            for i in range(10)
        ]
        
        result = self.selector.select(pop, SelectionStrategy.ROULETTE)
        assert len(result.selected) == 10


class TestCrossoverEngine:
    """交叉遗传引擎测试"""
    
    def setup_method(self):
        self.config = EvolutionConfig(individual_dimensions=10)
        self.crossover = CrossoverEngine(self.config)
        
    def test_single_point_crossover(self):
        """测试单点交叉"""
        parent1 = Individual(genes=np.ones(10))
        parent2 = Individual(genes=np.zeros(10))
        
        result = self.crossover.crossover(parent1, parent2, CrossoverStrategy.SINGLE_POINT)
        
        assert len(result.offspring1.genes) == 10
        assert len(result.offspring2.genes) == 10
        assert len(result.crossover_points) == 1
        
    def test_uniform_crossover(self):
        """测试均匀交叉"""
        parent1 = Individual(genes=np.ones(10))
        parent2 = Individual(genes=np.zeros(10))
        
        result = self.crossover.crossover(parent1, parent2, CrossoverStrategy.UNIFORM)
        
        assert result.success
        # 检查 offspring1 有一些1和0
        offspring1 = result.offspring1.genes
        assert 0 in offspring1 or 1 in offspring1


class TestEvolutionEngine:
    """进化引擎集成测试"""
    
    def test_sphere_function_optimization(self):
        """测试球面函数优化"""
        def sphere(x):
            return -sum(x ** 2)  # 最大化时接近0
            
        config = EvolutionConfig(
            population_size=20,
            individual_dimensions=5,
            max_generations=50,
        )
        
        engine = EvolutionEngine(config)
        result = engine.run(sphere)
        
        assert result.generations > 0
        assert result.best_fitness <= 0
        # 球面函数最优解在原点，最优值应该接近0
        assert result.best_fitness > -10  # 应该接近0
        
    def test_rastrigin_function_optimization(self):
        """测试Rastrigin函数优化"""
        def rastrigin(x):
            A = 10
            n = len(x)
            return -(A * n + sum(x ** 2 - A * np.cos(2 * np.pi * x)))
            
        config = EvolutionConfig(
            population_size=30,
            individual_dimensions=5,
            max_generations=100,
            mutation_rate=0.1,
        )
        
        engine = EvolutionEngine(config)
        result = engine.run(rastrigin)
        
        assert result.best_fitness is not None
        assert result.generations > 0
        
    def test_callback_function(self):
        """测试回调函数"""
        generations_recorded = []
        
        def on_generation(gen, pop):
            generations_recorded.append(gen)
            
        def sphere(x):
            return -sum(x ** 2)
            
        config = EvolutionConfig(population_size=10, max_generations=10)
        engine = EvolutionEngine(config)
        engine.on_generation = on_generation
        
        engine.run(sphere)
        
        assert len(generations_recorded) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
