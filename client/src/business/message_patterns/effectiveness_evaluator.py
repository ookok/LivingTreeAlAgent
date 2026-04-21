"""
效果评估器
Effectiveness Evaluator - 多维度评估、持续学习
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import threading

from .models import MessagePattern, PatternMetadata, PatternUsageRecord


@dataclass
class EvaluationMetrics:
    """评估指标"""
    # 质量维度
    accuracy: float = 0.0        # 准确性
    relevance: float = 0.0      # 相关性
    completeness: float = 0.0   # 完整性
    usefulness: float = 0.0      # 实用性
    creativity: float = 0.0     # 创造性

    # 效率维度
    response_time: float = 0.0   # 响应时间
    token_usage: float = 0.0    # Token使用量
    success_rate: float = 0.0   # 成功率

    # 用户体验
    satisfaction: float = 0.0   # 满意度
    clarity: float = 0.0        # 清晰度
    helpfulness: float = 0.0    # 有帮助程度

    # 综合评分
    overall: float = 0.0        # 综合评分

    def to_dict(self) -> Dict:
        return {
            "accuracy": self.accuracy,
            "relevance": self.relevance,
            "completeness": self.completeness,
            "usefulness": self.usefulness,
            "creativity": self.creativity,
            "response_time": self.response_time,
            "token_usage": self.token_usage,
            "success_rate": self.success_rate,
            "satisfaction": self.satisfaction,
            "clarity": self.clarity,
            "helpfulness": self.helpfulness,
            "overall": self.overall
        }

    def weighted_score(self, weights: Dict[str, float] = None) -> float:
        """计算加权分数"""
        if weights is None:
            weights = {
                "accuracy": 0.2,
                "relevance": 0.15,
                "completeness": 0.15,
                "usefulness": 0.15,
                "creativity": 0.1,
                "satisfaction": 0.15,
                "clarity": 0.1
            }

        total = 0.0
        weight_sum = 0.0
        for metric, weight in weights.items():
            if hasattr(self, metric):
                total += getattr(self, metric) * weight
                weight_sum += weight

        return total / weight_sum if weight_sum > 0 else 0.0


@dataclass
class EvaluationResult:
    """评估结果"""
    pattern_id: str
    pattern_name: str
    metrics: EvaluationMetrics
    timestamp: str
    sample_size: int = 0
    trend: str = "stable"  # improving, declining, stable
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "metrics": self.metrics.to_dict(),
            "timestamp": self.timestamp,
            "sample_size": self.sample_size,
            "trend": self.trend,
            "insights": self.insights,
            "recommendations": self.recommendations
        }


@dataclass
class UserFeedback:
    """用户反馈"""
    id: str = ""
    pattern_id: str = ""
    usage_record_id: str = ""
    rating: int = 0           # 1-5 评分
    helpful: bool = True
    accurate: bool = True
    relevant: bool = True
    feedback_text: str = ""
    improvement_suggestions: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "pattern_id": self.pattern_id,
            "usage_record_id": self.usage_record_id,
            "rating": self.rating,
            "helpful": self.helpful,
            "accurate": self.accurate,
            "relevant": self.relevant,
            "feedback_text": self.feedback_text,
            "improvement_suggestions": self.improvement_suggestions,
            "created_at": self.created_at
        }


class TextAnalyzer:
    """文本分析器"""

    # 质量指标模式
    QUALITY_PATTERNS = {
        "has_structure": [r'^#{1,6}\s', r'\n- ', r'\n\d+\.'],
        "has_examples": [r'例如', r'比如', r'案例', r'example'],
        "has_steps": [r'\d+\.\s', r'首先', r'然后', r'最后'],
        "is_comprehensive": [r'第一', r'第二', r'第三', r'此外', r'另外'],
        "has_conclusion": [r'总之', r'综上所述', r'因此', r'结论']
    }

    def analyze_quality(self, text: str) -> Dict[str, float]:
        """分析文本质量"""
        text_lower = text.lower()

        scores = {}
        for metric, patterns in self.QUALITY_PATTERNS.items():
            matches = sum(1 for p in patterns if re.search(p, text_lower, re.MULTILINE))
            scores[metric] = min(matches / 2, 1.0)

        return scores

    def calculate_readability(self, text: str) -> float:
        """计算可读性分数"""
        # 简单的可读性计算
        sentences = re.split(r'[.!?。！？]', text)
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)

        # 句子长度越短，可读性越高
        if avg_sentence_length < 15:
            return 0.9
        elif avg_sentence_length < 25:
            return 0.7
        elif avg_sentence_length < 40:
            return 0.5
        else:
            return 0.3

    def extract_keywords(self, text: str, top_n: int = 10) -> List[Tuple[str, float]]:
        """提取关键词"""
        # 简单的词频统计
        words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', text.lower())

        # 停用词
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}

        # 过滤停用词
        filtered_words = [w for w in words if w not in stopwords and len(w) > 1]

        # 词频统计
        word_freq = defaultdict(int)
        for word in filtered_words:
            word_freq[word] += 1

        # 排序
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

        # 计算TF分数
        max_freq = max(word_freq.values()) if word_freq else 1
        return [(w, f/max_freq) for w, f in sorted_words[:top_n]]


class EffectivenessEvaluator:
    """效果评估器"""

    def __init__(self):
        self._analyzer = TextAnalyzer()
        self._history: Dict[str, List[EvaluationResult]] = defaultdict(list)
        self._feedback: List[UserFeedback] = []
        self._lock = threading.Lock()

    def evaluate(
        self,
        pattern: MessagePattern,
        usage_records: List[PatternUsageRecord] = None,
        feedback_list: List[UserFeedback] = None
    ) -> EvaluationResult:
        """评估模式效果"""
        metrics = EvaluationMetrics()
        insights = []
        recommendations = []

        # 使用历史数据评估
        records = usage_records or []
        feedback = feedback_list or []

        # 基础指标计算
        if records:
            metrics.sample_size = len(records)

            # 成功率
            success_count = sum(1 for r in records if r.success)
            metrics.success_rate = success_count / len(records)

            # 平均响应时间
            if records:
                metrics.response_time = sum(r.response_time for r in records) / len(records)

            # 用户评分
            if feedback:
                metrics.satisfaction = sum(f.rating for f in feedback) / len(feedback) / 5.0

        # 从元数据获取历史表现
        if pattern.metadata.usage_count > 0:
            metrics.usefulness = pattern.metadata.effectiveness
            metrics.satisfaction = pattern.metadata.user_rating / 5.0 if pattern.metadata.user_rating > 0 else 0.5

        # 计算综合评分
        metrics.overall = metrics.weighted_score()

        # 生成洞察和建议
        insights, recommendations = self._generate_insights(pattern, metrics, feedback)

        # 计算趋势
        trend = self._calculate_trend(pattern.id)

        return EvaluationResult(
            pattern_id=pattern.id,
            pattern_name=pattern.name,
            metrics=metrics,
            timestamp=datetime.now().isoformat(),
            sample_size=len(records),
            trend=trend,
            insights=insights,
            recommendations=recommendations
        )

    def evaluate_output(
        self,
        pattern: MessagePattern,
        generated_output: str,
        user_input: str = "",
        expected_output: str = None
    ) -> EvaluationMetrics:
        """评估生成输出"""
        metrics = EvaluationMetrics()

        # 文本质量分析
        quality = self._analyzer.analyze_quality(generated_output)
        metrics.completeness = quality.get("has_structure", 0.5)
        metrics.accuracy = quality.get("has_examples", 0.7)

        # 可读性
        metrics.clarity = self._analyzer.calculate_readability(generated_output)

        # 相关性分析
        if user_input:
            metrics.relevance = self._calculate_relevance(user_input, generated_output)

        # 与预期对比（如果有）
        if expected_output:
            similarity = self._calculate_similarity(generated_output, expected_output)
            metrics.accuracy = (metrics.accuracy + similarity) / 2

        # 综合评分
        metrics.overall = metrics.weighted_score()

        return metrics

    def _calculate_relevance(self, input_text: str, output_text: str) -> float:
        """计算相关性"""
        input_keywords = set(self._analyzer.extract_keywords(input_text, 5))
        output_keywords = set(self._analyzer.extract_keywords(output_text, 10))

        if not input_keywords:
            return 0.5

        overlap = len(input_keywords & output_keywords)
        return min(overlap / len(input_keywords), 1.0)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算相似度"""
        # 简单的Jaccard相似度
        words1 = set(re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', text1.lower()))
        words2 = set(re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', text2.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _generate_insights(
        self,
        pattern: MessagePattern,
        metrics: EvaluationMetrics,
        feedback: List[UserFeedback]
    ) -> Tuple[List[str], List[str]]:
        """生成洞察和建议"""
        insights = []
        recommendations = []

        # 基于使用情况
        if pattern.metadata.usage_count < 5:
            insights.append("该模式使用次数较少，可能需要更多曝光或优化")
        elif pattern.metadata.usage_count > 100:
            insights.append("该模式已被广泛使用，具有较高的实用价值")

        # 基于评分
        if pattern.metadata.user_rating > 4.0:
            insights.append("用户评分较高，说明模式效果良好")
        elif pattern.metadata.user_rating < 3.0 and pattern.metadata.user_rating > 0:
            insights.append("用户评分较低，需要考虑优化")

        # 基于成功率
        if metrics.success_rate > 0.9:
            insights.append("模式执行成功率高")
        elif metrics.success_rate < 0.7:
            insights.append("模式执行成功率偏低，需要检查触发条件")
            recommendations.append("建议审查模式的触发条件和变量配置")

        # 基于响应时间
        if metrics.response_time > 10.0:
            recommendations.append("响应时间较长，可考虑优化模板结构减少Token使用")

        # 基于反馈
        negative_count = sum(1 for f in feedback if not f.helpful)
        if negative_count > len(feedback) * 0.3:
            recommendations.append("较多用户反馈不够有帮助，建议重新审视模式设计")

        # 通用建议
        if metrics.overall < 0.6:
            recommendations.append("综合评分偏低，建议从准确性、完整性、实用性等方面优化")

        return insights, recommendations

    def _calculate_trend(self, pattern_id: str) -> str:
        """计算趋势"""
        history = self._history.get(pattern_id, [])

        if len(history) < 3:
            return "stable"

        recent = history[-3:]
        scores = [h.metrics.overall for h in recent]

        if all(scores[i] > scores[i-1] for i in range(1, len(scores))):
            return "improving"
        elif all(scores[i] < scores[i-1] for i in range(1, len(scores))):
            return "declining"
        return "stable"

    def add_feedback(self, feedback: UserFeedback):
        """添加用户反馈"""
        with self._lock:
            self._feedback.append(feedback)

    def get_feedback_for_pattern(self, pattern_id: str) -> List[UserFeedback]:
        """获取模式的所有反馈"""
        return [f for f in self._feedback if f.pattern_id == pattern_id]

    def record_evaluation(self, result: EvaluationResult):
        """记录评估结果"""
        with self._lock:
            self._history[result.pattern_id].append(result)
            # 只保留最近30天的记录
            cutoff = datetime.now() - timedelta(days=30)
            self._history[result.pattern_id] = [
                r for r in self._history[result.pattern_id]
                if datetime.fromisoformat(r.timestamp) > cutoff
            ]


# ============ 模式优化器 ============

class PatternOptimizer:
    """模式优化器"""

    def __init__(self, evaluator: EffectivenessEvaluator):
        self._evaluator = evaluator
        self._optimization_strategies: Dict[str, Callable] = {}

    def optimize(
        self,
        pattern: MessagePattern,
        evaluation: EvaluationResult
    ) -> MessagePattern:
        """根据评估结果优化模式"""
        optimized = MessagePattern.from_dict(pattern.to_dict())

        # 基于指标进行优化
        metrics = evaluation.metrics

        # 准确性优化
        if metrics.accuracy < 0.7:
            optimized = self._optimize_for_accuracy(optimized)

        # 完整性优化
        if metrics.completeness < 0.7:
            optimized = self._optimize_for_completeness(optimized)

        # 实用性优化
        if metrics.usefulness < 0.7:
            optimized = self._optimize_for_usefulness(optimized)

        # 清晰度优化
        if metrics.clarity < 0.7:
            optimized = self._optimize_for_clarity(optimized)

        return optimized

    def _optimize_for_accuracy(self, pattern: MessagePattern) -> MessagePattern:
        """优化准确性"""
        # 添加准确性相关的提示
        accuracy_prompt = "\n\n请确保回答基于准确的信息，避免编造内容。"
        pattern.template.content += accuracy_prompt

        # 更新版本
        pattern.version = self._increment_version(pattern.version)

        return pattern

    def _optimize_for_completeness(self, pattern: MessagePattern) -> MessagePattern:
        """优化完整性"""
        # 添加完整性检查
        completeness_prompt = "\n\n请确保回答完整，覆盖所有相关方面。"
        pattern.template.content += completeness_prompt

        # 增加思考深度
        if pattern.enhancement.thinking.depth.value == "shallow":
            pattern.enhancement.thinking.depth.value = "medium"

        pattern.version = self._increment_version(pattern.version)

        return pattern

    def _optimize_for_usefulness(self, pattern: MessagePattern) -> MessagePattern:
        """优化实用性"""
        # 添加实用性提示
        usefulness_prompt = "\n\n请提供实用的建议和可操作的方案。"
        pattern.template.content += usefulness_prompt

        pattern.version = self._increment_version(pattern.version)

        return pattern

    def _optimize_for_clarity(self, pattern: MessagePattern) -> MessagePattern:
        """优化清晰度"""
        # 添加清晰度要求
        clarity_prompt = "\n\n请使用清晰易懂的语言表达，避免歧义。"
        pattern.template.content += clarity_prompt

        pattern.version = self._increment_version(pattern.version)

        return pattern

    def _increment_version(self, version: str) -> str:
        """递增版本号"""
        parts = version.split('.')
        if len(parts) == 3:
            patch = int(parts[2]) + 1
            return f"{parts[0]}.{parts[1]}.{patch}"
        return version


# ============ 学习系统 ============

class LearningSystem:
    """持续学习系统"""

    def __init__(self):
        self._patterns: Dict[str, Dict] = defaultdict(dict)
        self._learning_rules: List[Dict] = []

    def learn_from_feedback(
        self,
        pattern_id: str,
        feedback: UserFeedback,
        output: str
    ) -> Dict[str, Any]:
        """从反馈中学习"""
        learning_result = {
            "pattern_id": pattern_id,
            "feedback_type": "positive" if feedback.helpful else "negative",
            "learned_insights": [],
            "suggested_changes": []
        }

        # 分析负面反馈
        if not feedback.helpful:
            if feedback.feedback_text:
                learning_result["learned_insights"].append(
                    f"用户反馈: {feedback.feedback_text}"
                )

            if feedback.improvement_suggestions:
                learning_result["suggested_changes"].append(
                    feedback.improvement_suggestions
                )

        # 记录学习结果
        self._patterns[pattern_id][datetime.now().isoformat()] = learning_result

        return learning_result

    def suggest_improvements(
        self,
        pattern: MessagePattern,
        evaluation: EvaluationResult
    ) -> List[str]:
        """建议改进"""
        suggestions = []

        metrics = evaluation.metrics

        # 低准确性
        if metrics.accuracy < 0.6:
            suggestions.append("建议添加更多具体示例来提高准确性")

        # 低相关性
        if metrics.relevance < 0.6:
            suggestions.append("建议更明确地聚焦于用户的核心需求")

        # 低完整性
        if metrics.completeness < 0.6:
            suggestions.append("建议增加分析的维度和深度")

        # 低实用性
        if metrics.usefulness < 0.6:
            suggestions.append("建议增加更多可操作的建议")

        return suggestions


# 全局实例
_evaluator_instance = None


def get_effectiveness_evaluator() -> EffectivenessEvaluator:
    """获取效果评估器实例"""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = EffectivenessEvaluator()
    return _evaluator_instance
