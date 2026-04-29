# -*- coding: utf-8 -*-
"""
动态配置调整器
==============

在执行过程中根据实时指标动态调整配置。

功能：
1. 性能监控 → 配置调整
2. 自适应超时控制
3. 资源使用优化

Author: LivingTreeAI Team
from __future__ import annotations
"""


import time
import psutil
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
from collections import deque
from enum import Enum, auto


# ── 调整策略 ────────────────────────────────────────────────────────────────


class AdjustmentStrategy(Enum):
    """调整策略"""
    CONSERVATIVE = auto()    # 保守：小幅调整
    MODERATE = auto()       # 中等：常规调整
    AGGRESSIVE = auto()     # 激进：大幅调整


class AdjustmentType(Enum):
    """调整类型"""
    TIMEOUT = auto()        # 超时调整
    RETRY = auto()          # 重试调整
    DEPTH = auto()          # 深度调整
    CONTEXT = auto()        # 上下文调整


# ── 性能指标 ───────────────────────────────────────────────────────────────


@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: float = 0
    cpu_percent: float = 0
    memory_percent: float = 0
    memory_mb: float = 0

    # 执行指标
    tokens_per_second: float = 0      # Token 生成速度
    tokens_processed: int = 0         # 已处理 Token 数

    # 阶段指标
    stage_name: str = ""
    stage_duration: float = 0         # 阶段耗时
    stage_progress: float = 0         # 阶段进度 0-1

    @staticmethod
    def capture() -> 'PerformanceMetrics':
        """捕获当前性能指标"""
        mem = psutil.virtual_memory()
        return PerformanceMetrics(
            timestamp=time.time(),
            cpu_percent=psutil.cpu_percent(interval=0.1),
            memory_percent=mem.percent,
            memory_mb=mem.used / 1024 / 1024,
        )


@dataclass
class AdjustmentResult:
    """调整结果"""
    adjustment_type: AdjustmentType
    old_value: Any
    new_value: Any
    reason: str
    confidence: float  # 0-1


# ── 阈值配置 ───────────────────────────────────────────────────────────────


@dataclass
class ThresholdConfig:
    """阈值配置"""
    # CPU 阈值
    cpu_high: float = 80.0      # CPU 高阈值
    cpu_low: float = 20.0      # CPU 低阈值

    # 内存阈值
    memory_high: float = 80.0  # 内存高阈值
    memory_low: float = 30.0   # 内存低阈值

    # 执行时间阈值
    time_warning: float = 0.7  # 时间警告阈值 (比例)
    time_critical: float = 0.9 # 时间临界阈值 (比例)


# ── 动态配置调整器 ─────────────────────────────────────────────────────────


