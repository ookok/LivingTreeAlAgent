"""
GEP 基因表达式编程集成模块

将 GEP (Gene Expression Programming) 集成到进化引擎中
用于优化提示词和技能进化
"""

import random
import numpy as np
from typing import List, Dict, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
import time
import uuid


@dataclass
class Gene:
    """基因"""
    id: str
    value: str
    weight: float = 1.0
    fitness: float = 0.0


@dataclass
class Chromosome:
    """染色体"""
    genes: List[Gene]
    fitness: float = 0.0
    age: int = 0


@dataclass
class Population:
    """种群"""
    chromosomes: List[Chromosome]
    size: int
    generation: int = 0
    best_fitness: float = 0.0
    best_chromosome: Optional[Chromosome] = None


class GEPConfig:
    """GEP 配置"""
    def __init__(self):
        self.population_size = 50
        self.gene_length = 20
        self.max_generations = 100
        self.mutation_rate = 0.05
        self.crossover_rate = 0.7
        self.elitism_rate = 0.1
        self.tournament_size = 5


class GEPEngine:
    """GEP 基因表达式编程引擎"""

    def __init__(self, config: Optional[GEPConfig] = None):
        self.config = config or GEPConfig()
        self.population: Optional[Population] = None
        self.fitness_function: Optional[Callable] = None

    def initialize_population(self, seed_genes: Optional[List[str]] = None) -> Population:
        """初始化种群"""
        chromosomes = []
        seed_genes = seed_genes or self._generate_default_genes()

        for _ in range(self.config.population_size):
            genes = []
            for _ in range(self.config.gene_length):
                gene_value = random.choice(seed_genes)
                gene = Gene(
                    id=str(uuid.uuid4()),
                    value=gene_value
                )
                genes.append(gene)
            chromosome = Chromosome(genes=genes)
            chromosomes.append(chromosome)

        population = Population(
            chromosomes=chromosomes,
            size=self.config.population_size
        )
        self.population = population
        return population

    def _generate_default_genes(self) -> List[str]:
        """生成默认基因"""
        return [
            "你是一个专业的",
            "请详细分析",
            "从多个角度",
            "提供具体建议",
            "考虑用户需求",
            "基于最佳实践",
            "结合行业标准",
            "提供可行方案",
            "分析优缺点",
            "给出具体步骤",
            "考虑成本效益",
            "关注用户体验",
            "确保安全性",
            "考虑可扩展性",
            "结合最新趋势",
            "保持专业性",
            "提供详细说明",
            "考虑时间因素",
            "分析风险因素",
            "提供最佳方案"
        ]

    def evaluate_population(self, fitness_function: Callable) -> float:
        """评估种群"""
        self.fitness_function = fitness_function
        best_fitness = 0.0
        best_chromosome = None

        for chromosome in self.population.chromosomes:
            prompt = self.chromosome_to_prompt(chromosome)
            fitness = fitness_function(prompt)
            chromosome.fitness = fitness

            if fitness > best_fitness:
                best_fitness = fitness
                best_chromosome = chromosome

        self.population.best_fitness = best_fitness
        self.population.best_chromosome = best_chromosome
        return best_fitness

    def evolve(self) -> Population:
        """进化一代"""
        if not self.population:
            raise ValueError("Population not initialized")

        new_chromosomes = []
        elite_count = int(self.config.elitism_rate * self.config.population_size)

        # 保留精英
        sorted_chromosomes = sorted(
            self.population.chromosomes,
            key=lambda c: c.fitness, 
            reverse=True
        )
        elite = sorted_chromosomes[:elite_count]
        new_chromosomes.extend(elite)

        # 生成新个体
        while len(new_chromosomes) < self.config.population_size:
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()

            if random.random() < self.config.crossover_rate:
                child1, child2 = self._crossover(parent1, parent2)
                new_chromosomes.extend([child1, child2])
            else:
                new_chromosomes.extend([parent1, parent2])

        # 变异
        for chromosome in new_chromosomes[elite_count:]:
            self._mutate(chromosome)

        # 更新种群
        self.population.chromosomes = new_chromosomes[:self.config.population_size]
        self.population.generation += 1

        return self.population

    def _tournament_selection(self) -> Chromosome:
        """锦标赛选择"""
        competitors = random.sample(
            self.population.chromosomes,
            min(self.config.tournament_size, len(self.population.chromosomes))
        )
        return max(competitors, key=lambda c: c.fitness)

    def _crossover(self, parent1: Chromosome, parent2: Chromosome) -> Tuple[Chromosome, Chromosome]:
        """交叉"""
        crossover_point = random.randint(1, len(parent1.genes) - 1)

        child1_genes = parent1.genes[:crossover_point] + parent2.genes[crossover_point:]
        child2_genes = parent2.genes[:crossover_point] + parent1.genes[crossover_point:]

        child1 = Chromosome(genes=child1_genes)
        child2 = Chromosome(genes=child2_genes)

        return child1, child2

    def _mutate(self, chromosome: Chromosome):
        """变异"""
        for gene in chromosome.genes:
            if random.random() < self.config.mutation_rate:
                # 随机替换基因值
                new_values = [
                    "需要特别注意",
                    "请重点关注",
                    "考虑实际应用",
                    "结合具体场景",
                    "提供专业建议",
                    "分析潜在问题",
                    "给出优化方案",
                    "考虑长期发展",
                    "关注核心需求",
                    "提供创新方案"
                ]
                gene.value = random.choice(new_values)

    def chromosome_to_prompt(self, chromosome: Chromosome) -> str:
        """将染色体转换为提示词"""
        prompt_parts = [gene.value for gene in chromosome.genes if gene.value]
        return " ".join(prompt_parts)

    def run_evolution(self, seed_genes: Optional[List[str]] = None) -> Chromosome:
        """运行进化"""
        if not self.fitness_function:
            raise ValueError("Fitness function not set")

        self.initialize_population(seed_genes)

        for generation in range(self.config.max_generations):
            self.evaluate_population(self.fitness_function)
            
            if generation % 10 == 0:
                print(f"Generation {generation}: Best fitness = {self.population.best_fitness}")
                print(f"Best prompt: {self.chromosome_to_prompt(self.population.best_chromosome)}")

            if self.population.best_fitness >= 0.95:
                print("Evolution completed early - reached fitness threshold")
                break

            self.evolve()

        return self.population.best_chromosome


