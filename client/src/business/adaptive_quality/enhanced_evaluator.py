# -*- coding: utf-8 -*-
"""
Enhanced Quality Evaluator - 增强型质量评估器
============================================

多维度质量评估 + 智能升级决策驱动

评估维度（增强版）：
1. 相关性评估：回答是否针对问题
2. 准确性评估：事实是否正确，逻辑是否严密
3. 完整性评估：是否覆盖问题的各个方面
4. 连贯性评估：表达是否流畅，逻辑是否连贯
5. 深度评估：分析是否深入，是否有洞察

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

import re
import time
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════════════════════
# 质量维度定义
# ═══════════════════════════════════════════════════════════════════════════════

class QualityDimension(Enum):
    """质量评估维度"""
    RELEVANCE = "relevance"           # 相关性
    ACCURACY = "accuracy"            # 准确性
    COMPLETENESS = "completeness"   # 完整性
    COHERENCE = "coherence"          # 连贯性
    DEPTH = "depth"                  # 深度


class QualityLevel(Enum):
    """质量等级"""
    EXCELLENT = "excellent"   # 优秀，无需优化
    GOOD = "good"             # 良好，可用
    ACCEPTABLE = "acceptable"  # 可接受
    POOR = "poor"             # 较差，需要优化
    FAILED = "failed"         # 失败


@dataclass
class DimensionScore:
    """单个维度评分"""
    dimension: QualityDimension
    score: float = 0.0                    # 0-1 评分
    weight: float = 1.0                  # 权重
    confidence: float = 0.5               # 评估置信度
    reasons: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def weighted_score(self) -> float:
        """加权评分"""
        return self.score * self.weight


@dataclass
class QualityReport:
    """完整质量报告"""
    # 综合评分
    overall_score: float = 0.0
    overall_level: QualityLevel = QualityLevel.FAILED
    
    # 各维度评分
    dimension_scores: Dict[QualityDimension, DimensionScore] = field(default_factory=dict)
    
    # 升级建议
    upgrade_reasons: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)
    
    # 元数据
    response_length: int = 0
    processing_time_ms: float = 0.0
    evaluator_version: str = "1.0"
    
    # 升级相关
    needs_upgrade: bool = False
    upgrade_reason: Optional[str] = None
    suggested_model_level: Optional[int] = None  # 建议的模型级别
    
    @property
    def dimensions_summary(self) -> str:
        """维度摘要"""
        return ", ".join([
            f"{d.value}={s.score:.2f}"
            for d, s in self.dimension_scores.items()
        ])


# ═══════════════════════════════════════════════════════════════════════════════
# 评估器实现
# ═══════════════════════════════════════════════════════════════════════════════

class EnhancedQualityEvaluator:
    """
    增强型质量评估器
    
    支持多维度评估 + 升级决策驱动
    """
    
    # 维度权重配置
    DEFAULT_WEIGHTS = {
        QualityDimension.RELEVANCE: 0.25,     # 相关性权重最高
        QualityDimension.ACCURACY: 0.25,      # 准确性权重最高
        QualityDimension.COMPLETENESS: 0.20,
        QualityDimension.COHERENCE: 0.15,
        QualityDimension.DEPTH: 0.15,
    }
    
    # 质量阈值配置
    THRESHOLDS = {
        "excellent": 0.8,    # ≥0.8 优秀
        "good": 0.6,        # ≥0.6 良好
        "acceptable": 0.4, # ≥0.4 可接受
        "poor": 0.2,       # ≥0.2 较差
    }
    
    # 升级阈值
    UPGRADE_THRESHOLD = 0.5  # 综合评分 < 0.5 需要考虑升级
    
    # 关键维度阈值（任一低于此值需要升级）
    CRITICAL_DIMENSION_THRESHOLD = 0.3
    
    # 拒绝/不确定性关键词
    REFUSAL_PATTERNS = [
        "不知道", "无法回答", "抱歉", "无法提供",
        "不在我能力范围内", "我无法", "我不能",
        "超出我的", "知识截止", "无法处理",
        "这个我不懂", "我不确定", "可能我理解有误",
    ]
    
    # 不确定性表达
    UNCERTAINTY_PATTERNS = [
        "可能", "也许", "大概", "我认为",
        "一般来说", "通常", "应该", "或许",
        "不确定", "不太确定", "我说不准",
    ]
    
    # 幻觉检测关键词
    HALLUCINATION_PATTERNS = [
        "根据最新研究", "据报道", "权威研究表明",
        "历史数据显示", "专家称", "据官方",
    ]
    
    # 深度分析标记
    DEPTH_MARKERS = [
        "原因", "本质", "核心", "关键",
        "首先", "其次", "最后", "综上所述",
        "然而", "但是", "因此", "从而",
        "一方面", "另一方面", "值得注意的是",
    ]
    
    # 结构化标记
    STRUCTURE_MARKERS = [
        r"^\d+[.)]", r"^\d+、",          # 1. 2. 或 1、2、
        r"^[-*]\s",                       # - 或 *
        r"^#{1,6}\s",                     # Markdown 标题
        r"^\|",                           # 表格
    ]

    def __init__(
        self,
        weights: Optional[Dict[QualityDimension, float]] = None,
        custom_thresholds: Optional[Dict[str, float]] = None,
    ):
        """
        初始化评估器
        
        Args:
            weights: 自定义维度权重
            custom_thresholds: 自定义阈值
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.thresholds = custom_thresholds or self.THRESHOLDS.copy()
        
        # 评估回调
        self._on_evaluate: Optional[Callable] = None
    
    def evaluate(
        self,
        response: str,
        query: str = "",
        context: Optional[Dict[str, Any]] = None,
        model_level: int = 0,
    ) -> QualityReport:
        """
        评估响应质量
        
        Args:
            response: 响应文本
            query: 原始查询
            context: 额外上下文
            model_level: 当前模型级别（用于升级决策）
            
        Returns:
            QualityReport: 完整质量报告
        """
        start_time = time.time()
        context = context or {}
        
        # 1. 各维度评分
        dimension_scores = {}
        
        # 相关性评估
        relevance = self._evaluate_relevance(response, query)
        relevance.weight = self.weights[QualityDimension.RELEVANCE]
        dimension_scores[QualityDimension.RELEVANCE] = relevance
        
        # 准确性评估
        accuracy = self._evaluate_accuracy(response, query)
        accuracy.weight = self.weights[QualityDimension.ACCURACY]
        dimension_scores[QualityDimension.ACCURACY] = accuracy
        
        # 完整性评估
        completeness = self._evaluate_completeness(response, query)
        completeness.weight = self.weights[QualityDimension.COMPLETENESS]
        dimension_scores[QualityDimension.COMPLETENESS] = completeness
        
        # 连贯性评估
        coherence = self._evaluate_coherence(response)
        coherence.weight = self.weights[QualityDimension.COHERENCE]
        dimension_scores[QualityDimension.COHERENCE] = coherence
        
        # 深度评估
        depth = self._evaluate_depth(response, query)
        depth.weight = self.weights[QualityDimension.DEPTH]
        dimension_scores[QualityDimension.DEPTH] = depth
        
        # 2. 计算综合评分
        overall_score = sum(d.weighted_score() for d in dimension_scores.values())
        
        # 3. 确定质量等级
        overall_level = self._determine_level(overall_score)
        
        # 4. 升级决策
        needs_upgrade, upgrade_reason, suggested_level = self._decide_upgrade(
            dimension_scores, overall_score, model_level
        )
        
        # 5. 收集建议
        suggestions = []
        for dim_score in dimension_scores.values():
            if dim_score.score < self.THRESHOLDS["good"]:
                suggestions.extend(dim_score.suggestions)
        
        # 构建报告
        processing_time = (time.time() - start_time) * 1000
        
        report = QualityReport(
            overall_score=overall_score,
            overall_level=overall_level,
            dimension_scores=dimension_scores,
            upgrade_reasons=[upgrade_reason] if upgrade_reason else [],
            improvement_suggestions=suggestions[:5],  # 最多5条建议
            response_length=len(response),
            processing_time_ms=processing_time,
            needs_upgrade=needs_upgrade,
            upgrade_reason=upgrade_reason,
            suggested_model_level=suggested_level,
        )
        
        # 触发回调
        if self._on_evaluate:
            self._on_evaluate(report)
        
        return report
    
    def _evaluate_relevance(self, response: str, query: str) -> DimensionScore:
        """评估相关性"""
        score = DimensionScore(dimension=QualityDimension.RELEVANCE)
        
        if not response.strip():
            score.score = 0.0
            score.reasons.append("空响应")
            return score
        
        if not query.strip():
            score.score = 0.8
            score.confidence = 0.5
            return score
        
        # 提取查询关键词
        query_words = self._extract_keywords(query)
        
        if not query_words:
            score.score = 0.8
            score.confidence = 0.5
            return score
        
        # 计算匹配度
        response_lower = response.lower()
        matches = sum(1 for word in query_words if word in response_lower)
        match_ratio = matches / len(query_words)
        
        # 考虑位置（开头匹配更重要）
        first_part = response[:200].lower()
        first_matches = sum(1 for word in query_words if word in first_part)
        position_bonus = first_matches / len(query_words) * 0.2
        
        score.score = min(1.0, match_ratio * 0.8 + position_bonus)
        score.confidence = 0.8
        
        if score.score < 0.5:
            score.reasons.append(f"关键词匹配度仅 {score.score:.0%}")
            score.suggestions.append("直接回应用户提出的具体问题")
        
        return score
    
    def _evaluate_accuracy(self, response: str, query: str) -> DimensionScore:
        """评估准确性"""
        score = DimensionScore(dimension=QualityDimension.ACCURACY)
        
        if not response.strip():
            score.score = 0.0
            return score
        
        reasons = []
        
        # 1. 拒绝检测
        refusal_count = sum(1 for p in self.REFUSAL_PATTERNS if p in response)
        refusal_penalty = min(0.4, refusal_count * 0.15)
        
        if refusal_count > 0:
            reasons.append(f"检测到 {refusal_count} 处拒绝表达")
        
        # 2. 不确定性检测
        uncertainty_count = sum(1 for p in self.UNCERTAINTY_PATTERNS if p in response)
        # 适度的不确定性是可接受的
        if uncertainty_count > 5:
            reasons.append(f"过多不确定性表达 ({uncertainty_count}处)")
        
        # 3. 幻觉检测
        hallucination_count = sum(1 for p in self.HALLUCINATION_PATTERNS if p in response)
        hallucination_penalty = hallucination_count * 0.1
        
        if hallucination_count > 0:
            reasons.append(f"检测到 {hallucination_count} 处可能幻觉表述")
        
        # 4. 逻辑一致性（简单检测）
        logical_issues = self._check_logical_consistency(response)
        
        # 计算评分
        base_score = 1.0 - refusal_penalty - hallucination_penalty
        logical_penalty = min(0.2, logical_issues * 0.05)
        score.score = max(0.0, base_score - logical_penalty)
        score.confidence = 0.7
        
        if reasons:
            score.reasons.extend(reasons)
        
        if score.score < 0.5:
            score.suggestions.append("确保回答有事实依据，避免过度推测")
        
        return score
    
    def _evaluate_completeness(self, response: str, query: str) -> DimensionScore:
        """评估完整性"""
        score = DimensionScore(dimension=QualityDimension.COMPLETENESS)
        
        if not response.strip():
            score.score = 0.0
            return score
        
        length = len(response)
        
        # 长度评分
        if length < 50:
            length_score = 0.3
            score.reasons.append("回答过短")
        elif length < 200:
            length_score = 0.6
        elif length < 500:
            length_score = 0.8
        else:
            length_score = 1.0
        
        # 结构化评分
        structure_score = self._evaluate_structure(response)
        
        # 多角度检查（基于查询类型）
        aspect_score = 0.8  # 默认
        
        # 如果是问答题，检查是否涵盖多角度
        if any(k in query for k in ["为什么", "分析", "解释", "如何"]):
            # 检查是否有分析性内容
            analysis_markers = ["首先", "其次", "一方面", "另一方面", "原因", "结果"]
            has_analysis = sum(1 for m in analysis_markers if m in response)
            aspect_score = min(1.0, has_analysis / 3)
        
        # 综合评分
        score.score = length_score * 0.4 + structure_score * 0.3 + aspect_score * 0.3
        score.confidence = 0.7
        
        if score.score < 0.5:
            score.suggestions.append("请更全面地回答问题，补充关键细节")
        
        return score
    
    def _evaluate_coherence(self, response: str) -> DimensionScore:
        """评估连贯性"""
        score = DimensionScore(dimension=QualityDimension.COHERENCE)
        
        if not response.strip():
            score.score = 0.0
            return score
        
        # 1. 句子完整性
        sentences = re.split(r'[。！？\n]', response)
        complete_sentences = sum(1 for s in sentences if len(s.strip()) > 5)
        sentence_ratio = complete_sentences / max(1, len(sentences))
        
        # 2. 过渡词使用
        transitions = ["首先", "其次", "然后", "最后", "因此", "然而", "但是", "总之"]
        transition_count = sum(1 for t in transitions if t in response)
        transition_score = min(1.0, transition_count / 3)
        
        # 3. 重复检测
        lines = response.split('\n')
        unique_lines = len(set(l.strip() for l in lines if l.strip()))
        repetition_ratio = unique_lines / max(1, len(lines))
        
        # 综合评分
        score.score = sentence_ratio * 0.4 + transition_score * 0.3 + repetition_ratio * 0.3
        score.confidence = 0.6
        
        if score.score < 0.5:
            score.suggestions.append("建议使用过渡词改善文章连贯性")
        
        return score
    
    def _evaluate_depth(self, response: str, query: str) -> DimensionScore:
        """评估深度"""
        score = DimensionScore(dimension=QualityDimension.DEPTH)
        
        if not response.strip():
            score.score = 0.0
            return score
        
        length = len(response)
        
        # 1. 深度标记词
        depth_count = sum(1 for m in self.DEPTH_MARKERS if m in response)
        depth_marker_score = min(1.0, depth_count / 5)
        
        # 2. 长度考量（短回答难以有深度）
        if length < 100:
            length_factor = 0.3
        elif length < 300:
            length_factor = 0.6
        elif length < 600:
            length_factor = 0.8
        else:
            length_factor = 1.0
        
        # 3. 问句检测（反问体现思考）
        question_count = response.count('?') + response.count('？')
        question_bonus = min(0.1, question_count * 0.02)
        
        # 4. 专业术语检测
        tech_terms = self._detect_technical_terms(response)
        tech_score = min(1.0, len(tech_terms) / 3)
        
        # 综合评分
        score.score = (
            depth_marker_score * 0.3 +
            length_factor * 0.3 +
            tech_score * 0.3 +
            question_bonus
        )
        score.confidence = 0.6
        
        if score.score < 0.4:
            score.suggestions.append("建议提供更深入的分析和见解")
        
        return score
    
    def _evaluate_structure(self, response: str) -> float:
        """评估结构化程度"""
        matches = 0
        response_lower = response.lower()
        for marker in self.STRUCTURE_MARKERS:
            if re.search(marker, response, re.MULTILINE):
                matches += 1
        return min(1.0, matches / 2)
    
    def _extract_keywords(self, text: str) -> set:
        """提取关键词"""
        # 简单分词 + 停用词过滤
        stopwords = {
            "的", "了", "是", "在", "和", "与", "或", "等", "这", "那",
            "我", "你", "他", "她", "它", "们", "个", "把", "被", "要",
            "会", "能", "可以", "也", "都", "就", "还", "很", "到", "说",
        }
        words = set(text.lower().split())
        words -= stopwords
        # 过滤单字
        words = {w for w in words if len(w) >= 2}
        return words
    
    def _check_logical_consistency(self, response: str) -> int:
        """检查逻辑一致性问题"""
        issues = 0
        
        # 矛盾检测（简单模式）
        contradictions = [
            ("是", "不是"),
            ("有", "没有"),
            ("可以", "不可以"),
            ("会", "不会"),
        ]
        
        for pos, neg in contradictions:
            if pos in response and neg in response:
                issues += 1
        
        return issues
    
    def _detect_technical_terms(self, text: str) -> List[str]:
        """检测专业术语"""
        # 简单检测：连续的专业词模式
        tech_patterns = [
            r'\w+化\w+',  # 规范化
            r'\w+性\w+',  # 可靠性
            r'\w+机制',   # 机制
            r'\w+算法',  # 算法
            r'\w+模型',  # 模型
            r'\w+系统',  # 系统
        ]
        
        terms = []
        for pattern in tech_patterns:
            matches = re.findall(pattern, text)
            terms.extend(matches)
        
        return list(set(terms))
    
    def _determine_level(self, overall_score: float) -> QualityLevel:
        """确定质量等级"""
        if overall_score >= self.thresholds["excellent"]:
            return QualityLevel.EXCELLENT
        if overall_score >= self.thresholds["good"]:
            return QualityLevel.GOOD
        if overall_score >= self.thresholds["acceptable"]:
            return QualityLevel.ACCEPTABLE
        if overall_score >= self.thresholds["poor"]:
            return QualityLevel.POOR
        return QualityLevel.FAILED
    
    def _decide_upgrade(
        self,
        dimension_scores: Dict[QualityDimension, DimensionScore],
        overall_score: float,
        current_level: int,
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        决定是否需要升级
        
        Returns:
            (是否升级, 升级原因, 建议级别)
        """
        max_level = 4  # L4 是最高级别
        
        # 条件1: 综合评分低于阈值
        if overall_score < self.UPGRADE_THRESHOLD:
            # 分析原因
            weak_dimensions = [
                d for d, s in dimension_scores.items()
                if s.score < self.CRITICAL_DIMENSION_THRESHOLD
            ]
            
            if weak_dimensions:
                reason = f"综合评分 {overall_score:.2f} 低于阈值，"
                reason += f"弱维度: {[d.value for d in weak_dimensions]}"
                
                # 根据弱维度推断需要的升级
                suggested_level = self._infer_upgrade_level(weak_dimensions, current_level)
                return True, reason, suggested_level
        
        # 条件2: 关键维度严重不足
        for dim, dim_score in dimension_scores.items():
            if dim_score.score < self.CRITICAL_DIMENSION_THRESHOLD:
                reason = f"关键维度 '{dim.value}' 严重不足 ({dim_score.score:.2f})"
                suggested_level = self._infer_upgrade_level([dim], current_level)
                return True, reason, suggested_level
        
        # 条件3: 准确性维度较低（需要更高质量模型）
        accuracy = dimension_scores.get(QualityDimension.ACCURACY)
        if accuracy and accuracy.score < 0.5:
            reason = f"准确性维度较低 ({accuracy.score:.2f})，可能需要更专业的模型"
            return True, reason, min(current_level + 1, max_level)
        
        return False, None, None
    
    def _infer_upgrade_level(
        self,
        weak_dimensions: List[QualityDimension],
        current_level: int,
    ) -> int:
        """根据弱维度推断需要的升级级别"""
        max_level = 4
        
        # 准确性/深度不足 → 需要更高能力模型
        if QualityDimension.ACCURACY in weak_dimensions:
            return min(current_level + 1, max_level)
        
        if QualityDimension.DEPTH in weak_dimensions:
            return min(current_level + 1, max_level)
        
        # 完整性不足 → 可能需要更多知识
        if QualityDimension.COMPLETENESS in weak_dimensions:
            return min(current_level + 2, max_level)  # 跳级
        
        # 默认升一级
        return min(current_level + 1, max_level)
    
    def set_evaluate_callback(self, callback: Callable):
        """设置评估回调"""
        self._on_evaluate = callback


# ═══════════════════════════════════════════════════════════════════════════════
# 快速评估函数
# ═══════════════════════════════════════════════════════════════════════════════

_evaluator: Optional[EnhancedQualityEvaluator] = None


def get_enhanced_evaluator() -> EnhancedQualityEvaluator:
    """获取增强评估器实例"""
    global _evaluator
    if _evaluator is None:
        _evaluator = EnhancedQualityEvaluator()
    return _evaluator


def quick_evaluate(
    response: str,
    query: str = "",
    model_level: int = 0,
) -> Tuple[float, bool, Optional[int]]:
    """
    快速评估
    
    Returns:
        (综合评分, 是否需要升级, 建议级别)
    """
    evaluator = get_enhanced_evaluator()
    report = evaluator.evaluate(response, query, model_level=model_level)
    return report.overall_score, report.needs_upgrade, report.suggested_model_level
