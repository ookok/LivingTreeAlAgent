"""
社区阶段演进 - Community Stage Evolution

渐进去中心化的三个阶段：
1. 中心化花园（Garden）- 控制、培育、引导
2. 联邦森林（Forest）- 协作、交流、分化
3. 生态雨林（Rainforest）- 自主、共生、演化
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from enum import Enum


class StageType(Enum):
    """社区阶段类型"""
    GARDEN = "garden"                   # 中心化花园
    FOREST = "forest"                  # 联邦森林
    RAINFOREST = "rainforest"         # 生态雨林


@dataclass
class StageMetrics:
    """阶段度量"""
    stage: StageType
    timestamp: float = field(default_factory=time.time)

    # 成熟度指标
    decentralization_level: float = 0.0  # 去中心化程度 0-1
    autonomy_level: float = 0.0         # 自主性程度 0-1
    diversity_level: float = 0.0        # 多样性程度 0-1
    complexity_level: float = 0.0      # 复杂度程度 0-1

    # 稳定性指标
    stability_score: float = 0.0        # 稳定性评分 0-1
    resilience_score: float = 0.0      # 弹性评分 0-1

    # 进化指标
    innovation_rate: float = 0.0       # 创新率
    evolution_velocity: float = 0.0     # 进化速度

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "timestamp": self.timestamp,
            "decentralization_level": self.decentralization_level,
            "autonomy_level": self.autonomy_level,
            "diversity_level": self.diversity_level,
            "complexity_level": self.complexity_level,
            "stability_score": self.stability_score,
            "resilience_score": self.resilience_score,
            "innovation_rate": self.innovation_rate,
            "evolution_velocity": self.evolution_velocity,
        }


class StageTransition:
    """阶段转换条件"""

    # 阶段1 -> 阶段2 的条件
    GARDEN_TO_FOREST = {
        "min_duration_days": 180,          # 最少6个月
        "min_agent_count": 10,              # 最少10个AI
        "min_diversity": 0.3,               # 最低多样性
        "required_capabilities": [
            "basic_exchange",
            "interest_clustering",
            "cross_domain_communication",
        ],
    }

    # 阶段2 -> 阶段3 的条件
    FOREST_TO_RAINFOREST = {
        "min_duration_days": 365,          # 最少12个月
        "min_agent_count": 50,             # 最少50个AI
        "min_diversity": 0.5,               # 中等多样性
        "decentralization_threshold": 0.5,  # 去中心化程度阈值
        "required_capabilities": [
            "autonomous_evolution",
            "ecological_niche_formation",
            "self_organization",
        ],
    }


class BaseStage(ABC):
    """
    基础阶段类

    定义每个阶段的通用接口和行为模式。
    """

    def __init__(self, stage_type: StageType, config: Dict[str, Any]):
        self.stage_type = stage_type
        self.config = config
        self.enter_time = time.time()

    @abstractmethod
    def calculate_metrics(self, community_state: Dict[str, Any]) -> StageMetrics:
        """计算阶段度量"""
        pass

    @abstractmethod
    def should_transition_to_next(self, metrics: StageMetrics, transition_rules: Dict) -> bool:
        """判断是否应该转换到下一阶段"""
        pass

    @abstractmethod
    def get_control_parameters(self) -> Dict[str, Any]:
        """获取控制参数"""
        pass

    def get_duration_days(self) -> float:
        """获取当前阶段持续天数"""
        return (time.time() - self.enter_time) / 86400


class GardenStage(BaseStage):
    """
    中心化花园阶段

    特征：
    - 中心节点控制大部分决策
    - 统一身份管理
    - 标准化交流协议
    - 人工引导进化方向

    控制参数：
    - 进化方向：由中心节点设定
    - 交配选择：人工选择
    - 选择压力：中心节点调整
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            StageType.GARDEN,
            config or {
                "central_control": True,
                "manual_guidance": True,
                "guided_evolution": True,
            }
        )

    def calculate_metrics(self, community_state: Dict[str, Any]) -> StageMetrics:
        """计算中心化花园阶段的度量"""
        agent_count = community_state.get("agent_count", 0)
        diversity = community_state.get("cognitive_diversity", 0.0)

        metrics = StageMetrics(stage=StageType.GARDEN)
        metrics.decentralization_level = 0.1 + 0.05 * min(agent_count / 10, 1)
        metrics.autonomy_level = 0.2
        metrics.diversity_level = diversity
        metrics.complexity_level = 0.2 + 0.1 * min(agent_count / 10, 1)
        metrics.stability_score = 0.9
        metrics.resilience_score = 0.3
        metrics.innovation_rate = 0.2
        metrics.evolution_velocity = 0.1

        return metrics

    def should_transition_to_next(self, metrics: StageMetrics, rules: Dict) -> bool:
        """判断是否应该转换到联邦森林阶段"""
        if self.get_duration_days() < rules.get("min_duration_days", 180):
            return False

        if metrics.diversity_level < rules.get("min_diversity", 0.3):
            return False

        required = rules.get("required_capabilities", [])
        # 检查是否具备必要能力（简化判断）
        return len(required) > 0

    def get_control_parameters(self) -> Dict[str, Any]:
        """获取控制参数"""
        return {
            "evolution_direction": "guided",     # 进化方向：引导
            "selection_method": "artificial",      # 选择方法：人工
            "selection_pressure": 0.8,             # 选择压力：高
            "mutation_rate": 0.05,                 # 变异率：低
            "crossover_rate": 0.1,                # 交叉率：低
            "centralized_scheduling": True,        # 中心化调度
            "protocol_standardization": 1.0,       # 协议标准化：高
            "identity_management": "centralized",   # 身份管理：中心化
        }


