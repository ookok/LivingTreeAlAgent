"""
A/B Testing Framework - A/B测试框架

核心功能：
1. 实验管理 - 创建、运行、停止A/B实验
2. 流量分配 - 智能分配用户到不同变体
3. 指标追踪 - 收集和分析实验数据
4. 统计分析 - 计算显著性和效果评估
5. 自动优化 - 根据结果自动选择最优变体

设计理念：
- 无侵入式集成
- 实时数据收集
- 科学统计分析
- 自动化决策
"""

import asyncio
import json
import random
import statistics
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """实验状态"""
    DRAFT = "draft"           # 草稿
    RUNNING = "running"       # 运行中
    PAUSED = "paused"         # 暂停
    COMPLETED = "completed"   # 完成
    ARCHIVED = "archived"     # 归档


class MetricType(Enum):
    """指标类型"""
    CLICK_THROUGH = "click_through"   # 点击率
    CONVERSION = "conversion"         # 转化率
    TIME_ON_PAGE = "time_on_page"     # 停留时间
    ERROR_RATE = "error_rate"         # 错误率
    USER_SATISFACTION = "user_satisfaction"  # 用户满意度


@dataclass
class ExperimentVariant:
    """实验变体"""
    variant_id: str
    name: str
    description: Optional[str] = None
    weight: float = 0.5  # 流量权重
    config: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, List[float]] = field(default_factory=dict)


@dataclass
class Experiment:
    """实验"""
    experiment_id: str
    name: str
    description: Optional[str] = None
    status: ExperimentStatus = ExperimentStatus.DRAFT
    variants: List[ExperimentVariant] = field(default_factory=list)
    metrics_to_track: List[MetricType] = field(default_factory=list)
    target_users: Optional[List[str]] = None  # None表示所有用户
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExperimentResult:
    """实验结果"""
    experiment_id: str
    winner: Optional[str] = None
    confidence: float = 0.0
    variant_results: Dict[str, Dict[str, float]] = field(default_factory=dict)
    statistical_significance: Optional[float] = None
    conclusion: Optional[str] = None


