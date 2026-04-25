"""
多路径探索器 - 路径评估器

评估和排序探索路径的质量
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Callable, Optional
from datetime import datetime

from .path_models import ExplorationPath, PathType, PathStatus


@dataclass
class EvaluationMetrics:
    """
    评估指标
    
    路径的多维度评估结果
    """
    # 基础质量
    quality_score: float = 0.0          # 总体质量分数 (0-1)
    
    # 效率指标
    efficiency_score: float = 0.0       # 效率分数 (0-1)
    speed_score: float = 0.0            # 速度分数 (0-1)
    
    # 可靠性指标
    reliability_score: float = 0.0      # 可靠性分数 (0-1)
    success_probability: float = 0.0     # 成功概率 (0-1)
    
    # 资源指标
    cost_score: float = 0.0             # 成本效益分数 (0-1)
    resource_efficiency: float = 0.0     # 资源效率 (0-1)
    
    # 创新指标
    novelty_score: float = 0.0          # 新颖性分数 (0-1)
    
    # 详细分析
    breakdown: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    
    @property
    def overall_score(self) -> float:
        """综合评分"""
        weights = {
            "quality": 0.30,
            "efficiency": 0.20,
            "reliability": 0.25,
            "cost": 0.15,
            "novelty": 0.10
        }
        return (
            weights["quality"] * self.quality_score +
            weights["efficiency"] * self.efficiency_score +
            weights["reliability"] * self.reliability_score +
            weights["cost"] * self.cost_score +
            weights["novelty"] * self.novelty_score
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "quality_score": self.quality_score,
            "efficiency_score": self.efficiency_score,
            "speed_score": self.speed_score,
            "reliability_score": self.reliability_score,
            "success_probability": self.success_probability,
            "cost_score": self.cost_score,
            "resource_efficiency": self.resource_efficiency,
            "novelty_score": self.novelty_score,
            "breakdown": self.breakdown,
            "recommendations": self.recommendations
        }


class PathEvaluator:
    """
    路径评估器
    
    评估探索路径的质量和潜力
    """
    
    def __init__(
        self,
        # 权重配置
        quality_weight: float = 0.30,
        efficiency_weight: float = 0.20,
        reliability_weight: float = 0.25,
        cost_weight: float = 0.15,
        novelty_weight: float = 0.10,
        
        # 参考值（用于归一化）
        reference_time: float = 10.0,      # 参考执行时间（秒）
        reference_cost: float = 1.0,       # 参考资源消耗
        max_acceptable_time: float = 60.0  # 最大可接受时间
    ):
        self.weights = {
            "quality": quality_weight,
            "efficiency": efficiency_weight,
            "reliability": reliability_weight,
            "cost": cost_weight,
            "novelty": novelty_weight
        }
        self.reference_time = reference_time
        self.reference_cost = reference_cost
        self.max_acceptable_time = max_acceptable_time
        
        # 注册自定义评估器
        self._custom_evaluators: Dict[str, Callable] = {}
    
    def register_evaluator(
        self,
        name: str,
        evaluator: Callable[[ExplorationPath], float]
    ) -> None:
        """注册自定义评估器"""
        self._custom_evaluators[name] = evaluator
    
    def evaluate(self, path: ExplorationPath) -> EvaluationMetrics:
        """
        评估路径
        
        Args:
            path: 待评估的探索路径
            
        Returns:
            评估指标
        """
        # 1. 质量评估
        quality_score = self._evaluate_quality(path)
        
        # 2. 效率评估
        efficiency_score, speed_score = self._evaluate_efficiency(path)
        
        # 3. 可靠性评估
        reliability_score, success_prob = self._evaluate_reliability(path)
        
        # 4. 成本评估
        cost_score, resource_eff = self._evaluate_cost(path)
        
        # 5. 新颖性评估
        novelty_score = self._evaluate_novelty(path)
        
        # 6. 构建评估结果
        metrics = EvaluationMetrics(
            quality_score=quality_score,
            efficiency_score=efficiency_score,
            speed_score=speed_score,
            reliability_score=reliability_score,
            success_probability=success_prob,
            cost_score=cost_score,
            resource_efficiency=resource_eff,
            novelty_score=novelty_score,
            breakdown=self._get_breakdown(path, quality_score, efficiency_score, reliability_score, cost_score, novelty_score),
            recommendations=self._generate_recommendations(path, metrics=None)
        )
        
        # 更新建议
        metrics.recommendations = self._generate_recommendations(path, metrics)
        
        return metrics
    
    def _evaluate_quality(self, path: ExplorationPath) -> float:
        """评估质量分数"""
        if not path.nodes:
            return 0.0
        
        # 成功率
        success_rate = path.success_rate
        
        # 结果完整性
        has_result = 1.0 if path.result else 0.0
        has_no_error = 1.0 if not path.error else 0.0
        
        # 节点完成度
        completed_ratio = sum(1 for n in path.nodes.values() if n.is_completed) / len(path.nodes)
        
        # 综合质量
        quality = (
            success_rate * 0.5 +
            has_result * 0.2 +
            has_no_error * 0.2 +
            completed_ratio * 0.1
        )
        
        return min(1.0, max(0.0, quality))
    
    def _evaluate_efficiency(self, path: ExplorationPath) -> tuple:
        """评估效率"""
        if not path.nodes:
            return 0.0, 0.0
        
        # 速度分数：基于执行时间
        total_time = path.total_duration
        if total_time <= 0:
            speed_score = 0.5  # 未执行，假设中等速度
        elif total_time <= self.reference_time:
            speed_score = 1.0
        elif total_time <= self.max_acceptable_time:
            speed_score = 1.0 - (total_time - self.reference_time) / (self.max_acceptable_time - self.reference_time)
        else:
            speed_score = 0.1
        
        # 效率分数：结果与时间的比率
        result_value = 1.0 if path.result else (0.5 if path.is_success else 0.0)
        
        if total_time <= 0:
            efficiency = result_value * 0.5
        else:
            efficiency = result_value / (1 + total_time / self.reference_time)
        
        return min(1.0, max(0.0, efficiency)), min(1.0, max(0.0, speed_score))
    
    def _evaluate_reliability(self, path: ExplorationPath) -> tuple:
        """评估可靠性"""
        if not path.nodes:
            return 0.0, 0.0
        
        # 成功节点比例
        success_ratio = path.success_rate
        
        # 失败节点比例
        failed_ratio = sum(1 for n in path.nodes.values() if n.status == PathStatus.FAILED) / len(path.nodes)
        
        # 稳定性：没有突然的失败
        is_stable = 1.0 if failed_ratio < 0.3 else 0.5
        
        # 成功概率估计
        success_prob = success_ratio * is_stable
        
        # 可靠性分数
        reliability = success_ratio * 0.6 + is_stable * 0.4
        
        return min(1.0, max(0.0, reliability)), min(1.0, max(0.0, success_prob))
    
    def _evaluate_cost(self, path: ExplorationPath) -> tuple:
        """评估成本效益"""
        # 资源消耗
        cost = path.cost if path.cost > 0 else 1.0
        
        # 成本分数：消耗越少分数越高
        if cost <= self.reference_cost:
            cost_score = 1.0
        else:
            cost_score = self.reference_cost / cost
        
        # 资源效率：结果价值与成本的比率
        result_value = 1.0 if path.result else (0.5 if path.is_success else 0.0)
        resource_efficiency = result_value / (1 + cost / self.reference_cost)
        
        return min(1.0, max(0.0, cost_score)), min(1.0, max(0.0, resource_efficiency))
    
    def _evaluate_novelty(self, path: ExplorationPath) -> float:
        """评估新颖性"""
        # 基于路径类型
        novelty_by_type = {
            PathType.DEFAULT: 0.3,
            PathType.OPTIMISTIC: 0.5,
            PathType.CONSERVATIVE: 0.4,
            PathType.CREATIVE: 0.9,
            PathType.FALLBACK: 0.2
        }
        
        base_novelty = novelty_by_type.get(path.path_type, 0.3)
        
        # 基于元数据中的标记
        if path.metadata.get("uses_unusual_approach"):
            base_novelty += 0.2
        if path.metadata.get("combines_uncommon_tools"):
            base_novelty += 0.15
        
        # 自定义新颖性评估
        for name, evaluator in self._custom_evaluators.items():
            try:
                custom_score = evaluator(path)
                base_novelty = (base_novelty + custom_score) / 2
            except Exception:
                pass
        
        return min(1.0, max(0.0, base_novelty))
    
    def _get_breakdown(
        self,
        path: ExplorationPath,
        quality: float,
        efficiency: float,
        reliability: float,
        cost: float,
        novelty: float
    ) -> Dict[str, float]:
        """获取评估分解"""
        return {
            "success_rate": path.success_rate,
            "node_count": path.node_count,
            "total_duration": path.total_duration,
            "resource_cost": path.cost,
            "path_type": path.path_type.value,
            "quality_contribution": quality * self.weights["quality"],
            "efficiency_contribution": efficiency * self.weights["efficiency"],
            "reliability_contribution": reliability * self.weights["reliability"],
            "cost_contribution": cost * self.weights["cost"],
            "novelty_contribution": novelty * self.weights["novelty"]
        }
    
    def _generate_recommendations(
        self,
        path: ExplorationPath,
        metrics: Optional[EvaluationMetrics]
    ) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        if not path.is_complete:
            recommendations.append("路径未完成，可能需要更多执行时间")
        
        if path.success_rate < 0.8:
            recommendations.append("部分步骤失败，建议检查失败节点的错误")
        
        if path.total_duration > self.max_acceptable_time:
            recommendations.append("执行时间过长，考虑优化步骤或使用更快的方法")
        
        if path.cost > self.reference_cost * 2:
            recommendations.append("资源消耗较高，考虑简化流程")
        
        if path.path_type == PathType.CONSERVATIVE:
            recommendations.append("保守路径虽然可靠，但可以考虑更高效的方案")
        
        if metrics and metrics.novelty_score < 0.3:
            recommendations.append("方案较为常规，可以尝试更多创意方法")
        
        if not recommendations:
            recommendations.append("路径质量良好，无需特别改进")
        
        return recommendations
    
    def rank_paths(
        self,
        paths: List[ExplorationPath],
        top_k: Optional[int] = None
    ) -> List[tuple]:
        """
        对路径进行排名
        
        Args:
            paths: 待排名的路径列表
            top_k: 返回前k个，None表示全部
            
        Returns:
            [(path, metrics), ...] 排序后的路径和评估
        """
        # 评估所有路径
        evaluated = []
        for path in paths:
            if path.is_complete:
                metrics = self.evaluate(path)
                evaluated.append((path, metrics))
        
        # 按综合分数排序
        evaluated.sort(key=lambda x: x[1].overall_score, reverse=True)
        
        # 更新路径的score和confidence
        for path, metrics in evaluated:
            path.score = metrics.overall_score
            path.confidence = metrics.success_probability
        
        if top_k is not None:
            return evaluated[:top_k]
        return evaluated


class AdaptiveEvaluator(PathEvaluator):
    """
    自适应评估器
    
    根据任务类型和上下文动态调整评估权重
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._context_weights: Dict[str, Dict[str, float]] = {}
        self._initialize_context_weights()
    
    def _initialize_context_weights(self) -> None:
        """初始化不同上下文的权重配置"""
        # 速度优先场景
        self._context_weights["speed_critical"] = {
            "quality": 0.15,
            "efficiency": 0.35,
            "reliability": 0.15,
            "cost": 0.15,
            "novelty": 0.20
        }
        
        # 可靠性优先场景
        self._context_weights["reliability_critical"] = {
            "quality": 0.25,
            "efficiency": 0.10,
            "reliability": 0.45,
            "cost": 0.10,
            "novelty": 0.10
        }
        
        # 成本优先场景
        self._context_weights["cost_critical"] = {
            "quality": 0.20,
            "efficiency": 0.15,
            "reliability": 0.20,
            "cost": 0.40,
            "novelty": 0.05
        }
        
        # 创新优先场景
        self._context_weights["innovation_focused"] = {
            "quality": 0.20,
            "efficiency": 0.10,
            "reliability": 0.10,
            "cost": 0.10,
            "novelty": 0.50
        }
    
    def set_context(self, context: str) -> None:
        """设置评估上下文"""
        if context in self._context_weights:
            self.weights = self._context_weights[context].copy()
    
    def optimize_for(self, objective: str) -> None:
        """针对特定目标优化权重"""
        if objective == "fastest":
            self.set_context("speed_critical")
        elif objective == "most_reliable":
            self.set_context("reliability_critical")
        elif objective == "cheapest":
            self.set_context("cost_critical")
        elif objective == "most_innovative":
            self.set_context("innovation_focused")
