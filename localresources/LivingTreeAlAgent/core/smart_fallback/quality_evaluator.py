"""
Response Quality Evaluator - 响应质量评估器
==========================================

评估本地模型响应质量，决定是否需要降级

评估维度:
1. 长度评分 - 50-2000字符为佳
2. 结构化评分 - 有无 Markdown/列表/步骤
3. 相关性评分 - 关键词匹配度
4. 拒绝检测 - 是否包含"不知道"等拒绝回答
5. 置信度评分 - 模型自身的置信表示
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class QualityLevel(Enum):
    """质量等级"""
    EXCELLENT = "excellent"  # 无需优化
    GOOD = "good"            # 可用，但可优化
    POOR = "poor"           # 需要优化
    FAILED = "failed"       # 完全失败


@dataclass
class QualityScore:
    """质量评分详情"""
    overall: float = 0.0           # 综合评分 (0-1)
    length_score: float = 0.0       # 长度评分
    structure_score: float = 0.0   # 结构化评分
    relevance_score: float = 0.0    # 相关性评分
    refusal_score: float = 0.0    # 拒绝检测 (越高越好, 1=无拒绝)
    confidence_indicators: float = 0.0  # 置信度指标

    # 各维度权重
    LENGTH_WEIGHT: float = 0.20
    STRUCTURE_WEIGHT: float = 0.20
    RELEVANCE_WEIGHT: float = 0.25
    REFUSAL_WEIGHT: float = 0.25
    CONFIDENCE_WEIGHT: float = 0.10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall,
            "length_score": self.length_score,
            "structure_score": self.structure_score,
            "relevance_score": self.relevance_score,
            "refusal_score": self.refusal_score,
            "confidence_indicators": self.confidence_indicators,
        }


@dataclass
class EvaluationResult:
    """评估结果"""
    quality_level: QualityLevel
    score: QualityScore
    reasons: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def needs_fallback(self) -> bool:
        """是否需要降级"""
        return self.quality_level in (QualityLevel.POOR, QualityLevel.FAILED)

    @property
    def needs_optimization(self) -> bool:
        """是否需要优化提示词"""
        return self.quality_level in (QualityLevel.GOOD, QualityLevel.POOR, QualityLevel.FAILED)


class ResponseQualityEvaluator:
    """
    响应质量评估器

    使用规则引擎评估本地模型响应质量，无需外部依赖
    """

    # 拒绝关键词
    REFUSAL_PATTERNS = [
        "不知道",
        "无法回答",
        "抱歉",
        "无法提供",
        "不在我能力范围内",
        "我无法",
        "我不能",
        "这个我不懂",
        "超出我的",
        "知识截止",
        "无法处理",
    ]

    # 结构化标记
    STRUCTURE_MARKERS = [
        r"^\d+\.",           # 1. 2. 3.
        r"^[-*]",           # - 或 *
        r"^#{1,6}\s",       # Markdown 标题
        "步骤",
        "建议",
        "首先",
        "其次",
        "最后",
        "第一",
        "第二",
        "第三",
    ]

    # 置信度指标词
    CONFIDENCE_WORDS = [
        "可能",
        "也许",
        "大概",
        "我认为",
        "一般来说",
        "通常",
        "应该",
        "或许",
    ]

    def __init__(self):
        pass

    def evaluate(
        self,
        response: str,
        query: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """
        评估响应质量

        Args:
            response: 响应文本
            query: 原始查询（用于相关性评估）
            context: 额外上下文

        Returns:
            EvaluationResult: 评估结果
        """
        context = context or {}
        reasons = []
        suggestions = []

        # 1. 长度评分
        length_score = self._evaluate_length(response)
        if length_score < 0.3:
            reasons.append(f"回答过短 ({len(response)} 字符)")
            suggestions.append("建议补充更多细节或背景信息")

        # 2. 结构化评分
        structure_score = self._evaluate_structure(response)
        if structure_score < 0.3 and len(response) > 200:
            reasons.append("回答缺乏结构化组织")
            suggestions.append("建议使用列表、步骤或分点回答")

        # 3. 相关性评分
        relevance_score = self._evaluate_relevance(response, query)
        if relevance_score < 0.3:
            reasons.append("回答与问题相关性较低")
            suggestions.append("请明确回答用户提出的具体问题")

        # 4. 拒绝检测
        refusal_score = self._evaluate_refusal(response)
        if refusal_score < 0.5:
            reasons.append("检测到拒绝回答或不确定表述")
            suggestions.append("建议直接回答问题或说明限制条件")

        # 5. 置信度指标
        confidence_indicators = self._evaluate_confidence(response)

        # 计算综合评分
        overall = (
            length_score * 0.20 +
            structure_score * 0.20 +
            relevance_score * 0.25 +
            refusal_score * 0.25 +
            confidence_indicators * 0.10
        )

        # 防止极端值
        overall = max(0.0, min(1.0, overall))

        # 确定质量等级
        quality_level = self._determine_quality_level(overall, refusal_score)

        score = QualityScore(
            overall=overall,
            length_score=length_score,
            structure_score=structure_score,
            relevance_score=relevance_score,
            refusal_score=refusal_score,
            confidence_indicators=confidence_indicators,
        )

        return EvaluationResult(
            quality_level=quality_level,
            score=score,
            reasons=reasons,
            suggestions=suggestions,
            metadata={
                "response_length": len(response),
                "query_length": len(query),
                "timestamp": context.get("timestamp", ""),
            }
        )

    def _evaluate_length(self, response: str) -> float:
        """评估长度分数"""
        length = len(response.strip())

        if length == 0:
            return 0.0

        # 50-2000 字符为佳
        if 50 <= length <= 2000:
            return 1.0
        elif length < 50:
            # 太短
            return max(0.0, length / 50)
        else:
            # 太长（但不一定差）
            return max(0.5, 1.0 - (length - 2000) / 5000)

    def _evaluate_structure(self, response: str) -> float:
        """评估结构化分数"""
        if not response.strip():
            return 0.0

        matches = 0
        response_lower = response.lower()
        for marker in self.STRUCTURE_MARKERS:
            if marker.lower() in response_lower or re.search(marker, response):
                matches += 1

        return min(1.0, matches / 3)

    def _evaluate_relevance(self, response: str, query: str) -> float:
        """评估相关性分数"""
        if not query.strip():
            return 0.8

        if not response.strip():
            return 0.0

        # 提取查询关键词（简单分词）
        query_words = set(query.lower().split())
        # 过滤停用词
        stopwords = {"的", "了", "是", "在", "和", "与", "或", "等", "这", "那", "我", "你", "他"}
        query_words -= stopwords

        if not query_words:
            return 0.8

        response_lower = response.lower()
        matches = sum(1 for word in query_words if word in response_lower)

        return matches / len(query_words)

    def _evaluate_refusal(self, response: str) -> float:
        """评估拒绝分数（越高越好，1=无拒绝）"""
        if not response.strip():
            return 0.0

        response_lower = response.lower()
        refusals = sum(1 for pattern in self.REFUSAL_PATTERNS if pattern in response_lower)

        # 无拒绝 = 1.0，有拒绝则递减
        return max(0.0, 1.0 - refusals * 0.3)

    def _evaluate_confidence(self, response: str) -> float:
        """评估置信度指标"""
        if not response.strip():
            return 0.0

        response_lower = response.lower()
        confidence_count = sum(1 for word in self.CONFIDENCE_WORDS if word in response_lower)

        # 适度的不确定表述是正常的
        if confidence_count == 0:
            return 0.8
        elif confidence_count <= 2:
            return 1.0
        else:
            return max(0.3, 1.0 - (confidence_count - 2) * 0.2)

    def _determine_quality_level(
        self,
        overall: float,
        refusal_score: float,
    ) -> QualityLevel:
        """确定质量等级"""
        if overall >= 0.7 and refusal_score >= 0.7:
            return QualityLevel.EXCELLENT
        if overall >= 0.5:
            return QualityLevel.GOOD
        if overall >= 0.3:
            return QualityLevel.POOR
        return QualityLevel.FAILED

    def batch_evaluate(
        self,
        responses: List[str],
        queries: Optional[List[str]] = None,
    ) -> List[EvaluationResult]:
        """
        批量评估

        Args:
            responses: 响应列表
            queries: 查询列表（可选）

        Returns:
            评估结果列表
        """
        queries = queries or ["" for _ in responses]
        return [
            self.evaluate(response, query)
            for response, query in zip(responses, queries)
        ]


# 全局实例
_evaluator: Optional[ResponseQualityEvaluator] = None


def get_quality_evaluator() -> ResponseQualityEvaluator:
    """获取质量评估器实例"""
    global _evaluator
    if _evaluator is None:
        _evaluator = ResponseQualityEvaluator()
    return _evaluator