"""
开放式进化策略 (Open-Ended Evolution)
====================================

参考论文: https://arxiv.org/abs/2603.19461

实现开放式进化的核心机制：
1. 开放式搜索空间 - 不受限的策略探索
2. 自动发现新策略 - 无需人工干预的策略生成
3. 自我复制与变异 - 策略的进化操作
4. 进化压力机制 - 选择压力驱动进化

核心特性：
- 策略生成器 - 自动生成新策略
- 变异算子 - 策略变异操作
- 选择机制 - 基于适应度的选择
- 多样性维护 - 保持策略多样性

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import random
import string
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class MutationType(Enum):
    """变异类型"""
    PARAMETER_ADJUSTMENT = "parameter_adjustment"
    STRATEGY_COMBINATION = "strategy_combination"
    NOVELTY_INJECTION = "novelty_injection"
    STRUCTURAL_MUTATION = "structural_mutation"


class SelectionPressure(Enum):
    """选择压力级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class StrategyGenome:
    """策略基因组"""
    name: str
    parameters: Dict[str, Any]
    fitness: float = 0.0
    age: int = 0
    parent_ids: List[str] = field(default_factory=list)
    mutation_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EvolutionEvent:
    """进化事件"""
    event_type: str
    strategy_id: str
    parent_ids: List[str]
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PopulationSnapshot:
    """种群快照"""
    generation: int
    population_size: int
    avg_fitness: float
    best_fitness: float
    diversity: float
    timestamp: float


