"""
evolution_depth_optimizer.py - Evolution 深度优化器
=====================================================

将 Optimal Config 集成到 Evolution Engine 中，根据评估结果自动调整 depth。

功能：
1. 评估驱动 depth 调整
2. 评估历史追踪
3. 预测最优 depth
4. 批量评估优化

Author: Hermes Desktop Team
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# 导入配置计算
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "client" / "src" / "business"))

# ============= Mock logger =============

class MockLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def debug(self, msg): pass

logger = MockLogger()

# ============= 尝试导入 optimal_config =============

try:
    from client.src.business.optimal_config import compute_optimal_config, compute_optimal_config_for_task
    OPTIMAL_CONFIG_AVAILABLE = True
except ImportError:
    # Fallback 实现
    import math
    
    def compute_optimal_config(depth: int) -> Dict[str, Any]:
        depth = max(1, min(10, depth))
        return {
            'depth': depth,
            'timeout': int(30 * (1 + 0.3 * depth ** 0.7)),
            'max_retries': max(1, 2 + int(math.log2(depth))),
            'max_tokens': int(2048 * depth ** 1.5),
            'max_workers': max(1, 2 * int(math.sqrt(depth))),
            'memory_limit': depth * 128,
            'context_window': 4096 * depth,
        }
    
    def compute_optimal_config_for_task(task_type: str) -> Dict[str, Any]:
        task_depth_map = {
            'ping': 1, 'list': 1, 'quick_fix': 2, 'fix': 3, 'code_fix': 3,
            'search': 4, 'refactor': 5, 'generate': 5, 'auto_fix': 7,
            'architecture': 8, 'evolve': 9, 'autonomous': 10,
        }
        depth = task_depth_map.get(task_type.lower(), 5)
        return compute_optimal_config(depth)
    
    OPTIMAL_CONFIG_AVAILABLE = False
    logger.warning("optimal_config not available, using fallback")


# ============= 枚举定义 =============

class AdjustmentStrategy(Enum):
    """调整策略"""
    CONSERVATIVE = "conservative"    # 保守: ±1
    MODERATE = "moderate"           # 中等: ±2
    AGGRESSIVE = "aggressive"       # 激进: ±3


class EvaluationThreshold:
    """评估阈值"""
    LOW_SCORE = 0.6      # < 0.6: 需要增加 depth
    HIGH_SCORE = 0.85   # > 0.85: 可以尝试降低 depth
    EXCELLENT = 0.95    # > 0.95: 降低 depth
    
    # 调整幅度
    CONSERVATIVE_STEP = 1
    MODERATE_STEP = 2
    AGGRESSIVE_STEP = 3


# ============= 数据类 =============

@dataclass
class DepthHistory:
    """Depth 历史记录"""
    depth: int
    score: float
    timestamp: datetime = field(default_factory=datetime.now)
    task_type: str = ""
    improvement: float = 0.0  # 相比上次的提升


@dataclass
class OptimizationResult:
    """优化结果"""
    current_depth: int
    suggested_depth: int
    adjustment: int
    strategy: AdjustmentStrategy
    confidence: float  # 0-1
    reason: str
    history_count: int


# ============= 核心优化器 =============

class EvolutionDepthOptimizer:
    """
    Evolution 深度优化器
    
    根据评估结果自动调整 depth，实现自适应配置。
    """
    
    def __init__(
        self,
        initial_depth: int = 5,
        strategy: AdjustmentStrategy = AdjustmentStrategy.MODERATE,
        min_depth: int = 1,
        max_depth: int = 10
    ):
        """
        初始化优化器
        
        Args:
            initial_depth: 初始 depth
            strategy: 调整策略
            min_depth: 最小 depth
            max_depth: 最大 depth
        """
        self.current_depth = initial_depth
        self.strategy = strategy
        self.min_depth = min_depth
        self.max_depth = max_depth
        
        # 历史记录
        self.history: List[DepthHistory] = []
        
        # 统计
        self.total_adjustments = 0
        self.successful_adjustments = 0
        
        # 性能追踪
        self._score_trend: List[float] = []
        self._depth_changes: List[Tuple[int, int]] = []  # (old, new)
        
        logger.info(f"EvolutionDepthOptimizer 初始化 (depth={initial_depth}, strategy={strategy.value})")
    
    def record_evaluation(self, score: float, task_type: str = "") -> DepthHistory:
        """
        记录评估结果
        
        Args:
            score: 评估分数 (0-1)
            task_type: 任务类型
            
        Returns:
            DepthHistory: 历史记录
        """
        # 计算相比上次的提升
        improvement = 0.0
        if self.history:
            last_score = self.history[-1].score
            improvement = score - last_score
        
        # 创建记录
        record = DepthHistory(
            depth=self.current_depth,
            score=score,
            task_type=task_type,
            improvement=improvement
        )
        self.history.append(record)
        self._score_trend.append(score)
        
        logger.info(f"记录评估: depth={self.current_depth}, score={score:.3f}, improvement={improvement:+.3f}")
        
        return record
    
    def analyze_and_adjust(self) -> OptimizationResult:
        """
        分析历史记录并调整 depth
        
        Returns:
            OptimizationResult: 优化结果
        """
        if not self.history:
            return OptimizationResult(
                current_depth=self.current_depth,
                suggested_depth=self.current_depth,
                adjustment=0,
                strategy=self.strategy,
                confidence=0.0,
                reason="无历史记录，保持当前 depth",
                history_count=0
            )
        
        # 获取历史数据
        recent = self.history[-5:]  # 最近5次
        avg_score = sum(h.score for h in recent) / len(recent)
        last_score = self.history[-1].score
        
        # 判断趋势
        trend = "stable"
        if len(recent) >= 3:
            if self._score_trend[-1] > self._score_trend[-2] > self._score_trend[-3]:
                trend = "improving"
            elif self._score_trend[-1] < self._score_trend[-2] < self._score_trend[-3]:
                trend = "declining"
        
        # 根据分数和策略决定调整
        suggested_depth, adjustment, reason, confidence = self._compute_adjustment(
            avg_score, last_score, trend
        )
        
        # 更新状态
        if adjustment != 0:
            old_depth = self.current_depth
            self.current_depth = suggested_depth
            self._depth_changes.append((old_depth, suggested_depth))
            self.total_adjustments += 1
            
            # 检查是否成功
            if self.history and len(self.history) >= 2:
                if self.history[-1].score > self.history[-2].score:
                    self.successful_adjustments += 1
        
        return OptimizationResult(
            current_depth=self.current_depth,
            suggested_depth=suggested_depth,
            adjustment=adjustment,
            strategy=self.strategy,
            confidence=confidence,
            reason=reason,
            history_count=len(self.history)
        )
    
    def _compute_adjustment(
        self,
        avg_score: float,
        last_score: float,
        trend: str
    ) -> Tuple[int, int, str, float]:
        """计算调整幅度"""
        
        step = {
            AdjustmentStrategy.CONSERVATIVE: 1,
            AdjustmentStrategy.MODERATE: 2,
            AdjustmentStrategy.AGGRESSIVE: 3,
        }[self.strategy]
        
        # 低分: 需要增加 depth
        if avg_score < EvaluationThreshold.LOW_SCORE:
            new_depth = min(self.max_depth, self.current_depth + step)
            adjustment = new_depth - self.current_depth
            reason = f"平均分 {avg_score:.2f} < {EvaluationThreshold.LOW_SCORE}，增加 depth"
            confidence = 0.8 if trend == "declining" else 0.6
            
        # 高分: 可以尝试降低 depth
        elif avg_score > EvaluationThreshold.HIGH_SCORE:
            # 如果趋势是 improving，不调整
            if trend == "improving":
                new_depth = self.current_depth
                adjustment = 0
                reason = f"趋势 improving，保持 depth={self.current_depth}"
                confidence = 0.9
            else:
                new_depth = max(self.min_depth, self.current_depth - step)
                adjustment = new_depth - self.current_depth
                reason = f"平均分 {avg_score:.2f} > {EvaluationThreshold.HIGH_SCORE}，尝试降低 depth"
                confidence = 0.7
                
        # 极高分: 降低 depth
        elif avg_score > EvaluationThreshold.EXCELLENT:
            new_depth = max(self.min_depth, self.current_depth - step)
            adjustment = new_depth - self.current_depth
            reason = f"平均分 {avg_score:.2f} > {EvaluationThreshold.EXCELLENT}，降低 depth 优化资源"
            confidence = 0.85
            
        # 中等分数: 保持
        else:
            new_depth = self.current_depth
            adjustment = 0
            reason = f"平均分 {avg_score:.2f} 在正常范围，保持 depth={self.current_depth}"
            confidence = 0.5
        
        return new_depth, adjustment, reason, confidence
    
    def get_optimal_config(self) -> Dict[str, Any]:
        """
        获取当前最优配置
        
        Returns:
            dict: 最优配置
        """
        return compute_optimal_config(self.current_depth)
    
    def predict_best_depth(self, task_type: str) -> int:
        """
        预测任务的最优 depth
        
        Args:
            task_type: 任务类型
            
        Returns:
            int: 预测的 depth
        """
        # 从历史中学习
        relevant_records = [h for h in self.history if h.task_type == task_type]
        
        if relevant_records:
            # 使用该任务类型的历史最佳 depth
            best_record = max(relevant_records, key=lambda h: h.score)
            logger.info(f"基于历史: {task_type} → depth={best_record.depth} (score={best_record.score:.3f})")
            return best_record.depth
        
        # 使用任务类型推荐
        config = compute_optimal_config_for_task(task_type)
        recommended = config.get('depth', 5)
        
        # 结合当前 depth 进行微调
        if len(self.history) >= 3:
            avg_recent_score = sum(h.score for h in self.history[-3:]) / 3
            if avg_recent_score < 0.7:
                recommended = min(10, recommended + 1)
            elif avg_recent_score > 0.85:
                recommended = max(1, recommended - 1)
        
        logger.info(f"推荐 depth: {task_type} → {recommended}")
        return recommended
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            'current_depth': self.current_depth,
            'total_evaluations': len(self.history),
            'total_adjustments': self.total_adjustments,
            'successful_adjustments': self.successful_adjustments,
            'adjustment_success_rate': 0.0,
        }
        
        if self.total_adjustments > 0:
            stats['adjustment_success_rate'] = self.successful_adjustments / self.total_adjustments
        
        if self.history:
            scores = [h.score for h in self.history]
            stats['avg_score'] = sum(scores) / len(scores)
            stats['best_score'] = max(scores)
            stats['worst_score'] = min(scores)
        
        return stats
    
    def reset(self):
        """重置优化器"""
        self.history.clear()
        self._score_trend.clear()
        self._depth_changes.clear()
        self.total_adjustments = 0
        self.successful_adjustments = 0
        logger.info("优化器已重置")


# ============= 便捷函数 =============

def create_optimizer(
    initial_depth: int = 5,
    strategy: str = "moderate"
) -> EvolutionDepthOptimizer:
    """
    创建优化器
    
    Args:
        initial_depth: 初始 depth
        strategy: 策略 (conservative/moderate/aggressive)
        
    Returns:
        EvolutionDepthOptimizer: 优化器实例
    """
    strategy_map = {
        'conservative': AdjustmentStrategy.CONSERVATIVE,
        'moderate': AdjustmentStrategy.MODERATE,
        'aggressive': AdjustmentStrategy.AGGRESSIVE,
    }
    return EvolutionDepthOptimizer(
        initial_depth=initial_depth,
        strategy=strategy_map.get(strategy, AdjustmentStrategy.MODERATE)
    )


# ============= 测试 =============

if __name__ == "__main__":
    print("=" * 60)
    print("EvolutionDepthOptimizer 测试")
    print("=" * 60)
    
    # 创建优化器
    optimizer = create_optimizer(initial_depth=5, strategy="moderate")
    
    # 模拟评估序列
    test_evaluations = [
        (0.5, "code_fix"),   # 低分 -> 应该增加 depth
        (0.55, "code_fix"),
        (0.6, "refactor"),
        (0.7, "refactor"),   # 好转
        (0.75, "refactor"),
        (0.85, "refactor"),  # 高分 -> 可以降低
        (0.88, "auto_fix"),
    ]
    
    print("\n[测试序列]")
    for score, task_type in test_evaluations:
        print(f"\n--- 评估: score={score}, task={task_type} ---")
        
        # 记录评估
        optimizer.record_evaluation(score, task_type)
        
        # 分析调整
        result = optimizer.analyze_and_adjust()
        
        print(f"  当前 depth: {result.current_depth}")
        print(f"  建议 depth: {result.suggested_depth}")
        print(f"  调整: {result.adjustment:+d}")
        print(f"  原因: {result.reason}")
        print(f"  置信度: {result.confidence:.2f}")
        
        # 显示配置
        config = optimizer.get_optimal_config()
        print(f"  timeout: {config['timeout']}s, max_tokens: {config['max_tokens']}")
    
    # 最终统计
    print("\n" + "=" * 60)
    print("最终统计")
    print("=" * 60)
    stats = optimizer.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 预测测试
    print("\n[预测测试]")
    for task in ["code_fix", "refactor", "architecture", "auto_fix"]:
        depth = optimizer.predict_best_depth(task)
        print(f"  {task} → depth={depth}")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