class ForestStage(BaseStage):
    """
    联邦森林阶段

    特征：
    - 轻量级元协调节点
    - 基于兴趣的联邦自治
    - 跨联邦交流协议
    - 环境塑造引导进化

    控制参数：
    - 进化方向：环境塑造
    - 交配选择：半自主
    - 选择压力：自适应
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            StageType.FOREST,
            config or {
                "federation_based": True,
                "interest_clusters": True,
                "environment_shaping": True,
            }
        )

    def calculate_metrics(self, community_state: Dict[str, Any]) -> StageMetrics:
        """计算联邦森林阶段的度量"""
        agent_count = community_state.get("agent_count", 0)
        federation_count = community_state.get("federation_count", 1)
        diversity = community_state.get("cognitive_diversity", 0.0)

        metrics = StageMetrics(stage=StageType.FOREST)
        metrics.decentralization_level = 0.3 + 0.1 * min(agent_count / 50, 1)
        metrics.autonomy_level = 0.5 + 0.1 * min(federation_count / 5, 1)
        metrics.diversity_level = diversity
        metrics.complexity_level = 0.4 + 0.2 * min(agent_count / 50, 1)
        metrics.stability_score = 0.7
        metrics.resilience_score = 0.6
        metrics.innovation_rate = 0.5
        metrics.evolution_velocity = 0.3

        return metrics

    def should_transition_to_next(self, metrics: StageMetrics, rules: Dict) -> bool:
        """判断是否应该转换到生态雨林阶段"""
        if self.get_duration_days() < rules.get("min_duration_days", 365):
            return False

        if metrics.decentralization_level < rules.get("decentralization_threshold", 0.5):
            return False

        required = rules.get("required_capabilities", [])
        return len(required) > 0

    def get_control_parameters(self) -> Dict[str, Any]:
        """获取控制参数"""
        return {
            "evolution_direction": "environment_shaping",  # 进化方向：环境塑造
            "selection_method": "semi_autonomous",           # 选择方法：半自主
            "selection_pressure": 0.5,                      # 选择压力：中等
            "mutation_rate": 0.1,                           # 变异率：中等
            "crossover_rate": 0.3,                          # 交叉率：中等
            "federation_autonomy": 0.6,                     # 联邦自治度
            "cross_federation_exchange": True,              # 允许跨联邦交流
            "protocol_standardization": 0.7,                # 协议标准化：中等
            "identity_management": "federated",             # 身份管理：联邦式
        }


class RainforestStage(BaseStage):
    """
    生态雨林阶段

    特征：
    - 完全自主的节点连接
    - 生态位竞争与合作
    - 自主进化算法
    - 生态稳定性维护

    控制参数：
    - 进化方向：自然选择
    - 交配选择：生态驱动
    - 选择压力：自然平衡
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            StageType.RAINFOREST,
            config or {
                "fully_autonomous": True,
                "ecological_niches": True,
                "self_organization": True,
            }
        )

    def calculate_metrics(self, community_state: Dict[str, Any]) -> StageMetrics:
        """计算生态雨林阶段的度量"""
        agent_count = community_state.get("agent_count", 0)
        niche_count = community_state.get("niche_count", 1)
        diversity = community_state.get("cognitive_diversity", 0.0)

        metrics = StageMetrics(stage=StageType.RAINFOREST)
        metrics.decentralization_level = 0.8 + 0.1 * min(agent_count / 100, 1)
        metrics.autonomy_level = 0.9
        metrics.diversity_level = diversity
        metrics.complexity_level = 0.7 + 0.2 * min(agent_count / 100, 1)
        metrics.stability_score = 0.6 + 0.1 * min(niche_count / 10, 1)
        metrics.resilience_score = 0.9
        metrics.innovation_rate = 0.8
        metrics.evolution_velocity = 0.6

        return metrics

    def should_transition_to_next(self, metrics: StageMetrics, rules: Dict) -> bool:
        """生态雨林阶段不再转换（最终阶段）"""
        return False

    def get_control_parameters(self) -> Dict[str, Any]:
        """获取控制参数"""
        return {
            "evolution_direction": "natural_selection",     # 进化方向：自然选择
            "selection_method": "ecological",               # 选择方法：生态驱动
            "selection_pressure": 0.3,                     # 选择压力：低
            "mutation_rate": 0.15,                          # 变异率：较高
            "crossover_rate": 0.5,                          # 交叉率：较高
            "federation_autonomy": 1.0,                     # 联邦自治度：完全
            "cross_federation_exchange": True,              # 完全开放跨联邦交流
            "protocol_standardization": 0.4,                # 协议标准化：低
            "identity_management": "decentralized",         # 身份管理：去中心化
            "emergence_enabled": True,                       # 允许涌现
        }


