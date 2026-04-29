# -*- coding: utf-8 -*-
"""
Agent Pipeline 优化器
====================

基于任务类型和上下文自动优化 Agent 执行管道。

功能：
1. 任务分类 → 选择最优管道配置
2. 自适应管道选择
3. 管道执行优化

Author: LivingTreeAI Team
from __future__ import annotations
"""


import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, Dict, Any, List, Iterator
from collections import defaultdict
import json
from pathlib import Path

logger = logging.getLogger(__name__)


# ── 任务类型枚举 ────────────────────────────────────────────────────────────


class TaskType(Enum):
    """任务类型枚举"""
    CODE_GENERATION = auto()      # 代码生成
    CODE_FIX = auto()             # 代码修复
    REFACTOR = auto()             # 重构
    ARCHITECTURE = auto()         # 架构设计
    DOCUMENTATION = auto()        # 文档生成
    ANALYSIS = auto()             # 分析任务
    QUERY = auto()                # 问答查询
    CREATIVE = auto()             # 创意任务
    UNKNOWN = auto()              # 未知类型


class PipelineStage(Enum):
    """管道阶段"""
    INTENT_CLASSIFY = auto()
    CONTEXT_RETRIEVE = auto()
    REASONING = auto()
    EXECUTE = auto()
    VERIFY = auto()
    RESPOND = auto()


# ── 数据结构 ─────────────────────────────────────────────────────────────────


@dataclass
class PipelineConfig:
    """管道配置"""
    # 管道选择
    use_reasoning: bool = True           # 是否使用推理
    use_execution: bool = False           # 是否执行代码
    use_verification: bool = False        # 是否验证结果

    # 执行参数
    max_depth: int = 5                   # 最大深度
    timeout: float = 60.0                # 超时时间
    max_retries: int = 3                 # 最大重试次数

    # 上下文控制
    context_limit: int = 8192             # 上下文限制
    use_compression: bool = True          # 是否压缩上下文

    # 工具选择
    enabled_tools: List[str] = field(default_factory=list)  # 启用的工具

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


@dataclass
class PipelineMetrics:
    """管道执行指标"""
    task_type: TaskType
    pipeline_config: PipelineConfig

    # 性能指标
    start_time: float = 0
    end_time: float = 0
    total_duration: float = 0

    # 阶段指标
    stage_durations: Dict[PipelineStage, float] = field(default_factory=dict)
    stage_success: Dict[PipelineStage, bool] = field(default_factory=dict)

    # 结果指标
    final_score: float = 0
    tokens_used: int = 0
    cache_hits: int = 0

    def mark_start(self):
        self.start_time = time.time()

    def mark_end(self):
        self.end_time = time.time()
        self.total_duration = self.end_time - self.start_time

    def record_stage(self, stage: PipelineStage, duration: float, success: bool):
        self.stage_durations[stage] = duration
        self.stage_success[stage] = success

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_type': self.task_type.name,
            'total_duration': self.total_duration,
            'stage_durations': {k.name: v for k, v in self.stage_durations.items()},
            'stage_success': {k.name: v for k, v in self.stage_success.items()},
            'final_score': self.final_score,
            'tokens_used': self.tokens_used,
            'cache_hits': self.cache_hits,
        }


# ── 管道配置映射 ─────────────────────────────────────────────────────────────