class GEPIntegration:
    """GEP 与进化引擎集成"""

    def __init__(self, gep_engine: Optional[GEPEngine] = None):
        self.gep_engine = gep_engine or GEPEngine()

    def optimize_prompt(
        self,
        base_prompt: str,
        evaluation_function: Callable[[str], float],
        seed_genes: Optional[List[str]] = None
    ) -> str:
        """
        优化提示词

        Args:
            base_prompt: 基础提示词
            evaluation_function: 评估函数
            seed_genes: 种子基因

        Returns:
            str: 优化后的提示词
        """
        def fitness_function(prompt: str) -> float:
            combined_prompt = f"{base_prompt}\n{prompt}"
            return evaluation_function(combined_prompt)

        self.gep_engine.fitness_function = fitness_function
        best_chromosome = self.gep_engine.run_evolution(seed_genes)
        optimized_prompt = self.gep_engine.chromosome_to_prompt(best_chromosome)

        return f"{base_prompt}\n{optimized_prompt}"

    def evolve_skill(
        self,
        skill_name: str,
        current_prompt: str,
        evaluation_function: Callable[[str], float]
    ) -> Dict:
        """
        进化技能

        Args:
            skill_name: 技能名称
            current_prompt: 当前提示词
            evaluation_function: 评估函数

        Returns:
            Dict: 进化结果
        """
        seed_genes = self._extract_genes_from_prompt(current_prompt)

        optimized_prompt = self.optimize_prompt(
            current_prompt,
            evaluation_function,
            seed_genes
        )

        return {
            "skill_name": skill_name,
            "original_prompt": current_prompt,
            "optimized_prompt": optimized_prompt,
            "improvement": "GEP 优化"
        }

    def _extract_genes_from_prompt(self, prompt: str) -> List[str]:
        """从提示词提取基因"""
        sentences = [s.strip() for s in prompt.split('.') if s.strip()]
        return sentences[:10]  # 最多提取10个基因


class GEPMonitor:
    """GEP 监控器"""

    def __init__(self):
        self.evolution_history = []
        self.best_solutions = []

    def record_evolution(self, generation: int, best_fitness: float, best_prompt: str):
        """记录进化过程"""
        self.evolution_history.append({
            "generation": generation,
            "best_fitness": best_fitness,
            "best_prompt": best_prompt,
            "timestamp": time.time()
        })

    def get_best_solution(self) -> Optional[Dict]:
        """获取最佳解决方案"""
        if not self.evolution_history:
            return None

        best = max(self.evolution_history, key=lambda x: x["best_fitness"])
        return best

    def export_history(self) -> List[Dict]:
        """导出历史"""
        return self.evolution_history


# 示例使用
def example_evaluation(prompt: str) -> float:
    """示例评估函数"""
    # 简单的评估逻辑：长度、多样性、专业性
    length_score = min(len(prompt) / 200, 1.0)
    diversity_score = len(set(prompt.split())) / len(prompt.split())
    professional_score = sum(1 for word in prompt.split() if word in [
        "专业", "分析", "建议", "方案", "优化", "效率", "创新"
    ]) / 5

    return (length_score + diversity_score + professional_score) / 3


def demo_gep():
    """演示 GEP"""
    gep = GEPEngine()
    integration = GEPIntegration(gep)

    base_prompt = "你是一个数据分析专家"
    optimized = integration.optimize_prompt(
        base_prompt,
        example_evaluation
    )

    print("原始提示词:", base_prompt)
    print("优化后提示词:", optimized)


if __name__ == "__main__":
    demo_gep()