class ABTestFramework:
    """
    A/B测试框架
    
    核心特性：
    1. 实验管理 - 创建和管理A/B实验
    2. 智能流量分配 - 根据权重分配用户
    3. 多维度指标追踪 - 点击、转化、满意度等
    4. 统计显著性检验 - 科学评估实验效果
    5. 自动决策 - 根据结果选择最优方案
    """
    
    def __init__(self):
        # 实验存储
        self._experiments: Dict[str, Experiment] = {}
        
        # 用户分配缓存
        self._user_assignments: Dict[str, str] = {}
        
        # 实验结果
        self._experiment_results: Dict[str, ExperimentResult] = {}
        
        # 决策阈值
        self._significance_threshold = 0.95  # 95%置信度
        
        logger.info("✅ ABTestFramework 初始化完成")
    
    def create_experiment(self, name: str, description: Optional[str] = None) -> str:
        """
        创建新实验
        
        Args:
            name: 实验名称
            description: 实验描述
        
        Returns:
            实验ID
        """
        experiment_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            status=ExperimentStatus.DRAFT
        )
        
        self._experiments[experiment_id] = experiment
        logger.info(f"✅ 创建实验: {experiment_id} - {name}")
        
        return experiment_id
    
    def add_variant(self, experiment_id: str, name: str, config: Dict[str, Any], 
                    weight: float = 0.5, description: Optional[str] = None):
        """
        为实验添加变体
        
        Args:
            experiment_id: 实验ID
            name: 变体名称
            config: 变体配置
            weight: 流量权重
            description: 变体描述
        """
        if experiment_id not in self._experiments:
            raise ValueError(f"实验不存在: {experiment_id}")
        
        experiment = self._experiments[experiment_id]
        
        # 检查变体数量限制
        if len(experiment.variants) >= 5:
            raise ValueError("每个实验最多支持5个变体")
        
        variant = ExperimentVariant(
            variant_id=f"var_{len(experiment.variants) + 1}",
            name=name,
            description=description,
            weight=weight,
            config=config
        )
        
        experiment.variants.append(variant)
        experiment.updated_at = datetime.now()
        
        # 重新计算权重，确保总和为1
        self._normalize_weights(experiment_id)
        
        logger.info(f"✅ 为实验 {experiment_id} 添加变体: {name}")
    
    def _normalize_weights(self, experiment_id: str):
        """归一化变体权重"""
        experiment = self._experiments[experiment_id]
        total_weight = sum(v.weight for v in experiment.variants)
        
        if total_weight > 0:
            for variant in experiment.variants:
                variant.weight = variant.weight / total_weight
    
    def set_metrics(self, experiment_id: str, metrics: List[MetricType]):
        """设置要追踪的指标"""
        if experiment_id not in self._experiments:
            raise ValueError(f"实验不存在: {experiment_id}")
        
        self._experiments[experiment_id].metrics_to_track = metrics
        logger.info(f"✅ 为实验 {experiment_id} 设置指标: {[m.value for m in metrics]}")
    
    def start_experiment(self, experiment_id: str):
        """启动实验"""
        if experiment_id not in self._experiments:
            raise ValueError(f"实验不存在: {experiment_id}")
        
        experiment = self._experiments[experiment_id]
        
        if len(experiment.variants) < 2:
            raise ValueError("实验至少需要2个变体")
        
        experiment.status = ExperimentStatus.RUNNING
        experiment.start_time = datetime.now()
        experiment.updated_at = datetime.now()
        
        logger.info(f"🚀 启动实验: {experiment_id}")
    
    def pause_experiment(self, experiment_id: str):
        """暂停实验"""
        if experiment_id not in self._experiments:
            raise ValueError(f"实验不存在: {experiment_id}")
        
        self._experiments[experiment_id].status = ExperimentStatus.PAUSED
        logger.info(f"⏸️ 暂停实验: {experiment_id}")
    
    def stop_experiment(self, experiment_id: str):
        """停止实验并计算结果"""
        if experiment_id not in self._experiments:
            raise ValueError(f"实验不存在: {experiment_id}")
        
        experiment = self._experiments[experiment_id]
        experiment.status = ExperimentStatus.COMPLETED
        experiment.end_time = datetime.now()
        experiment.updated_at = datetime.now()
        
        # 计算实验结果
        result = self._calculate_results(experiment)
        self._experiment_results[experiment_id] = result
        
        logger.info(f"🛑 停止实验: {experiment_id}, 获胜者: {result.winner}")
    
    def assign_variant(self, user_id: str, experiment_id: str) -> Optional[str]:
        """
        为用户分配变体
        
        Args:
            user_id: 用户ID
            experiment_id: 实验ID
        
        Returns:
            变体ID
        """
        if experiment_id not in self._experiments:
            return None
        
        experiment = self._experiments[experiment_id]
        
        if experiment.status != ExperimentStatus.RUNNING:
            return None
        
        # 检查目标用户限制
        if experiment.target_users and user_id not in experiment.target_users:
            return None
        
        # 检查是否已有分配
        cache_key = f"{user_id}_{experiment_id}"
        if cache_key in self._user_assignments:
            return self._user_assignments[cache_key]
        
        # 根据权重随机分配
        rand = random.random()
        cumulative = 0.0
        
        for variant in experiment.variants:
            cumulative += variant.weight
            if rand <= cumulative:
                self._user_assignments[cache_key] = variant.variant_id
                return variant.variant_id
        
        # 默认返回第一个变体
        first_variant = experiment.variants[0].variant_id
        self._user_assignments[cache_key] = first_variant
        return first_variant
    
    def get_variant_config(self, experiment_id: str, variant_id: str) -> Optional[Dict[str, Any]]:
        """获取变体配置"""
        if experiment_id not in self._experiments:
            return None
        
        experiment = self._experiments[experiment_id]
        
        for variant in experiment.variants:
            if variant.variant_id == variant_id:
                return variant.config
        
        return None
    
    def track_metric(self, experiment_id: str, variant_id: str, 
                     metric_type: MetricType, value: float):
        """
        追踪指标
        
        Args:
            experiment_id: 实验ID
            variant_id: 变体ID
            metric_type: 指标类型
            value: 指标值
        """
        if experiment_id not in self._experiments:
            return
        
        experiment = self._experiments[experiment_id]
        
        if experiment.status != ExperimentStatus.RUNNING:
            return
        
        for variant in experiment.variants:
            if variant.variant_id == variant_id:
                if metric_type.value not in variant.metrics:
                    variant.metrics[metric_type.value] = []
                variant.metrics[metric_type.value].append(value)
                break
    
    def _calculate_results(self, experiment: Experiment) -> ExperimentResult:
        """计算实验结果"""
        result = ExperimentResult(experiment_id=experiment.experiment_id)
        variant_results = {}
        
        for variant in experiment.variants:
            variant_result = {}
            
            for metric in experiment.metrics_to_track:
                values = variant.metrics.get(metric.value, [])
                if values:
                    variant_result[metric.value] = statistics.mean(values)
                else:
                    variant_result[metric.value] = 0.0
            
            variant_results[variant.variant_id] = variant_result
        
        result.variant_results = variant_results
        
        # 选择获胜者（简单实现：选择综合指标最高的）
        if variant_results:
            winner = max(variant_results.keys(), key=lambda k: sum(variant_results[k].values()))
            result.winner = winner
            
            # 计算置信度（简化版本）
            winner_metrics = variant_results[winner]
            other_metrics = [v for k, v in variant_results.items() if k != winner]
            
            if other_metrics:
                avg_other = sum(sum(m.values()) for m in other_metrics) / len(other_metrics)
                avg_winner = sum(winner_metrics.values())
                
                if avg_other > 0:
                    result.confidence = min(avg_winner / avg_other, 1.0)
                else:
                    result.confidence = 0.95
            
            # 判断统计显著性
            result.statistical_significance = self._calculate_significance(experiment)
            
            if result.confidence >= self._significance_threshold:
                result.conclusion = f"变体 {winner} 在 {', '.join([m.value for m in experiment.metrics_to_track])} 指标上表现最优"
            else:
                result.conclusion = "实验结果不显著，建议继续观察"
        
        return result
    
    def _calculate_significance(self, experiment: Experiment) -> Optional[float]:
        """计算统计显著性（简化实现）"""
        if len(experiment.variants) < 2:
            return None
        
        # 获取主要指标的数据
        main_metric = experiment.metrics_to_track[0].value if experiment.metrics_to_track else "click_through"
        
        variant_data = []
        for variant in experiment.variants:
            values = variant.metrics.get(main_metric, [])
            if values:
                variant_data.append(values)
        
        if len(variant_data) < 2:
            return None
        
        # 简单的t检验近似
        try:
            from scipy import stats
            
            if len(variant_data) == 2:
                t_stat, p_value = stats.ttest_ind(variant_data[0], variant_data[1])
                return 1 - p_value
            else:
                f_stat, p_value = stats.f_oneway(*variant_data)
                return 1 - p_value
        except ImportError:
            # 如果没有scipy，返回基于样本量的估计
            total_samples = sum(len(d) for d in variant_data)
            return min(total_samples / 100, 1.0)
    
    def get_experiment_result(self, experiment_id: str) -> Optional[ExperimentResult]:
        """获取实验结果"""
        return self._experiment_results.get(experiment_id)
    
    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """获取实验详情"""
        return self._experiments.get(experiment_id)
    
    def list_experiments(self) -> List[Experiment]:
        """列出所有实验"""
        return list(self._experiments.values())
    
    async def run_auto_optimization(self, experiment_id: str):
        """
        自动优化 - 将获胜变体应用到生产环境
        
        Args:
            experiment_id: 实验ID
        """
        result = self._experiment_results.get(experiment_id)
        
        if not result or not result.winner:
            logger.warning(f"无法自动优化，实验 {experiment_id} 没有有效结果")
            return
        
        # 获取获胜变体配置
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return
        
        winning_variant = None
        for variant in experiment.variants:
            if variant.variant_id == result.winner:
                winning_variant = variant
                break
        
        if winning_variant:
            # 应用获胜配置到生产环境
            await self._apply_winning_config(winning_variant.config)
            logger.info(f"✅ 已将获胜变体 {winning_variant.name} 应用到生产环境")
    
    async def _apply_winning_config(self, config: Dict[str, Any]):
        """应用获胜配置"""
        # 这里可以实现将配置应用到UI引擎
        try:
            from business.dynamic_ui_engine import get_dynamic_ui_engine
            
            engine = get_dynamic_ui_engine()
            
            # 更新组件推荐策略
            if 'component_priorities' in config:
                for component_id, priority in config['component_priorities'].items():
                    gene = engine.get_component_gene(component_id)
                    if gene:
                        # 通过奖励来影响组件选择
                        engine.record_reward(component_id, priority * 0.5)
            
        except ImportError:
            logger.warning("动态UI引擎未加载")


