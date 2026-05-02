"""
认知推理系统 (Cognitive Reasoning System)

多引擎认知推理框架，整合多种推理范式：
1. 类比推理 (Analogical Reasoning) - 基于案例相似性的推理
2. 因果推理 (Causal Reasoning) - 基于因果关系的推理
3. 符号推理 (Symbolic Reasoning) - 基于形式逻辑的推理
4. 反事实推理 (Counterfactual Reasoning) - 假设性推理

通过 ReasoningCoordinator 协调各引擎，实现多引擎融合推理。
"""

from .reasoning_coordinator import ReasoningCoordinator
from .analogical_reasoner import AnalogicalReasoner
from .causal_reasoner import CausalReasoner
from .symbolic_engine import SymbolicEngine
from .counterfactual_engine import CounterfactualEngine

__all__ = [
    "ReasoningCoordinator",
    "AnalogicalReasoner",
    "CausalReasoner",
    "SymbolicEngine",
    "CounterfactualEngine",
]
