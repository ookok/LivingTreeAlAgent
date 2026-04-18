"""
消息模式与智能提示词系统
User-Defined Message Pattern & Smart Prompt System
"""

from typing import List, Dict, Any, Optional, Callable

from .models import (
    # 枚举
    TriggerType, OperatorType, VariableType, VariableSource,
    TemplateType, StructureType, ThinkingStyle, ThinkingDepth,
    OutputFormat, PatternCategory, SharingLicense,
    # 数据模型
    MessagePattern, VariableDefinition, TriggerCondition, TriggerConfig,
    TemplateConfig, ThinkingConfig, CustomRule, EnhancementConfig,
    ContextConfig, OutputConfig, PatternMetadata, SharingConfig,
    PatternUsageRecord, SystemVariables, BuiltInPatterns
)
from .pattern_manager import PatternManager, get_pattern_manager
from .variable_resolver import VariableResolver, ResolverContext, VariableValue, ContextBuilder, get_variable_resolver
from .pattern_matcher import (
    PatternMatcher, IntentClassifier, PatternRecommender, MatchResult, IntentResult,
    get_pattern_matcher, get_intent_classifier
)
from .prompt_generator import (
    PromptGenerator, GeneratedPrompt, GenerationOptions, PromptOptimizer,
    get_prompt_generator
)
from .effectiveness_evaluator import (
    EffectivenessEvaluator, EvaluationMetrics, EvaluationResult,
    UserFeedback, TextAnalyzer, PatternOptimizer, LearningSystem,
    get_effectiveness_evaluator
)


__all__ = [
    # 枚举
    'TriggerType', 'OperatorType', 'VariableType', 'VariableSource',
    'TemplateType', 'StructureType', 'ThinkingStyle', 'ThinkingDepth',
    'OutputFormat', 'PatternCategory', 'SharingLicense',
    # 数据模型
    'MessagePattern', 'VariableDefinition', 'TriggerCondition', 'TriggerConfig',
    'TemplateConfig', 'ThinkingConfig', 'CustomRule', 'EnhancementConfig',
    'ContextConfig', 'OutputConfig', 'PatternMetadata', 'SharingConfig',
    'PatternUsageRecord', 'SystemVariables', 'BuiltInPatterns',
    # 管理器
    'PatternManager', 'get_pattern_manager',
    # 变量解析
    'VariableResolver', 'ResolverContext', 'VariableValue', 'ContextBuilder',
    'get_variable_resolver',
    # 匹配引擎
    'PatternMatcher', 'IntentClassifier', 'PatternRecommender',
    'MatchResult', 'IntentResult',
    'get_pattern_matcher', 'get_intent_classifier',
    # 生成器
    'PromptGenerator', 'GeneratedPrompt', 'GenerationOptions', 'PromptOptimizer',
    'get_prompt_generator',
    # 评估器
    'EffectivenessEvaluator', 'EvaluationMetrics', 'EvaluationResult',
    'UserFeedback', 'TextAnalyzer', 'PatternOptimizer', 'LearningSystem',
    'get_effectiveness_evaluator'
]


class MessagePatternSystem:
    """消息模式系统 - 统一入口"""

    def __init__(self):
        self.manager = get_pattern_manager()
        self.resolver = get_variable_resolver()
        self.matcher = get_pattern_matcher(self.resolver)
        self.generator = get_prompt_generator(self.resolver)
        self.evaluator = get_effectiveness_evaluator()

    def process(
        self,
        user_input: str,
        conversation_history: List[dict] = None,
        user_profile: dict = None
    ):
        """处理用户输入并生成提示词"""
        from .variable_resolver import ContextBuilder

        # 构建上下文
        context = ContextBuilder.build_from_conversation(
            user_input=user_input,
            history=conversation_history or [],
            user_profile=user_profile or {}
        )

        # 获取所有可用模式
        patterns = self.manager.get_all_patterns()

        # 匹配最佳模式
        matches = self.matcher.match(patterns, context)

        if not matches:
            return None

        # 生成提示词
        best_match = matches[0]
        prompt = self.generator.generate(best_match.pattern, context)

        return {
            "match": best_match,
            "prompt": prompt,
            "alternatives": matches[1:5] if len(matches) > 1 else []
        }

    def get_recommendations(
        self,
        user_input: str,
        conversation_history: List[dict] = None
    ):
        """获取模式推荐"""
        from .variable_resolver import ContextBuilder

        context = ContextBuilder.build_from_conversation(
            user_input=user_input,
            history=conversation_history or [],
            user_profile={}
        )

        patterns = self.manager.get_all_patterns()

        # 基于意图推荐
        intent = self.matcher._intent_classifier.classify(user_input)
        recommender = PatternRecommender(self.matcher)
        recommendations = recommender.recommend_by_intent(patterns, intent, context)

        return {
            "intent": intent,
            "recommendations": recommendations
        }


# 全局系统实例
_system_instance = None


def get_message_pattern_system() -> MessagePatternSystem:
    """获取消息模式系统"""
    global _system_instance
    if _system_instance is None:
        _system_instance = MessagePatternSystem()
    return _system_instance
