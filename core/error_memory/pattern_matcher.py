# -*- coding: utf-8 -*-
"""
Error Pattern Matcher - 错误模式匹配器
====================================

基于多维度相似度的智能错误模式匹配

核心功能：
1. 多维度相似度计算
2. 加权匹配：错误信息 > 上下文 > 操作类型
3. 模糊匹配支持变体错误
4. 相似度阈值自动调整

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

# Levenshtein 是可选的
try:
    import Levenshtein
    HAS_LEVENSHTEIN = True
except ImportError:
    HAS_LEVENSHTEIN = False

# 导入错误模型
try:
    from .error_models import (
        ErrorSurfaceFeatures,
        ErrorPattern,
        FixTemplate,
        PatternMatchResult,
        ErrorCategory,
    )
except ImportError:
    from error_models import (
        ErrorSurfaceFeatures,
        ErrorPattern,
        FixTemplate,
        PatternMatchResult,
        ErrorCategory,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 匹配器配置
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MatcherConfig:
    """匹配器配置"""
    # 相似度权重
    error_type_weight: float = 0.30      # 错误类型权重
    message_keyword_weight: float = 0.35  # 错误信息关键词权重
    operation_type_weight: float = 0.20  # 操作类型权重
    context_weight: float = 0.15         # 上下文权重
    
    # 阈值配置
    min_confidence_threshold: float = 0.5   # 最小置信度阈值
    high_confidence_threshold: float = 0.8   # 高置信度阈值
    
    # 模糊匹配
    fuzzy_match_enabled: bool = True
    fuzzy_threshold: float = 0.6         # 模糊匹配阈值
    
    # 匹配数量限制
    max_patterns: int = 5                # 最多返回的匹配模式数
    max_templates: int = 3               # 最多推荐的模板数


# ═══════════════════════════════════════════════════════════════════════════════
# 特征提取器
# ═══════════════════════════════════════════════════════════════════════════════

class FeatureExtractor:
    """错误特征提取器"""
    
    # 常见错误类型模式
    ERROR_TYPE_PATTERNS = {
        r"UnicodeDecodeError": "encoding",
        r"UnicodeEncodeError": "encoding",
        r"FileNotFoundError": "file_io",
        r"PermissionError": "file_io",
        r"TimeoutError": "network",
        r"ConnectionError": "network",
        r"ImportError": "dependency",
        r"ModuleNotFoundError": "dependency",
        r"SyntaxError": "syntax",
        r"IndentationError": "syntax",
        r"TypeError": "logic",
        r"ValueError": "logic",
        r"KeyError": "logic",
        r"AttributeError": "logic",
        r"MemoryError": "resource",
        r"DiskFull": "resource",
        r"ConfigurationError": "config",
    }
    
    # 操作类型关键词
    OPERATION_KEYWORDS = {
        "file": ["read", "write", "open", "close", "load", "save", "文件", "读取", "写入"],
        "network": ["request", "connect", "send", "receive", "http", "api", "网络", "请求"],
        "database": ["query", "insert", "update", "delete", "commit", "数据库", "SQL"],
        "import": ["import", "from", "require", "include", "导入", "引入"],
        "execute": ["run", "exec", "call", "invoke", "执行", "调用"],
    }
    
    @classmethod
    def extract_error_type(cls, raw_message: str) -> str:
        """提取错误类型"""
        for pattern, error_type in cls.ERROR_TYPE_PATTERNS.items():
            if re.search(pattern, raw_message, re.IGNORECASE):
                return error_type
        return "unknown"
    
    @classmethod
    def extract_error_name(cls, raw_message: str) -> str:
        """提取错误名称"""
        match = re.search(r"(\w+Error|\w+Exception)", raw_message)
        return match.group(1) if match else "UnknownError"
    
    @classmethod
    def extract_operation_type(cls, context: str) -> str:
        """提取操作类型"""
        context_lower = context.lower()
        for op_type, keywords in cls.OPERATION_KEYWORDS.items():
            if any(kw in context_lower for kw in keywords):
                return op_type
        return "unknown"
    
    @classmethod
    def extract_keywords(cls, text: str, max_keywords: int = 10) -> List[str]:
        """提取关键词"""
        # 移除常见停用词
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", 
            "in", "on", "at", "to", "for", "of", "with",
            "的", "了", "是", "在", "和", "与", "或", "等",
            "file", "error", "occurred", "failed", "could not",
            "文件", "错误", "发生", "无法", "不能",
        }
        
        # 提取英文和中文词
        words = re.findall(r"[a-zA-Z_]+", text.lower())
        chinese = re.findall(r"[\u4e00-\u9fff]+", text)
        
        # 过滤停用词
        filtered_words = [w for w in words if w not in stopwords and len(w) > 2]
        filtered_chinese = [c for c in chinese if c not in stopwords]
        
        # 合并并返回
        keywords = filtered_words + filtered_chinese
        return list(set(keywords))[:max_keywords]
    
    @classmethod
    def extract_context_features(cls, raw_message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """提取上下文特征"""
        features = {}
        
        # 从错误信息中提取
        features["has_file_path"] = bool(re.search(r"['\"][^'\"]+\.py['\"]", raw_message))
        features["has_line_number"] = bool(re.search(r"line \d+", raw_message))
        features["has_function_name"] = bool(re.search(r"in \w+\(", raw_message))
        
        # 从上下文提取
        features["environment"] = context.get("environment", "unknown")
        features["platform"] = context.get("platform", "unknown")
        
        return features


# ═══════════════════════════════════════════════════════════════════════════════
# 相似度计算器
# ═══════════════════════════════════════════════════════════════════════════════

class SimilarityCalculator:
    """相似度计算器"""
    
    @staticmethod
    def string_similarity(s1: str, s2: str) -> float:
        """字符串相似度（Levenshtein）"""
        if not s1 or not s2:
            return 0.0
        
        if HAS_LEVENSHTEIN:
            # 归一化编辑距离
            max_len = max(len(s1), len(s2))
            if max_len == 0:
                return 1.0
            distance = Levenshtein.distance(s1.lower(), s2.lower())
            return 1.0 - (distance / max_len)
        else:
            # 简单字符重叠计算
            set1 = set(s1.lower())
            set2 = set(s2.lower())
            if not set1 or not set2:
                return 0.0
            overlap = len(set1 & set2)
            union = len(set1 | set2)
            return overlap / union if union > 0 else 0.0
    
    @staticmethod
    def keyword_overlap(keywords1: List[str], keywords2: List[str]) -> float:
        """关键词重叠度"""
        if not keywords1 or not keywords2:
            return 0.0
        
        set1 = set(k.lower() for k in keywords1)
        set2 = set(k.lower() for k in keywords2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def fuzzy_match_score(pattern: str, text: str) -> float:
        """模糊匹配分数"""
        if not pattern or not text:
            return 0.0
        
        # 尝试正则匹配
        try:
            if re.search(pattern, text, re.IGNORECASE):
                return 1.0
        except re.error:
            pass
        
        # 使用编辑距离
        return SimilarityCalculator.string_similarity(pattern, text)
    
    @staticmethod
    def category_match(category1: ErrorCategory, category2: ErrorCategory) -> float:
        """类别匹配度"""
        return 1.0 if category1 == category2 else 0.0
    
    @staticmethod
    def weighted_similarity(
        features: ErrorSurfaceFeatures,
        pattern: ErrorPattern,
        config: MatcherConfig,
    ) -> float:
        """加权相似度计算"""
        scores = []
        weights = []
        
        # 1. 错误类型匹配
        error_type = FeatureExtractor.extract_error_type(features.raw_message)
        type_score = 1.0 if error_type == pattern.category.value else 0.0
        scores.append(type_score)
        weights.append(config.error_type_weight)
        
        # 2. 错误信息关键词匹配
        features_keywords = FeatureExtractor.extract_keywords(features.raw_message)
        keyword_score = SimilarityCalculator.keyword_overlap(
            features_keywords,
            pattern.message_keywords
        )
        scores.append(keyword_score)
        weights.append(config.message_keyword_weight)
        
        # 3. 操作类型匹配
        if features.operation_type:
            op_type = FeatureExtractor.extract_operation_type(features.operation_type)
            operation_score = SimilarityCalculator.keyword_overlap(
                [op_type],
                pattern.trigger_conditions
            )
            scores.append(operation_score)
            weights.append(config.operation_type_weight)
        else:
            weights.append(0)  # 不参与计算
        
        # 4. 上下文匹配
        context_score = 0.5  # 默认中等匹配
        if features.environment:
            if features.environment in pattern.affected_systems:
                context_score = 0.8
        scores.append(context_score)
        weights.append(config.context_weight)
        
        # 加权平均
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(s * w for s, w in zip(scores, weights) if w > 0)
        return weighted_sum / total_weight


# ═══════════════════════════════════════════════════════════════════════════════
# 错误模式匹配器
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorPatternMatcher:
    """
    错误模式匹配器
    
    基于多维度相似度的智能匹配
    """

    def __init__(self, config: Optional[MatcherConfig] = None):
        self.config = config or MatcherConfig()
        self._patterns: Dict[str, ErrorPattern] = {}
        self._templates: Dict[str, FixTemplate] = {}
        
        # 加载预定义模式
        try:
            from .error_models import PRESET_PATTERNS, PRESET_TEMPLATES
        except ImportError:
            from error_models import PRESET_PATTERNS, PRESET_TEMPLATES
from core.logger import get_logger
logger = get_logger('error_memory.pattern_matcher')

        self._patterns.update(PRESET_PATTERNS)
        self._templates.update(PRESET_TEMPLATES)
        
        # 匹配统计
        self._match_stats = defaultdict(int)
        
        logger.info(f"[ErrorPatternMatcher] 已初始化，{len(self._patterns)} 个模式，{len(self._templates)} 个模板")

    def register_pattern(self, pattern: ErrorPattern):
        """注册错误模式"""
        self._patterns[pattern.pattern_id] = pattern
        logger.info(f"[ErrorPatternMatcher] 注册模式: {pattern.pattern_name}")

    def register_template(self, template: FixTemplate):
        """注册修复模板"""
        self._templates[template.template_id] = template
        logger.info(f"[ErrorPatternMatcher] 注册模板: {template.template_name}")

    def find_matching_patterns(
        self,
        features: ErrorSurfaceFeatures,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[PatternMatchResult]:
        """
        查找匹配的错误模式
        
        Args:
            features: 错误表层特征
            context: 额外上下文
            
        Returns:
            匹配结果列表（按置信度排序）
        """
        context = context or {}
        results = []
        
        # 提取错误类型
        error_type = FeatureExtractor.extract_error_type(features.raw_message)
        error_name = FeatureExtractor.extract_error_name(features.raw_message)
        
        # 计算每个模式的匹配度
        for pattern in self._patterns.values():
            # 1. 直接匹配（错误类型）
            if pattern.category.value == error_type:
                base_score = 0.7
            else:
                base_score = 0.3
            
            # 2. 计算加权相似度
            similarity = SimilarityCalculator.weighted_similarity(
                features, pattern, self.config
            )
            
            # 3. 组合得分
            confidence = base_score * 0.5 + similarity * 0.5
            
            # 4. 模糊匹配增强
            if self.config.fuzzy_match_enabled:
                fuzzy_score = self._fuzzy_match_enhancement(features, pattern)
                confidence = confidence * 0.7 + fuzzy_score * 0.3
            
            # 5. 检查是否通过阈值
            if confidence >= self.config.min_confidence_threshold:
                matched_keywords = self._get_matched_keywords(features, pattern)
                missing_keywords = self._get_missing_keywords(features, pattern)
                
                # 获取推荐的修复模板
                recommended_templates = self._get_recommended_templates(pattern.pattern_id)
                
                result = PatternMatchResult(
                    pattern=pattern,
                    confidence=confidence,
                    matched_features=matched_keywords,
                    missing_features=missing_keywords,
                    similarity_score=similarity,
                    recommended_templates=recommended_templates,
                    template_scores={t.template_id: t.success_rate for t in recommended_templates},
                    context_fitness=self._calculate_context_fitness(pattern, context),
                )
                results.append(result)
                
                # 更新统计
                self._match_stats[pattern.pattern_id] += 1
        
        # 按置信度排序
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        # 限制返回数量
        return results[:self.config.max_patterns]

    def _fuzzy_match_enhancement(
        self,
        features: ErrorSurfaceFeatures,
        pattern: ErrorPattern,
    ) -> float:
        """模糊匹配增强"""
        max_fuzzy_score = 0.0
        
        # 模糊匹配错误消息
        for keyword in pattern.message_keywords[:3]:  # 只检查前3个关键词
            if len(keyword) >= 3:  # 避免太短的关键词
                score = SimilarityCalculator.fuzzy_match_score(
                    keyword,
                    features.raw_message
                )
                if score > max_fuzzy_score:
                    max_fuzzy_score = score
        
        # 模糊匹配错误类型模式
        if pattern.error_type_pattern:
            score = SimilarityCalculator.fuzzy_match_score(
                pattern.error_type_pattern,
                features.raw_message
            )
            if score > max_fuzzy_score:
                max_fuzzy_score = score
        
        return max_fuzzy_score

    def _get_matched_keywords(
        self,
        features: ErrorSurfaceFeatures,
        pattern: ErrorPattern,
    ) -> Dict[str, Any]:
        """获取匹配到的关键词"""
        features_keywords = set(FeatureExtractor.extract_keywords(features.raw_message))
        pattern_keywords = set(k.lower() for k in pattern.message_keywords)
        
        matched = features_keywords & pattern_keywords
        return {"keywords": list(matched), "count": len(matched)}

    def _get_missing_keywords(
        self,
        features: ErrorSurfaceFeatures,
        pattern: ErrorPattern,
    ) -> List[str]:
        """获取缺失的关键词"""
        features_keywords = set(FeatureExtractor.extract_keywords(features.raw_message))
        pattern_keywords = set(k.lower() for k in pattern.message_keywords)
        
        return list(pattern_keywords - features_keywords)[:5]

    def _get_recommended_templates(self, pattern_id: str) -> List[FixTemplate]:
        """获取推荐的修复模板"""
        recommended = []
        
        for template in self._templates.values():
            if pattern_id in template.applicable_patterns:
                recommended.append(template)
        
        # 按成功率排序
        recommended.sort(key=lambda x: x.success_rate, reverse=True)
        
        return recommended[:self.config.max_templates]

    def _calculate_context_fitness(
        self,
        pattern: ErrorPattern,
        context: Dict[str, Any],
    ) -> float:
        """计算上下文适应度"""
        if not context:
            return 0.5
        
        fitness_scores = []
        
        # 检查环境匹配
        if "environment" in context:
            env = context["environment"]
            if env in pattern.affected_systems:
                fitness_scores.append(1.0)
            else:
                fitness_scores.append(0.3)
        
        # 检查操作类型匹配
        if "operation_type" in context:
            op = context["operation_type"]
            if any(op in cond for cond in pattern.trigger_conditions):
                fitness_scores.append(1.0)
            else:
                fitness_scores.append(0.3)
        
        # 检查平台匹配
        if "platform" in context:
            platform = context["platform"]
            if platform in pattern.affected_systems:
                fitness_scores.append(0.8)
        
        return sum(fitness_scores) / len(fitness_scores) if fitness_scores else 0.5

    def get_pattern_stats(self) -> Dict[str, Any]:
        """获取匹配统计"""
        return {
            "total_patterns": len(self._patterns),
            "total_templates": len(self._templates),
            "match_distribution": dict(self._match_stats),
            "top_patterns": sorted(
                self._match_stats.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
        }

    def learn_from_fix(
        self,
        features: ErrorSurfaceFeatures,
        pattern: ErrorPattern,
        template: FixTemplate,
        success: bool,
    ):
        """从修复中学习"""
        # 更新模板统计
        if template.template_id in self._templates:
            t = self._templates[template.template_id]
            if success:
                t.success_count += 1
            else:
                t.failure_count += 1
        
        # 如果是新模式，可以考虑创建
        if pattern.pattern_id not in self._patterns:
            # 评估是否需要注册
            pass  # TODO: 实现自动模式学习


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════

_matcher: Optional[ErrorPatternMatcher] = None


def get_matcher() -> ErrorPatternMatcher:
    """获取匹配器实例"""
    global _matcher
    if _matcher is None:
        _matcher = ErrorPatternMatcher()
    return _matcher
