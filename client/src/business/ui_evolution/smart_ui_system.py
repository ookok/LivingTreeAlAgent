# -*- coding: utf-8 -*-
"""
智能 UI 预测系统 (Smart UI Prediction System)
============================================

统一入口，组合所有组件，提供端到端的 UI 智能预测服务。

核心功能:
- 操作序列预测 (<1ms)
- 置信度路由
- 用户反馈收集
- 自动进化

Author: LivingTreeAI Team
Date: 2026-04-24
"""

from core.logger import get_logger
logger = get_logger('ui_evolution.smart_ui_system')

import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .operation_sequence import (
    OperationSequenceDB,
    OperationRecord,
    record_action,
    get_operation_db,
)
from .tfidf_predictor import (
    TFIDFPredictor,
    PredictionResult,
    predict_next,
    quick_predict,
    get_predictor,
)
from .feedback_collector import (
    FeedbackCollector,
    FeedbackType,
    record_prediction_feedback,
    get_feedback_collector,
    get_feedback_stats,
)
from .evolution_scheduler import (
    EvolutionScheduler,
    EvolutionLevel,
    trigger_learning,
    get_evolution_status,
    get_evolution_scheduler,
)


# =============================================================================
# 建议数据结构
# =============================================================================

@dataclass
class Suggestion:
    """智能建议"""
    action: str                   # 建议的操作
    confidence: float             # 置信度
    source: str = "local"        # 来源: local, rag, llm
    reason: str = ""             # 原因
    alternatives: List[Tuple[str, float]] = field(default_factory=list)
    
    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.7
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "source": self.source,
            "reason": self.reason,
            "alternatives": [
                {"action": a, "confidence": c}
                for a, c in self.alternatives
            ],
        }


@dataclass
class ProcessingResult:
    """处理结果"""
    suggestion: Suggestion
    prediction_time_ms: float
    sequence: List[str]
    knowledge_used: bool
    evolution_triggered: bool


# =============================================================================
# 智能 UI 系统
# =============================================================================

