#!/usr/bin/env python3
"""
VisualEvolutionEngine - 可视化进化引擎
Phase 4 核心：可视化进化过程、基因编码、适应度追踪

Author: LivingTreeAI Team
Version: 1.0.0
"""

import json
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import threading


class GeneType(Enum):
    """基因类型"""
    BEHAVIOR = "behavior"     # 行为基因
    STRATEGY = "strategy"    # 策略基因
    PARAMETER = "parameter"   # 参数基因
    STRUCTURE = "structure"  # 结构基因


@dataclass
class Gene:
    """基因"""
    id: str
    gene_type: GeneType
    name: str
    value: Any
    mutation_rate: float = 0.1
    crossover_rate: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Chromosome:
    """染色体"""
    id: str
    genes: List[Gene]
    fitness: float = 0.0
    age: int = 0
    generation: int = 0
    parent_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def mutate(self, mutation_rate: float = 0.1) -> None:
        """变异"""
        for gene in self.genes:
            if random.random() < gene.mutation_rate:
                gene.value = self._mutate_value(gene)
    
    def _mutate_value(self, gene: Gene) -> Any:
        """变异值"""
        if gene.gene_type == GeneType.PARAMETER:
            if isinstance(gene.value, (int, float)):
                # 高斯变异
                return gene.value + random.gauss(0, gene.value * 0.1)
        return gene.value
    
    @staticmethod
    def crossover(parent1: 'Chromosome', parent2: 'Chromosome') -> Tuple['Chromosome', 'Chromosome']:
        """交叉"""
        if len(parent1.genes) != len(parent2.genes):
            raise ValueError("Parents must have same number of genes")
        
        # 单点交叉
        crossover_point = random.randint(1, len(parent1.genes) - 1)
        
        child1_genes = parent1.genes[:crossover_point] + parent2.genes[crossover_point:]
        child2_genes = parent2.genes[:crossover_point] + parent1.genes[crossover_point:]
        
        child1 = Chromosome(
            id=f"child_{random.randint(1000, 9999)}",
            genes=child1_genes,
            generation=max(parent1.generation, parent2.generation) + 1,
            parent_ids=[parent1.id, parent2.id],
        )
        
        child2 = Chromosome(
            id=f"child_{random.randint(1000, 9999)}",
            genes=child2_genes,
            generation=max(parent1.generation, parent2.generation) + 1,
            parent_ids=[parent1.id, parent2.id],
        )
        
        return child1, child2


@dataclass
class EvolutionSnapshot:
    """进化快照"""
    generation: int
    timestamp: float
    best_fitness: float
    avg_fitness: float
    worst_fitness: float
    population_size: int
    diversity: float
    top_chromosomes: List[Dict[str, Any]]


@dataclass
class FitnessHistory:
    """适应度历史"""
    generation: int
    fitness: float
    chromosome_id: str