# 任务类型 → 管道配置映射
TASK_PIPELINE_MAPPING: Dict[TaskType, PipelineConfig] = {
    TaskType.CODE_GENERATION: PipelineConfig(
        use_reasoning=True,
        use_execution=True,
        use_verification=True,
        max_depth=5,
        timeout=120.0,
        enabled_tools=['code_editor', 'terminal', 'file_manager'],
    ),
    TaskType.CODE_FIX: PipelineConfig(
        use_reasoning=True,
        use_execution=True,
        use_verification=True,
        max_depth=3,
        timeout=60.0,
        enabled_tools=['code_editor', 'debugger'],
    ),
    TaskType.REFACTOR: PipelineConfig(
        use_reasoning=True,
        use_execution=False,
        use_verification=True,
        max_depth=6,
        timeout=180.0,
        enabled_tools=['code_editor', 'git'],
    ),
    TaskType.ARCHITECTURE: PipelineConfig(
        use_reasoning=True,
        use_execution=False,
        use_verification=False,
        max_depth=8,
        timeout=300.0,
        enabled_tools=['diagram', 'document'],
    ),
    TaskType.DOCUMENTATION: PipelineConfig(
        use_reasoning=False,
        use_execution=False,
        use_verification=False,
        max_depth=3,
        timeout=60.0,
        enabled_tools=['document'],
    ),
    TaskType.ANALYSIS: PipelineConfig(
        use_reasoning=True,
        use_execution=False,
        use_verification=False,
        max_depth=5,
        timeout=120.0,
        enabled_tools=['search', 'calculator'],
    ),
    TaskType.QUERY: PipelineConfig(
        use_reasoning=False,
        use_execution=False,
        use_verification=False,
        max_depth=2,
        timeout=30.0,
        enabled_tools=['search'],
    ),
    TaskType.CREATIVE: PipelineConfig(
        use_reasoning=True,
        use_execution=False,
        use_verification=False,
        max_depth=4,
        timeout=90.0,
        enabled_tools=['brainstorm'],
    ),
    TaskType.UNKNOWN: PipelineConfig(),  # 默认配置
}


# ── Pipeline 优化器 ───────────────────────────────────────────────────────────


class PipelineOptimizer:
    """
    Agent Pipeline 优化器

    功能：
    1. 任务分类 → 选择最优管道配置
    2. 自适应管道选择
    3. 执行指标收集
    """

    def __init__(self):
        # 任务类型推断器
        self._task_classifier: Optional[TaskClassifier] = None

        # 历史指标
        self._metrics_history: List[PipelineMetrics] = []

        # 自适应权重
        self._task_weights: Dict[TaskType, float] = defaultdict(lambda: 1.0)

    @property
    def task_classifier(self) -> 'TaskClassifier':
        """延迟初始化任务分类器"""
        if self._task_classifier is None:
            self._task_classifier = TaskClassifier()
        return self._task_classifier

    def classify_task(self, intent: str) -> TaskType:
        """分类任务类型"""
        return self.task_classifier.classify(intent)

    def get_optimal_config(self, task_type: TaskType, intent: str = "") -> PipelineConfig:
        """
        获取最优管道配置

        Args:
            task_type: 任务类型
            intent: 原始意图（可选）

        Returns:
            PipelineConfig: 最优配置
        """
        # 从映射获取基础配置
        base_config = TASK_PIPELINE_MAPPING.get(task_type, PipelineConfig())

        # 根据历史性能调整
        adjusted_config = self._adjust_by_history(task_type, base_config)

        return adjusted_config

    def _adjust_by_history(self, task_type: TaskType, config: PipelineConfig) -> PipelineConfig:
        """根据历史指标调整配置"""
        # 获取该任务类型的历史指标
        relevant_metrics = [
            m for m in self._metrics_history[-20:]
            if m.task_type == task_type
        ]

        if not relevant_metrics:
            return config

        # 计算平均分数
        avg_score = sum(m.final_score for m in relevant_metrics) / len(relevant_metrics)

        # 根据平均分数调整配置
        if avg_score < 0.6:
            # 低分 → 增加深度和超时
            config.max_depth = min(10, config.max_depth + 1)
            config.timeout = min(300, config.timeout * 1.2)
        elif avg_score > 0.85:
            # 高分 → 减少资源消耗
            config.max_depth = max(2, config.max_depth - 1)
            config.timeout = max(30, config.timeout * 0.9)

        return config

    def record_metrics(self, metrics: PipelineMetrics):
        """记录执行指标"""
        self._metrics_history.append(metrics)

        # 限制历史长度
        if len(self._metrics_history) > 1000:
            self._metrics_history = self._metrics_history[-500:]

    def get_statistics(self) -> Dict[str, Any]:
        """获取优化统计"""
        if not self._metrics_history:
            return {'total_tasks': 0}

        # 按任务类型分组
        by_type: Dict[TaskType, List[PipelineMetrics]] = defaultdict(list)
        for m in self._metrics_history:
            by_type[m.task_type].append(m)

        stats = {
            'total_tasks': len(self._metrics_history),
            'avg_duration': sum(m.total_duration for m in self._metrics_history) / len(self._metrics_history),
            'by_task_type': {},
        }

        for task_type, metrics in by_type.items():
            type_stats = {
                'count': len(metrics),
                'avg_score': sum(m.final_score for m in metrics) / len(metrics),
                'avg_duration': sum(m.total_duration for m in metrics) / len(metrics),
            }
            stats['by_task_type'][task_type.name] = type_stats

        return stats


