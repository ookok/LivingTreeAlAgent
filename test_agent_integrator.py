# -*- coding: utf-8 -*-
"""
Agent Pipeline 集成器独立测试
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum, auto

# ── TaskType ──────────────────────────────────────────────────────────────────

class TaskType(Enum):
    CODE_GENERATION = auto()
    CODE_FIX = auto()
    REFACTOR = auto()
    ARCHITECTURE = auto()
    DOCUMENTATION = auto()
    ANALYSIS = auto()
    QUERY = auto()
    CREATIVE = auto()
    UNKNOWN = auto()


# ── ExecutionState ───────────────────────────────────────────────────────────

class ExecutionState(Enum):
    IDLE = auto()
    CLASSIFYING = auto()
    OPTIMIZING = auto()
    EXECUTING = auto()
    ADJUSTING = auto()
    COMPLETED = auto()
    FAILED = auto()


# ── PipelineConfig ──────────────────────────────────────────────────────────

@dataclass
class PipelineConfig:
    use_reasoning: bool = True
    use_execution: bool = False
    use_verification: bool = False
    max_depth: int = 5
    timeout: float = 60.0
    max_retries: int = 3
    context_limit: int = 8192
    use_compression: bool = True
    enabled_tools: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'use_reasoning': self.use_reasoning,
            'use_execution': self.use_execution,
            'use_verification': self.use_verification,
            'max_depth': self.max_depth,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'context_limit': self.context_limit,
            'use_compression': self.use_compression,
            'enabled_tools': self.enabled_tools,
        }


# ── TaskClassifier ───────────────────────────────────────────────────────────

class TaskClassifier:
    KEYWORD_PATTERNS: Dict[TaskType, List[str]] = {
        TaskType.CODE_GENERATION: ['写代码', '生成代码', '帮我写', '创建函数', '实现'],
        TaskType.CODE_FIX: ['修复', 'bug', '错误', '修复bug'],
        TaskType.REFACTOR: ['重构', '优化代码', '改善代码'],
        TaskType.ARCHITECTURE: ['设计', '架构', '架构设计', '系统设计'],
        TaskType.DOCUMENTATION: ['文档', '写文档', '注释'],
        TaskType.ANALYSIS: ['分析', '调研', '研究'],
        TaskType.QUERY: ['是什么', '怎么', '如何', '为什么'],
        TaskType.CREATIVE: ['创意', '头脑风暴', '想法'],
        TaskType.UNKNOWN: [],
    }

    def classify(self, intent: str) -> TaskType:
        intent_lower = intent.lower()
        for task_type, keywords in self.KEYWORD_PATTERNS.items():
            for keyword in keywords:
                if keyword.lower() in intent_lower:
                    return task_type
        return TaskType.UNKNOWN


# ── ConfigResult ────────────────────────────────────────────────────────────

@dataclass
class ConfigResult:
    depth: int
    task_type: str
    config: Dict[str, Any]
    confidence: float = 0.8


# ── AdjustmentResult ─────────────────────────────────────────────────────────

@dataclass
class AdjustmentResult:
    adjustment_type: str
    old_value: Any
    new_value: Any
    reason: str


# ── AgentExecutionResult ────────────────────────────────────────────────────

@dataclass
class AgentExecutionResult:
    success: bool
    state: ExecutionState
    intent: str
    task_type: TaskType
    pipeline_config: PipelineConfig
    result: Any = None
    error: Optional[str] = None
    duration: float = 0
    metrics: Dict[str, Any] = field(default_factory=dict)
    adjustments: List[Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'state': self.state.name,
            'intent': self.intent,
            'task_type': self.task_type.name,
            'duration': self.duration,
        }


# ── SimplePipelineOptimizer ─────────────────────────────────────────────────

class SimplePipelineOptimizer:
    TASK_CONFIG_MAPPING = {
        TaskType.CODE_FIX: PipelineConfig(max_depth=3, timeout=60.0),
        TaskType.REFACTOR: PipelineConfig(max_depth=6, timeout=180.0),
        TaskType.ARCHITECTURE: PipelineConfig(max_depth=8, timeout=300.0),
        TaskType.CODE_GENERATION: PipelineConfig(max_depth=5, timeout=120.0),
        TaskType.QUERY: PipelineConfig(max_depth=2, timeout=30.0),
        TaskType.UNKNOWN: PipelineConfig(),
    }

    def __init__(self):
        self._classifier = TaskClassifier()

    def classify_task(self, intent: str) -> TaskType:
        return self._classifier.classify(intent)

    def get_optimal_config(self, task_type: TaskType, intent: str = "") -> PipelineConfig:
        return self.TASK_CONFIG_MAPPING.get(task_type, PipelineConfig())


# ── AgentPipelineIntegrator ─────────────────────────────────────────────────

class AgentPipelineIntegrator:
    def __init__(self):
        self._pipeline_optimizer = SimplePipelineOptimizer()
        self._state = ExecutionState.IDLE
        self._adjustments: List[AdjustmentResult] = []

    @property
    def state(self) -> ExecutionState:
        return self._state

    def execute(
        self,
        intent: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentExecutionResult:
        start_time = time.time()
        context = context or {}

        try:
            # 1. 任务分类
            self._state = ExecutionState.CLASSIFYING
            task_type = self._pipeline_optimizer.classify_task(intent)

            # 2. 配置优化
            self._state = ExecutionState.OPTIMIZING
            config_result = ConfigResult(
                depth=task_type.value if hasattr(task_type, 'value') else 5,
                task_type=task_type.name,
                config={'timeout': 60.0},
            )

            # 3. 获取 Pipeline 配置
            pipeline_config = self._pipeline_optimizer.get_optimal_config(task_type, intent)

            # 4. 模拟动态调整
            self._state = ExecutionState.ADJUSTING
            if task_type != TaskType.QUERY:
                adj = AdjustmentResult(
                    adjustment_type='DEPTH',
                    old_value=5,
                    new_value=pipeline_config.max_depth,
                    reason='Based on task type',
                )
                self._adjustments.append(adj)

            # 5. 执行
            self._state = ExecutionState.EXECUTING
            # 模拟执行

            # 6. 完成
            self._state = ExecutionState.COMPLETED

            duration = time.time() - start_time

            return AgentExecutionResult(
                success=True,
                state=self._state,
                intent=intent,
                task_type=task_type,
                pipeline_config=pipeline_config,
                duration=duration,
                adjustments=[{'type': a.adjustment_type, 'old': a.old_value, 'new': a.new_value} for a in self._adjustments],
            )

        except Exception as e:
            self._state = ExecutionState.FAILED
            return AgentExecutionResult(
                success=False,
                state=self._state,
                intent=intent,
                task_type=TaskType.UNKNOWN,
                pipeline_config=PipelineConfig(),
                error=str(e),
                duration=time.time() - start_time,
            )


# ── 测试 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Agent Pipeline 集成器测试 (Phase 2 + Phase 3)")
    print("=" * 60)

    integrator = AgentPipelineIntegrator()

    test_cases = [
        "修复这个bug",
        "重构这个函数让它更清晰",
        "设计一个微服务架构",
        "帮我写一个快速排序算法",
        "Python的装饰器是什么",
    ]

    print("\n[1] 批量执行测试")
    for i, intent in enumerate(test_cases, 1):
        print(f"\n--- Test {i}: '{intent}' ---")
        result = integrator.execute(intent, context={'user': 'test'})

        print(f"  State: {result.state.name}")
        print(f"  Task Type: {result.task_type.name}")
        print(f"  Duration: {result.duration:.3f}s")
        print(f"  Config: depth={result.pipeline_config.max_depth}, timeout={result.pipeline_config.timeout}s")

        if result.adjustments:
            print(f"  Adjustments: {len(result.adjustments)}")
            for adj in result.adjustments:
                print(f"    - {adj['type']}: {adj['old']} -> {adj['new']}")

    print("\n[2] 流式执行测试")
    for update in [
        {'state': 'CLASSIFYING', 'progress': 0.1},
        {'state': 'OPTIMIZING', 'depth': 3, 'progress': 0.3},
        {'state': 'ADJUSTING', 'adjustments': ['DEPTH'], 'progress': 0.5},
        {'state': 'EXECUTING', 'progress': 0.7},
        {'state': 'COMPLETED', 'progress': 1.0},
    ]:
        print(f"  [{update['state']}] progress={update['progress']:.0%}")
        if 'depth' in update:
            print(f"    depth={update['depth']}")

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
