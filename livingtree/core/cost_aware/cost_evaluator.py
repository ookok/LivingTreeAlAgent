"""
CostEvaluator - 成本评估器

实现成本认知系统的第一层：成本评估

核心功能：
- 在任务执行前，评估所需成本
- 支持三维度成本评估：金钱成本、时间成本、空间成本
- 提供决策规则：预估成本 > 预算时拒绝执行或请求确认

借鉴人类的成本意识：在行动前评估风险和收益
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class CostDimension(Enum):
    MONEY = "money"
    TIME = "time"
    SPACE = "space"
    COMPUTE = "compute"


class TaskComplexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    EXPERT = "expert"


@dataclass
class CostEstimation:
    task_id: str
    task_description: str
    complexity: TaskComplexity
    money_cost_usd: float = 0.0
    time_cost_seconds: float = 0.0
    space_cost_mb: float = 0.0
    compute_cost_gpu: float = 0.0
    api_calls: int = 0
    l4_calls: int = 0
    steps: int = 0
    confidence: float = 0.0


@dataclass
class CostBreakdown:
    item: str
    dimension: CostDimension
    amount: float
    unit: str
    cost_usd: float


class CostEvaluator:

    def __init__(self):
        self._logger = logger.bind(component="CostEvaluator")
        self._cost_baseline = {
            "l0_call": 0.0001,
            "l1_call": 0.001,
            "l4_call": 0.01,
            "api_call": 0.001,
            "step_time": 2.0,
            "memory_per_step": 10.0,
        }
        self._logger.info("✅ CostEvaluator 初始化完成")

    def estimate(self, task_description: str, task_id: str = "") -> CostEstimation:
        complexity = self._infer_complexity(task_description)
        estimation = self._estimate_by_complexity(complexity)
        estimation.task_id = task_id or f"task_{hash(task_description)}"
        estimation.task_description = task_description
        self._refine_estimation(task_description, estimation)
        self._logger.info(
            f"💰 成本评估完成: task={estimation.task_id}, "
            f"money=${estimation.money_cost_usd:.4f}, "
            f"time={estimation.time_cost_seconds:.1f}s, "
            f"space={estimation.space_cost_mb:.1f}MB"
        )
        return estimation

    def _infer_complexity(self, task_description: str) -> TaskComplexity:
        description = task_description.lower()
        expert_keywords = ["复杂", "深度分析", "大量数据", "优化", "推理", "规划"]
        complex_keywords = ["分析", "报告", "研究", "设计", "方案"]
        simple_keywords = ["查询", "搜索", "帮助", "介绍", "解释"]
        if any(keyword in description for keyword in expert_keywords):
            return TaskComplexity.EXPERT
        elif any(keyword in description for keyword in complex_keywords):
            return TaskComplexity.COMPLEX
        elif any(keyword in description for keyword in simple_keywords):
            return TaskComplexity.SIMPLE
        else:
            return TaskComplexity.MEDIUM

    def _estimate_by_complexity(self, complexity: TaskComplexity) -> CostEstimation:
        estimation = CostEstimation(
            task_id="",
            task_description="",
            complexity=complexity,
            confidence=0.7
        )
        if complexity == TaskComplexity.SIMPLE:
            estimation.l4_calls = 0
            estimation.api_calls = 1
            estimation.steps = 1
            estimation.confidence = 0.9
        elif complexity == TaskComplexity.MEDIUM:
            estimation.l4_calls = 1
            estimation.api_calls = 2
            estimation.steps = 3
            estimation.confidence = 0.8
        elif complexity == TaskComplexity.COMPLEX:
            estimation.l4_calls = 3
            estimation.api_calls = 5
            estimation.steps = 5
            estimation.confidence = 0.7
        elif complexity == TaskComplexity.EXPERT:
            estimation.l4_calls = 5
            estimation.api_calls = 10
            estimation.steps = 10
            estimation.confidence = 0.6
        self._calculate_costs(estimation)
        return estimation

    def _calculate_costs(self, estimation: CostEstimation):
        estimation.money_cost_usd = (
            estimation.l4_calls * self._cost_baseline["l4_call"] +
            estimation.api_calls * self._cost_baseline["api_call"]
        )
        estimation.time_cost_seconds = estimation.steps * self._cost_baseline["step_time"]
        estimation.space_cost_mb = estimation.steps * self._cost_baseline["memory_per_step"]
        estimation.compute_cost_gpu = estimation.l4_calls * 20000

    def _refine_estimation(self, task_description: str, estimation: CostEstimation):
        desc = task_description.lower()
        if "数据" in desc or "分析" in desc:
            estimation.space_cost_mb *= 2
            estimation.time_cost_seconds *= 1.5
        if "优化" in desc or "迭代" in desc:
            estimation.l4_calls *= 2
            estimation.steps *= 2
        if "工具" in desc or "调用" in desc:
            estimation.api_calls += 2
        self._calculate_costs(estimation)

    def get_breakdown(self, estimation: CostEstimation) -> List[CostBreakdown]:
        breakdown = []
        if estimation.l4_calls > 0:
            breakdown.append(CostBreakdown(
                item=f"L4模型调用 ({estimation.l4_calls}次)",
                dimension=CostDimension.MONEY,
                amount=estimation.l4_calls,
                unit="次",
                cost_usd=estimation.l4_calls * self._cost_baseline["l4_call"]
            ))
        if estimation.api_calls > 0:
            breakdown.append(CostBreakdown(
                item=f"API调用 ({estimation.api_calls}次)",
                dimension=CostDimension.MONEY,
                amount=estimation.api_calls,
                unit="次",
                cost_usd=estimation.api_calls * self._cost_baseline["api_call"]
            ))
        breakdown.append(CostBreakdown(
            item="执行时间",
            dimension=CostDimension.TIME,
            amount=estimation.time_cost_seconds,
            unit="秒",
            cost_usd=0.0
        ))
        breakdown.append(CostBreakdown(
            item="内存占用",
            dimension=CostDimension.SPACE,
            amount=estimation.space_cost_mb,
            unit="MB",
            cost_usd=0.0
        ))
        return breakdown

    def is_within_budget(self, estimation: CostEstimation, budget_usd: float) -> bool:
        return estimation.money_cost_usd <= budget_usd

    def get_decision(self, estimation: CostEstimation, budget_usd: float) -> str:
        if estimation.money_cost_usd <= budget_usd * 0.5:
            return "execute"
        elif estimation.money_cost_usd <= budget_usd:
            return "confirm"
        else:
            return "reject"


cost_evaluator = CostEvaluator()


def get_cost_evaluator() -> CostEvaluator:
    return cost_evaluator