# ── 任务分类器 ───────────────────────────────────────────────────────────────


class TaskClassifier:
    """
    任务分类器

    基于关键词和模式匹配进行快速任务分类
    """

    # 关键词映射
    KEYWORD_PATTERNS: Dict[TaskType, List[str]] = {
        TaskType.CODE_GENERATION: [
            '写代码', '生成代码', '帮我写', '创建函数', '实现',
            'write code', 'generate', 'create function', 'implement',
        ],
        TaskType.CODE_FIX: [
            '修复', 'bug', '错误', '修复bug', '修复错误',
            'fix', 'fix bug', 'error', 'issue',
        ],
        TaskType.REFACTOR: [
            '重构', '优化代码', '改善代码',
            'refactor', 'improve code', 'clean up',
        ],
        TaskType.ARCHITECTURE: [
            '设计', '架构', '架构设计', '系统设计',
            'design', 'architecture', 'system design',
        ],
        TaskType.DOCUMENTATION: [
            '文档', '写文档', '注释', '说明',
            'document', 'documentation', 'comment',
        ],
        TaskType.ANALYSIS: [
            '分析', '调研', '研究',
            'analyze', 'analyse', 'research', 'investigate',
        ],
        TaskType.QUERY: [
            '是什么', '怎么', '如何', '为什么',
            'what is', 'how to', 'why', 'explain',
        ],
        TaskType.CREATIVE: [
            '创意', '头脑风暴', '想法',
            'creative', 'brainstorm', 'ideas',
        ],
    }

    def classify(self, intent: str) -> TaskType:
        """
        分类任务类型

        Args:
            intent: 用户意图文本

        Returns:
            TaskType: 任务类型
        """
        intent_lower = intent.lower()

        # 精确匹配
        for task_type, keywords in self.KEYWORD_PATTERNS.items():
            for keyword in keywords:
                if keyword.lower() in intent_lower:
                    return task_type

        # 默认返回 UNKNOWN
        return TaskType.UNKNOWN

    def get_confidence(self, intent: str) -> float:
        """获取分类置信度"""
        task_type = self.classify(intent)

        # 简单实现：关键词匹配数越多，置信度越高
        matched = 0
        for keyword in self.KEYWORD_PATTERNS.get(task_type, []):
            if keyword.lower() in intent.lower():
                matched += 1

        return min(1.0, matched * 0.2 + 0.5)


# ── 管道执行器 ───────────────────────────────────────────────────────────────


