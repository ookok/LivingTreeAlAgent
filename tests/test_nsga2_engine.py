"""
NSGA-II 多目标进化引擎测试
"""

import unittest
import numpy as np
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.evolution.nsga2_engine import NSGA2Engine, Individual


class TestNSGA2Engine(unittest.TestCase):
    """NSGA-II 引擎测试"""
    
    def setUp(self):
        """测试初始化"""
        self.engine = NSGA2Engine(
            population_size=20,
            n_objectives=2,
            gene_dim=5,
            gene_min=0.0,
            gene_max=1.0,
        )
        
        # ZDT1 测试函数（多目标优化经典测试）
        def zdt1(genes: np.ndarray) -> List[float]:
            f1 = genes[0]
            g = 1 + 9 * np.sum(genes[1:]) / (len(genes) - 1)
            h = 1 - np.sqrt(f1 / g)
            f2 = g * h
            return [f1, f2]
            
        self.engine.set_objectives_function(zdt1)
        
    def test_initialization(self):
        """测试初始化"""
        self.engine.initialize_population()
        
        self.assertEqual(len(self.engine.population), 20)
        self.assertEqual(self.engine.gene_dim, 5)
        self.assertEqual(self.engine.n_objectives, 2)
        
        # 检查基因范围
        for ind in self.engine.population:
            self.assertTrue(np.all(ind.genes >= 0.0))
            self.assertTrue(np.all(ind.genes <= 1.0))
            
    def test_non_dominated_sort(self):
        """测试非支配排序"""
        self.engine.initialize_population()
        
        fronts = self.engine._non_dominated_sort(self.engine.population)
        
        # 检查前沿是否存在
        self.assertGreater(len(fronts), 0)
        
        # 检查所有个体都被分配了
        total_individuals = sum(len(front) for front in fronts)
        self.assertEqual(total_individuals, len(self.engine.population))
        
        # 检查排序正确性（第一前沿的个体 rank=0）
        for ind in fronts[0]:
            self.assertEqual(ind.rank, 0)
            
    def test_crowding_distance(self):
        """测试拥挤度距离计算"""
        # 创建测试个体
        ind1 = Individual(genes=np.array([0.0, 0.0]))
        ind1.objectives = [0.0, 1.0]
        
        ind2 = Individual(genes=np.array([0.5, 0.5]))
        ind2.objectives = [0.5, 0.5]
        
        ind3 = Individual(genes=np.array([1.0, 1.0]))
        ind3.objectives = [1.0, 0.0]
        
        front = [ind1, ind2, ind3]
        
        self.engine._calculate_crowding_distance(front)
        
        # 边界个体拥挤度应为无穷
        self.assertEqual(ind1.crowding_distance, float('inf'))
        self.assertEqual(ind3.crowding_distance, float('inf'))
        
    def test_run(self):
        """测试运行"""
        pareto, history = self.engine.run(max_generations=50)
        
        # 检查 Pareto 前沿
        self.assertGreater(len(pareto), 0)
        
        # 检查历史记录
        self.assertEqual(len(history), 50)
        
        # 检查 Pareto 前沿的正确性（所有个体应在第一前沿）
        for ind in pareto:
            self.assertEqual(ind.rank, 0)
            
    def test_get_pareto_front(self):
        """测试获取 Pareto 前沿"""
        self.engine.run(max_generations=50)
        
        pareto = self.engine.get_pareto_front()
        
        self.assertGreater(len(pareto), 0)
        for ind in pareto:
            self.assertEqual(ind.rank, 0)
            
    def test_hypervolume(self):
        """测试超体积计算（2D）"""
        self.engine.run(max_generations=50)
        
        reference_point = [1.1, 1.1]
        hv = self.engine.get_hypervolume(reference_point)
        
        # 超体积应为正数
        self.assertGreater(hv, 0.0)
        self.assertLess(hv, 1.1 * 1.1)  # 不超过参考点面积
        
    def test_crossover(self):
        """测试交叉操作"""
        parent1 = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
        parent2 = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
        
        child1, child2 = self.engine._crossover(parent1, parent2)
        
        # 子代基因应在父代范围内
        self.assertTrue(np.all(child1 >= 0.0))
        self.assertTrue(np.all(child1 <= 1.0))
        self.assertTrue(np.all(child2 >= 0.0))
        self.assertTrue(np.all(child2 <= 1.0))
        
    def test_mutation(self):
        """测试变异操作"""
        genes = np.array([0.5, 0.5, 0.5, 0.5, 0.5])
        
        mutated = self.engine._mutate(genes)
        
        # 变异后基因应在范围内
        self.assertTrue(np.all(mutated >= 0.0))
        self.assertTrue(np.all(mutated <= 1.0))
        

class TestIndividual(unittest.TestCase):
    """Individual 类测试"""
    
    def test_individual_creation(self):
        """测试个体创建"""
        genes = np.array([1.0, 2.0, 3.0])
        ind = Individual(genes=genes)
        
        self.assertTrue(np.array_equal(ind.genes, genes))
        self.assertEqual(ind.objectives, [])
        self.assertEqual(ind.rank, 0)
        self.assertEqual(ind.crowding_distance, 0.0)
        
    def test_individual_ordering(self):
        """测试个体排序（按 rank 和 crowding distance）"""
        ind1 = Individual(genes=np.array([1.0]))
        ind1.rank = 0
        ind1.crowding_distance = 1.0
        
        ind2 = Individual(genes=np.array([2.0]))
        ind2.rank = 1
        ind2.crowding_distance = 2.0
        
        # ind1 < ind2 应为 True（rank 更小）
        self.assertTrue(ind1 < ind2)
        
        # 相同 rank，比较 crowding distance
        ind2.rank = 0
        ind2.crowding_distance = 0.5
        
        # ind1 < ind2 应为 False（crowding distance 更大）
        self.assertFalse(ind1 < ind2)
        

if __name__ == '__main__':
    unittest.main()
