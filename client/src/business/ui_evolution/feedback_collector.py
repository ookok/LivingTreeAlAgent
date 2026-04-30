# -*- coding: utf-8 -*-
"""
用户反馈收集器 (User Feedback Collector)
=======================================

收集和管理用户对预测建议的反馈，用于持续学习。

核心功能:
- 记录用户接受/拒绝预测
- 记录纠正操作
- 统计预测准确率
- 生成训练数据

复用: intelligent_hints/HintMemory 的持久化机制

Author: LivingTreeAI Team
Date: 2026-04-24
"""

from business.logger import get_logger
logger = get_logger('ui_evolution.feedback_collector')

import json
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, Counter
from enum import Enum


# =============================================================================
# 数据模型
# =============================================================================

class FeedbackType(Enum):
    """反馈类型"""
    ACCEPTED = "accepted"           # 接受建议
    REJECTED = "rejected"          # 拒绝建议
    CORRECTED = "corrected"         # 纠正建议
    DISMISSED = "dismissed"        # 忽略建议
    IGNORED = "ignored"            # 未查看


class ConfidenceLevel(Enum):
    """置信度等级"""
    VERY_LOW = 0.3
    LOW = 0.5
    MEDIUM = 0.7
    HIGH = 0.85
    VERY_HIGH = 0.95


@dataclass
class FeedbackRecord:
    """反馈记录"""
    id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 预测信息
    predicted_action: str = ""
    prediction_source: str = ""    # tfidf, pattern, fallback
    prediction_confidence: float = 0.0
    
    # 反馈信息
    feedback_type: FeedbackType = FeedbackType.IGNORED
    actual_action: str = ""         # 用户实际执行的操作
    corrected_action: str = ""     # 纠正后的操作
    
    # 上下文
    context_features: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    user_id: str = "default"
    
    # 元数据
    response_time_ms: int = 0     # 预测到反馈的响应时间
    is_positive: bool = False      # 是否是正向反馈


@dataclass
class FeedbackStats:
    """反馈统计"""
    total_predictions: int = 0
    accepted: int = 0
    rejected: int = 0
    corrected: int = 0
    ignored: int = 0
    
    # 置信度分布 {"level": {"total": int, "success": int}}
    confidence_buckets: Dict[str, Dict[str, int]] = field(default_factory=lambda: {
        "low": {"total": 0, "success": 0},
        "medium": {"total": 0, "success": 0},
        "high": {"total": 0, "success": 0},
    })
    
    # 按来源统计 {"source": {"total": int, "success": int}}
    source_stats: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"total": 0, "success": 0}))
    
    @property
    def acceptance_rate(self) -> float:
        if self.total_predictions == 0:
            return 0.0
        return (self.accepted + self.corrected) / self.total_predictions
    
    @property
    def accuracy_by_confidence(self) -> Dict[str, float]:
        """按置信度分级的准确率"""
        result = {}
        for level in ["low", "medium", "high"]:
            bucket = self.confidence_buckets.get(level, {"total": 0, "success": 0})
            total = bucket.get("total", 0)
            success = bucket.get("success", 0)
            result[level] = success / total if total > 0 else 0.0
        return result


# =============================================================================
# 反馈收集器
# =============================================================================

