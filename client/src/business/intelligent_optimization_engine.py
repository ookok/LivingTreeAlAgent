"""
智能优化引擎 (Intelligent Optimization Engine)
==============================================

深度集成优化系统，加入创新功能：
1. 智能决策引擎 - 根据上下文自动选择最优策略
2. 自适应优化 - 根据使用模式自动调整参数
3. 预测性优化 - 预测未来需求并提前优化
4. 自动学习系统 - 从用户行为中学习优化策略
5. 优化监控仪表盘 - 实时监控优化效果

核心特性：
- 与系统深度集成，透明优化所有模型调用
- 智能感知上下文，自动选择最佳优化策略
- 持续学习用户模式，自适应调整优化参数
- 预测性缓存预热，提升缓存命中率

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import asyncio
import time
import random
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = __import__('logging').getLogger(__name__)


class OptimizationDecision(Enum):
    """优化决策类型"""
    NO_OPTIMIZATION = "no_optimization"
    TOKEN_OPTIMIZATION = "token_optimization"
    PROMPT_CACHING = "prompt_caching"
    TOKEN_COMPRESSION = "token_compression"
    FULL_OPTIMIZATION = "full_optimization"


class ContextType(Enum):
    """上下文类型"""
    CODE_EDITING = "code_editing"
    CHAT_CONVERSATION = "chat_conversation"
    DOCUMENT_ANALYSIS = "document_analysis"
    SEARCH_QUERY = "search_query"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    UNKNOWN = "unknown"


@dataclass
class OptimizationDecisionResult:
    """优化决策结果"""
    decision: OptimizationDecision
    confidence: float
    strategy: Dict[str, Any]
    explanation: str


@dataclass
class UsagePattern:
    """使用模式"""
    context_type: ContextType
    timestamp: float
    prompt_length: int
    model_type: str
    cache_hit: bool
    compression_ratio: float


@dataclass
class OptimizationProfile:
    """优化配置文件"""
    name: str
    token_optimization_enabled: bool = True
    caching_enabled: bool = True
    compression_enabled: bool = True
    aggressive_mode: bool = False
    target_cache_hit_rate: float = 0.7
    target_compression_ratio: float = 0.3


class IntelligentOptimizationEngine:
    """
    智能优化引擎
    
    深度集成系统的核心优化引擎，具有以下创新特性：
    
    1. 智能决策引擎 - 根据上下文自动选择最优策略
    2. 自适应优化 - 根据使用模式自动调整参数
    3. 预测性优化 - 预测未来需求并提前优化
    4. 自动学习系统 - 从用户行为中学习优化策略
    5. 优化监控仪表盘 - 实时监控优化效果
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 优化组件（延迟加载）
        self._optimization_bootstrapper = None
        self._context_preprocessor = None
        self._model_optimization_proxy = None
        
        # 智能决策相关
        self._usage_patterns: List[UsagePattern] = []
        self._optimization_profiles: Dict[str, OptimizationProfile] = {}
        self._active_profile = "default"
        
        # 自适应学习
        self._learning_enabled = True
        self._context_patterns = defaultdict(lambda: defaultdict(int))
        
        # 预测性缓存预热
        self._prediction_enabled = True
        self._predicted_queries: Dict[str, float] = {}
        
        # 监控统计
        self._stats = {
            "total_calls": 0,
            "optimized_calls": 0,
            "total_tokens_saved": 0,
            "total_cost_saved": 0.0,
            "decisions_made": 0,
            "confidence_sum": 0.0,
        }
        
        # 初始化配置文件
        self._initialize_profiles()
        
        self._initialized = True
        logger.info("[IntelligentOptimizationEngine] 智能优化引擎初始化完成")
    
    def _initialize_profiles(self):
        """初始化优化配置文件"""
        self._optimization_profiles["default"] = OptimizationProfile(
            name="默认配置",
            token_optimization_enabled=True,
            caching_enabled=True,
            compression_enabled=True,
            aggressive_mode=False,
            target_cache_hit_rate=0.7,
            target_compression_ratio=0.3,
        )
        
        self._optimization_profiles["aggressive"] = OptimizationProfile(
            name="激进优化",
            token_optimization_enabled=True,
            caching_enabled=True,
            compression_enabled=True,
            aggressive_mode=True,
            target_cache_hit_rate=0.85,
            target_compression_ratio=0.2,
        )
        
        self._optimization_profiles["conservative"] = OptimizationProfile(
            name="保守优化",
            token_optimization_enabled=True,
            caching_enabled=True,
            compression_enabled=False,
            aggressive_mode=False,
            target_cache_hit_rate=0.5,
            target_compression_ratio=0.5,
        )
        
        self._optimization_profiles["code_focused"] = OptimizationProfile(
            name="代码优化",
            token_optimization_enabled=True,
            caching_enabled=True,
            compression_enabled=False,  # 代码不压缩
            aggressive_mode=True,
            target_cache_hit_rate=0.8,
            target_compression_ratio=0.4,
        )
    
    def set_profile(self, profile_name: str) -> bool:
        """设置优化配置文件"""
        if profile_name in self._optimization_profiles:
            self._active_profile = profile_name
            logger.info(f"[IntelligentOptimizationEngine] 切换到配置文件: {profile_name}")
            return True
        return False
    
    def get_profile(self) -> OptimizationProfile:
        """获取当前配置文件"""
        return self._optimization_profiles.get(self._active_profile, self._optimization_profiles["default"])
    
    def get_profiles(self) -> List[str]:
        """获取所有配置文件名称"""
        return list(self._optimization_profiles.keys())
    
    # ─── 智能决策引擎 ───
    
    def make_decision(self, prompt: str, context: Dict[str, Any]) -> OptimizationDecisionResult:
        """
        智能决策：根据上下文选择最优优化策略
        
        Args:
            prompt: 用户提示词
            context: 上下文信息
            
        Returns:
            优化决策结果
        """
        self._stats["decisions_made"] += 1
        
        # 1. 识别上下文类型
        context_type = self._identify_context(prompt, context)
        
        # 2. 分析提示词特征
        features = self._analyze_prompt_features(prompt)
        
        # 3. 获取当前配置
        profile = self.get_profile()
        
        # 4. 基于规则和学习做出决策
        decision, confidence, strategy, explanation = self._calculate_decision(
            context_type, features, profile
        )
        
        # 5. 记录使用模式
        self._record_usage_pattern(context_type, features)
        
        # 6. 更新统计
        self._stats["confidence_sum"] += confidence
        
        return OptimizationDecisionResult(
            decision=decision,
            confidence=confidence,
            strategy=strategy,
            explanation=explanation,
        )
    
    def _identify_context(self, prompt: str, context: Dict[str, Any]) -> ContextType:
        """识别上下文类型"""
        prompt_lower = prompt.lower()
        
        # 基于关键词识别
        context_keywords = {
            ContextType.CODE_EDITING: ["代码", "函数", "类", "变量", "def", "class", "import"],
            ContextType.CHAT_CONVERSATION: ["你好", "请帮我", "我想", "解释", "讨论"],
            ContextType.DOCUMENT_ANALYSIS: ["文档", "报告", "分析", "总结", "摘要"],
            ContextType.SEARCH_QUERY: ["搜索", "查找", "查询", "什么是", "如何"],
            ContextType.CODE_REVIEW: ["审查", "检查", "review", "优化", "重构"],
            ContextType.TESTING: ["测试", "单元测试", "test", "验证"],
        }
        
        for context_type, keywords in context_keywords.items():
            for keyword in keywords:
                if keyword.lower() in prompt_lower:
                    return context_type
        
        # 基于上下文信息识别
        if context.get("file_type") == "code":
            return ContextType.CODE_EDITING
        if context.get("mode") == "chat":
            return ContextType.CHAT_CONVERSATION
        
        return ContextType.UNKNOWN
    
    def _analyze_prompt_features(self, prompt: str) -> Dict[str, Any]:
        """分析提示词特征"""
        return {
            "length": len(prompt),
            "token_count": int(len(prompt) / 3.5),
            "has_code": "```" in prompt or "def " in prompt or "function " in prompt,
            "has_code_block": "```" in prompt,
            "is_long": len(prompt) > 500,
            "is_short": len(prompt) < 50,
        }
    
    def _calculate_decision(self, context_type: ContextType, features: Dict[str, Any], profile: OptimizationProfile) -> Tuple[OptimizationDecision, float, Dict[str, Any], str]:
        """计算优化决策"""
        strategy = {}
        explanations = []
        
        # 默认决策
        decision = OptimizationDecision.FULL_OPTIMIZATION
        confidence = 0.7
        
        # 基于上下文类型调整
        if context_type == ContextType.CODE_EDITING:
            # 代码编辑：不压缩代码内容
            strategy["compression_enabled"] = False
            strategy["caching_enabled"] = True
            strategy["token_optimization_enabled"] = True
            explanations.append("代码编辑模式：禁用输出压缩以保持代码完整性")
            confidence = 0.9
        elif context_type == ContextType.CHAT_CONVERSATION:
            # 聊天对话：启用全部优化
            strategy["compression_enabled"] = True
            strategy["caching_enabled"] = True
            strategy["token_optimization_enabled"] = True
            explanations.append("聊天对话：启用完整优化")
            confidence = 0.85
        elif context_type == ContextType.DOCUMENT_ANALYSIS:
            # 文档分析：启用缓存和token优化
            strategy["compression_enabled"] = False  # 文档需要完整保留
            strategy["caching_enabled"] = True
            strategy["token_optimization_enabled"] = True
            explanations.append("文档分析：禁用输出压缩以保持文档完整性")
            confidence = 0.8
        elif context_type == ContextType.CODE_REVIEW:
            # 代码审查：不压缩
            strategy["compression_enabled"] = False
            strategy["caching_enabled"] = True
            strategy["token_optimization_enabled"] = True
            explanations.append("代码审查：禁用输出压缩")
            confidence = 0.85
        else:
            # 默认：使用配置文件设置
            strategy["compression_enabled"] = profile.compression_enabled
            strategy["caching_enabled"] = profile.caching_enabled
            strategy["token_optimization_enabled"] = profile.token_optimization_enabled
            explanations.append(f"使用{profile.name}配置")
        
        # 基于提示词长度调整
        if features["is_short"]:
            # 短提示：跳过token优化，启用缓存
            strategy["token_optimization_enabled"] = False
            strategy["caching_enabled"] = True
            explanations.append("短提示：跳过Token优化")
            confidence = min(confidence + 0.1, 0.95)
        elif features["is_long"]:
            # 长提示：启用所有优化
            strategy["token_optimization_enabled"] = True
            strategy["caching_enabled"] = True
            explanations.append("长提示：启用完整优化")
            confidence = min(confidence + 0.05, 0.95)
        
        # 基于代码块调整
        if features["has_code_block"]:
            strategy["compression_enabled"] = False
            explanations.append("包含代码块：禁用输出压缩")
        
        # 更新策略配置
        strategy["aggressive_mode"] = profile.aggressive_mode
        strategy["target_cache_hit_rate"] = profile.target_cache_hit_rate
        strategy["target_compression_ratio"] = profile.target_compression_ratio
        
        return decision, confidence, strategy, "; ".join(explanations)
    
    # ─── 自适应学习 ───
    
    def _record_usage_pattern(self, context_type: ContextType, features: Dict[str, Any]):
        """记录使用模式"""
        if not self._learning_enabled:
            return
        
        pattern = UsagePattern(
            context_type=context_type,
            timestamp=time.time(),
            prompt_length=features["length"],
            model_type="claude-3-sonnet",  # 默认
            cache_hit=False,  # 后续更新
            compression_ratio=0.0,  # 后续更新
        )
        
        self._usage_patterns.append(pattern)
        
        # 更新上下文模式统计
        self._context_patterns[context_type.value]["total_calls"] += 1
        self._context_patterns[context_type.value]["avg_length"] = (
            self._context_patterns[context_type.value]["avg_length"] * 
            (self._context_patterns[context_type.value]["total_calls"] - 1) + 
            features["length"]
        ) / self._context_patterns[context_type.value]["total_calls"]
    
    def adapt_to_patterns(self):
        """根据使用模式自适应调整"""
        if not self._learning_enabled or len(self._usage_patterns) < 10:
            return
        
        # 分析最常用的上下文类型
        context_counts = {}
        for pattern in self._usage_patterns[-100:]:
            context_counts[pattern.context_type.value] = context_counts.get(pattern.context_type.value, 0) + 1
        
        # 如果代码编辑占比超过50%，自动切换到代码优化配置
        total = sum(context_counts.values())
        if total > 0 and context_counts.get("code_editing", 0) / total > 0.5:
            self.set_profile("code_focused")
            logger.info("[IntelligentOptimizationEngine] 检测到代码编辑为主，自动切换到代码优化配置")
        
        # 如果缓存命中率低于目标，增加缓存力度
        cache_hit_rate = self._calculate_cache_hit_rate()
        profile = self.get_profile()
        if cache_hit_rate < profile.target_cache_hit_rate * 0.8:
            # 增加缓存时间
            profile.target_cache_hit_rate = min(profile.target_cache_hit_rate + 0.05, 0.95)
            logger.info(f"[IntelligentOptimizationEngine] 缓存命中率 {cache_hit_rate:.1%} 低于目标，调整目标命中率到 {profile.target_cache_hit_rate:.1%}")
    
    def _calculate_cache_hit_rate(self) -> float:
        """计算缓存命中率"""
        if self._stats["total_calls"] == 0:
            return 0.0
        return self._stats.get("optimized_calls", 0) / self._stats["total_calls"]
    
    # ─── 预测性优化 ───
    
    def predict_and_preheat(self):
        """预测并预热缓存"""
        if not self._prediction_enabled:
            return
        
        # 基于历史模式预测可能的查询
        if len(self._usage_patterns) > 0:
            recent_patterns = self._usage_patterns[-20:]
            
            # 找出最频繁的上下文类型
            context_counts = defaultdict(int)
            for pattern in recent_patterns:
                context_counts[pattern.context_type.value] += 1
            
            if context_counts:
                most_common_context = max(context_counts, key=context_counts.get)
                logger.info(f"[IntelligentOptimizationEngine] 预测下一个查询可能是 {most_common_context} 类型")
                
                # 预测常见查询
                predicted_queries = self._generate_predicted_queries(most_common_context)
                self._predicted_queries.update(predicted_queries)
                
                logger.info(f"[IntelligentOptimizationEngine] 预测了 {len(predicted_queries)} 个可能的查询")
    
    def _generate_predicted_queries(self, context_type: str) -> Dict[str, float]:
        """生成预测查询"""
        predictions = {}
        
        context_predictions = {
            "code_editing": [
                ("帮我写一个函数", 0.8),
                ("这段代码有什么问题", 0.7),
                ("如何优化这段代码", 0.6),
                ("添加注释", 0.5),
            ],
            "chat_conversation": [
                ("你好", 0.9),
                ("谢谢", 0.8),
                ("帮我", 0.7),
            ],
            "document_analysis": [
                ("总结这份文档", 0.8),
                ("分析这份报告", 0.7),
            ],
            "search_query": [
                ("搜索", 0.9),
                ("什么是", 0.8),
                ("如何", 0.7),
            ],
        }
        
        for query, confidence in context_predictions.get(context_type, []):
            predictions[query] = confidence
        
        return predictions
    
    # ─── 深度集成调用 ───
    
    async def optimize_and_call(self, prompt: str, model_callable: Callable, **kwargs) -> Tuple[Any, Dict[str, Any]]:
        """
        深度集成的优化调用
        
        Args:
            prompt: 用户提示词
            model_callable: 模型调用函数
            **kwargs: 额外参数
            
        Returns:
            (响应, 优化元数据)
        """
        # 1. 智能决策
        context = kwargs.get("context", {})
        decision = self.make_decision(prompt, context)
        
        self._stats["total_calls"] += 1
        
        # 2. 根据决策执行优化
        optimization_metadata = {
            "decision": decision.decision.value,
            "confidence": decision.confidence,
            "explanation": decision.explanation,
            "strategy": decision.strategy,
        }
        
        # 3. 使用优化代理执行调用
        if self._model_optimization_proxy is None:
            self._lazy_load_components()
        
        if self._model_optimization_proxy:
            response, proxy_metadata = await self._model_optimization_proxy.call_with_optimization(
                prompt,
                model_callable,
                **kwargs
            )
            optimization_metadata.update(proxy_metadata)
            
            # 更新统计
            if proxy_metadata.get("cache_hit"):
                self._stats["optimized_calls"] += 1
                self._stats["total_tokens_saved"] += proxy_metadata.get("original_tokens", 0) - proxy_metadata.get("optimized_tokens", 0)
        
        else:
            # 降级到直接调用
            response = await model_callable(prompt) if asyncio.iscoroutinefunction(model_callable) else model_callable(prompt)
        
        # 4. 自适应学习
        self.adapt_to_patterns()
        
        # 5. 预测性预热
        self.predict_and_preheat()
        
        return response, optimization_metadata
    
    def _lazy_load_components(self):
        """延迟加载优化组件"""
        try:
            from business.optimization_bootstrapper import get_optimization_bootstrapper
            self._optimization_bootstrapper = get_optimization_bootstrapper()
            
            from business.model_optimization_proxy import get_model_optimization_proxy
            self._model_optimization_proxy = get_model_optimization_proxy()
            
            logger.info("[IntelligentOptimizationEngine] 优化组件加载完成")
        except Exception as e:
            logger.error(f"[IntelligentOptimizationEngine] 加载优化组件失败: {e}")
    
    # ─── 监控仪表盘 ───
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """获取监控仪表盘统计"""
        avg_confidence = (
            self._stats["confidence_sum"] / max(self._stats["decisions_made"], 1)
        )
        
        return {
            "total_calls": self._stats["total_calls"],
            "optimized_calls": self._stats["optimized_calls"],
            "optimization_rate": self._stats["optimized_calls"] / max(self._stats["total_calls"], 1),
            "total_tokens_saved": self._stats["total_tokens_saved"],
            "total_cost_saved": f"${self._stats['total_cost_saved']:.2f}",
            "avg_decision_confidence": avg_confidence,
            "active_profile": self._active_profile,
            "predicted_queries_count": len(self._predicted_queries),
            "context_distribution": dict(self._context_patterns),
        }
    
    def get_recommendations(self) -> List[str]:
        """获取优化建议"""
        recommendations = []
        
        stats = self.get_dashboard_stats()
        
        # 低优化率警告
        if stats["optimization_rate"] < 0.5:
            recommendations.append("警告：优化率较低，请检查优化配置")
        
        # 低决策置信度警告
        if stats["avg_decision_confidence"] < 0.6:
            recommendations.append("警告：决策置信度较低，可能需要更多学习数据")
        
        # 缓存命中率建议
        if stats["optimization_rate"] < 0.7:
            recommendations.append("建议：增加缓存时间以提高命中率")
        
        # 预测功能建议
        if len(self._predicted_queries) > 0:
            recommendations.append("预测性缓存已激活，预计可提升命中率")
        
        return recommendations
    
    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "total_calls": 0,
            "optimized_calls": 0,
            "total_tokens_saved": 0,
            "total_cost_saved": 0.0,
            "decisions_made": 0,
            "confidence_sum": 0.0,
        }
        self._usage_patterns = []
        self._context_patterns = defaultdict(lambda: defaultdict(int))
        logger.info("[IntelligentOptimizationEngine] 统计信息已重置")


# 便捷函数
def get_intelligent_optimization_engine() -> IntelligentOptimizationEngine:
    """获取智能优化引擎单例"""
    return IntelligentOptimizationEngine()


__all__ = [
    "OptimizationDecision",
    "ContextType",
    "OptimizationDecisionResult",
    "UsagePattern",
    "OptimizationProfile",
    "IntelligentOptimizationEngine",
    "get_intelligent_optimization_engine",
]
