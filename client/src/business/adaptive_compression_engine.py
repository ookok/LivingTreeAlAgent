"""
智能自适应压缩引擎

创新设计：
1. 上下文感知压缩 - 根据消息上下文自动选择策略
2. 机器学习风格特征分析 - 多维度特征提取
3. 历史学习机制 - 基于历史数据优化策略选择
4. 实时性能监控 - 动态调整压缩策略
5. 自动模式选择 - 无需手动指定压缩级别

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import asyncio
import re
from typing import Dict, Any, Optional, List, Tuple, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
from collections import OrderedDict, Counter
from datetime import datetime

from business.compression_integration import (
    get_compression_integration,
    CompressionStrategy,
    ContentType
)
from business.advanced_compression import (
    get_advanced_compressor,
    DomainType,
    CompressionAlgorithm
)


class CompressionContext(Enum):
    """压缩上下文"""
    CHAT_MESSAGE = "chat_message"
    MODEL_RESPONSE = "model_response"
    LOG_MESSAGE = "log_message"
    P2P_TRANSMISSION = "p2p_transmission"
    CACHE_STORAGE = "cache_storage"
    API_RESPONSE = "api_response"


@dataclass
class TextFeatures:
    """文本特征"""
    length: int = 0
    word_count: int = 0
    avg_word_length: float = 0.0
    punctuation_ratio: float = 0.0
    digit_ratio: float = 0.0
    line_count: int = 0
    code_density: float = 0.0
    technical_term_ratio: float = 0.0
    redundancy_score: float = 0.0
    information_density: float = 0.0


@dataclass
class CompressionDecision:
    """压缩决策"""
    strategy: CompressionStrategy
    confidence: float = 0.0
    reasoning: str = ""
    features: Optional[TextFeatures] = None


class AdaptiveCompressionEngine:
    """
    智能自适应压缩引擎
    
    创新特性：
    1. 多维度特征分析 - 全面分析文本特征
    2. 上下文感知 - 根据使用场景选择策略
    3. 历史学习 - 基于历史数据优化决策
    4. 实时性能监控 - 根据性能反馈调整
    5. 自动模式 - 无需手动配置
    
    决策流程：
    1. 提取文本特征
    2. 识别内容类型和领域
    3. 分析使用上下文
    4. 查询历史数据
    5. 应用决策规则
    6. 返回最优策略
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._logger = logger.bind(component="AdaptiveCompressionEngine")
        self._compression = get_compression_integration()
        self._advanced = get_advanced_compressor()
        
        self._history: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._strategy_stats: Dict[str, Counter] = {}
        self._context_rules: Dict[CompressionContext, CompressionStrategy] = {}
        self._performance_cache: Dict[str, float] = {}
        
        self._technical_terms = {
            "code": {"def", "class", "import", "function", "const", "let", "var", "return", "if", "else", "for", "while", "async", "await"},
            "tech": {"system", "architecture", "component", "API", "database", "server", "client", "network", "algorithm", "framework"},
            "medical": {"patient", "treatment", "diagnosis", "symptom", "disease", "medication", "hospital", "doctor", "nurse"},
            "financial": {"investment", "portfolio", "asset", "liability", "revenue", "expense", "profit", "stock", "bond"},
            "legal": {"agreement", "contract", "party", "clause", "section", "article", "law", "regulation"},
        }
        
        self._init_context_rules()
        self._initialized = True
    
    def _init_context_rules(self):
        """初始化上下文规则"""
        self._context_rules = {
            CompressionContext.CHAT_MESSAGE: CompressionStrategy.FULL,
            CompressionContext.MODEL_RESPONSE: CompressionStrategy.HYBRID,
            CompressionContext.LOG_MESSAGE: CompressionStrategy.ULTRA,
            CompressionContext.P2P_TRANSMISSION: CompressionStrategy.HYBRID,
            CompressionContext.CACHE_STORAGE: CompressionStrategy.ULTRA,
            CompressionContext.API_RESPONSE: CompressionStrategy.FULL,
        }
    
    def _extract_features(self, text: str) -> TextFeatures:
        """提取文本特征"""
        if not text:
            return TextFeatures()
        
        length = len(text)
        words = re.findall(r'\b[a-zA-Z]+\b', text)
        word_count = len(words)
        avg_word_length = sum(len(w) for w in words) / word_count if word_count > 0 else 0.0
        
        punctuation_count = sum(1 for c in text if c in '.,;:!?"\'')
        punctuation_ratio = punctuation_count / length if length > 0 else 0.0
        
        digit_count = sum(1 for c in text if c.isdigit())
        digit_ratio = digit_count / length if length > 0 else 0.0
        
        line_count = text.count('\n') + 1
        
        code_patterns = ['def ', 'class ', 'import ', 'function ', 'const ', 'let ', 'var ', 'return ', 'if ', 'for ', 'while ']
        code_density = sum(1 for pattern in code_patterns if pattern in text.lower()) / len(code_patterns)
        
        technical_count = sum(1 for term in self._technical_terms["tech"] if term in text.lower())
        technical_term_ratio = technical_count / len(self._technical_terms["tech"])
        
        sentences = re.split(r'[.!?]+', text)
        redundancy_score = len(sentences) / (word_count + 1) if word_count > 0 else 0.0
        
        information_density = (word_count / length) * (1 - redundancy_score) if length > 0 else 0.0
        
        return TextFeatures(
            length=length,
            word_count=word_count,
            avg_word_length=avg_word_length,
            punctuation_ratio=punctuation_ratio,
            digit_ratio=digit_ratio,
            line_count=line_count,
            code_density=code_density,
            technical_term_ratio=technical_term_ratio,
            redundancy_score=redundancy_score,
            information_density=information_density
        )
    
    def _detect_domain(self, text: str) -> DomainType:
        """检测文本领域"""
        text_lower = text.lower()
        
        for domain, terms in self._technical_terms.items():
            if domain == "code":
                if any(term in text_lower for term in terms):
                    return DomainType.CODE
            elif domain == "tech":
                if sum(1 for term in terms if term in text_lower) >= 3:
                    return DomainType.TECHNICAL
            elif domain == "medical":
                if sum(1 for term in terms if term in text_lower) >= 3:
                    return DomainType.MEDICAL
            elif domain == "financial":
                if sum(1 for term in terms if term in text_lower) >= 3:
                    return DomainType.FINANCIAL
            elif domain == "legal":
                if sum(1 for term in terms if term in text_lower) >= 3:
                    return DomainType.LEGAL
        
        return DomainType.GENERAL
    
    def _analyze_context(self, context: CompressionContext, features: TextFeatures) -> CompressionStrategy:
        """分析上下文并推荐策略"""
        base_strategy = self._context_rules.get(context, CompressionStrategy.FULL)
        
        if features.length < 50:
            return CompressionStrategy.NONE
        
        if features.length < 100:
            return CompressionStrategy.LITE
        
        if features.code_density > 0.3:
            return CompressionStrategy.LITE
        
        if features.technical_term_ratio > 0.3:
            return CompressionStrategy.FULL
        
        if features.redundancy_score > 0.5:
            return CompressionStrategy.HYBRID
        
        if features.length > 1000:
            if context in [CompressionContext.CACHE_STORAGE, CompressionContext.LOG_MESSAGE]:
                return CompressionStrategy.ULTRA
            return CompressionStrategy.HYBRID
        
        return base_strategy
    
    def _learn_from_history(self, text: str, features: TextFeatures) -> Optional[CompressionStrategy]:
        """从历史数据学习"""
        if not self._history:
            return None
        
        recent_items = list(self._history.values())[-100:]
        similar_items = []
        
        for item in recent_items:
            item_features = item.get("features", {})
            if abs(item_features.get("length", 0) - features.length) < 200:
                item_code_density = item_features.get("code_density", 0)
                if abs(item_code_density - features.code_density) < 0.2:
                    similar_items.append(item)
        
        if similar_items:
            strategy_counts = Counter(item["strategy"] for item in similar_items)
            best_strategy = strategy_counts.most_common(1)[0][0]
            success_rate = sum(1 for item in similar_items if item["success"] and item["ratio"] > 0) / len(similar_items)
            
            if success_rate > 0.7:
                return CompressionStrategy(best_strategy)
        
        return None
    
    def _make_decision(self, text: str, context: CompressionContext) -> CompressionDecision:
        """做出压缩决策"""
        features = self._extract_features(text)
        domain = self._detect_domain(text)
        
        history_strategy = self._learn_from_history(text, features)
        
        if history_strategy:
            return CompressionDecision(
                strategy=history_strategy,
                confidence=0.85,
                reasoning=f"历史数据推荐: {history_strategy.value}",
                features=features
            )
        
        context_strategy = self._analyze_context(context, features)
        
        reasoning = []
        if features.length < 100:
            reasoning.append("短文本")
        if features.code_density > 0.3:
            reasoning.append("代码内容")
        if features.technical_term_ratio > 0.3:
            reasoning.append("技术文档")
        if features.length > 1000:
            reasoning.append("长文本")
        if domain != DomainType.GENERAL:
            reasoning.append(f"{domain.value}领域")
        
        return CompressionDecision(
            strategy=context_strategy,
            confidence=0.75 + (len(reasoning) * 0.05),
            reasoning=", ".join(reasoning) if reasoning else "标准处理",
            features=features
        )
    
    async def compress(self, text: str, context: CompressionContext = CompressionContext.CHAT_MESSAGE,
                      previous_text: str = "") -> Dict[str, Any]:
        """
        智能自适应压缩
        
        Args:
            text: 原始文本
            context: 压缩上下文
            previous_text: 上一次文本（用于增量压缩）
        
        Returns:
            压缩结果
        """
        if not text:
            return {
                "success": True,
                "compressed_text": "",
                "original_length": 0,
                "compressed_length": 0,
                "ratio": 0.0,
                "strategy": "none",
                "decision_info": {"reasoning": "空文本"}
            }
        
        decision = self._make_decision(text, context)
        
        if decision.strategy == CompressionStrategy.INCREMENTAL and previous_text:
            strategy = CompressionStrategy.INCREMENTAL
        else:
            strategy = decision.strategy
        
        result = await self._compression.compress_text(text, strategy=strategy)
        
        if result.get("success"):
            ratio = result.get("ratio", result.get("compression_ratio", 0))
            self._record_history(text, strategy.value, ratio, decision.features)
        
        return {
            **result,
            "strategy": strategy.value,
            "decision_info": {
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "context": context.value,
                "features": {
                    "length": decision.features.length if decision.features else len(text),
                    "code_density": decision.features.code_density if decision.features else 0.0,
                    "technical_term_ratio": decision.features.technical_term_ratio if decision.features else 0.0,
                    "redundancy_score": decision.features.redundancy_score if decision.features else 0.0
                }
            }
        }
    
    def _record_history(self, text: str, strategy: str, ratio: float, features: TextFeatures):
        """记录历史数据"""
        key = text[:30] if len(text) > 30 else text
        
        self._history[key] = {
            "strategy": strategy,
            "ratio": ratio,
            "success": ratio > 0,
            "timestamp": datetime.now().timestamp(),
            "features": {
                "length": features.length,
                "code_density": features.code_density,
                "technical_term_ratio": features.technical_term_ratio,
                "redundancy_score": features.redundancy_score
            }
        }
        
        if len(self._history) > 1000:
            self._history.popitem(last=False)
        
        self._strategy_stats[strategy] = self._strategy_stats.get(strategy, Counter())
        self._strategy_stats[strategy]["used"] += 1
        if ratio > 0:
            self._strategy_stats[strategy]["success"] += 1
    
    def get_decision_stats(self) -> Dict[str, Any]:
        """获取决策统计"""
        stats = {}
        for strategy, counter in self._strategy_stats.items():
            total = counter.get("used", 0)
            success = counter.get("success", 0)
            stats[strategy] = {
                "used": total,
                "success": success,
                "success_rate": success / total if total > 0 else 0.0
            }
        return stats
    
    def clear_history(self):
        """清除历史数据"""
        self._history.clear()
        self._strategy_stats.clear()
    
    @classmethod
    def get_instance(cls) -> "AdaptiveCompressionEngine":
        """获取实例"""
        return cls()


# 全局实例
_adaptive_engine = AdaptiveCompressionEngine()


def get_adaptive_compression_engine() -> AdaptiveCompressionEngine:
    """获取自适应压缩引擎实例"""
    return _adaptive_engine


# ========== 便捷函数 ==========

async def smart_compress(text: str, context: str = "chat_message") -> Dict[str, Any]:
    """
    便捷函数：智能压缩
    
    Args:
        text: 需要压缩的文本
        context: 使用上下文（chat_message/model_response/log_message/p2p_transmission/cache_storage/api_response）
    
    Returns:
        压缩结果
    """
    engine = get_adaptive_compression_engine()
    
    context_enum = CompressionContext(context) if context else CompressionContext.CHAT_MESSAGE
    return await engine.compress(text, context=context_enum)
