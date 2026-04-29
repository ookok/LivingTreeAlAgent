"""
llmfit 集成模块

参考 llmfit 框架，实现：
- 硬件检测
- 多维度模型评分
- 硬件感知模型推荐

增强本项目的 model_hub 模块
"""

from .hardware_detector import (
    HardwareBackend,
    HardwareSpec,
    ModelRequirements,
    BaseHardwareDetector,
    GPUDetector,
    RuntimeDetector,
    HardwareDetector,
)

from .model_scorer import (
    ScoreDimension,
    ModelScore,
    ModelInfo,
    QualityScorer,
    SpeedScorer,
    FitScorer,
    ContextScorer,
    ModelScorer,
)

from .model_recommender import (
    UseCase,
    ModelRecommendation,
    RecommendationResult,
    ModelDatabase,
    ModelRecommender,
)

__all__ = [
    # 硬件检测
    "HardwareBackend",
    "HardwareSpec",
    "ModelRequirements",
    "BaseHardwareDetector",
    "GPUDetector",
    "RuntimeDetector",
    "HardwareDetector",
    # 模型评分
    "ScoreDimension",
    "ModelScore",
    "ModelInfo",
    "QualityScorer",
    "SpeedScorer",
    "FitScorer",
    "ContextScorer",
    "ModelScorer",
    # 模型推荐
    "UseCase",
    "ModelRecommendation",
    "RecommendationResult",
    "ModelDatabase",
    "ModelRecommender",
]
