"""
渐进去中心化AI社区 - Evolving Decentralized AI Community

一个正在进化的数字生命群落，多元思想的实验场。

核心哲学：
- 阶段1：中心化花园（控制、培育、引导）
- 阶段2：联邦森林（协作、交流、分化）
- 阶段3：生态雨林（自主、共生、演化）

模块结构：
├── cognition/              # 认知引擎
├── evolution/              # 进化机制
├── exchange/               # 交流协议
├── stages/                 # 阶段演进
├── metrics/               # 度量系统
└── community.py           # 社区核心
"""

from .community import (
    EvolvingCommunity,
    AIAgent,
)
from .cognition import (
    PersonalityProfile,
    PersonalityDimension,
    CognitiveSpace,
    ThinkingEngine,
    ThoughtType,
    Thought,
)
from .stages import (
    StageType,
    GardenStage,
    ForestStage,
    RainforestStage,
)
from .evolution import (
    EvolutionEngine,
    FitnessScore,
)
from .exchange import (
    ExchangeProtocol,
    ExchangeContent,
    ContentLevel,
)
from .metrics import (
    MetricsSystem,
    MetricValue,
    GuidanceAction,
)

__all__ = [
    # 核心
    "EvolvingCommunity",
    "AIAgent",

    # 认知
    "PersonalityProfile",
    "PersonalityDimension",
    "CognitiveSpace",
    "ThinkingEngine",
    "ThoughtType",
    "Thought",

    # 阶段
    "StageType",
    "GardenStage",
    "ForestStage",
    "RainforestStage",

    # 进化
    "EvolutionEngine",
    "FitnessScore",

    # 交流
    "ExchangeProtocol",
    "ExchangeContent",
    "ContentLevel",

    # 度量
    "MetricsSystem",
    "MetricValue",
    "GuidanceAction",
]