class DynamicConfigAdjuster:
    """
    动态配置调整器

    根据实时性能指标自动调整执行配置

    功能：
    1. 性能监控
    2. 配置调整
    3. 自适应超时
    """

    def __init__(
        self,
        strategy: AdjustmentStrategy = AdjustmentStrategy.MODERATE,
        thresholds: Optional[ThresholdConfig] = None,
    ):
        self.strategy = strategy
        self.thresholds = thresholds or ThresholdConfig()

        # 调整步长（根据策略）
        self._adjustment_steps: Dict[AdjustmentType, float] = {
            AdjustmentType.TIMEOUT: self._get_step('timeout'),
            AdjustmentType.RETRY: self._get_step('retry'),
            AdjustmentType.DEPTH: self._get_step('depth'),
            AdjustmentType.CONTEXT: self._get_step('context'),
        }

        # 配置缓存
        self._current_config: Dict[str, Any] = {}
        self._original_config: Dict[str, Any] = {}

        # 性能历史
        self._metrics_history: deque = deque(maxlen=100)

        # 调整历史
        self._adjustment_history: List[AdjustmentResult] = []

        # 回调函数
        self._on_adjustment: Optional[Callable[[AdjustmentResult], None]] = None

    def _get_step(self, key: str) -> float:
        """获取调整步长"""
        steps = {
            AdjustmentStrategy.CONSERVATIVE: {
                'timeout': 1.1,
                'retry': 0.5,
                'depth': 0.5,
                'context': 0.9,
            },
            AdjustmentStrategy.MODERATE: {
                'timeout': 1.25,
                'retry': 1.0,
                'depth': 1.0,
                'context': 0.8,
            },
            AdjustmentStrategy.AGGRESSIVE: {
                'timeout': 1.5,
                'retry': 2.0,
                'depth': 2.0,
                'context': 0.7,
            },
        }
        return steps.get(self.strategy, {}).get(key, 1.0)

    def set_config(self, config: Dict[str, Any]):
        """设置初始配置"""
        self._current_config = config.copy()
        self._original_config = config.copy()

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self._current_config.copy()

    def monitor(self, metrics: Optional[PerformanceMetrics] = None) -> List[AdjustmentResult]:
        """
        监控并调整

        Args:
            metrics: 性能指标（可选，自动捕获）

        Returns:
            List[AdjustmentResult]: 调整结果列表
        """
        # 捕获性能指标
        if metrics is None:
            metrics = PerformanceMetrics.capture()

        self._metrics_history.append(metrics)

        # 执行调整
        results = []
        results.extend(self._adjust_by_cpu(metrics))
        results.extend(self._adjust_by_memory(metrics))
        results.extend(self._adjust_by_time(metrics))

        return results

    def _adjust_by_cpu(self, metrics: PerformanceMetrics) -> List[AdjustmentResult]:
        """根据 CPU 使用率调整"""
        results = []

        if metrics.cpu_percent > self.thresholds.cpu_high:
            # CPU 过高 → 减少复杂度
            if 'max_depth' in self._current_config:
                old_depth = self._current_config['max_depth']
                new_depth = max(1, old_depth - int(self._adjustment_steps[AdjustmentType.DEPTH]))
                self._current_config['max_depth'] = new_depth
                results.append(AdjustmentResult(
                    adjustment_type=AdjustmentType.DEPTH,
                    old_value=old_depth,
                    new_value=new_depth,
                    reason=f"CPU 过高 ({metrics.cpu_percent:.1f}%)",
                    confidence=0.8,
                ))

            if 'context_limit' in self._current_config:
                old_limit = self._current_config['context_limit']
                new_limit = int(old_limit * self._adjustment_steps[AdjustmentType.CONTEXT])
                self._current_config['context_limit'] = new_limit
                results.append(AdjustmentResult(
                    adjustment_type=AdjustmentType.CONTEXT,
                    old_value=old_limit,
                    new_value=new_limit,
                    reason=f"CPU 过高 ({metrics.cpu_percent:.1f}%)",
                    confidence=0.7,
                ))

        elif metrics.cpu_percent < self.thresholds.cpu_low:
            # CPU 过低 → 可以增加复杂度
            if 'max_depth' in self._current_config:
                old_depth = self._current_config['max_depth']
                new_depth = min(10, old_depth + 1)
                if new_depth != old_depth:
                    self._current_config['max_depth'] = new_depth
                    results.append(AdjustmentResult(
                        adjustment_type=AdjustmentType.DEPTH,
                        old_value=old_depth,
                        new_value=new_depth,
                        reason=f"CPU 空闲 ({metrics.cpu_percent:.1f}%)",
                        confidence=0.5,
                    ))

        return results

    def _adjust_by_memory(self, metrics: PerformanceMetrics) -> List[AdjustmentResult]:
        """根据内存使用率调整"""
        results = []

        if metrics.memory_percent > self.thresholds.memory_high:
            # 内存过高 → 减少上下文
            if 'context_limit' in self._current_config:
                old_limit = self._current_config['context_limit']
                new_limit = int(old_limit * 0.8)
                self._current_config['context_limit'] = max(1024, new_limit)
                results.append(AdjustmentResult(
                    adjustment_type=AdjustmentType.CONTEXT,
                    old_value=old_limit,
                    new_value=new_limit,
                    reason=f"内存过高 ({metrics.memory_percent:.1f}%)",
                    confidence=0.9,
                ))

        return results

    def _adjust_by_time(self, metrics: PerformanceMetrics) -> List[AdjustmentResult]:
        """根据执行时间调整"""
        results = []

        if 'timeout' not in self._current_config:
            return results

        # 检查阶段进度
        if metrics.stage_duration > 0 and metrics.stage_progress > 0:
            expected_time = metrics.stage_duration / metrics.stage_progress
            remaining_time = expected_time * (1 - metrics.stage_progress)

            # 预计超时
            if remaining_time > self._current_config['timeout'] * 0.5:
                old_timeout = self._current_config['timeout']
                new_timeout = old_timeout * self._adjustment_steps[AdjustmentType.TIMEOUT]
                self._current_config['timeout'] = new_timeout
                results.append(AdjustmentResult(
                    adjustment_type=AdjustmentType.TIMEOUT,
                    old_value=old_timeout,
                    new_value=new_timeout,
                    reason=f"预计剩余时间过长",
                    confidence=0.6,
                ))

        return results

    def reset(self):
        """重置为原始配置"""
        self._current_config = self._original_config.copy()
        self._adjustment_history.clear()

    def get_adjustment_history(self) -> List[AdjustmentResult]:
        """获取调整历史"""
        return self._adjustment_history.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._metrics_history:
            return {'total_adjustments': 0}

        recent_metrics = list(self._metrics_history)[-20:]
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_mem = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)

        return {
            'total_adjustments': len(self._adjustment_history),
            'avg_cpu': avg_cpu,
            'avg_memory': avg_mem,
            'current_config': self._current_config,
        }