class PipelineExecutor:
    """
    管道执行器

    根据配置执行管道，集成：
    - IntentEngine: 意图解析 → 任务分类
    - ExecutionAgent: 安全代码执行
    - EvolutionIntentBridge: 意图→进化联动
    """

    def __init__(self, optimizer: Optional[PipelineOptimizer] = None):
        self.optimizer = optimizer or PipelineOptimizer()
        self._execution_agent = None  # 延迟初始化
        self._intent_bridge = None    # 延迟初始化

    @property
    def execution_agent(self):
        """延迟创建 ExecutionAgent"""
        if self._execution_agent is None:
            from client.src.business.evolution_engine.execution_agent import create_execution_agent
            self._execution_agent = create_execution_agent('sandbox')
        return self._execution_agent

    @property
    def intent_bridge(self):
        """延迟创建 EvolutionIntentBridge"""
        if self._intent_bridge is None:
            try:
                from client.src.business.evolution_engine.bridge import create_full_bridge
                self._intent_bridge = create_full_bridge()
            except Exception as e:
                logger.warning(f"无法创建 IntentBridge: {e}")
        return self._intent_bridge

    def execute(
        self,
        intent: str,
        task_type: Optional[TaskType] = None,
        context: Optional[Dict[str, Any]] = None,
        config: Optional[PipelineConfig] = None,
    ) -> Dict[str, Any]:
        """
        执行管道

        Args:
            intent: 用户意图
            task_type: 任务类型（可选，自动推断）
            context: 上下文
            config: 管道配置（可选）

        Returns:
            Dict: 执行结果
        """
        # 推断任务类型
        if task_type is None:
            task_type = self.optimizer.classify_task(intent)

        # 获取配置
        if config is None:
            config = self.optimizer.get_optimal_config(task_type, intent)

        # 创建指标
        metrics = PipelineMetrics(
            task_type=task_type,
            pipeline_config=config,
        )
        metrics.mark_start()

        try:
            # 执行管道
            result = self._execute_pipeline(intent, task_type, context, config, metrics)

            # 标记结束
            metrics.mark_end()

            # 基于验证阶段计算真实分数
            verify_stage = result.get("stages", [])
            real_score = 0.8  # 默认分数（无验证阶段时）
            for stage_name, stage_data in verify_stage:
                if stage_name == "verify" and isinstance(stage_data, dict):
                    real_score = stage_data.get("score", real_score)
                    break
            metrics.final_score = real_score

            # 记录指标
            self.optimizer.record_metrics(metrics)

            return {
                'success': True,
                'result': result,
                'task_type': task_type,
                'config': config.to_dict(),
                'metrics': metrics.to_dict(),
            }

        except Exception as e:
            metrics.mark_end()
            metrics.final_score = 0.0
            self.optimizer.record_metrics(metrics)

            return {
                'success': False,
                'error': str(e),
                'task_type': task_type,
                'metrics': metrics.to_dict(),
            }

    def _execute_pipeline(
        self,
        intent: str,
        task_type: TaskType,
        context: Optional[Dict[str, Any]],
        config: PipelineConfig,
        metrics: PipelineMetrics,
    ) -> Dict[str, Any]:
        """执行管道各阶段"""
        stages = []
        context = context or {}
        execution_result = None

        # 0. 意图增强（通过 EvolutionIntentBridge）
        try:
            bridge = self.intent_bridge
            if bridge:
                enhanced_intent = bridge.process_intent(intent)
                context["enhanced_intent"] = enhanced_intent
                if hasattr(enhanced_intent, "context") and enhanced_intent.context:
                    context["evolution_insights"] = enhanced_intent.context.get("evolution_enhancement")
                logger.info("Intent → Evolution 联动成功")
        except Exception as e:
            logger.debug(f"Intent 联动跳过: {e}")

        # 1. 意图分类 + 推理
        if config.use_reasoning:
            stage_start = time.time()
            stage_config = self.optimizer.get_optimal_config(task_type, intent)
            stages.append(('reasoning', stage_config))
            metrics.record_stage(PipelineStage.REASONING, time.time() - stage_start, True)

        # 2. 执行（集成 ExecutionAgent）
        if config.use_execution:
            stage_start = time.time()
            try:
                agent = self.execution_agent
                report = agent.execute_code(
                    code=intent,
                    description=f"Pipeline execution for: {intent[:100]}",
                    timeout=int(config.timeout),
                )
                execution_result = {
                    "success": report.success,
                    "output": report.output,
                    "error": report.error,
                    "execution_time": report.execution_time,
                }
                stages.append(('execute', execution_result))
                metrics.record_stage(
                    PipelineStage.EXECUTE,
                    time.time() - stage_start,
                    report.success,
                )
            except Exception as e:
                execution_result = {"success": False, "error": str(e)}
                stages.append(('execute', execution_result))
                metrics.record_stage(PipelineStage.EXECUTE, time.time() - stage_start, False)
                logger.warning(f"ExecutionAgent 执行失败: {e}")

        # 3. 验证（基于执行结果的真实评分）
        if config.use_verification:
            stage_start = time.time()
            verify_result = self._verify_result(intent, execution_result)
            stages.append(('verify', verify_result))
            metrics.record_stage(PipelineStage.VERIFY, time.time() - stage_start, verify_result.get("passed", False))

        return {
            'stages': stages,
            'context': context,
        }

    def _verify_result(
        self,
        intent: str,
        execution_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        验证执行结果，返回评分

        验证维度：
        1. 执行是否成功
        2. 输出是否非空
        3. 是否包含错误
        4. 执行时间是否在合理范围内
        """
        if not execution_result:
            return {"passed": False, "score": 0.0, "reason": "无执行结果"}

        score = 0.0
        issues = []

        # 1. 执行成功 (+0.4)
        if execution_result.get("success"):
            score += 0.4
        else:
            issues.append(f"执行失败: {execution_result.get('error', 'unknown')[:100]}")

        # 2. 输出非空 (+0.3)
        output = execution_result.get("output", "")
        if output and output.strip():
            score += 0.3
            # 输出长度评分 (+0.1)
            if len(output.strip()) > 20:
                score += 0.1
        else:
            issues.append("输出为空")

        # 3. 无错误 (+0.1)
        error = execution_result.get("error", "")
        if not error:
            score += 0.1
        else:
            issues.append(f"包含错误: {error[:50]}")

        # 4. 执行时间合理 (+0.1)
        exec_time = execution_result.get("execution_time", 0)
        if exec_time > 0 and exec_time < 60:
            score += 0.1
        elif exec_time >= 60:
            issues.append(f"执行时间过长: {exec_time:.1f}s")

        return {
            "passed": score >= 0.6,
            "score": round(score, 2),
            "issues": issues,
            "execution_time": exec_time,
        }


# ── 工厂函数 ─────────────────────────────────────────────────────────────────


def create_pipeline_optimizer() -> PipelineOptimizer:
    """创建管道优化器"""
    return PipelineOptimizer()


def create_pipeline_executor(
    optimizer: Optional[PipelineOptimizer] = None,
) -> PipelineExecutor:
    """创建管道执行器"""
    return PipelineExecutor(optimizer)


# ── 测试入口 ─────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("=" * 50)
    print("Agent Pipeline 优化器测试")
    print("=" * 50)

    optimizer = create_pipeline_optimizer()
    executor = create_pipeline_executor(optimizer)

    # 测试任务分类
    test_intents = [
        "修复这个bug",
        "重构这个函数",
        "设计一个用户认证系统",
        "帮我写一个排序算法",
        "Python的装饰器是什么",
    ]

    print("\n[1] 任务分类测试")
    for intent in test_intents:
        task_type = optimizer.classify_task(intent)
        config = optimizer.get_optimal_config(task_type, intent)
        print(f"  '{intent}'")
        print(f"    → {task_type.name}")
        print(f"    → depth={config.max_depth}, timeout={config.timeout}s")
        print()

    # 测试管道执行
    print("\n[2] 管道执行测试")
    result = executor.execute("修复这个bug", context={'file': 'test.py'})
    print(f"  Success: {result['success']}")
    print(f"  Task Type: {result['task_type'].name}")
    print(f"  Duration: {result['metrics']['total_duration']:.3f}s")

    # 统计
    print("\n[3] 优化统计")
    stats = optimizer.get_statistics()
    print(f"  Total Tasks: {stats['total_tasks']}")
    print(f"  Avg Duration: {stats.get('avg_duration', 0):.3f}s")

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