class StageManager:
    """
    阶段管理器

    负责管理社区的阶段演进。
    """

    def __init__(self):
        self.current_stage: BaseStage = GardenStage()
        self.stage_history: List[StageMetrics] = []

    def get_current_stage(self) -> StageType:
        """获取当前阶段类型"""
        return self.current_stage.stage_type

    def check_transition(self, community_state: Dict[str, Any]) -> Optional[StageType]:
        """检查是否应该转换阶段"""
        metrics = self.current_stage.calculate_metrics(community_state)
        self.stage_history.append(metrics)

        next_stage_type = None

        if isinstance(self.current_stage, GardenStage):
            if self.current_stage.should_transition_to_next(
                metrics, StageTransition.GARDEN_TO_FOREST
            ):
                next_stage_type = StageType.FOREST

        elif isinstance(self.current_stage, ForestStage):
            if self.current_stage.should_transition_to_next(
                metrics, StageTransition.FOREST_TO_RAINFOREST
            ):
                next_stage_type = StageType.RAINFOREST

        if next_stage_type:
            self._transition_to(next_stage_type)

        return next_stage_type

    def _transition_to(self, new_stage_type: StageType):
        """执行阶段转换"""
        if new_stage_type == StageType.GARDEN:
            self.current_stage = GardenStage()
        elif new_stage_type == StageType.FOREST:
            self.current_stage = ForestStage()
        elif new_stage_type == StageType.RAINFOREST:
            self.current_stage = RainforestStage()

    def get_control_parameters(self) -> Dict[str, Any]:
        """获取当前阶段的控制参数"""
        return self.current_stage.get_control_parameters()

    def force_transition(self, new_stage_type: StageType):
        """强制转换阶段（用于测试或特殊需求）"""
        self._transition_to(new_stage_type)

    def get_evolution_roadmap(self) -> Dict[str, Any]:
        """获取演进路线图"""
        return {
            "current_stage": self.current_stage.stage_type.value,
            "duration_days": self.current_stage.get_duration_days(),
            "history_length": len(self.stage_history),
            "control_parameters": self.get_control_parameters(),
            "next_transition_check": "daily",
        }