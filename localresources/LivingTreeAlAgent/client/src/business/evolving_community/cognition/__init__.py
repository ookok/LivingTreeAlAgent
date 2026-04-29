"""
认知引擎模块 - Cognition Engine

包含：
- personality.py: 个性化人格参数
- cognition_space.py: 个性化认知空间
- thinking_engine.py: 思考引擎
"""

from .personality import (
    PersonalityProfile,
    PersonalityDimension,
    PersonalityFactory,
)
from .cognition_space import (
    CognitiveSpace,
    ConceptNode,
    CognitiveSpaceFactory,
)
from .thinking_engine import (
    ThinkingEngine,
    ThoughtType,
    Thought,
    ThinkingContext,
)

__all__ = [
    "PersonalityProfile",
    "PersonalityDimension",
    "PersonalityFactory",
    "CognitiveSpace",
    "ConceptNode",
    "CognitiveSpaceFactory",
    "ThinkingEngine",
    "ThoughtType",
    "Thought",
    "ThinkingContext",
]