# 全局单例
_global_ab_test_framework: Optional[ABTestFramework] = None


def get_ab_test_framework() -> ABTestFramework:
    """获取全局A/B测试框架单例"""
    global _global_ab_test_framework
    if _global_ab_test_framework is None:
        _global_ab_test_framework = ABTestFramework()
    return _global_ab_test_framework


# 测试函数
async def test_ab_test_framework():
    """测试A/B测试框架"""
    print("🧪 测试A/B测试框架")
    print("="*60)
    
    framework = get_ab_test_framework()
    
    # 创建实验
    print("\n📋 创建实验")
    exp_id = framework.create_experiment("组件布局测试", "测试不同UI组件布局的效果")
    print(f"   实验ID: {exp_id}")
    
    # 添加变体
    print("\n➕ 添加变体")
    framework.add_variant(
        exp_id,
        "变体A",
        {"layout": "vertical", "primary_color": "#3b82f6"},
        weight=0.5
    )
    framework.add_variant(
        exp_id,
        "变体B",
        {"layout": "horizontal", "primary_color": "#10b981"},
        weight=0.5
    )
    print("   已添加2个变体")
    
    # 设置指标
    print("\n📊 设置指标")
    framework.set_metrics(exp_id, [MetricType.CLICK_THROUGH, MetricType.CONVERSION])
    
    # 启动实验
    print("\n🚀 启动实验")
    framework.start_experiment(exp_id)
    
    # 模拟用户分配
    print("\n🎲 模拟用户分配")
    for i in range(10):
        user_id = f"user_{i}"
        variant_id = framework.assign_variant(user_id, exp_id)
        print(f"   用户 {user_id} → 变体 {variant_id}")
    
    # 模拟数据收集
    print("\n📈 模拟数据收集")
    for i in range(50):
        user_id = f"user_{i}"
        variant_id = framework.assign_variant(user_id, exp_id)
        
        # 模拟指标值（变体B表现更好）
        if variant_id == "var_1":  # 变体A
            click_rate = random.uniform(0.1, 0.3)
            conversion = random.uniform(0.05, 0.15)
        else:  # 变体B
            click_rate = random.uniform(0.25, 0.45)
            conversion = random.uniform(0.15, 0.25)
        
        framework.track_metric(exp_id, variant_id, MetricType.CLICK_THROUGH, click_rate)
        framework.track_metric(exp_id, variant_id, MetricType.CONVERSION, conversion)
    
    print("   已收集50个用户的数据")
    
    # 停止实验
    print("\n🛑 停止实验")
    framework.stop_experiment(exp_id)
    
    # 获取结果
    print("\n🏆 获取实验结果")
    result = framework.get_experiment_result(exp_id)
    print(f"   获胜变体: {result.winner}")
    print(f"   置信度: {result.confidence:.2%}")
    print(f"   结论: {result.conclusion}")
    
    # 打印变体结果
    print("\n📝 变体详细结果:")
    for variant_id, metrics in result.variant_results.items():
        print(f"   {variant_id}:")
        for metric, value in metrics.items():
            print(f"     {metric}: {value:.4f}")
    
    # 自动优化
    print("\n⚡ 自动优化")
    await framework.run_auto_optimization(exp_id)
    
    print("\n🎉 A/B测试框架测试完成！")
    return True


if __name__ == "__main__":
    asyncio.run(test_ab_test_framework())