# evaluator/__init__.py - Evaluation Framework 模块导出

"""
Evaluation Framework - 量化评估模块

提供 Agent 能力量化评估的完整解决方案
"""

from .base_evaluator import (
    BaseEvaluator,
    EvaluationResult,
    MetricScore,
    MetricType,
    EvaluationSuite,
    EvaluationConfig,
    TestCase,
    calculate_accuracy,
    calculate_f1,
    normalize_score,
    calculate_perplexity,
    calculate_bpb
)

from .dclm_evaluator import DCLMEvaluator, DCLMScore
from .bpb_evaluator import BPBEvaluator, BPBScore
from .benchmark_evaluator import BenchmarkEvaluator, BenchmarkScore, BenchmarkTask
from .evolution_evaluator import (
    EvolutionEvaluator,
    EvaluationMode,
    CapabilityDimension,
    CapabilityScore,
    EvolutionMetrics
)

__all__ = [
    # 基类
    'BaseEvaluator',
    'EvaluationResult',
    'MetricScore',
    'MetricType',
    'EvaluationSuite',
    'EvaluationConfig',
    'TestCase',
    'calculate_accuracy',
    'calculate_f1',
    'normalize_score',
    'calculate_perplexity',
    'calculate_bpb',
    
    # DCLM 评估器
    'DCLMEvaluator',
    'DCLMScore',
    
    # BPB 评估器
    'BPBEvaluator',
    'BPBScore',
    
    # Benchmark 评估器
    'BenchmarkEvaluator',
    'BenchmarkScore',
    'BenchmarkTask',
    
    # Evolution Evaluator
    'EvolutionEvaluator',
    'EvaluationMode',
    'CapabilityDimension',
    'CapabilityScore',
    'EvolutionMetrics',
]
