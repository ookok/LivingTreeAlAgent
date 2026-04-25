# base_evaluator.py - 评估器基类和指标体系

"""
评估器基类定义

提供统一的评估器接口和指标定义
"""

from typing import List, Dict, Any, Optional, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import time


class MetricType(Enum):
    """指标类型"""
    ACCURACY = "accuracy"              # 准确率
    F1_SCORE = "f1_score"              # F1 分数
    PRECISION = "precision"            # 精确率
    RECALL = "recall"                   # 召回率
    PERPLEXITY = "perplexity"          # 困惑度（越低越好）
    BPB = "bpb"                        # Bits Per Byte（越低越好）
    LATENCY = "latency"                # 延迟（越低越好）
    THROUGHPUT = "throughput"          # 吞吐量（越高越好）
    QUALITY = "quality"                # 质量评分
    COVERAGE = "coverage"              # 覆盖率
    CUSTOM = "custom"                  # 自定义指标


@dataclass
class MetricScore:
    """指标分数"""
    name: str                          # 指标名称
    value: float                       # 分值
    metric_type: MetricType            # 指标类型
    unit: str = ""                     # 单位
    higher_is_better: bool = True      # 是否越高越好
    description: str = ""              # 描述
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'value': self.value,
            'type': self.metric_type.value,
            'unit': self.unit,
            'higher_is_better': self.higher_is_better,
            'description': self.description,
            'metadata': self.metadata
        }


@dataclass
class EvaluationResult:
    """评估结果"""
    evaluator_name: str                 # 评估器名称
    timestamp: str = ""                 # 评估时间
    duration_ms: float = 0.0           # 评估耗时
    metrics: Dict[str, MetricScore] = field(default_factory=dict)  # 指标分数
    raw_data: Dict[str, Any] = field(default_factory=dict)  # 原始数据
    errors: Optional[List[str]] = None # 错误信息
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'evaluator_name': self.evaluator_name,
            'timestamp': self.timestamp,
            'duration_ms': self.duration_ms,
            'metrics': {k: v.to_dict() for k, v in self.metrics.items()},
            'raw_data': self.raw_data,
            'errors': self.errors,
            'metadata': self.metadata
        }
    
    def get_overall_score(self) -> float:
        """获取总分"""
        if not self.metrics:
            return 0.0
        
        scores = []
        for metric in self.metrics.values():
            # 如果越低越好，取反
            score = metric.value if metric.higher_is_better else (100 - metric.value)
            scores.append(score)
        
        return sum(scores) / len(scores)
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        return {
            'evaluator': self.evaluator_name,
            'timestamp': self.timestamp,
            'metrics_count': len(self.metrics),
            'overall_score': self.get_overall_score(),
            'has_errors': bool(self.errors)
        }


@dataclass
class EvaluationSuite:
    """评估套件"""
    name: str                           # 套件名称
    version: str                        # 版本
    evaluators: List[str] = field(default_factory=list)  # 评估器列表
    description: str = ""               # 描述
    created_at: str = ""                # 创建时间
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationConfig:
    """评估配置"""
    enabled: bool = True                # 是否启用
    cache_results: bool = True          # 是否缓存结果
    parallel_execution: bool = False   # 是否并行执行
    timeout_seconds: int = 300         # 超时时间
    retry_count: int = 3               # 重试次数
    custom_config: Dict[str, Any] = field(default_factory=dict)  # 自定义配置


@dataclass
class TestCase:
    """测试用例"""
    id: str                             # 用例ID
    prompt: str                         # 输入提示
    expected: Any                       # 期望输出
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    category: str = ""                  # 类别
    difficulty: str = "medium"          # 难度


class BaseEvaluator(ABC):
    """
    评估器基类
    
    所有评估器必须继承此类并实现 evaluate 方法
    """
    
    def __init__(
        self,
        name: str,
        project_root: str,
        config: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.project_root = project_root
        self.config = config or {}
        self._cache: Dict[str, EvaluationResult] = {}
    
    @abstractmethod
    def evaluate(
        self,
        custom_prompts: Optional[List[Dict[str, Any]]] = None
    ) -> EvaluationResult:
        """
        执行评估
        
        Args:
            custom_prompts: 自定义测试用例
        
        Returns:
            评估结果
        """
        pass
    
    def _create_result(
        self,
        metrics: Dict[str, MetricScore],
        raw_data: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None
    ) -> EvaluationResult:
        """创建评估结果"""
        return EvaluationResult(
            evaluator_name=self.name,
            metrics=metrics,
            raw_data=raw_data or {},
            errors=errors
        )
    
    def _create_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType,
        unit: str = "",
        higher_is_better: bool = True,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> MetricScore:
        """创建指标"""
        return MetricScore(
            name=name,
            value=value,
            metric_type=metric_type,
            unit=unit,
            higher_is_better=higher_is_better,
            description=description,
            metadata=metadata or {}
        )
    
    def get_cache_key(self, custom_prompts: Optional[List[Dict]] = None) -> str:
        """获取缓存键"""
        if custom_prompts:
            prompts_str = str(sorted([p.get('id', '') for p in custom_prompts]))
            return f"{self.name}:{hash(prompts_str)}"
        return f"{self.name}:default"
    
    def get_cached_result(self, cache_key: str) -> Optional[EvaluationResult]:
        """获取缓存结果"""
        return self._cache.get(cache_key)
    
    def cache_result(self, cache_key: str, result: EvaluationResult):
        """缓存结果"""
        self._cache[cache_key] = result
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
    
    def get_info(self) -> Dict[str, Any]:
        """获取评估器信息"""
        return {
            'name': self.name,
            'project_root': self.project_root,
            'config': self.config,
            'cached_results': len(self._cache)
        }


# 辅助函数
from dataclasses import asdict


def calculate_accuracy(predictions: List[Any], ground_truth: List[Any]) -> float:
    """计算准确率"""
    if len(predictions) != len(ground_truth):
        raise ValueError("预测和真值长度不一致")
    if not predictions:
        return 0.0
    correct = sum(1 for p, t in zip(predictions, ground_truth) if p == t)
    return (correct / len(predictions)) * 100


def calculate_f1(
    precision: float,
    recall: float
) -> float:
    """计算 F1 分数"""
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


def normalize_score(
    score: float,
    min_val: float = 0.0,
    max_val: float = 100.0,
    higher_is_better: bool = True
) -> float:
    """归一化分数到 0-100"""
    normalized = (score - min_val) / (max_val - min_val) * 100
    normalized = max(0.0, min(100.0, normalized))
    return normalized if higher_is_better else (100 - normalized)


def calculate_perplexity(log_likelihood: float, num_tokens: int) -> float:
    """计算困惑度"""
    if num_tokens == 0:
        return float('inf')
    return pow(2, -log_likelihood / num_tokens)


def calculate_bpb(log_likelihood: float, num_bytes: int) -> float:
    """计算 Bits Per Byte"""
    if num_bytes == 0:
        return float('inf')
    return -log_likelihood / num_bytes
