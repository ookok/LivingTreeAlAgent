"""
认知推理系统 (Cognitive Reasoning System)

核心能力：
1. 因果推理 - 建立因果图并进行推理
2. 符号推理 - 规则引擎与逻辑推理
3. 类比推理 - 类比迁移与相似性匹配
4. 反事实推理 - 假设性推理

推理层次：
- 因果层次第1层：关联推理
- 因果层次第2层：干预推理 (do-calculus)
- 因果层次第3层：反事实推理
"""

from .causal_reasoner import CausalReasoner, CausalGraph, CausalNode, InterventionResult
from .symbolic_engine import SymbolicEngine, Rule, SymbolicResult
from .analogical_reasoner import AnalogicalReasoner, AnalogicalMapping, AnalogicalResult
from .counterfactual_engine import CounterfactualEngine, CounterfactualResult
from .reasoning_coordinator import ReasoningCoordinator, get_reasoning_coordinator, ReasoningType

__all__ = [
    # 因果推理
    'CausalReasoner',
    'CausalGraph',
    'CausalNode',
    'InterventionResult',
    
    # 符号推理
    'SymbolicEngine',
    'Rule',
    'SymbolicResult',
    
    # 类比推理
    'AnalogicalReasoner',
    'AnalogicalMapping',
    'AnalogicalResult',
    
    # 反事实推理
    'CounterfactualEngine',
    'CounterfactualResult',
    
    # 推理协调
    'ReasoningCoordinator',
    'get_reasoning_coordinator',
    'ReasoningType',
]


def reason(query: str, reasoning_type: str = "causal") -> dict:
    """
    统一推理接口
    
    Args:
        query: 查询内容
        reasoning_type: 推理类型 (causal/symbolic/analogical/counterfactual)
    
    Returns:
        推理结果
    """
    coordinator = get_reasoning_coordinator()
    return coordinator.reason(query, reasoning_type)