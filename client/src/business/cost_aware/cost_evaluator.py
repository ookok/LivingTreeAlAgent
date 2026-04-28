"""
CostEvaluator - 成本评估器

实现成本认知系统的第一层：成本评估

核心功能：
- 在任务执行前，评估所需成本
- 支持三维度成本评估：金钱成本、时间成本、空间成本
- 提供决策规则：预估成本 > 预算时拒绝执行或请求确认

借鉴人类的成本意识：在行动前评估风险和收益

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class CostDimension(Enum):
    """成本维度"""
    MONEY = "money"       # 金钱成本（API调用费用）
    TIME = "time"         # 时间成本（执行时间）
    SPACE = "space"       # 空间成本（存储/内存）
    COMPUTE = "compute"   # 算力成本（GPU/CPU）


class TaskComplexity(Enum):
    """任务复杂度"""
    SIMPLE = "simple"     # 简单任务
    MEDIUM = "medium"     # 中等任务
    COMPLEX = "complex"   # 复杂任务
    EXPERT = "expert"     # 专家级任务


@dataclass
class CostEstimation:
    """
    成本预估结果
    """
    task_id: str
    task_description: str
    complexity: TaskComplexity
    
    # 成本预估
    money_cost_usd: float = 0.0      # 预估金钱成本（USD）
    time_cost_seconds: float = 0.0   # 预估时间成本（秒）
    space_cost_mb: float = 0.0       # 预估空间成本（MB）
    compute_cost_gpu: float = 0.0    # 预估算力成本（GPU显存 MB）
    
    # 详细分解
    api_calls: int = 0               # 预计API调用次数
    l4_calls: int = 0                # 预计L4模型调用次数
    steps: int = 0                   # 预计步骤数
    
    # 置信度
    confidence: float = 0.0          # 预估置信度 (0-1)


@dataclass
class CostBreakdown:
    """
    成本明细
    """
    item: str             # 成本项名称
    dimension: CostDimension
    amount: float         # 数量
    unit: str             # 单位
    cost_usd: float       # 费用（USD）


class CostEvaluator:
    """
    成本评估器
    
    在任务执行前评估所需成本，支持：
    1. 金钱成本评估（API调用费用）
    2. 时间成本评估（执行时间）
    3. 空间成本评估（存储/内存）
    """
    
    def __init__(self):
        self._logger = logger.bind(component="CostEvaluator")
        
        # 成本基准（可配置）
        self._cost_baseline = {
            "l0_call": 0.0001,   # L0模型调用成本（USD）
            "l1_call": 0.001,    # L1模型调用成本（USD）
            "l4_call": 0.01,     # L4模型调用成本（USD）
            "api_call": 0.001,   # 普通API调用成本（USD）
            "step_time": 2.0,    # 每步平均时间（秒）
            "memory_per_step": 10.0,  # 每步内存占用（MB）
        }
        
        self._logger.info("✅ CostEvaluator 初始化完成")
    
    def estimate(self, task_description: str, task_id: str = "") -> CostEstimation:
        """
        评估任务成本
        
        Args:
            task_description: 任务描述
            task_id: 任务ID（可选）
            
        Returns:
            成本预估结果
        """
        # 确定任务复杂度
        complexity = self._infer_complexity(task_description)
        
        # 根据复杂度估算成本
        estimation = self._estimate_by_complexity(complexity)
        
        # 设置基本信息
        estimation.task_id = task_id or f"task_{hash(task_description)}"
        estimation.task_description = task_description
        
        # 进一步细化评估（基于任务描述）
        self._refine_estimation(task_description, estimation)
        
        self._logger.info(
            f"💰 成本评估完成: task={estimation.task_id}, "
            f"money=${estimation.money_cost_usd:.4f}, "
            f"time={estimation.time_cost_seconds:.1f}s, "
            f"space={estimation.space_cost_mb:.1f}MB"
        )
        
        return estimation
    
    def _infer_complexity(self, task_description: str) -> TaskComplexity:
        """
        根据任务描述推断复杂度
        
        Args:
            task_description: 任务描述
            
        Returns:
            任务复杂度
        """
        description = task_description.lower()
        
        # 关键词匹配
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
        """
        根据复杂度估算成本
        
        Args:
            complexity: 任务复杂度
            
        Returns:
            成本预估结果
        """
        estimation = CostEstimation(
            task_id="",
            task_description="",
            complexity=complexity,
            confidence=0.7  # 默认置信度
        )
        
        # 根据复杂度设置不同的预估参数
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
        
        # 计算成本
        self._calculate_costs(estimation)
        
        return estimation
    
    def _calculate_costs(self, estimation: CostEstimation):
        """
        根据调用次数计算成本
        
        Args:
            estimation: 成本预估对象（会被修改）
        """
        # 金钱成本
        estimation.money_cost_usd = (
            estimation.l4_calls * self._cost_baseline["l4_call"] +
            estimation.api_calls * self._cost_baseline["api_call"]
        )
        
        # 时间成本
        estimation.time_cost_seconds = estimation.steps * self._cost_baseline["step_time"]
        
        # 空间成本
        estimation.space_cost_mb = estimation.steps * self._cost_baseline["memory_per_step"]
        
        # 算力成本（假设L4调用需要GPU）
        estimation.compute_cost_gpu = estimation.l4_calls * 20000  # 每次L4调用约20GB显存
    
    def _refine_estimation(self, task_description: str, estimation: CostEstimation):
        """
        根据任务描述进一步细化评估
        
        Args:
            task_description: 任务描述
            estimation: 成本预估对象（会被修改）
        """
        desc = task_description.lower()
        
        # 如果涉及大量数据处理
        if "数据" in desc or "分析" in desc:
            estimation.space_cost_mb *= 2
            estimation.time_cost_seconds *= 1.5
        
        # 如果涉及多次迭代
        if "优化" in desc or "迭代" in desc:
            estimation.l4_calls *= 2
            estimation.steps *= 2
        
        # 如果涉及工具调用
        if "工具" in desc or "调用" in desc:
            estimation.api_calls += 2
        
        # 重新计算成本
        self._calculate_costs(estimation)
    
    def get_breakdown(self, estimation: CostEstimation) -> List[CostBreakdown]:
        """
        获取成本明细
        
        Args:
            estimation: 成本预估结果
            
        Returns:
            成本明细列表
        """
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
            cost_usd=0.0  # 时间成本不直接转换为金钱
        ))
        
        breakdown.append(CostBreakdown(
            item="内存占用",
            dimension=CostDimension.SPACE,
            amount=estimation.space_cost_mb,
            unit="MB",
            cost_usd=0.0  # 空间成本不直接转换为金钱
        ))
        
        return breakdown
    
    def is_within_budget(self, estimation: CostEstimation, budget_usd: float) -> bool:
        """
        判断预估成本是否在预算内
        
        Args:
            estimation: 成本预估结果
            budget_usd: 预算（USD）
            
        Returns:
            是否在预算内
        """
        return estimation.money_cost_usd <= budget_usd
    
    def get_decision(self, estimation: CostEstimation, budget_usd: float) -> str:
        """
        获取决策建议
        
        Args:
            estimation: 成本预估结果
            budget_usd: 预算（USD）
            
        Returns:
            决策建议（"execute" / "confirm" / "reject"）
        """
        if estimation.money_cost_usd <= budget_usd * 0.5:
            return "execute"  # 可以直接执行
        elif estimation.money_cost_usd <= budget_usd:
            return "confirm"  # 需要用户确认
        else:
            return "reject"   # 超出预算，拒绝执行


# 创建全局实例
cost_evaluator = CostEvaluator()


def get_cost_evaluator() -> CostEvaluator:
    """获取成本评估器实例"""
    return cost_evaluator


# 测试函数
async def test_cost_evaluator():
    """测试成本评估器"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 CostEvaluator")
    print("=" * 60)
    
    evaluator = CostEvaluator()
    
    # 1. 测试简单任务评估
    print("\n[1] 测试简单任务评估...")
    estimation = evaluator.estimate("帮我查询天气")
    print(f"    ✓ 任务: {estimation.task_description}")
    print(f"    ✓ 复杂度: {estimation.complexity.value}")
    print(f"    ✓ 金钱成本: ${estimation.money_cost_usd:.4f}")
    print(f"    ✓ 时间成本: {estimation.time_cost_seconds:.1f}秒")
    print(f"    ✓ 空间成本: {estimation.space_cost_mb:.1f}MB")
    
    # 2. 测试复杂任务评估
    print("\n[2] 测试复杂任务评估...")
    estimation = evaluator.estimate("分析市场数据并生成详细报告")
    print(f"    ✓ 任务: {estimation.task_description}")
    print(f"    ✓ 复杂度: {estimation.complexity.value}")
    print(f"    ✓ 金钱成本: ${estimation.money_cost_usd:.4f}")
    print(f"    ✓ 时间成本: {estimation.time_cost_seconds:.1f}秒")
    print(f"    ✓ L4调用次数: {estimation.l4_calls}")
    
    # 3. 测试专家任务评估
    print("\n[3] 测试专家任务评估...")
    estimation = evaluator.estimate("使用深度强化学习优化复杂系统的参数")
    print(f"    ✓ 任务: {estimation.task_description}")
    print(f"    ✓ 复杂度: {estimation.complexity.value}")
    print(f"    ✓ 金钱成本: ${estimation.money_cost_usd:.4f}")
    print(f"    ✓ 预估置信度: {estimation.confidence:.2f}")
    
    # 4. 测试成本明细
    print("\n[4] 测试成本明细...")
    breakdown = evaluator.get_breakdown(estimation)
    print(f"    ✓ 成本明细 ({len(breakdown)}项):")
    for item in breakdown:
        print(f"      - {item.item}: ${item.cost_usd:.4f}")
    
    # 5. 测试预算判断
    print("\n[5] 测试预算判断...")
    budget = 0.1
    is_within = evaluator.is_within_budget(estimation, budget)
    decision = evaluator.get_decision(estimation, budget)
    print(f"    ✓ 预算: ${budget}")
    print(f"    ✓ 是否在预算内: {'是' if is_within else '否'}")
    print(f"    ✓ 决策建议: {decision}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_cost_evaluator())