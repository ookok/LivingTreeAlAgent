"""
动态学习与优化 (Credit Learning)
=================================

系统运行一段时间后，发现实际数据与"预测值"有偏差时，引入学习反馈环：
- 调整插件的性能画像
- 优化调度策略
- 预测用户满意度

核心机制：
1. 记录每次任务的实际表现
2. 指数加权移动平均更新预测
3. 检测异常并触发重校准
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from threading import RLock
import time
import math

from .credit_registry import CreditRegistry, PluginCreditProfile


@dataclass
class PerformanceRecord:
    """
    性能记录

    每次任务完成后记录的实际数据。
    """
    record_id: str
    plugin_id: str
    task_id: str
    task_type: str                       # 任务类型

    # 时间预测
    predicted_time_sec: float            # 预测耗时
    actual_time_sec: float               # 实际耗时

    # 成本预测
    predicted_credits: float             # 预测积分消耗
    actual_credits: float               # 实际积分消耗

    # 质量
    predicted_quality: int               # 预测质量
    actual_quality: int                  # 实际质量（用户评分1-5映射到0-100）

    # 用户反馈
    user_satisfaction: float = 0.0      # 用户满意度（1-5分）
    user_feedback: str = ""              # 用户反馈

    # 元数据
    timestamp: float = field(default_factory=time.time)
    execution_mode: str = "online"      # online / batch / test

    @property
    def time_error_ratio(self) -> float:
        """时间误差率（正值=比预测慢）"""
        if self.predicted_time_sec == 0:
            return 0
        return (self.actual_time_sec - self.predicted_time_sec) / self.predicted_time_sec

    @property
    def cost_error_ratio(self) -> float:
        """成本误差率"""
        if self.predicted_credits == 0:
            return 0
        return (self.actual_credits - self.predicted_credits) / self.predicted_credits

    @property
    def quality_error(self) -> float:
        """质量误差"""
        return self.predicted_quality - self.actual_quality


@dataclass
class LearningFeedback:
    """学习反馈"""
    plugin_id: str
    updated_fields: Dict[str, Any]       # 更新的字段
    adjustment_reason: str               # 调整原因
    confidence: float                    # 置信度（0-1）
    timestamp: float = field(default_factory=time.time)


@dataclass
class LearningMetrics:
    """学习指标"""
    plugin_id: str
    sample_count: int = 0                # 样本数量
    avg_time_error: float = 0.0          # 平均时间误差
    avg_cost_error: float = 0.0         # 平均成本误差
    avg_satisfaction: float = 0.0       # 平均满意度
    prediction_accuracy: float = 0.0     # 预测准确度
    confidence: float = 0.0             # 置信度


class CreditLearning:
    """
    动态学习引擎

    核心职责：
    1. 收集任务执行反馈
    2. 更新插件性能画像
    3. 优化调度策略
    4. 预测用户满意度
    """

    _instance = None
    _lock = RLock()

    # 学习参数
    EWMA_ALPHA = 0.1                     # 指数加权移动平均系数
    MIN_SAMPLES = 5                       # 最小样本数
    ANOMALY_THRESHOLD = 0.5              # 异常检测阈值（50%误差）

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.registry = CreditRegistry.get_instance()

        # 性能记录
        self._records: Dict[str, List[PerformanceRecord]] = {}  # plugin_id -> records

        # 更新历史
        self._feedback_history: List[LearningFeedback] = []

        # 观察者
        self._observers: Dict[str, List[Callable]] = {}

    @classmethod
    def get_instance(cls) -> 'CreditLearning':
        return cls()

    # ==================== 记录与学习 ====================

    def record(
        self,
        plugin_id: str,
        task_id: str,
        task_type: str,
        predicted_time: float,
        actual_time: float,
        predicted_credits: float,
        actual_credits: float,
        predicted_quality: int,
        actual_quality: int,
        user_satisfaction: float = 0.0,
        user_feedback: str = ""
    ) -> Optional[LearningFeedback]:
        """
        记录任务执行结果并触发学习

        Args:
            plugin_id: 插件ID
            task_id: 任务ID
            task_type: 任务类型
            predicted_time: 预测耗时
            actual_time: 实际耗时
            predicted_credits: 预测积分
            actual_credits: 实际积分
            predicted_quality: 预测质量
            actual_quality: 实际质量
            user_satisfaction: 用户满意度（1-5）
            user_feedback: 用户反馈

        Returns:
            学习反馈（如果有重大调整）
        """
        with self._lock:
            # 创建记录
            record = PerformanceRecord(
                record_id=f"{plugin_id}_{task_id}_{int(time.time())}",
                plugin_id=plugin_id,
                task_id=task_id,
                task_type=task_type,
                predicted_time_sec=predicted_time,
                actual_time_sec=actual_time,
                predicted_credits=predicted_credits,
                actual_credits=actual_credits,
                predicted_quality=predicted_quality,
                actual_quality=actual_quality,
                user_satisfaction=user_satisfaction,
                user_feedback=user_feedback,
            )

            # 保存记录
            if plugin_id not in self._records:
                self._records[plugin_id] = []
            self._records[plugin_id].append(record)

            # 保留最近100条
            if len(self._records[plugin_id]) > 100:
                self._records[plugin_id] = self._records[plugin_id][-100:]

            # 检查是否需要更新
            feedback = self._maybe_update_plugin(record)

            # 通知观察者
            self._notify_observers("record_added", record)

            return feedback

    def _maybe_update_plugin(
        self,
        record: PerformanceRecord
    ) -> Optional[LearningFeedback]:
        """
        检查是否需要更新插件配置

        当误差超过阈值时，进行调整。
        """
        records = self._records.get(record.plugin_id, [])
        if len(records) < self.MIN_SAMPLES:
            return None

        # 计算近期误差
        recent = records[-self.MIN_SAMPLES:]
        avg_time_error = sum(r.time_error_ratio for r in recent) / len(recent)
        avg_cost_error = sum(r.cost_error_ratio for r in recent) / len(recent)

        # 检测异常
        adjustments = []

        # 时间预测偏差大
        if abs(avg_time_error) > self.ANOMALY_THRESHOLD:
            adjustments.append(("avg_time_sec_per_kchar", avg_time_error))

        # 成本预测偏差大
        if abs(avg_cost_error) > self.ANOMALY_THRESHOLD:
            adjustments.append(("cost_model", avg_cost_error))

        if not adjustments:
            return None

        # 执行更新
        plugin = self.registry.get_plugin(record.plugin_id)
        if not plugin:
            return None

        updated_fields = {}

        for field_name, error_ratio in adjustments:
            if field_name == "avg_time_sec_per_kchar":
                # 调整处理速度
                old_speed = plugin.capability.avg_time_sec_per_kchar
                # 如果实际比预测慢，说明预估速度太乐观，需要增大系数
                correction_factor = 1 + error_ratio
                new_speed = old_speed * correction_factor
                new_speed = max(0.1, min(new_speed, 1000))  # 限制范围
                plugin.capability.avg_time_sec_per_kchar = new_speed
                updated_fields["avg_time_sec_per_kchar"] = {
                    "old": old_speed,
                    "new": new_speed,
                    "correction_factor": correction_factor
                }

            elif field_name == "cost_model":
                # 调整积分模型
                if plugin.credit_model.per_kchar > 0:
                    old_cost = plugin.credit_model.per_kchar
                    new_cost = old_cost * (1 + error_ratio)
                    new_cost = max(0, min(new_cost, 100000))
                    plugin.credit_model.per_kchar = new_cost
                    updated_fields["per_kchar"] = {
                        "old": old_cost,
                        "new": new_cost,
                    }

        if updated_fields:
            feedback = LearningFeedback(
                plugin_id=record.plugin_id,
                updated_fields=updated_fields,
                adjustment_reason=f"检测到预测误差: 时间{avg_time_error*100:.1f}%, 成本{avg_cost_error*100:.1f}%",
                confidence=self._calculate_confidence(len(recent)),
            )
            self._feedback_history.append(feedback)
            self._notify_observers("plugin_updated", feedback)
            return feedback

        return None

    def _calculate_confidence(self, sample_count: int) -> float:
        """计算置信度"""
        # 样本越多置信度越高
        return min(1.0, sample_count / 20)

    # ==================== 预测 ====================

    def predict_satisfaction(
        self,
        plugin_id: str,
        quality_score: int,
        wait_time_sec: float,
        credit_cost: float
    ) -> float:
        """
        预测用户满意度

        基于插件历史表现和任务参数预测。

        Args:
            plugin_id: 插件ID
            quality_score: 质量分数
            wait_time_sec: 等待时间
            credit_cost: 积分消耗

        Returns:
            预测满意度（1-5）
        """
        # 基础分
        base_score = 3.0

        # 质量贡献（质量分数到满意度的映射）
        quality_contribution = (quality_score - 50) / 50 * 1.0  # 50分=0, 100分=+1, 0分=-1

        # 时间惩罚（等待越长越不满意）
        time_penalty = -min(wait_time_sec / 60, 1.0) * 0.5  # 超过1分钟开始扣分

        # 成本惩罚（积分消耗相对于用户承受力）
        # 假设用户平均预算1000积分
        cost_penalty = -(credit_cost / 1000) * 0.3

        # 插件历史满意度加成
        history_bonus = self._get_historical_satisfaction_bonus(plugin_id)

        total = base_score + quality_contribution + time_penalty + cost_penalty + history_bonus
        return max(1.0, min(5.0, total))

    def _get_historical_satisfaction_bonus(self, plugin_id: str) -> float:
        """获取历史满意度加成"""
        records = self._records.get(plugin_id, [])
        if not records:
            return 0.0

        recent = records[-10:]
        avg_satisfaction = sum(r.user_satisfaction for r in recent) / len(recent)

        # 转换为加成：4.5分=0, 5分=+0.5, 3分=-0.5
        return (avg_satisfaction - 4.0) * 0.3

    def predict_execution_time(
        self,
        plugin_id: str,
        input_length: int
    ) -> float:
        """
        预测执行时间

        Args:
            plugin_id: 插件ID
            input_length: 输入长度

        Returns:
            预测时间（秒）
        """
        plugin = self.registry.get_plugin(plugin_id)
        if not plugin:
            return 60.0  # 默认60秒

        base_time = (input_length / 1000) * plugin.capability.avg_time_sec_per_kchar

        # 根据历史误差调整
        records = self._records.get(plugin_id, [])
        if len(records) >= 3:
            recent = records[-5:]
            avg_error = sum(r.time_error_ratio for r in recent) / len(recent)
            base_time *= (1 + avg_error)

        return base_time

    # ==================== 指标 ====================

    def get_metrics(self, plugin_id: str) -> LearningMetrics:
        """获取插件学习指标"""
        records = self._records.get(plugin_id, [])

        if not records:
            return LearningMetrics(plugin_id=plugin_id)

        recent = records[-20:]  # 最近的20条

        avg_time_error = sum(r.time_error_ratio for r in recent) / len(recent)
        avg_cost_error = sum(r.cost_error_ratio for r in recent) / len(recent)
        avg_satisfaction = sum(r.user_satisfaction for r in recent) / len(recent) if recent else 0

        # 预测准确度 = 1 - 平均绝对误差
        time_accuracy = max(0, 1 - abs(avg_time_error))
        cost_accuracy = max(0, 1 - abs(avg_cost_error))
        prediction_accuracy = (time_accuracy + cost_accuracy) / 2

        return LearningMetrics(
            plugin_id=plugin_id,
            sample_count=len(records),
            avg_time_error=avg_time_error,
            avg_cost_error=avg_cost_error,
            avg_satisfaction=avg_satisfaction,
            prediction_accuracy=prediction_accuracy,
            confidence=self._calculate_confidence(len(recent))
        )

    def get_all_metrics(self) -> Dict[str, LearningMetrics]:
        """获取所有插件的学习指标"""
        return {pid: self.get_metrics(pid) for pid in self._records.keys()}

    # ==================== 建议 ====================

    def suggest_optimization(self, plugin_id: str) -> List[str]:
        """
        提供优化建议

        根据学习分析，提供改进建议。
        """
        suggestions = []
        metrics = self.get_metrics(plugin_id)

        if metrics.sample_count < self.MIN_SAMPLES:
            suggestions.append("样本量不足，建议继续收集数据")
            return suggestions

        # 时间预测问题
        if abs(metrics.avg_time_error) > 0.2:
            if metrics.avg_time_error > 0:
                suggestions.append(f"预测时间偏乐观，实际耗时多{metrics.avg_time_error*100:.0f}%，建议提高预估系数")
            else:
                suggestions.append(f"预测时间偏悲观，实际耗时少{abs(metrics.avg_time_error)*100:.0f}%，可以降低预估加快调度")

        # 成本预测问题
        if abs(metrics.avg_cost_error) > 0.2:
            if metrics.avg_cost_error > 0:
                suggestions.append(f"预测成本偏低，实际消耗多{metrics.avg_cost_error*100:.0f}%，建议调高积分模型")
            else:
                suggestions.append(f"预测成本偏高，实际消耗少{abs(metrics.avg_cost_error)*100:.0f}%，可以降低积分消耗吸引更多使用")

        # 满意度问题
        if metrics.avg_satisfaction < 3.5:
            suggestions.append(f"用户满意度偏低({metrics.avg_satisfaction:.1f}/5)，建议检查输出质量或响应时间")

        # 准确度问题
        if metrics.prediction_accuracy < 0.7:
            suggestions.append(f"预测准确度较低({metrics.prediction_accuracy:.0%})，建议收集更多样本或调整模型")

        if not suggestions:
            suggestions.append("各项指标正常，无需特殊优化")

        return suggestions

    # ==================== 批量学习 ====================

    def batch_learn(self, records: List[Dict]) -> List[LearningFeedback]:
        """
        批量学习

        用于离线批量处理历史数据。
        """
        feedbacks = []
        for r in records:
            feedback = self.record(
                plugin_id=r["plugin_id"],
                task_id=r["task_id"],
                task_type=r["task_type"],
                predicted_time=r["predicted_time"],
                actual_time=r["actual_time"],
                predicted_credits=r["predicted_credits"],
                actual_credits=r["actual_credits"],
                predicted_quality=r["predicted_quality"],
                actual_quality=r["actual_quality"],
                user_satisfaction=r.get("user_satisfaction", 0),
                user_feedback=r.get("user_feedback", ""),
            )
            if feedback:
                feedbacks.append(feedback)
        return feedbacks

    # ==================== 观察者 ====================

    def add_observer(self, event_type: str, callback: Callable) -> None:
        """添加观察者"""
        if event_type not in self._observers:
            self._observers[event_type] = []
        self._observers[event_type].append(callback)

    def _notify_observers(self, event_type: str, data: Any) -> None:
        """通知观察者"""
        for callback in self._observers.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Learning observer error: {e}")

    # ==================== 历史 ====================

    def get_feedback_history(self, limit: int = 20) -> List[LearningFeedback]:
        """获取更新历史"""
        return self._feedback_history[-limit:]


def get_learning() -> CreditLearning:
    """获取学习引擎单例"""
    return CreditLearning.get_instance()