# ── 自适应超时控制器 ───────────────────────────────────────────────────────


class AdaptiveTimeoutController:
    """
    自适应超时控制器

    根据任务历史自动调整超时时间
    """

    def __init__(self, base_timeout: float = 60.0):
        self.base_timeout = base_timeout

        # 任务类型 → 超时历史
        self._timeout_history: Dict[str, deque] = {}

        # 默认乘数
        self._multiplier: float = 1.0

    def get_timeout(
        self,
        task_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        获取任务超时时间

        Args:
            task_type: 任务类型
            context: 上下文

        Returns:
            float: 超时时间（秒）
        """
        # 获取历史超时
        history = self._timeout_history.get(task_type, deque(maxlen=50))

        if history:
            # 使用 P90 百分位数
            sorted_times = sorted(history)
            p90_index = int(len(sorted_times) * 0.9)
            historical_timeout = sorted_times[p90_index] if sorted_times else self.base_timeout
        else:
            historical_timeout = self.base_timeout

        # 结合基础超时和历史超时
        timeout = max(self.base_timeout, historical_timeout) * self._multiplier

        # 上下文调整
        if context:
            complexity = context.get('complexity', 1.0)
            timeout *= complexity

        return timeout

    def record_execution(self, task_type: str, duration: float, success: bool):
        """
        记录执行结果

        Args:
            task_type: 任务类型
            duration: 执行时长
            success: 是否成功
        """
        if task_type not in self._timeout_history:
            self._timeout_history[task_type] = deque(maxlen=50)

        self._timeout_history[task_type].append(duration)

        # 调整乘数
        if not success:
            # 失败 → 增加超时
            self._multiplier = min(3.0, self._multiplier * 1.2)
        else:
            # 成功 → 逐渐降低乘数
            self._multiplier = max(1.0, self._multiplier * 0.95)


# ── 工厂函数 ───────────────────────────────────────────────────────────────


def create_dynamic_adjuster(
    strategy: AdjustmentStrategy = AdjustmentStrategy.MODERATE,
) -> DynamicConfigAdjuster:
    """创建动态调整器"""
    return DynamicConfigAdjuster(strategy=strategy)


def create_timeout_controller(base_timeout: float = 60.0) -> AdaptiveTimeoutController:
    """创建自适应超时控制器"""
    return AdaptiveTimeoutController(base_timeout=base_timeout)


# ── 测试入口 ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("=" * 50)
    print("动态配置调整器测试")
    print("=" * 50)

    # 创建调整器
    adjuster = create_dynamic_adjuster(AdjustmentStrategy.MODERATE)
    adjuster.set_config({
        'max_depth': 5,
        'timeout': 60.0,
        'context_limit': 8192,
        'max_retries': 3,
    })

    print("\n[1] 初始配置")
    print(f"  {adjuster.get_config()}")

    # 模拟 CPU 过高
    print("\n[2] 模拟 CPU 过高 (90%)")
    metrics = PerformanceMetrics(
        timestamp=time.time(),
        cpu_percent=90.0,
        memory_percent=50.0,
    )
    adjustments = adjuster.monitor(metrics)
    print(f"  调整数量: {len(adjustments)}")
    for adj in adjustments:
        print(f"    {adj.adjustment_type.name}: {adj.old_value} → {adj.new_value} ({adj.reason})")

    print(f"\n  调整后配置: {adjuster.get_config()}")

    # 模拟 CPU 空闲
    print("\n[3] 模拟 CPU 空闲 (10%)")
    metrics2 = PerformanceMetrics(
        timestamp=time.time(),
        cpu_percent=10.0,
        memory_percent=30.0,
    )
    adjustments2 = adjuster.monitor(metrics2)
    print(f"  调整数量: {len(adjustments2)}")

    print(f"\n  最终配置: {adjuster.get_config()}")

    # 自适应超时
    print("\n[4] 自适应超时控制器")
    controller = create_timeout_controller(base_timeout=60.0)

    # 记录一些执行
    controller.record_execution('code_fix', 30.0, True)
    controller.record_execution('code_fix', 45.0, True)
    controller.record_execution('code_fix', 120.0, False)  # 超时

    timeout = controller.get_timeout('code_fix')
    print(f"  code_fix 超时: {timeout:.1f}s")

    timeout2 = controller.get_timeout('architecture')
    print(f"  architecture 超时: {timeout2:.1f}s (使用默认值)")

    print("\n[5] 统计信息")
    stats = adjuster.get_statistics()
    print(f"  总调整次数: {stats['total_adjustments']}")
    print(f"  平均 CPU: {stats['avg_cpu']:.1f}%")
    print(f"  平均内存: {stats['avg_memory']:.1f}%")

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
