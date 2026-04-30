"""
Evolution Common - 进化引擎公共接口

提供所有进化引擎的公共基类和工具。
各领域的进化引擎应继承 BaseEvolutionEngine。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 公共枚举和配置
# ============================================================

class EvolutionTarget(Enum):
    """进化目标类型"""
    SKILL = "skill"                        # 技能进化
    AGENT = "agent"                        # 智能体进化
    CODE = "code"                          # 代码进化
    KNOWLEDGE = "knowledge"                # 知识进化
    REPORT = "report"                      # 报告进化


class EvolutionStrategy(Enum):
    """进化策略"""
    GENETIC = "genetic"                    # 遗传算法
    GRADIENT = "gradient"                  # 梯度下降
    REINFORCEMENT = "reinforcement"        # 强化学习
    LAMARCKIAN = "lamarckian"             # 拉马克进化
    BALDWINIAN = "baldwinian"             # 鲍德温进化


@dataclass
class EvolutionConfig:
    """进化配置（公共字段）"""
    target: EvolutionTarget = EvolutionTarget.SKILL
    strategy: EvolutionStrategy = EvolutionStrategy.GENETIC
    
    # 通用参数
    population_size: int = 20
    max_generations: int = 50
    mutation_rate: float = 0.1
    crossover_rate: float = 0.3
    
    # 早停
    early_stopping: bool = True
    patience: int = 5
    
    # 日志
    verbose: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target.value,
            "strategy": self.strategy.value,
            "population_size": self.population_size,
            "max_generations": self.max_generations,
            "mutation_rate": self.mutation_rate,
            "crossover_rate": self.crossover_rate,
            "early_stopping": self.early_stopping,
            "patience": self.patience,
            "verbose": self.verbose,
        }


# ============================================================
# 抽象基类
# ============================================================

class BaseEvolutionEngine(ABC):
    """
    进化引擎抽象基类
    
    所有领域进化引擎（技能、社区、代码、知识图谱、报告）应继承此类。
    子类只需实现：evolve(), evaluate(), mutate(), crossover()
    """
    
    def __init__(
        self,
        config: Optional[EvolutionConfig] = None,
        **kwargs,
    ):
        self.config = config or EvolutionConfig()
        self._history: List[Dict[str, Any]] = []
        self._best_individual: Optional[Any] = None
        self._best_fitness: float = float('-inf')
        logger.info(f"[{self.__class__.__name__}] 初始化完成")
    
    # ---------- 子类必须实现的抽象方法 ----------
    
    @abstractmethod
    def evolve(self, initial_population: List[Any], **kwargs) -> Any:
        """
        执行进化
        
        Args:
            initial_population: 初始种群
            **kwargs: 领域特定参数
            
        Returns:
            进化后的最佳个体
        """
        pass
    
    @abstractmethod
    def evaluate(self, individual: Any) -> float:
        """
        评估个体适应度
        
        Args:
            individual: 待评估个体
            
        Returns:
            适应度分数（越高越好）
        """
        pass
    
    @abstractmethod
    def mutate(self, individual: Any) -> Any:
        """
        对个体进行变异
        
        Args:
            individual: 待变异个体
            
        Returns:
            变异后的新个体
        """
        pass
    
    @abstractmethod
    def crossover(self, parent_a: Any, parent_b: Any) -> Any:
        """
        两个个体交叉产生后代
        
        Args:
            parent_a: 父代 A
            parent_b: 父代 B
            
        Returns:
            后代个体
        """
        pass
    
    # ---------- 可选覆盖的方法 ----------
    
    def select(self, population: List[Any], fitnesses: List[float]) -> List[Any]:
        """
        选择操作（默认：锦标赛选择）
        
        Args:
            population: 当前种群
            fitnesses: 每个个体的适应度
            
        Returns:
            选中的个体列表
        """
        import random
        tournament_size = max(2, len(population) // 10)
        selected = []
        for _ in range(len(population)):
            contestants = random.sample(range(len(population)), 
                                       min(tournament_size, len(population)))
            winner = max(contestants, key=lambda i: fitnesses[i])
            selected.append(population[winner])
        return selected
    
    def should_stop(self, generation: int, fitness_history: List[float]) -> bool:
        """
        判断是否早停
        
        Returns:
            True 如果应该停止
        """
        if not self.config.early_stopping:
            return False
        if generation >= self.config.max_generations:
            return True
        if len(fitness_history) < self.config.patience:
            return False
        recent = fitness_history[-self.config.patience:]
        return max(recent) - min(recent) < 1e-6
    
    # ---------- 公共工具方法 ----------
    
    def log_generation(self, generation: int, best_fitness: float, 
                      avg_fitness: float, population_size: int):
        """记录一代的进化信息"""
        record = {
            "generation": generation,
            "best_fitness": best_fitness,
            "avg_fitness": avg_fitness,
            "population_size": population_size,
            "timestamp": time.time(),
        }
        self._history.append(record)
        if self.config.verbose:
            logger.info(
                f"[{self.__class__.__name__}] Gen {generation}: "
                f"best={best_fitness:.4f}, avg={avg_fitness:.4f}, "
                f"size={population_size}"
            )
    
    def get_evolution_history(self) -> List[Dict[str, Any]]:
        """获取进化历史"""
        return self._history.copy()
    
    def reset(self):
        """重置引擎状态"""
        self._history.clear()
        self._best_individual = None
        self._best_fitness = float('-inf')
        logger.info(f"[{self.__class__.__name__}] 状态已重置")


# ============================================================
# 工厂方法
# ============================================================

def create_evolution_engine(
    target: EvolutionTarget,
    config: Optional[EvolutionConfig] = None,
    **kwargs,
) -> BaseEvolutionEngine:
    """
    根据目标类型创建对应的进化引擎
    
    Args:
        target: 进化目标类型
        config: 进化配置
        **kwargs: 传递给具体引擎的额外参数
        
    Returns:
        对应的进化引擎实例
    """
    if target == EvolutionTarget.SKILL:
        from business.skill_evolution.engine import EvolutionEngine as SkillEE
        return SkillEE(database=kwargs.get("database"), **kwargs)
    
    elif target == EvolutionTarget.AGENT:
        from business.evolving_community.evolution.evolution_engine import (
            EvolutionEngine as CommunityEE,
        )
        return CommunityEE(config=config.to_dict() if config else None, **kwargs)
    
    elif target == EvolutionTarget.CODE:
        from business.evolution_engine.evolution_engine import (
            EvolutionEngine as CodeEE,
        )
        return CodeEE(project_root=kwargs.get("project_root", "."), 
                     config=config.to_dict() if config else None)
    
    elif target == EvolutionTarget.KNOWLEDGE:
        from business.knowledge_graph.evolution import (
            EvolutionEngine as KnowledgeEE,
        )
        return KnowledgeEE(**kwargs)
    
    elif target == EvolutionTarget.REPORT:
        from business.living_tree_ai.eia_system.report_evolution import (
            EvolutionEngine as ReportEE,
        )
        return ReportEE(**kwargs)
    
    else:
        raise ValueError(f"不支持的进化目标: {target}")


from .facade import (
    EvolutionEngineFacade,
    get_evolution_facade,
    evolve_skill,
    evolve_knowledge,
)

__all__ = [
    "EvolutionTarget",
    "EvolutionStrategy", 
    "EvolutionConfig",
    "BaseEvolutionEngine",
    "create_evolution_engine",
    "EvolutionEngineFacade",
    "get_evolution_facade",
    "evolve_skill",
    "evolve_knowledge",
]