class FeedbackCollector:
    """
    用户反馈收集器
    
    功能:
    1. 记录预测反馈
    2. 计算准确率统计
    3. 生成训练数据
    4. 识别低效模式
    """
    
    def __init__(self, storage_path: str = None):
        if storage_path is None:
            storage_path = Path.home() / ".hermes-desktop" / "ui_feedback.json"
        
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 内存存储
        self._records: List[FeedbackRecord] = []
        self._current_prediction: Optional[Dict[str, Any]] = None
        
        # 统计
        self._stats = FeedbackStats()
        
        # 锁
        self._lock = threading.Lock()
        
        # 加载持久化数据
        self._load()
    
    def _load(self):
        """加载持久化数据"""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 恢复记录
            for record_data in data.get("records", []):
                record = FeedbackRecord(
                    timestamp=datetime.fromisoformat(record_data["timestamp"]),
                    predicted_action=record_data["predicted_action"],
                    prediction_source=record_data.get("prediction_source", ""),
                    prediction_confidence=record_data.get("prediction_confidence", 0.0),
                    feedback_type=FeedbackType(record_data["feedback_type"]),
                    actual_action=record_data.get("actual_action", ""),
                    corrected_action=record_data.get("corrected_action", ""),
                    context_features=record_data.get("context_features", {}),
                    session_id=record_data.get("session_id", ""),
                    user_id=record_data.get("user_id", "default"),
                    response_time_ms=record_data.get("response_time_ms", 0),
                    is_positive=record_data.get("is_positive", False),
                )
                self._records.append(record)
            
            # 重建统计
            self._rebuild_stats()
            
        except Exception as e:
            logger.info(f"加载反馈数据失败: {e}")
    
    def _save(self):
        """保存到持久化"""
        try:
            data = {
                "records": [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "predicted_action": r.predicted_action,
                        "prediction_source": r.prediction_source,
                        "prediction_confidence": r.prediction_confidence,
                        "feedback_type": r.feedback_type.value,
                        "actual_action": r.actual_action,
                        "corrected_action": r.corrected_action,
                        "context_features": r.context_features,
                        "session_id": r.session_id,
                        "user_id": r.user_id,
                        "response_time_ms": r.response_time_ms,
                        "is_positive": r.is_positive,
                    }
                    for r in self._records[-1000:]  # 只保留最近1000条
                ],
                "last_updated": datetime.now().isoformat(),
            }
            
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.info(f"保存反馈数据失败: {e}")
    
    def record_prediction(
        self,
        predicted_action: str,
        confidence: float,
        source: str = "unknown",
        context: Dict[str, Any] = None,
        session_id: str = None,
    ):
        """记录一次预测"""
        with self._lock:
            self._current_prediction = {
                "predicted_action": predicted_action,
                "confidence": confidence,
                "source": source,
                "context": context or {},
                "session_id": session_id or "",
                "timestamp": datetime.now(),
            }
    
    def record_feedback(
        self,
        feedback_type: FeedbackType,
        actual_action: str = "",
        corrected_action: str = "",
        context: Dict[str, Any] = None,
    ):
        """
        记录用户反馈
        
        Args:
            feedback_type: 反馈类型
            actual_action: 用户实际执行的操作
            corrected_action: 纠正后的操作
            context: 额外上下文
        """
        with self._lock:
            if not self._current_prediction:
                return
            
            # 计算响应时间
            response_time = int(
                (datetime.now() - self._current_prediction["timestamp"]).total_seconds() * 1000
            )
            
            # 判断是否正向
            is_positive = feedback_type in [FeedbackType.ACCEPTED, FeedbackType.CORRECTED]
            
            # 创建记录
            record = FeedbackRecord(
                timestamp=datetime.now(),
                predicted_action=self._current_prediction["predicted_action"],
                prediction_source=self._current_prediction["source"],
                prediction_confidence=self._current_prediction["confidence"],
                feedback_type=feedback_type,
                actual_action=actual_action,
                corrected_action=corrected_action,
                context_features=context or self._current_prediction.get("context", {}),
                session_id=self._current_prediction["session_id"],
                response_time_ms=response_time,
                is_positive=is_positive,
            )
            
            self._records.append(record)
            
            # 更新统计
            self._update_stats(record)
            
            # 持久化
            self._save()
            
            # 清除当前预测
            self._current_prediction = None
            
            return record
    
    def _update_stats(self, record: FeedbackRecord):
        """更新统计"""
        self._stats.total_predictions += 1
        
        # 按类型统计
        if record.feedback_type == FeedbackType.ACCEPTED:
            self._stats.accepted += 1
        elif record.feedback_type == FeedbackType.REJECTED:
            self._stats.rejected += 1
        elif record.feedback_type == FeedbackType.CORRECTED:
            self._stats.corrected += 1
        elif record.feedback_type == FeedbackType.IGNORED:
            self._stats.ignored += 1
        
        # 按置信度统计
        conf_level = self._get_confidence_level(record.prediction_confidence)
        if conf_level not in self._stats.confidence_buckets:
            self._stats.confidence_buckets[conf_level] = {"total": 0, "success": 0}
        self._stats.confidence_buckets[conf_level]["total"] += 1
        if record.is_positive:
            self._stats.confidence_buckets[conf_level]["success"] += 1
        
        # 按来源统计
        source = record.prediction_source
        if source not in self._stats.source_stats:
            self._stats.source_stats[source] = {"total": 0, "success": 0}
        self._stats.source_stats[source]["total"] += 1
        if record.is_positive:
            self._stats.source_stats[source]["success"] += 1
    
    def _rebuild_stats(self):
        """重建统计"""
        self._stats = FeedbackStats()
        for record in self._records:
            self._update_stats(record)
    
    def _get_confidence_level(self, confidence: float) -> str:
        """获取置信度等级"""
        if confidence < 0.4:
            return "low"
        elif confidence < 0.7:
            return "medium"
        else:
            return "high"
    
    def get_stats(self) -> FeedbackStats:
        """获取统计信息"""
        with self._lock:
            return FeedbackStats(
                total_predictions=self._stats.total_predictions,
                accepted=self._stats.accepted,
                rejected=self._stats.rejected,
                corrected=self._stats.corrected,
                ignored=self._stats.ignored,
                confidence_buckets=dict(self._stats.confidence_buckets),
                source_stats={k: dict(v) for k, v in self._stats.source_stats.items()},
            )
    
    def get_training_data(
        self,
        min_samples: int = 10,
        positive_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        获取训练数据
        
        用于训练/更新预测模型
        """
        with self._lock:
            records = [
                r for r in self._records
                if r.feedback_type != FeedbackType.IGNORED
            ]
            
            if positive_only:
                records = [r for r in records if r.is_positive]
            
            if len(records) < min_samples:
                return []
            
            # 转换为训练格式
            training_data = []
            for i in range(len(records) - 1):
                current = records[i]
                next_record = records[i + 1]
                
                training_data.append({
                    "sequence": [current.predicted_action],
                    "next_action": next_record.actual_action or next_record.predicted_action,
                    "success": current.is_positive,
                    "confidence": current.prediction_confidence,
                    "source": current.prediction_source,
                })
            
            return training_data
    
    def get_poor_performing_patterns(
        self,
        threshold: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """识别表现差的模式"""
        with self._lock:
            pattern_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "success": 0})
            
            for record in self._records:
                pattern = f"{record.prediction_source}:{record.predicted_action}"
                pattern_stats[pattern]["total"] += 1
                if record.is_positive:
                    pattern_stats[pattern]["success"] += 1
            
            # 找出低性能模式
            poor_patterns = []
            for pattern, stats in pattern_stats.items():
                if stats["total"] >= 5:  # 至少5次样本
                    accuracy = stats["success"] / stats["total"]
                    if accuracy < threshold:
                        poor_patterns.append({
                            "pattern": pattern,
                            "accuracy": accuracy,
                            "samples": stats["total"],
                        })
            
            return sorted(poor_patterns, key=lambda x: x["accuracy"])
    
    def accept(self, actual_action: str = ""):
        """快捷方法：接受建议"""
        return self.record_feedback(
            FeedbackType.ACCEPTED,
            actual_action=actual_action,
        )
    
    def reject(self, actual_action: str = ""):
        """快捷方法：拒绝建议"""
        return self.record_feedback(
            FeedbackType.REJECTED,
            actual_action=actual_action,
        )
    
    def correct(self, corrected_action: str):
        """快捷方法：纠正建议"""
        return self.record_feedback(
            FeedbackType.CORRECTED,
            corrected_action=corrected_action,
        )
    
    def dismiss(self):
        """快捷方法：忽略建议"""
        return self.record_feedback(FeedbackType.DISMISSED)


# =============================================================================
# 全局实例
# =============================================================================

_instance: Optional[FeedbackCollector] = None
_instance_lock = threading.Lock()


def get_feedback_collector() -> FeedbackCollector:
    """获取全局反馈收集器实例"""
    global _instance
    
    with _instance_lock:
        if _instance is None:
            _instance = FeedbackCollector()
        return _instance


# =============================================================================
# 便捷函数
# =============================================================================

def record_prediction_feedback(
    predicted_action: str,
    confidence: float,
    feedback: str,  # "accept", "reject", "correct", "dismiss", "ignore"
    corrected_action: str = "",
    actual_action: str = "",
):
    """
    快速记录反馈
    
    使用示例:
    ```python
    from business.ui_evolution import record_prediction_feedback

    
    # 预测
    record_prediction_feedback(
        predicted_action="click:send",
        confidence=0.85,
        feedback="accept"
    )
    
    # 纠正
    record_prediction_feedback(
        predicted_action="click:send",
        confidence=0.7,
        feedback="correct",
        corrected_action="click:cancel"
    )
    ```
    """
    collector = get_feedback_collector()
    
    feedback_map = {
        "accept": FeedbackType.ACCEPTED,
        "reject": FeedbackType.REJECTED,
        "correct": FeedbackType.CORRECTED,
        "dismiss": FeedbackType.DISMISSED,
        "ignore": FeedbackType.IGNORED,
    }
    
    feedback_type = feedback_map.get(feedback.lower(), FeedbackType.IGNORED)
    
    collector.record_prediction(predicted_action, confidence)
    collector.record_feedback(
        feedback_type,
        actual_action=actual_action,
        corrected_action=corrected_action,
    )


def get_feedback_stats() -> Dict[str, Any]:
    """获取反馈统计"""
    collector = get_feedback_collector()
    stats = collector.get_stats()
    return {
        "total": stats.total_predictions,
        "accepted": stats.accepted,
        "rejected": stats.rejected,
        "corrected": stats.corrected,
        "ignored": stats.ignored,
        "acceptance_rate": f"{stats.acceptance_rate:.1%}",
    }
