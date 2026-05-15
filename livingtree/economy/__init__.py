"""LivingTree Economic Engine — 经济范式核心模块.

将"最小成本 × 最快速度 × 最高质量"三元悖论植入项目决策的每个环节，
同时确保合法合规，为用户谋求最大经济利益。

Core modules:
  - TrilemmaVector: 成本-速度-质量三元评分向量
  - EconomicPolicy: 可配置的经济策略权重与约束
  - ROIModel: 投入产出比计算与预测
  - ComplianceGate: 合法合规审查门控
  - EconomicOrchestrator: 经济决策编排器
  - GRPOOptimizer: 3-in-1 composite GRPO (Latent + Spatial + TDM)
"""

from .economic_engine import (
    TrilemmaVector,
    EconomicPolicy,
    ROIModel,
    ROIResult,
    ComplianceGate,
    ComplianceResult,
    EconomicOrchestrator,
    EconomicDecision,
    AdaptiveEconomicScheduler,
    get_economic_orchestrator,
)

from .grpo_optimizer import (
    LatentGRPO,
    LatentEncoder,
    LatentVector,
    LatentGRPOResult,
    get_latent_grpo,
    SpatialGRPOOptimizer,
    SpatialContextExtractor,
    SpatialContext,
    SpatialReward,
    SGRPOResult,
    get_sgrpo,
    TDMRewardOptimizer,
    SurrogateRewardModel,
    PerStepReward,
    TrajectoryReward,
    TDMOptimizationResult,
    RewardType,
    lifeengine_to_trajectory,
    get_tdm_optimizer,
    GRPOOptimizer,
    get_grpo_optimizer,
)

__all__ = [
    "TrilemmaVector",
    "EconomicPolicy",
    "ROIModel",
    "ROIResult",
    "ComplianceGate",
    "ComplianceResult",
    "EconomicOrchestrator",
    "EconomicDecision",
    "AdaptiveEconomicScheduler",
    "get_economic_orchestrator",
    "LatentGRPO",
    "LatentEncoder",
    "LatentVector",
    "LatentGRPOResult",
    "get_latent_grpo",
    "SpatialGRPOOptimizer",
    "SpatialContextExtractor",
    "SpatialContext",
    "SpatialReward",
    "SGRPOResult",
    "get_sgrpo",
    "TDMRewardOptimizer",
    "SurrogateRewardModel",
    "PerStepReward",
    "TrajectoryReward",
    "TDMOptimizationResult",
    "RewardType",
    "lifeengine_to_trajectory",
    "get_tdm_optimizer",
    "GRPOOptimizer",
    "get_grpo_optimizer",
]
