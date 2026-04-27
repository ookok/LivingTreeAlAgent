# -*- coding: utf-8 -*-
"""
专家指导学习系统
Expert-Guided Learning System

三层学习架构：
1. 快速缓存层 → 高频问题直接复用
2. 模型蒸馏层 → 学习专家推理模式
3. 知识图谱层 → 结构化存储专家知识

增强模块（2026-04-24）：
1. 完全离线的自学习循环 - 永不掉线
2. 多模型知识一致性验证 - 质量保障
3. 自动模型选择策略 - 智能选模
4. 成本优化引擎 - 节省成本
5. 多模型对比系统 - 并行推理
6. 增强性能监控 - 实时监控
"""

from .expert_guided_system import (
    # 枚举
    LearningPhase,
    CorrectionLevel,
    # 数据结构
    LearningRecord,
    ExpertGuidedResult,
    # 核心类
    ExpertGuidedLearningSystem,
    HermesAgentWithExpertLearning,
    ResponseComparator,
    # 工厂函数
    create_expert_learning_system,
)

# 新增模块导出
try:
    from .offline_learning_loop import (
        OfflineLearningLoop,
        get_offline_learning_loop,
        ConnectionStatus,
        OfflineResponse,
        KnowledgeFragment,
    )
except ImportError:
    pass

try:
    from .knowledge_consistency import (
        KnowledgeConsistencyVerifier,
        ConsensusLevel,
        VerificationStatus,
        ConsistencyResult,
    )
except ImportError:
    pass

try:
    from .auto_model_selector import (
        AutoModelSelector,
        TaskType,
        TaskComplexity,
        ModelCapability,
        ModelRecommendation,
    )
except ImportError:
    pass

try:
    from .cost_optimizer import (
        CostOptimizer,
        CostMode,
        BudgetStatus,
    )
except ImportError:
    pass

try:
    from .multi_model_comparison import (
        MultiModelComparison,
        ComparisonMetric,
        ModelOutput,
        ComparisonResult,
    )
except ImportError:
    pass

try:
    from .enhanced_performance_monitor import (
        EnhancedPerformanceMonitor,
        MetricType,
        ModelPerformance,
        PerformanceReport,
    )
except ImportError:
    pass

try:
    from .intelligent_learning_system import (
        IntelligentLearningSystem,
        get_intelligent_learning_system,
        LearningResult,
        SystemStatus,
    )
except ImportError:
    pass

__all__ = [
    # 枚举
    "LearningPhase",
    "CorrectionLevel",
    # 数据结构
    "LearningRecord",
    "ExpertGuidedResult",
    # 核心类
    "ExpertGuidedLearningSystem",
    "HermesAgentWithExpertLearning",
    "ResponseComparator",
    # 工厂函数
    "create_expert_learning_system",
    # 离线学习
    "OfflineLearningLoop",
    "get_offline_learning_loop",
    "ConnectionStatus",
    # 知识一致性
    "KnowledgeConsistencyVerifier",
    "ConsensusLevel",
    # 模型选择
    "AutoModelSelector",
    "TaskType",
    # 成本优化
    "CostOptimizer",
    "CostMode",
    # 多模型对比
    "MultiModelComparison",
    # 性能监控
    "EnhancedPerformanceMonitor",
    "MetricType",
    # 统一入口
    "IntelligentLearningSystem",
    "get_intelligent_learning_system",
]
