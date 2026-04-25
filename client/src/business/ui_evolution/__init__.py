# -*- coding: utf-8 -*-
"""
智能 UI 进化系统 (Smart UI Evolution System)
==========================================

三层进化体系：
1. 前端微型预测器 (<1ms响应)
2. 本地知识库 (RAG引擎)
3. 大模型协调器 (复杂推理)

Author: LivingTreeAI Team
Date: 2026-04-24
"""

from .operation_sequence import (
    OperationSequenceDB,
    OperationRecord,
    SequencePattern,
    record_action,
    get_operation_db,
    get_recent_sequence,
    update_sequence_feedback,
)
from .tfidf_predictor import (
    TFIDFPredictor,
    PredictionResult,
    TrainedModel,
    predict_next,
    quick_predict,
    get_predictor,
)
from .feedback_collector import (
    FeedbackCollector,
    FeedbackRecord,
    FeedbackStats,
    FeedbackType,
    ConfidenceLevel,
    record_prediction_feedback,
    get_feedback_collector,
    get_feedback_stats,
)
from .evolution_scheduler import (
    EvolutionScheduler,
    EvolutionLevel,
    EvolutionTask,
    EvolutionStats,
    KnowledgeBase,
    trigger_learning,
    get_evolution_status,
    get_evolution_scheduler,
)
from .smart_ui_system import (
    SmartUISystem,
    Suggestion,
    ProcessingResult,
    get_smart_ui_system,
    smart_predict,
    record_ui_feedback,
    get_ui_evolution_stats,
)


__all__ = [
    # 操作序列数据库
    "OperationSequenceDB",
    "OperationRecord",
    "SequencePattern",
    "record_action",
    "get_operation_db",
    "get_recent_sequence",
    "update_sequence_feedback",
    
    # TF-IDF 预测器
    "TFIDFPredictor",
    "PredictionResult",
    "TrainedModel",
    "predict_next",
    "quick_predict",
    "get_predictor",
    
    # 反馈收集器
    "FeedbackCollector",
    "FeedbackRecord",
    "FeedbackStats",
    "FeedbackType",
    "ConfidenceLevel",
    "record_prediction_feedback",
    "get_feedback_collector",
    "get_feedback_stats",
    
    # 进化调度器
    "EvolutionScheduler",
    "EvolutionLevel",
    "EvolutionTask",
    "EvolutionStats",
    "KnowledgeBase",
    "trigger_learning",
    "get_evolution_status",
    "get_evolution_scheduler",
    
    # 智能 UI 系统
    "SmartUISystem",
    "Suggestion",
    "ProcessingResult",
    "get_smart_ui_system",
    "smart_predict",
    "record_ui_feedback",
    "get_ui_evolution_stats",
]
