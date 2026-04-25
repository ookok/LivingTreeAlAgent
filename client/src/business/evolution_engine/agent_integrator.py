# -*- coding: utf-8 -*-
"""
Agent Pipeline 集成器
======================

统一整合 PipelineOptimizer + DynamicConfigAdjuster + ExecutionAgent

功能：
1. 意图 → 任务分类 → 配置优化 → 执行 → 调整
2. 完整执行闭环
3. 统一配置接口

Author: LivingTreeAI Team
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum, auto

# 导入 Phase 2 模块
from client.src.business.evolution_engine.evolution_integrator import (
    EvolutionConfigIntegrator,
    ConfigResult,
    OptimizationResult,
)
from client.src.business.evolution_engine.pipeline_optimizer import (
    PipelineOptimizer,
    PipelineExecutor,
    PipelineConfig,
    TaskType,
    create_pipeline_optimizer,
    create_pipeline_executor,
)
from client.src.business.evolution_engine.dynamic_config_adjuster import (
    DynamicConfigAdjuster,
    AdaptiveTimeoutController,
    AdjustmentStrategy,
    PerformanceMetrics,
)


# ── 执行状态 ───────────────────────────────────────────────────────────────


class ExecutionState(Enum):
    """执行状态"""
    IDLE = auto()
    CLASSIFYING = auto()
    OPTIMIZING = auto()
    EXECUTING = auto()
    ADJUSTING = auto()
    COMPLETED = auto()
    FAILED = auto()


# ── 执行结果 ───────────────────────────────────────────────────────────────


@dataclass
class AgentExecutionResult:
    """Agent 执行结果"""
    success: bool
    state: ExecutionState

    # 任务信息
    intent: str
    task_type: TaskType
    pipeline_config: PipelineConfig

    # 执行结果
    result: Any = None
    error: Optional[str] = None

    # 性能信息
    duration: float = 0
    metrics: Dict[str, Any] = field(default_factory=dict)

    # 调整历史
    adjustments: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'state': self.state.name,
            'intent': self.intent,
            'task_type': self.task_type.name,
            'duration': self.duration,
            'result': str(self.result)[:200] if self.result else None,
            'error': self.error,
            'metrics': self.metrics,
            'adjustments': self.adjustments,
        }


# ── Agent Pipeline 集成器 ─────────────────────────────────────────────────


class AgentPipelineIntegrator:
    """
    Agent Pipeline 集成器

    整合所有 Phase 2/3 模块，提供统一的 Agent 执行接口

    架构：
    ┌─────────────────────────────────────────────────────────────┐
    │                    AgentPipelineIntegrator                   │
    ├─────────────────────────────────────────────────────────────┤
    │  Intent → TaskClassifier → TaskType                         │
    │              ↓                                              │
    │       EvolutionConfigIntegrator → Config + Optimization     │
    │              ↓                                              │
    │       PipelineOptimizer → PipelineConfig                     │
    │              ↓                                              │
    │       DynamicConfigAdjuster → Real-time Adjustment          │
    │              ↓                                              │
    │       PipelineExecutor → Result                             │
    └─────────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        strategy: AdjustmentStrategy = AdjustmentStrategy.MODERATE,
        enable_adjustment: bool = True,
        enable_execution: bool = True,
    ):
        # Phase 2: Evolution 集成
        self._evolution_integrator = EvolutionConfigIntegrator()

        # Phase 3: Pipeline 优化
        self._pipeline_optimizer = create_pipeline_optimizer()
        self._pipeline_executor = create_pipeline_executor(self._pipeline_optimizer)

        # Phase 3: 动态调整
        self._config_adjuster = create_dynamic_adjuster(strategy)
        self._timeout_controller = create_timeout_controller()

        # 配置
        self._enable_adjustment = enable_adjustment
        self._enable_execution = enable_execution

        # 回调函数
        self._on_state_change: Optional[Callable[[ExecutionState], None]] = None
        self._on_adjustment: Optional[Callable[[Dict], None]] = None

        # 状态
        self._state = ExecutionState.IDLE

    @property
    def state(self) -> ExecutionState:
        return self._state

    def _set_state(self, state: ExecutionState):
        self._state = state
        if self._on_state_change:
            self._on_state_change(state)

    def execute(
        self,
        intent: str,
        context: Optional[Dict[str, Any]] = None,
        base_config: Optional[Dict[str, Any]] = None,
    ) -> AgentExecutionResult:
        """
        执行完整的 Agent 管道

        Args:
            intent: 用户意图
            context: 上下文
            base_config: 基础配置

        Returns:
            AgentExecutionResult: 执行结果
        """
        start_time = time.time()
        context = context or {}
        adjustments = []

        try:
            # 1. 任务分类
            self._set_state(ExecutionState.CLASSIFYING)
            task_type = self._pipeline_optimizer.classify_task(intent)

            # 2. 配置优化 (Phase 2)
            self._set_state(ExecutionState.OPTIMIZING)
            config_result, opt_result = self._evolution_integrator.record_and_adjust(
                task_type.value,
                0.7,  # 默认分数
            )

            # 3. 获取 Pipeline 配置
            pipeline_config = self._pipeline_optimizer.get_optimal_config(task_type, intent)

            # 4. 初始化动态调整器
            if self._enable_adjustment:
                adj_config = {
                    'max_depth': config_result.depth,
                    'timeout': config_result.config.get('timeout', 60.0),
                    'context_limit': config_result.config.get('context_limit', 8192),
                    'max_retries': config_result.config.get('max_retries', 3),
                }
                self._config_adjuster.set_config(adj_config)

            # 5. 执行管道
            self._set_state(ExecutionState.EXECUTING)
            execution_result = self._pipeline_executor.execute(
                intent=intent,
                task_type=task_type,
                context=context,
                config=pipeline_config,
            )

            # 6. 动态调整（执行中）
            if self._enable_adjustment and self._enable_execution:
                self._set_state(ExecutionState.ADJUSTING)
                perf_metrics = PerformanceMetrics.capture()
                adjustment_results = self._config_adjuster.monitor(perf_metrics)

                for adj in adjustment_results:
                    adjustments.append({
                        'type': adj.adjustment_type.name,
                        'old': adj.old_value,
                        'new': adj.new_value,
                        'reason': adj.reason,
                    })

            # 完成
            self._set_state(ExecutionState.COMPLETED)

            duration = time.time() - start_time

            # 记录超时
            self._timeout_controller.record_execution(
                task_type.value,
                duration,
                execution_result.get('success', False),
            )

            return AgentExecutionResult(
                success=True,
                state=self._state,
                intent=intent,
                task_type=task_type,
                pipeline_config=pipeline_config,
                result=execution_result.get('result'),
                duration=duration,
                metrics=execution_result.get('metrics', {}),
                adjustments=adjustments,
            )

        except Exception as e:
            self._set_state(ExecutionState.FAILED)
            return AgentExecutionResult(
                success=False,
                state=self._state,
                intent=intent,
                task_type=TaskType.UNKNOWN,
                pipeline_config=PipelineConfig(),
                error=str(e),
                duration=time.time() - start_time,
            )

    def execute_stream(
        self,
        intent: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        流式执行（生成器）

        Args:
            intent: 用户意图
            context: 上下文

        Yields:
            Dict: 执行状态更新
        """
        # 1. 任务分类
        self._set_state(ExecutionState.CLASSIFYING)
        task_type = self._pipeline_optimizer.classify_task(intent)
        yield {
            'state': self._state.name,
            'task_type': task_type.name,
            'progress': 0.1,
        }

        # 2. 配置优化
        self._set_state(ExecutionState.OPTIMIZING)
        config_result, _ = self._evolution_integrator.record_and_adjust(task_type.value, 0.7)
        yield {
            'state': self._state.name,
            'depth': config_result.depth,
            'progress': 0.3,
        }

        # 3. 动态调整
        if self._enable_adjustment:
            self._set_state(ExecutionState.ADJUSTING)
            perf_metrics = PerformanceMetrics.capture()
            adjustments = self._config_adjuster.monitor(perf_metrics)
            yield {
                'state': self._state.name,
                'adjustments': [a.adjustment_type.name for a in adjustments],
                'progress': 0.5,
            }

        # 4. 执行
        self._set_state(ExecutionState.EXECUTING)
        pipeline_config = self._pipeline_optimizer.get_optimal_config(task_type, intent)
        yield {
            'state': self._state.name,
            'pipeline_config': pipeline_config.to_dict(),
            'progress': 0.7,
        }

        # 5. 完成
        self._set_state(ExecutionState.COMPLETED)
        yield {
            'state': self._state.name,
            'progress': 1.0,
        }

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'pipeline': self._pipeline_optimizer.get_statistics(),
            'adjustment': self._config_adjuster.get_statistics(),
        }

    def reset(self):
        """重置状态"""
        self._config_adjuster.reset()
        self._set_state(ExecutionState.IDLE)


# ── 工厂函数 ───────────────────────────────────────────────────────────────


def create_agent_integrator(
    strategy: AdjustmentStrategy = AdjustmentStrategy.MODERATE,
    enable_adjustment: bool = True,
    enable_execution: bool = True,
) -> AgentPipelineIntegrator:
    """
    创建 Agent Pipeline 集成器

    Args:
        strategy: 调整策略
        enable_adjustment: 是否启用动态调整
        enable_execution: 是否启用代码执行

    Returns:
        AgentPipelineIntegrator: 集成器实例
    """
    return AgentPipelineIntegrator(
        strategy=strategy,
        enable_adjustment=enable_adjustment,
        enable_execution=enable_execution,
    )


# ── 测试入口 ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("=" * 60)
    print("Agent Pipeline 集成器测试 (Phase 2 + Phase 3)")
    print("=" * 60)

    # 创建集成器
    integrator = create_agent_integrator(
        strategy=AdjustmentStrategy.MODERATE,
        enable_adjustment=True,
        enable_execution=True,
    )

    # 测试用例
    test_cases = [
        "修复这个bug",
        "重构这个函数让它更清晰",
        "设计一个微服务架构",
        "帮我写一个快速排序算法",
    ]

    print("\n[1] 批量执行测试")
    for i, intent in enumerate(test_cases, 1):
        print(f"\n--- 测试 {i}: '{intent}' ---")
        result = integrator.execute(intent, context={'user': 'test'})

        print(f"  State: {result.state.name}")
        print(f"  Task Type: {result.task_type.name}")
        print(f"  Duration: {result.duration:.3f}s")
        print(f"  Config: depth={result.pipeline_config.max_depth}, "
              f"timeout={result.pipeline_config.timeout}s")

        if result.adjustments:
            print(f"  Adjustments: {len(result.adjustments)}")
            for adj in result.adjustments:
                print(f"    - {adj['type']}: {adj['old']} -> {adj['new']}")

    # 流式执行
    print("\n[2] 流式执行测试")
    for update in integrator.execute_stream("修复这个bug"):
        print(f"  [{update['state']}] progress={update['progress']:.0%}")
        if 'depth' in update:
            print(f"    depth={update['depth']}")

    # 统计
    print("\n[3] 统计信息")
    stats = integrator.get_statistics()
    print(f"  Pipeline Tasks: {stats['pipeline']['total_tasks']}")
    print(f"  Adjustments: {stats['adjustment']['total_adjustments']}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