class SmartUISystem:
    """
    智能 UI 预测系统
    
    工作流程:
    1. 记录用户操作 → 操作序列数据库
    2. 预测下一步 → TF-IDF 预测器
    3. 置信度路由 → 高置信度直接返回，低置信度检索知识库
    4. 返回建议 → 记录预测
    5. 收集反馈 → 反馈收集器
    6. 触发进化 → 进化调度器
    """
    
    # 置信度阈值
    HIGH_CONFIDENCE = 0.7
    MEDIUM_CONFIDENCE = 0.5
    
    def __init__(
        self,
        model_save_path: str = None,
        enable_evolution: bool = True,
    ):
        # 组件初始化
        self.operation_db = get_operation_db()
        self.predictor = get_predictor(model_save_path)
        self.feedback_collector = get_feedback_collector()
        
        # 进化调度器
        self.enable_evolution = enable_evolution
        if enable_evolution:
            self.evolution_scheduler = get_evolution_scheduler()
        else:
            self.evolution_scheduler = None
        
        # 锁
        self._lock = threading.Lock()
    
    def process_operation(
        self,
        action_type: str,
        action_target: str,
        action_value: str = "",
        context: Dict[str, Any] = None,
        session_id: str = None,
    ) -> ProcessingResult:
        """
        处理用户操作，返回智能建议
        
        Args:
            action_type: 操作类型 (click, input, select, etc.)
            action_target: 操作目标 (button_id, field_name, etc.)
            action_value: 操作值
            context: 上下文信息
            session_id: 会话 ID
            
        Returns:
            ProcessingResult: 处理结果和建议
        """
        start_time = time.perf_counter()
        
        with self._lock:
            # 1. 记录操作
            operation = OperationRecord(
                action_type=action_type,
                action_target=action_target,
                action_value=action_value,
                context_features=context or {},
                session_id=session_id or "",
            )
            self.operation_db.record_operation(operation)
            
            # 2. 获取操作序列
            sequence = self.operation_db.get_operation_sequence(
                session_id=session_id,
                max_length=10,
            )
            
            # 3. 预测下一步
            prediction = self.predictor.predict(sequence)
            
            # 4. 构建建议
            suggestion = Suggestion(
                action=prediction.predicted_action,
                confidence=prediction.confidence,
                source=prediction.source,
                reason=prediction.reason,
                alternatives=prediction.alternatives,
            )
            
            # 5. 记录预测
            self.feedback_collector.record_prediction(
                predicted_action=suggestion.action,
                confidence=suggestion.confidence,
                source=suggestion.source,
                context=context,
                session_id=session_id,
            )
            
            # 6. 计算处理时间
            prediction_time = (time.perf_counter() - start_time) * 1000
            
            return ProcessingResult(
                suggestion=suggestion,
                prediction_time_ms=prediction_time,
                sequence=sequence,
                knowledge_used=False,
                evolution_triggered=False,
            )
    
    def record_feedback(
        self,
        feedback: str,  # "accept", "reject", "correct", "dismiss"
        actual_action: str = "",
        corrected_action: str = "",
    ):
        """
        记录用户反馈
        
        Args:
            feedback: 反馈类型
            actual_action: 用户实际执行的操作
            corrected_action: 纠正后的操作
        """
        with self._lock:
            # 1. 记录反馈
            record_prediction_feedback(
                predicted_action=self.feedback_collector._current_prediction["predicted_action"] if self.feedback_collector._current_prediction else "",
                confidence=self.feedback_collector._current_prediction["confidence"] if self.feedback_collector._current_prediction else 0.0,
                feedback=feedback,
                actual_action=actual_action,
                corrected_action=corrected_action,
            )
            
            # 2. 触发进化
            if self.enable_evolution and self.evolution_scheduler:
                success = feedback in ["accept", "correct"]
                
                # 获取当前序列
                sequence = self.operation_db.get_operation_sequence(max_length=5)
                
                # 触发即时学习
                self.evolution_scheduler.trigger_learning(
                    context=sequence[-1] if sequence else "",
                    action=corrected_action or actual_action,
                    sequence=sequence,
                    success=success,
                )
    
    def predict_and_suggest(self, session_id: str = None) -> Suggestion:
        """
        仅预测和建议，不记录操作
        
        用于轮询或定时预测场景。
        """
        with self._lock:
            sequence = self.operation_db.get_operation_sequence(
                session_id=session_id,
                max_length=10,
            )
            
            prediction = self.predictor.predict(sequence)
            
            return Suggestion(
                action=prediction.predicted_action,
                confidence=prediction.confidence,
                source=prediction.source,
                reason=prediction.reason,
                alternatives=prediction.alternatives,
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取系统统计"""
        return {
            "operation_db": self.operation_db.get_operation_stats(),
            "pattern_stats": self.operation_db.get_pattern_stats(),
            "feedback": get_feedback_stats(),
            "evolution": get_evolution_status(),
        }
    
    def train_model(
        self,
        save_path: str = None,
    ):
        """手动触发模型训练"""
        # 获取所有序列数据
        # 这里简化处理，实际应该从数据库批量获取
        training_data = self.feedback_collector.get_training_data(min_samples=10)
        
        if len(training_data) >= 10:
            sequences = [item["sequence"] for item in training_data]
            self.predictor.train(sequences, save_path=save_path)
            return True
        
        return False
    
    def close(self):
        """关闭系统，清理资源"""
        if self.evolution_scheduler:
            self.evolution_scheduler.stop()
        self.operation_db.close()


# =============================================================================
# 全局实例
# =============================================================================

_instance: Optional[SmartUISystem] = None
_instance_lock = threading.Lock()


def get_smart_ui_system() -> SmartUISystem:
    """获取全局智能 UI 系统实例"""
    global _instance
    
    with _instance_lock:
        if _instance is None:
            _instance = SmartUISystem()
        return _instance


# =============================================================================
# 便捷函数
# =============================================================================

def smart_predict(
    action_type: str,
    action_target: str,
    action_value: str = "",
    session_id: str = None,
) -> Suggestion:
    """
    快速预测和建议
    
    使用示例:
    ```python
    from client.src.business.ui_evolution import smart_predict

    
    # 用户点击了输入框
    suggestion = smart_predict("click", "input_field")
    
    if suggestion.is_confident:
        logger.info(f"建议: {suggestion.action}, 置信度: {suggestion.confidence:.0%}")
    ```
    """
    system = get_smart_ui_system()
    result = system.process_operation(
        action_type=action_type,
        action_target=action_target,
        action_value=action_value,
        session_id=session_id,
    )
    return result.suggestion


def record_ui_feedback(
    feedback: str,
    actual_action: str = "",
    corrected_action: str = "",
):
    """快速记录反馈"""
    system = get_smart_ui_system()
    system.record_feedback(feedback, actual_action, corrected_action)


def get_ui_evolution_stats() -> Dict[str, Any]:
    """获取 UI 进化统计"""
    system = get_smart_ui_system()
    return system.get_stats()
