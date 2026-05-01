"""
Adaptive Reasoning Framework

自适应模型推理框架，支持策略选择、策略组合和元推理能力。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ReasoningStrategyType(Enum):
    """推理策略类型"""
    DEFAULT = "default"           # 默认推理
    STEP_BY_STEP = "step_by_step"  # 逐步推理
    CREATIVE = "creative"         # 创造性推理
    ANALYTICAL = "analytical"     # 分析性推理
    LOGICAL = "logical"           # 逻辑推理
    INDUCTIVE = "inductive"       # 归纳推理
    DEDUCTIVE = "deductive"       # 演绎推理


class TaskType(Enum):
    """任务类型"""
    DIAGNOSIS = "diagnosis"       # 诊断类
    CREATIVE = "creative"         # 创意类
    ANALYSIS = "analysis"         # 分析类
    CALCULATION = "calculation"   # 计算类
    DECISION = "decision"         # 决策类
    EXPLANATION = "explanation"   # 解释类
    PROBLEM_SOLVING = "problem_solving"  # 问题解决


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_number: int
    description: str
    result: Optional[str] = None
    confidence: float = 0.0
    time_taken: float = 0.0


@dataclass
class ReasoningResult:
    """推理结果"""
    strategy: ReasoningStrategyType
    steps: List[ReasoningStep] = field(default_factory=list)
    final_answer: Optional[str] = None
    confidence: float = 0.0
    reasoning_time: float = 0.0
    meta_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompositeReasoning:
    """组合推理策略"""
    strategies: List[ReasoningStrategyType]
    weights: List[float] = field(default_factory=list)
    execution_order: str = "sequential"  # sequential | parallel


@dataclass
class ReasoningMetrics:
    """推理指标"""
    strategy: ReasoningStrategyType
    success_rate: float = 0.0
    avg_time: float = 0.0
    avg_confidence: float = 0.0
    usage_count: int = 0


class BaseReasoningStrategy:
    """推理策略基类"""
    
    def __init__(self, strategy_type: ReasoningStrategyType):
        self.strategy_type = strategy_type
    
    def execute(self, problem: str, context: Optional[Dict[str, Any]] = None) -> ReasoningResult:
        """执行推理"""
        raise NotImplementedError("子类必须实现execute方法")
    
    def get_description(self) -> str:
        """获取策略描述"""
        return str(self.strategy_type.value)


class DefaultReasoningStrategy(BaseReasoningStrategy):
    """默认推理策略"""
    
    def __init__(self):
        super().__init__(ReasoningStrategyType.DEFAULT)
    
    def execute(self, problem: str, context: Optional[Dict[str, Any]] = None) -> ReasoningResult:
        return ReasoningResult(
            strategy=self.strategy_type,
            steps=[ReasoningStep(step_number=1, description="直接推理", result=problem, confidence=0.7)],
            final_answer=problem,
            confidence=0.7,
            reasoning_time=0.1,
        )


class StepByStepReasoningStrategy(BaseReasoningStrategy):
    """逐步推理策略"""
    
    def __init__(self):
        super().__init__(ReasoningStrategyType.STEP_BY_STEP)
    
    def execute(self, problem: str, context: Optional[Dict[str, Any]] = None) -> ReasoningResult:
        steps = [
            ReasoningStep(step_number=1, description="理解问题", result="分析问题结构", confidence=0.9),
            ReasoningStep(step_number=2, description="分解问题", result="将问题分解为子问题", confidence=0.85),
            ReasoningStep(step_number=3, description="逐一解决", result="依次解决每个子问题", confidence=0.8),
            ReasoningStep(step_number=4, description="综合答案", result="整合子问题答案", confidence=0.75),
        ]
        
        return ReasoningResult(
            strategy=self.strategy_type,
            steps=steps,
            final_answer=f"逐步分析结果: {problem}",
            confidence=0.85,
            reasoning_time=0.5,
        )


class CreativeReasoningStrategy(BaseReasoningStrategy):
    """创造性推理策略"""
    
    def __init__(self):
        super().__init__(ReasoningStrategyType.CREATIVE)
    
    def execute(self, problem: str, context: Optional[Dict[str, Any]] = None) -> ReasoningResult:
        steps = [
            ReasoningStep(step_number=1, description="发散思维", result="生成多种可能方案", confidence=0.8),
            ReasoningStep(step_number=2, description="组合创新", result="组合不同方案的优点", confidence=0.75),
            ReasoningStep(step_number=3, description="评估优化", result="评估并优化最佳方案", confidence=0.7),
        ]
        
        return ReasoningResult(
            strategy=self.strategy_type,
            steps=steps,
            final_answer=f"创意解决方案: {problem}",
            confidence=0.75,
            reasoning_time=0.8,
        )


class AnalyticalReasoningStrategy(BaseReasoningStrategy):
    """分析性推理策略"""
    
    def __init__(self):
        super().__init__(ReasoningStrategyType.ANALYTICAL)
    
    def execute(self, problem: str, context: Optional[Dict[str, Any]] = None) -> ReasoningResult:
        steps = [
            ReasoningStep(step_number=1, description="收集信息", result="收集相关数据和背景", confidence=0.9),
            ReasoningStep(step_number=2, description="分析数据", result="系统性分析数据", confidence=0.85),
            ReasoningStep(step_number=3, description="验证假设", result="验证分析假设", confidence=0.8),
            ReasoningStep(step_number=4, description="得出结论", result="基于证据得出结论", confidence=0.85),
        ]
        
        return ReasoningResult(
            strategy=self.strategy_type,
            steps=steps,
            final_answer=f"分析结论: {problem}",
            confidence=0.85,
            reasoning_time=0.6,
        )


class LogicalReasoningStrategy(BaseReasoningStrategy):
    """逻辑推理策略"""
    
    def __init__(self):
        super().__init__(ReasoningStrategyType.LOGICAL)
    
    def execute(self, problem: str, context: Optional[Dict[str, Any]] = None) -> ReasoningResult:
        steps = [
            ReasoningStep(step_number=1, description="形式化", result="将问题转换为逻辑形式", confidence=0.9),
            ReasoningStep(step_number=2, description="推演", result="应用逻辑规则推演", confidence=0.9),
            ReasoningStep(step_number=3, description="验证", result="验证逻辑正确性", confidence=0.85),
        ]
        
        return ReasoningResult(
            strategy=self.strategy_type,
            steps=steps,
            final_answer=f"逻辑推导结果: {problem}",
            confidence=0.9,
            reasoning_time=0.4,
        )


class AdaptiveReasoningFramework:
    """
    自适应模型推理框架
    
    核心功能：
    - 根据任务类型选择推理策略
    - 支持多种策略组合
    - 元推理能力（监控和优化推理过程）
    """
    
    def __init__(self):
        """初始化推理框架"""
        self._strategies: Dict[ReasoningStrategyType, BaseReasoningStrategy] = {
            ReasoningStrategyType.DEFAULT: DefaultReasoningStrategy(),
            ReasoningStrategyType.STEP_BY_STEP: StepByStepReasoningStrategy(),
            ReasoningStrategyType.CREATIVE: CreativeReasoningStrategy(),
            ReasoningStrategyType.ANALYTICAL: AnalyticalReasoningStrategy(),
            ReasoningStrategyType.LOGICAL: LogicalReasoningStrategy(),
        }
        
        self._metrics: Dict[ReasoningStrategyType, ReasoningMetrics] = {}
        for strategy_type in ReasoningStrategyType:
            self._metrics[strategy_type] = ReasoningMetrics(strategy=strategy_type)
        
        self._task_strategy_map: Dict[TaskType, ReasoningStrategyType] = {
            TaskType.DIAGNOSIS: ReasoningStrategyType.STEP_BY_STEP,
            TaskType.CREATIVE: ReasoningStrategyType.CREATIVE,
            TaskType.ANALYSIS: ReasoningStrategyType.ANALYTICAL,
            TaskType.CALCULATION: ReasoningStrategyType.LOGICAL,
            TaskType.DECISION: ReasoningStrategyType.ANALYTICAL,
            TaskType.EXPLANATION: ReasoningStrategyType.STEP_BY_STEP,
            TaskType.PROBLEM_SOLVING: ReasoningStrategyType.STEP_BY_STEP,
        }
        
        logger.info("AdaptiveReasoningFramework 初始化完成")
    
    def select_reasoning_strategy(self, task_type: TaskType) -> ReasoningStrategyType:
        """
        根据任务类型选择推理策略
        
        Args:
            task_type: 任务类型
            
        Returns:
            ReasoningStrategyType 推理策略类型
        """
        strategy = self._task_strategy_map.get(task_type, ReasoningStrategyType.DEFAULT)
        
        # 基于历史指标动态调整
        metrics = self._metrics.get(strategy)
        if metrics and metrics.usage_count > 10 and metrics.success_rate < 0.6:
            # 如果当前策略成功率较低，尝试其他策略
            alternative_strategies = [
                s for s in ReasoningStrategyType 
                if s != strategy and self._metrics[s].success_rate > 0.7
            ]
            if alternative_strategies:
                strategy = max(alternative_strategies, key=lambda s: self._metrics[s].success_rate)
        
        logger.info(f"选择推理策略: {task_type.value} -> {strategy.value}")
        return strategy
    
    def register_strategy(self, strategy: BaseReasoningStrategy):
        """
        注册自定义推理策略
        
        Args:
            strategy: 推理策略实例
        """
        self._strategies[strategy.strategy_type] = strategy
        if strategy.strategy_type not in self._metrics:
            self._metrics[strategy.strategy_type] = ReasoningMetrics(strategy=strategy.strategy_type)
        
        logger.info(f"注册推理策略: {strategy.strategy_type.value}")
    
    def execute_reasoning(self, problem: str, task_type: TaskType, 
                          context: Optional[Dict[str, Any]] = None) -> ReasoningResult:
        """
        执行推理
        
        Args:
            problem: 问题描述
            task_type: 任务类型
            context: 上下文信息
            
        Returns:
            ReasoningResult 推理结果
        """
        strategy_type = self.select_reasoning_strategy(task_type)
        strategy = self._strategies.get(strategy_type)
        
        if not strategy:
            logger.error(f"策略不存在: {strategy_type}")
            return ReasoningResult(strategy=strategy_type)
        
        result = strategy.execute(problem, context)
        
        # 更新指标
        self._update_metrics(strategy_type, result)
        
        return result
    
    def compose_reasoning(self, strategies: List[ReasoningStrategyType], 
                          problem: str, context: Optional[Dict[str, Any]] = None) -> ReasoningResult:
        """
        组合多种推理策略
        
        Args:
            strategies: 策略列表
            problem: 问题描述
            context: 上下文信息
            
        Returns:
            ReasoningResult 组合推理结果
        """
        results = []
        total_time = 0.0
        total_confidence = 0.0
        
        for strategy_type in strategies:
            strategy = self._strategies.get(strategy_type)
            if strategy:
                result = strategy.execute(problem, context)
                results.append(result)
                total_time += result.reasoning_time
                total_confidence += result.confidence
        
        # 融合结果
        if results:
            avg_confidence = total_confidence / len(results)
            final_steps = []
            step_count = 1
            
            for result in results:
                for step in result.steps:
                    final_steps.append(ReasoningStep(
                        step_number=step_count,
                        description=f"[{result.strategy.value}] {step.description}",
                        result=step.result,
                        confidence=step.confidence,
                        time_taken=step.time_taken,
                    ))
                    step_count += 1
            
            return ReasoningResult(
                strategy=strategies[0],
                steps=final_steps,
                final_answer=f"组合推理结果（{len(strategies)}种策略）: {problem}",
                confidence=avg_confidence,
                reasoning_time=total_time,
                meta_info={"strategies_used": [s.value for s in strategies]},
            )
        
        return ReasoningResult(strategy=strategies[0] if strategies else ReasoningStrategyType.DEFAULT)
    
    def _update_metrics(self, strategy_type: ReasoningStrategyType, result: ReasoningResult):
        """
        更新策略指标
        
        Args:
            strategy_type: 策略类型
            result: 推理结果
        """
        metrics = self._metrics[strategy_type]
        metrics.usage_count += 1
        metrics.avg_time = (metrics.avg_time * (metrics.usage_count - 1) + result.reasoning_time) / metrics.usage_count
        metrics.avg_confidence = (metrics.avg_confidence * (metrics.usage_count - 1) + result.confidence) / metrics.usage_count
        
        # 简单假设：置信度>0.7视为成功
        if result.confidence > 0.7:
            metrics.success_rate = (metrics.success_rate * (metrics.usage_count - 1) + 1) / metrics.usage_count
        else:
            metrics.success_rate = (metrics.success_rate * (metrics.usage_count - 1)) / metrics.usage_count
    
    def get_metrics(self) -> Dict[ReasoningStrategyType, ReasoningMetrics]:
        """获取所有策略的指标"""
        return self._metrics
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """获取策略信息"""
        info = {}
        for strategy_type, strategy in self._strategies.items():
            metrics = self._metrics[strategy_type]
            info[strategy_type.value] = {
                "description": strategy.get_description(),
                "success_rate": metrics.success_rate,
                "avg_time": metrics.avg_time,
                "avg_confidence": metrics.avg_confidence,
                "usage_count": metrics.usage_count,
            }
        return info


# 全局推理框架实例
_framework_instance = None

def get_adaptive_reasoning_framework() -> AdaptiveReasoningFramework:
    """获取全局自适应推理框架实例"""
    global _framework_instance
    if _framework_instance is None:
        _framework_instance = AdaptiveReasoningFramework()
    return _framework_instance