class OpenEndedEvolution:
    """
    开放式进化系统
    
    核心机制：
    1. 策略生成器 - 自动生成新策略
    2. 变异算子 - 支持多种变异类型
    3. 选择机制 - 基于适应度的选择
    4. 多样性维护 - 保持策略多样性
    5. 进化压力调节 - 动态调整选择压力
    """
    
    def __init__(self):
        # 策略种群
        self._population: Dict[str, StrategyGenome] = {}
        
        # 进化世代
        self._generation = 0
        
        # 选择压力
        self._selection_pressure = SelectionPressure.MEDIUM
        
        # 多样性目标
        self._target_diversity = 0.7
        
        # 种群大小限制
        self._max_population_size = 50
        
        # 进化历史
        self._evolution_events: List[EvolutionEvent] = []
        self._population_snapshots: List[PopulationSnapshot] = []
        
        # 创新计数
        self._novelty_count = 0
        
        # 初始化种子策略
        self._initialize_seed_population()
    
    def _initialize_seed_population(self):
        """初始化种子种群"""
        seed_strategies = [
            StrategyGenome(
                name="token_optimization_v1",
                parameters={
                    "type": "token_optimization",
                    "level": "balanced",
                    "target_ratio": 0.5,
                },
                fitness=0.5,
            ),
            StrategyGenome(
                name="cache_strategy_v1",
                parameters={
                    "type": "cache_optimization",
                    "ttl": 3600,
                    "max_entries": 1000,
                },
                fitness=0.6,
            ),
            StrategyGenome(
                name="context_aware_v1",
                parameters={
                    "type": "context_awareness",
                    "detection_threshold": 0.8,
                    "context_types": ["code", "chat", "document"],
                },
                fitness=0.55,
            ),
            StrategyGenome(
                name="cost_optimization_v1",
                parameters={
                    "type": "cost_management",
                    "budget_limit": 100.0,
                    "model_preference": ["haiku", "sonnet"],
                },
                fitness=0.45,
            ),
            StrategyGenome(
                name="performance_tuning_v1",
                parameters={
                    "type": "performance_optimization",
                    "timeout_threshold": 30,
                    "retry_policy": "exponential",
                },
                fitness=0.52,
            ),
        ]
        
        for strategy in seed_strategies:
            self._population[strategy.name] = strategy
    
    def generate_new_strategy(self) -> StrategyGenome:
        """
        生成新策略
        
        通过组合现有策略或注入新颖元素来生成新策略
        """
        # 随机选择生成方式
        if random.random() < 0.3:
            # 30% 概率生成完全新颖的策略
            return self._generate_novel_strategy()
        elif random.random() < 0.5:
            # 50% 概率组合现有策略
            return self._combine_strategies()
        else:
            # 20% 概率变异现有策略
            return self._mutate_random_strategy()
    
    def _generate_novel_strategy(self) -> StrategyGenome:
        """生成完全新颖的策略"""
        strategy_types = [
            "adaptive_routing",
            "dynamic_throttling",
            "predictive_caching",
            "contextual_compression",
            "intelligent_fallback",
            "adversarial_training",
            "meta_learning",
            "online_learning",
        ]
        
        strategy_type = random.choice(strategy_types)
        novelty_id = self._generate_unique_id()
        
        new_strategy = StrategyGenome(
            name=f"{strategy_type}_{novelty_id}",
            parameters={
                "type": strategy_type,
                "novelty_score": random.uniform(0.7, 1.0),
                "exploration_bonus": True,
            },
            fitness=0.0,
            parent_ids=[],
            mutation_history=[{
                "type": "novelty_injection",
                "description": "全新策略生成",
            }],
        )
        
        self._novelty_count += 1
        logger.info(f"[OpenEndedEvolution] 生成新颖策略: {new_strategy.name}")
        
        return new_strategy
    
    def _combine_strategies(self) -> StrategyGenome:
        """组合现有策略"""
        if len(self._population) < 2:
            return self._generate_novel_strategy()
        
        # 随机选择两个父策略
        parent_names = random.sample(list(self._population.keys()), 2)
        parent1 = self._population[parent_names[0]]
        parent2 = self._population[parent_names[1]]
        
        # 组合参数
        combined_params = {**parent1.parameters}
        combined_params.update({k: v for k, v in parent2.parameters.items() 
                               if k not in combined_params and random.random() > 0.5})
        
        # 添加混合标记
        combined_params["hybrid"] = True
        combined_params["parents"] = parent_names
        
        new_strategy = StrategyGenome(
            name=f"hybrid_{parent1.name.split('_')[0]}_{parent2.name.split('_')[0]}_{self._generate_unique_id()}",
            parameters=combined_params,
            fitness=(parent1.fitness + parent2.fitness) / 2 * 0.9,  # 杂种优势折扣
            parent_ids=parent_names,
            mutation_history=[{
                "type": "strategy_combination",
                "parents": parent_names,
            }],
        )
        
        logger.info(f"[OpenEndedEvolution] 组合策略: {new_strategy.name}")
        
        return new_strategy
    
    def _mutate_random_strategy(self) -> StrategyGenome:
        """变异随机策略"""
        if not self._population:
            return self._generate_novel_strategy()
        
        # 选择一个策略进行变异
        parent_name = random.choice(list(self._population.keys()))
        parent = self._population[parent_name]
        
        # 选择变异类型
        mutation_type = random.choice(list(MutationType))
        
        mutated_params = dict(parent.parameters)
        
        if mutation_type == MutationType.PARAMETER_ADJUSTMENT:
            # 参数调整
            if mutated_params:
                key_to_mutate = random.choice(list(mutated_params.keys()))
                value = mutated_params[key_to_mutate]
                if isinstance(value, (int, float)):
                    mutated_params[key_to_mutate] = value * random.uniform(0.8, 1.2)
        
        elif mutation_type == MutationType.NOVELTY_INJECTION:
            # 新颖性注入
            novel_params = {
                "innovation_tag": f"novel_{self._generate_unique_id()}",
                "experimental": True,
            }
            mutated_params.update(novel_params)
        
        elif mutation_type == MutationType.STRUCTURAL_MUTATION:
            # 结构变异
            mutated_params["version"] = mutated_params.get("version", 1) + 1
            mutated_params["mutated"] = True
        
        new_strategy = StrategyGenome(
            name=f"{parent_name}_mut_{self._generate_unique_id()}",
            parameters=mutated_params,
            fitness=parent.fitness * random.uniform(0.8, 1.1),
            parent_ids=[parent_name],
            mutation_history=[{
                "type": mutation_type.value,
                "parent": parent_name,
            }],
        )
        
        logger.info(f"[OpenEndedEvolution] 变异策略: {new_strategy.name} (类型: {mutation_type.value})")
        
        return new_strategy
    
    def _generate_unique_id(self) -> str:
        """生成唯一ID"""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    
    def select(self) -> List[StrategyGenome]:
        """
        选择策略
        
        根据选择压力选择下一代策略
        """
        if not self._population:
            return []
        
        # 获取适应度阈值
        threshold = self._get_selection_threshold()
        
        # 选择适应度高于阈值的策略
        selected = [
            strategy for strategy in self._population.values()
            if strategy.fitness >= threshold
        ]
        
        # 如果选择的太少，降低阈值
        if len(selected) < 2:
            threshold = min(threshold, min(s.fitness for s in self._population.values()))
            selected = [
                strategy for strategy in self._population.values()
                if strategy.fitness >= threshold
            ]
        
        logger.info(f"[OpenEndedEvolution] 选择: {len(selected)}/{len(self._population)} 策略 (阈值: {threshold:.2f})")
        
        return selected
    
    def _get_selection_threshold(self) -> float:
        """获取选择阈值"""
        if not self._population:
            return 0.0
        
        fitness_values = [s.fitness for s in self._population.values()]
        avg_fitness = sum(fitness_values) / len(fitness_values)
        std_fitness = (sum((f - avg_fitness) ** 2 for f in fitness_values) / len(fitness_values)) ** 0.5
        
        # 根据选择压力调整阈值
        pressure_map = {
            SelectionPressure.LOW: avg_fitness - std_fitness,
            SelectionPressure.MEDIUM: avg_fitness,
            SelectionPressure.HIGH: avg_fitness + std_fitness * 0.5,
            SelectionPressure.EXTREME: avg_fitness + std_fitness,
        }
        
        return pressure_map[self._selection_pressure]
    
    def evolve(self) -> Dict[str, Any]:
        """
        执行一轮进化
        
        进化流程：
        1. 选择
        2. 繁殖（变异/组合）
        3. 评估（由外部系统完成）
        4. 替换
        """
        # 1. 选择
        selected = self.select()
        
        # 2. 繁殖
        new_generation = []
        
        # 保留精英策略
        elite_count = max(1, int(len(selected) * 0.2))
        elite = sorted(selected, key=lambda s: s.fitness, reverse=True)[:elite_count]
        new_generation.extend(elite)
        
        # 生成新策略
        while len(new_generation) < self._max_population_size:
            try:
                new_strategy = self.generate_new_strategy()
                new_generation.append(new_strategy)
            except Exception as e:
                logger.error(f"[OpenEndedEvolution] 生成策略失败: {e}")
                break
        
        # 3. 更新种群
        self._population = {s.name: s for s in new_generation}
        self._generation += 1
        
        # 4. 更新选择压力
        self._adjust_selection_pressure()
        
        # 5. 记录快照
        self._record_snapshot()
        
        # 6. 维护多样性
        self._maintain_diversity()
        
        result = {
            "generation": self._generation,
            "population_size": len(self._population),
            "novelty_count": self._novelty_count,
            "avg_fitness": self._calculate_avg_fitness(),
            "best_fitness": self._calculate_best_fitness(),
        }
        
        logger.info(f"[OpenEndedEvolution] 进化完成: 世代 {self._generation}, 种群大小 {len(self._population)}")
        
        return result
    
    def _adjust_selection_pressure(self):
        """调整选择压力"""
        avg_fitness = self._calculate_avg_fitness()
        diversity = self._calculate_diversity()
        
        # 如果多样性太低，降低选择压力
        if diversity < 0.3:
            if self._selection_pressure != SelectionPressure.LOW:
                self._selection_pressure = SelectionPressure.LOW
                logger.info("[OpenEndedEvolution] 降低选择压力以增加多样性")
        
        # 如果多样性太高，增加选择压力
        elif diversity > 0.8:
            if self._selection_pressure != SelectionPressure.HIGH:
                self._selection_pressure = SelectionPressure.HIGH
                logger.info("[OpenEndedEvolution] 增加选择压力以提高质量")
        
        # 如果平均适应度持续提高，增加压力
        elif avg_fitness > 0.8:
            self._selection_pressure = SelectionPressure.EXTREME
    
    def _maintain_diversity(self):
        """维护种群多样性"""
        diversity = self._calculate_diversity()
        
        # 如果多样性不足，注入新颖策略
        if diversity < self._target_diversity:
            for _ in range(3):
                novel_strategy = self._generate_novel_strategy()
                if len(self._population) < self._max_population_size:
                    self._population[novel_strategy.name] = novel_strategy
    
    def _calculate_avg_fitness(self) -> float:
        """计算平均适应度"""
        if not self._population:
            return 0.0
        return sum(s.fitness for s in self._population.values()) / len(self._population)
    
    def _calculate_best_fitness(self) -> float:
        """计算最佳适应度"""
        if not self._population:
            return 0.0
        return max(s.fitness for s in self._population.values())
    
    def _calculate_diversity(self) -> float:
        """计算种群多样性"""
        if not self._population:
            return 0.0
        
        # 基于参数类型的多样性
        param_types = set()
        for strategy in self._population.values():
            param_types.add(strategy.parameters.get("type", "unknown"))
        
        return len(param_types) / len(self._population) if self._population else 0.0
    
    def _record_snapshot(self):
        """记录种群快照"""
        snapshot = PopulationSnapshot(
            generation=self._generation,
            population_size=len(self._population),
            avg_fitness=self._calculate_avg_fitness(),
            best_fitness=self._calculate_best_fitness(),
            diversity=self._calculate_diversity(),
            timestamp=__import__('time').time(),
        )
        
        self._population_snapshots.append(snapshot)
        
        # 限制快照数量
        if len(self._population_snapshots) > 100:
            self._population_snapshots = self._population_snapshots[-100:]
    
    def update_fitness(self, strategy_name: str, fitness: float):
        """更新策略适应度"""
        if strategy_name in self._population:
            # 指数移动平均更新
            old_fitness = self._population[strategy_name].fitness
            new_fitness = old_fitness * 0.8 + fitness * 0.2
            self._population[strategy_name].fitness = new_fitness
            self._population[strategy_name].age += 1
            
            logger.info(f"[OpenEndedEvolution] 更新适应度: {strategy_name} = {new_fitness:.2f}")
    
    def get_population(self) -> List[StrategyGenome]:
        """获取种群"""
        return list(self._population.values())
    
    def get_best_strategies(self, count: int = 5) -> List[StrategyGenome]:
        """获取最佳策略"""
        return sorted(
            self._population.values(),
            key=lambda s: s.fitness,
            reverse=True
        )[:count]
    
    def get_generation(self) -> int:
        """获取当前世代"""
        return self._generation
    
    def get_evolution_history(self) -> List[PopulationSnapshot]:
        """获取进化历史"""
        return self._population_snapshots
    
    def set_selection_pressure(self, pressure: SelectionPressure):
        """设置选择压力"""
        self._selection_pressure = pressure
        logger.info(f"[OpenEndedEvolution] 选择压力设置为: {pressure.value}")


# 便捷函数
def create_open_ended_evolution() -> OpenEndedEvolution:
    """创建开放式进化实例"""
    return OpenEndedEvolution()


__all__ = [
    "MutationType",
    "SelectionPressure",
    "StrategyGenome",
    "EvolutionEvent",
    "PopulationSnapshot",
    "OpenEndedEvolution",
    "create_open_ended_evolution",
]