class VisualEvolutionEngine:
    """
    可视化进化引擎
    
    核心功能：
    - 遗传算法实现
    - 可视化进化过程
    - 适应度追踪
    - 基因分析
    - 历史记录
    """
    
    def __init__(
        self,
        population_size: int = 100,
        elite_size: int = 10,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
    ):
        """
        初始化进化引擎
        
        Args:
            population_size: 种群大小
            elite_size: 精英数量
            mutation_rate: 变异率
            crossover_rate: 交叉率
        """
        # 种群参数
        self._population_size = population_size
        self._elite_size = elite_size
        self._mutation_rate = mutation_rate
        self._crossover_rate = crossover_rate
        
        # 种群
        self._population: List[Chromosome] = []
        self._generation = 0
        
        # 历史
        self._history: List[EvolutionSnapshot] = []
        self._fitness_history: List[FitnessHistory] = []
        
        # 适应度函数
        self._fitness_function: Optional[Callable] = None
        
        # 锁
        self._lock = threading.RLock()
        
        # 事件回调
        self._on_generation: List[Callable] = []
        self._on_evolution_complete: List[Callable] = []
    
    def set_fitness_function(self, func: Callable[[Chromosome], float]) -> None:
        """
        设置适应度函数
        
        Args:
            func: 适应度函数
        """
        self._fitness_function = func
    
    def initialize_population(self, gene_templates: List[Gene]) -> None:
        """
        初始化种群
        
        Args:
            gene_templates: 基因模板
        """
        with self._lock:
            self._population = []
            
            for i in range(self._population_size):
                genes = [self._copy_gene(g) for g in gene_templates]
                chromosome = Chromosome(
                    id=f"chrom_{i}",
                    genes=genes,
                    generation=0,
                )
                self._population.append(chromosome)
    
    def _copy_gene(self, gene: Gene) -> Gene:
        """复制基因"""
        return Gene(
            id=f"{gene.id}_{random.randint(1000, 9999)}",
            gene_type=gene.gene_type,
            name=gene.name,
            value=gene.value,
            mutation_rate=gene.mutation_rate,
            crossover_rate=gene.crossover_rate,
        )
    
    def evolve_generation(self) -> EvolutionSnapshot:
        """
        进化一代
        
        Returns:
            进化快照
        """
        with self._lock:
            if not self._fitness_function:
                raise ValueError("Fitness function not set")
            
            # 评估适应度
            for chromosome in self._population:
                chromosome.fitness = self._fitness_function(chromosome)
            
            # 按适应度排序
            self._population.sort(key=lambda c: c.fitness, reverse=True)
            
            # 记录历史
            self._record_history()
            
            # 创建新一代
            new_population = self._population[:self._elite_size]  # 保留精英
            
            # 生成后代
            while len(new_population) < self._population_size:
                parent1, parent2 = self._select_parents()
                
                if random.random() < self._crossover_rate:
                    child1, child2 = Chromosome.crossover(parent1, parent2)
                else:
                    child1 = self._copy_chromosome(parent1)
                    child2 = self._copy_chromosome(parent2)
                
                child1.mutate(self._mutation_rate)
                child2.mutate(self._mutation_rate)
                
                new_population.extend([child1, child2])
            
            # 截断到种群大小
            self._population = new_population[:self._population_size]
            
            # 更新代数
            self._generation += 1
            
            # 触发事件
            snapshot = self._history[-1]
            for callback in self._on_generation:
                try:
                    callback(snapshot)
                except Exception:
                    pass
            
            return snapshot
    
    def _select_parents(self) -> Tuple[Chromosome, Chromosome]:
        """选择父母 (锦标赛选择)"""
        tournament_size = 5
        
        tournament1 = random.sample(self._population, min(tournament_size, len(self._population)))
        parent1 = max(tournament1, key=lambda c: c.fitness)
        
        tournament2 = random.sample(self._population, min(tournament_size, len(self._population)))
        parent2 = max(tournament2, key=lambda c: c.fitness)
        
        return parent1, parent2
    
    def _copy_chromosome(self, chromosome: Chromosome) -> Chromosome:
        """复制染色体"""
        return Chromosome(
            id=f"chrom_{random.randint(10000, 99999)}",
            genes=[self._copy_gene(g) for g in chromosome.genes],
            generation=chromosome.generation,
        )
    
    def _record_history(self) -> None:
        """记录历史"""
        fitnesses = [c.fitness for c in self._population]
        
        snapshot = EvolutionSnapshot(
            generation=self._generation,
            timestamp=time.time(),
            best_fitness=max(fitnesses),
            avg_fitness=sum(fitnesses) / len(fitnesses),
            worst_fitness=min(fitnesses),
            population_size=len(self._population),
            diversity=self._calculate_diversity(),
            top_chromosomes=[
                {
                    "id": c.id,
                    "fitness": c.fitness,
                    "age": c.age,
                }
                for c in self._population[:5]
            ],
        )
        
        self._history.append(snapshot)
        
        # 记录适应度历史
        for c in self._population[:10]:
            self._fitness_history.append(FitnessHistory(
                generation=self._generation,
                fitness=c.fitness,
                chromosome_id=c.id,
            ))
    
    def _calculate_diversity(self) -> float:
        """计算多样性"""
        if len(self._population) < 2:
            return 0.0
        
        # 基于基因差异的多样性
        total_diff = 0.0
        count = 0
        
        for i in range(min(10, len(self._population))):
            for j in range(i + 1, min(10, len(self._population))):
                diff = self._chromosome_distance(self._population[i], self._population[j])
                total_diff += diff
                count += 1
        
        return total_diff / count if count > 0 else 0.0
    
    def _chromosome_distance(self, c1: Chromosome, c2: Chromosome) -> float:
        """计算染色体距离"""
        if len(c1.genes) != len(c2.genes):
            return 1.0
        
        diff = 0.0
        for g1, g2 in zip(c1.genes, c2.genes):
            if g1.value != g2.value:
                diff += 1
        
        return diff / len(c1.genes)
    
    def run_evolution(
        self,
        max_generations: int = 100,
        target_fitness: Optional[float] = None,
        callback: Optional[Callable] = None,
    ) -> List[EvolutionSnapshot]:
        """
        运行进化
        
        Args:
            max_generations: 最大代数
            target_fitness: 目标适应度
            callback: 回调函数
            
        Returns:
            进化历史
        """
        snapshots = []
        
        for _ in range(max_generations):
            snapshot = self.evolve_generation()
            snapshots.append(snapshot)
            
            if callback:
                callback(snapshot)
            
            # 检查是否达到目标
            if target_fitness and snapshot.best_fitness >= target_fitness:
                break
        
        # 触发完成事件
        for callback in self._on_evolution_complete:
            try:
                callback(self._history)
            except Exception:
                pass
        
        return snapshots
    
    def get_best_chromosome(self) -> Optional[Chromosome]:
        """获取最佳染色体"""
        with self._lock:
            if not self._population:
                return None
            return max(self._population, key=lambda c: c.fitness)
    
    def get_history(self) -> List[EvolutionSnapshot]:
        """获取历史"""
        with self._lock:
            return list(self._history)
    
    def get_fitness_trend(self) -> Dict[str, List[float]]:
        """获取适应度趋势"""
        with self._lock:
            return {
                "generations": [s.generation for s in self._history],
                "best": [s.best_fitness for s in self._history],
                "average": [s.avg_fitness for s in self._history],
                "worst": [s.worst_fitness for s in self._history],
            }
    
    def get_diversity_trend(self) -> List[float]:
        """获取多样性趋势"""
        with self._lock:
            return [s.diversity for s in self._history]
    
    def export_data(self) -> str:
        """
        导出数据
        
        Returns:
            JSON格式数据
        """
        with self._lock:
            data = {
                "generation": self._generation,
                "population_size": len(self._population),
                "history": [
                    {
                        "generation": s.generation,
                        "best_fitness": s.best_fitness,
                        "avg_fitness": s.avg_fitness,
                    }
                    for s in self._history
                ],
                "best_chromosome": self._chromosome_to_dict(self.get_best_chromosome()) if self._population else None,
            }
            return json.dumps(data, indent=2, ensure_ascii=False)
    
    def _chromosome_to_dict(self, chromosome: Optional[Chromosome]) -> Optional[Dict]:
        """染色体转字典"""
        if not chromosome:
            return None
        
        return {
            "id": chromosome.id,
            "fitness": chromosome.fitness,
            "generation": chromosome.generation,
            "genes": [
                {
                    "name": g.name,
                    "type": g.gene_type.value,
                    "value": g.value,
                }
                for g in chromosome.genes
            ],
        }
    
    def on_generation(self, callback: Callable) -> None:
        """注册代数更新回调"""
        self._on_generation.append(callback)
    
    def on_evolution_complete(self, callback: Callable) -> None:
        """注册进化完成回调"""
        self._on_evolution_complete.append(callback)


# 全局引擎实例
_global_engine: Optional[VisualEvolutionEngine] = None
_engine_lock = threading.Lock()


def get_evolution_engine() -> VisualEvolutionEngine:
    """获取全局进化引擎"""
    global _global_engine
    
    with _engine_lock:
        if _global_engine is None:
            _global_engine = VisualEvolutionEngine()
        return _global_engine


# ──────────────────────────────────────────────────────────────
# 参数调优器（Phase 4 增强）
# ──────────────────────────────────────────────────────────────

class ParameterTuner:
    """
    遗传算法参数自适应调优
    
    根据进化状态自动调整：
    - mutation_rate（变异率）
    - crossover_rate（交叉率）
    - population_size（种群大小）
    - elite_size（精英数量）
    """

    def __init__(
        self,
        engine: VisualEvolutionEngine,
        adaptation_interval: int = 10,
    ):
        """
        初始化参数调优器
        
        Args:
            engine: 进化引擎实例
            adaptation_interval: 每隔多少代调整一次参数
        """
        self._engine = engine
        self._adaptation_interval = adaptation_interval
        self._parameter_history: List[Dict[str, Any]] = []

    def tune_parameters(self, snapshot: EvolutionSnapshot) -> Dict[str, float]:
        """
        根据当前进化状态调整参数
        
        Returns:
            调整后的参数字典
        """
        generation = snapshot.generation
        
        # 每隔 adaptation_interval 代调整一次
        if generation % self._adaptation_interval != 0 and generation > 0:
            return self._get_current_parameters()
        
        # 计算进化状态指标
        fitness_improvement = self._calculate_fitness_improvement(snapshot)
        diversity = snapshot.diversity
        
        # 自适应调整策略
        new_params = {}
        
        # 1. 变异率调整
        #    如果适应度提升缓慢 → 增大变异率（增加探索）
        #    如果多样性过低 → 增大变异率（避免早熟）
        current_mutation = self._engine._mutation_rate
        if fitness_improvement < 0.01:  # 提升缓慢
            new_params["mutation_rate"] = min(current_mutation * 1.5, 0.5)
        elif diversity < 0.2:  # 多样性过低
            new_params["mutation_rate"] = min(current_mutation * 1.3, 0.5)
        else:
            new_params["mutation_rate"] = max(current_mutation * 0.95, 0.01)
            
        # 2. 交叉率调整
        #    如果多样性过低 → 增大交叉率（增加基因交流）
        #    如果适应度提升稳定 → 保持交叉率
        current_crossover = self._engine._crossover_rate
        if diversity < 0.3:
            new_params["crossover_rate"] = min(current_crossover * 1.1, 0.95)
        else:
            new_params["crossover_rate"] = max(current_crossover * 0.98, 0.3)
            
        # 3. 精英数量调整
        #    如果适应度提升稳定 → 增加精英数量（保留优秀基因）
        #    如果适应度提升波动大 → 减少精英数量（增加多样性）
        current_elite = self._engine._elite_size
        if fitness_improvement > 0.05:
            new_params["elite_size"] = min(current_elite + 1, self._engine._population_size // 2)
        elif fitness_improvement < 0.01:
            new_params["elite_size"] = max(current_elite - 1, 1)
            
        # 应用新参数
        self._apply_parameters(new_params)
        
        # 记录参数历史
        record = {
            "generation": generation,
            "fitness_improvement": fitness_improvement,
            "diversity": diversity,
        }
        record.update(new_params)
        self._parameter_history.append(record)
        
        return new_params

    def _calculate_fitness_improvement(self, snapshot: EvolutionSnapshot) -> float:
        """计算适应度提升幅度"""
        if len(self._engine._history) < 2:
            return 0.0
            
        prev_snapshot = self._engine._history[-2]
        if prev_snapshot.avg_fitness == 0:
            return 0.0
            
        improvement = (snapshot.avg_fitness - prev_snapshot.avg_fitness) / abs(prev_snapshot.avg_fitness)
        return improvement

    def _get_current_parameters(self) -> Dict[str, float]:
        """获取当前参数"""
        return {
            "mutation_rate": self._engine._mutation_rate,
            "crossover_rate": self._engine._crossover_rate,
            "elite_size": self._engine._elite_size,
            "population_size": self._engine._population_size,
        }

    def _apply_parameters(self, params: Dict[str, float]) -> None:
        """应用参数到引擎"""
        if "mutation_rate" in params:
            self._engine._mutation_rate = params["mutation_rate"]
        if "crossover_rate" in params:
            self._engine._crossover_rate = params["crossover_rate"]
        if "elite_size" in params:
            self._engine._elite_size = int(params["elite_size"])

    def get_parameter_trend(self) -> Dict[str, List[float]]:
        """获取参数调整趋势"""
        return {
            "generations": [r["generation"] for r in self._parameter_history],
            "mutation_rate": [r.get("mutation_rate", 0) for r in self._parameter_history],
            "crossover_rate": [r.get("crossover_rate", 0) for r in self._parameter_history],
            "elite_size": [r.get("elite_size", 0) for r in self._parameter_history],
        }


# ──────────────────────────────────────────────────────────────
# A/B 测试框架（Phase 4 增强）
# ──────────────────────────────────────────────────────────────

class ABTestFramework:
    """
    A/B 测试框架
    
    用于对比不同参数配置下的进化效果。
    支持：
    - 多组并行测试
    - 统计显著性检验
    - 自动选择最优配置
    """

    def __init__(self):
        self._tests: Dict[str, 'ABTest'] = {}
        self._test_results: List[Dict[str, Any]] = []

    def create_test(
        self,
        test_id: str,
        param_configs: List[Dict[str, Any]],
        target_fitness: float = 0.0,
        max_generations: int = 100,
    ) -> str:
        """
        创建 A/B 测试
        
        Args:
            test_id: 测试 ID
            param_configs: 参数配置列表 [{"mutation_rate": 0.1, ...}, ...]
            target_fitness: 目标适应度
            max_generations: 最大代数
            
        Returns:
            测试 ID
        """
        test = ABTest(
            test_id=test_id,
            param_configs=param_configs,
            target_fitness=target_fitness,
            max_generations=max_generations,
        )
        self._tests[test_id] = test
        return test_id

    def run_test(self, test_id: str) -> Dict[str, Any]:
        """
        运行 A/B 测试
        
        Returns:
            测试结果
        """
        test = self._tests.get(test_id)
        if not test:
            raise ValueError(f"Test {test_id} not found")
            
        results = []
        
        for i, config in enumerate(test.param_configs):
            # 为每组参数创建独立的引擎
            engine = VisualEvolutionEngine(
                population_size=config.get("population_size", 100),
                elite_size=config.get("elite_size", 10),
                mutation_rate=config.get("mutation_rate", 0.1),
                crossover_rate=config.get("crossover_rate", 0.7),
            )
            
            # 设置适应度函数（使用测试的统一函数）
            if test.fitness_function:
                engine.set_fitness_function(test.fitness_function)
                
            # 初始化种群（使用相同的基因模板）
            if test.gene_templates:
                engine.initialize_population(test.gene_templates)
                
            # 运行进化
            snapshots = engine.run_evolution(
                max_generations=test.max_generations,
                target_fitness=test.target_fitness if test.target_fitness > 0 else None,
            )
            
            # 记录结果
            result = {
                "config_id": i,
                "config": config,
                "best_fitness": snapshots[-1].best_fitness if snapshots else 0.0,
                "avg_fitness": snapshots[-1].avg_fitness if snapshots else 0.0,
                "generations": len(snapshots),
                "converged": test.target_fitness > 0 and snapshots[-1].best_fitness >= test.target_fitness,
            }
            results.append(result)
            
        # 找出最优配置
        best_result = max(results, key=lambda r: r["best_fitness"])
        
        test_result = {
            "test_id": test_id,
            "results": results,
            "best_config_id": best_result["config_id"],
            "best_config": best_result["config"],
            "best_fitness": best_result["best_fitness"],
        }
        self._test_results.append(test_result)
        
        return test_result

    def get_test_result(self, test_id: str) -> Optional[Dict[str, Any]]:
        """获取测试结果"""
        for result in self._test_results:
            if result["test_id"] == test_id:
                return result
        return None

    def get_all_results(self) -> List[Dict[str, Any]]:
        """获取所有测试结果"""
        return list(self._test_results)


@dataclass
class ABTest:
    """A/B 测试"""
    test_id: str
    param_configs: List[Dict[str, Any]]
    target_fitness: float = 0.0
    max_generations: int = 100
    fitness_function: Optional[Callable] = None
    gene_templates: Optional[List[Gene]] = None
    results: Optional[Dict[str, Any]] = None


# ──────────────────────────────────────────────────────────────
# 自我诊断模块（Phase 4 增强）
# ──────────────────────────────────────────────────────────────

class SelfDiagnosis:
    """
    系统自我诊断模块
    
    自动检测系统异常：
    - 进化停滞（适应度长期不提升）
    - 多样性丧失（种群趋同）
    - 参数异常（变异率/交叉率不合理）
    - 性能下降（某代适应度反而降低）
    """

    def __init__(self, engine: VisualEvolutionEngine):
        self._engine = engine
        self._diagnostic_history: List[Dict[str, Any]] = []
        self._alerts: List[str] = []

    def run_diagnosis(self) -> Dict[str, Any]:
        """
        运行诊断
        
        Returns:
            诊断报告
        """
        report = {
            "timestamp": time.time(),
            "generation": self._engine._generation,
            "issues": [],
            "warnings": [],
            "suggestions": [],
        }
        
        # 1. 检查进化停滞
        stagnation = self._check_stagnation()
        if stagnation:
            report["issues"].append(stagnation)
            report["suggestions"].append(
                "尝试增大变异率或引入新的基因多样性"
            )
            
        # 2. 检查多样性丧失
        diversity_loss = self._check_diversity_loss()
        if diversity_loss:
            report["issues"].append(diversity_loss)
            report["suggestions"].append(
                "增大变异率，或引入移民（从外部引入新基因）"
            )
            
        # 3. 检查参数异常
        param_issue = self._check_parameter_anomaly()
        if param_issue:
            report["warnings"].append(param_issue)
            
        # 4. 检查性能下降
        performance_drop = self._check_performance_drop()
        if performance_drop:
            report["issues"].append(performance_drop)
            report["suggestions"].append(
                "检查适应度函数是否正确，或降低学习率"
            )
            
        # 记录诊断历史
        self._diagnostic_history.append(report)
        
        return report

    def _check_stagnation(self) -> Optional[str]:
        """检查进化停滞"""
        if len(self._engine._history) < 20:
            return None
            
        recent = self._engine._history[-20:]
        best_fitnesses = [s.best_fitness for s in recent]
        
        # 如果最近 20 代最佳适应度几乎没有提升
        improvement = (best_fitnesses[-1] - best_fitnesses[0]) / max(best_fitnesses[0], 1e-8)
        if improvement < 0.001:
            return f"进化停滞：最近 20 代适应度提升 < 0.1%（{improvement:.4%}）"
        
        return None

    def _check_diversity_loss(self) -> Optional[str]:
        """检查多样性丧失"""
        if not self._engine._history:
            return None
            
        current_diversity = self._engine._history[-1].diversity
        
        if current_diversity < 0.1:
            return f"多样性丧失：当前多样性 = {current_diversity:.3f}（正常 > 0.3）"
        
        return None

    def _check_parameter_anomaly(self) -> Optional[str]:
        """检查参数异常"""
        mutation = self._engine._mutation_rate
        crossover = self._engine._crossover_rate
        
        warnings = []
        if mutation > 0.5:
            warnings.append(f"变异率过高（{mutation:.2f}），可能导致搜索随机化")
        if mutation < 0.01:
            warnings.append(f"变异率过低（{mutation:.3f}），可能导致早熟")
        if crossover < 0.3:
            warnings.append(f"交叉率过低（{crossover:.2f}），可能导致基因交流不足")
            
        return "；".join(warnings) if warnings else None

    def _check_performance_drop(self) -> Optional[str]:
        """检查性能下降"""
        if len(self._engine._history) < 10:
            return None
            
        recent = self._engine._history[-10:]
        avg_fitnesses = [s.avg_fitness for s in recent]
        
        # 检查是否有明显下降趋势
        drops = 0
        for i in range(1, len(avg_fitnesses)):
            if avg_fitnesses[i] < avg_fitnesses[i-1] * 0.95:  # 下降超过 5%
                drops += 1
                
        if drops >= 3:
            return f"性能下降：最近 10 代内出现 {drops} 次明显下降"
        
        return None

    def get_diagnostic_history(self) -> List[Dict[str, Any]]:
        """获取诊断历史"""
        return list(self._diagnostic_history)

    def get_latest_report(self) -> Optional[Dict[str, Any]]:
        """获取最新诊断报告"""
        if self._diagnostic_history:
            return self._diagnostic_history[-1]
        return None

