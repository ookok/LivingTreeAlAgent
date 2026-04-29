"""
智能匹配引擎
Pattern Matcher - 触发条件、意图识别、模式推荐
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import threading
from difflib import SequenceMatcher

from .models import (
    MessagePattern, TriggerType, TriggerCondition, OperatorType,
    PatternCategory, TriggerConfig
)
from .variable_resolver import VariableResolver, ResolverContext


@dataclass
class MatchResult:
    """匹配结果"""
    pattern: MessagePattern
    confidence: float = 0.0
    match_type: str = ""           # exact, keyword, context, similarity
    matched_keywords: List[str] = field(default_factory=list)
    matched_conditions: List[str] = field(default_factory=list)
    reasoning: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "pattern_id": self.pattern.id,
            "pattern_name": self.pattern.name,
            "confidence": self.confidence,
            "match_type": self.match_type,
            "matched_keywords": self.matched_keywords,
            "matched_conditions": self.matched_conditions,
            "reasoning": self.reasoning
        }


@dataclass
class IntentResult:
    """意图识别结果"""
    primary_intent: str
    secondary_intents: List[str] = field(default_factory=list)
    entities: Dict[str, List[str]] = field(default_factory=dict)
    sentiment: str = "neutral"
    confidence: float = 0.0
    keywords: List[str] = field(default_factory=list)
    topic: str = "general"

    def to_dict(self) -> Dict:
        return {
            "primary_intent": self.primary_intent,
            "secondary_intents": self.secondary_intents,
            "entities": self.entities,
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "keywords": self.keywords,
            "topic": self.topic
        }


class IntentClassifier:
    """意图分类器"""

    # 意图关键词映射
    INTENT_KEYWORDS = {
        "analysis": ["分析", "分析一下", "请分析", "分析报告", "分析结果", "分析一下", "analyze"],
        "writing": ["写", "帮我写", "创作", "起草", "编写", "撰写", "write", "compose"],
        "coding": ["代码", "程序", "函数", "实现", "编程", "开发", "code", "program", "function"],
        "design": ["设计", "方案", "架构", "规划", "蓝图", "design", "architecture"],
        "decision": ["选择", "决策", "比较", "建议", "推荐", "decision", "choose", "compare"],
        "research": ["研究", "调研", "调查", "搜索", "查找", "research", "investigate", "search"],
        "brainstorm": ["想法", "创意", "头脑风暴", "建议", "点子", "idea", "brainstorm"],
        "learning": ["学习", "了解", "解释", "教程", "讲解", "learn", "explain", "teach"],
        "planning": ["计划", "安排", "日程", "时间表", "plan", "schedule", "arrange"],
        "review": ["审查", "检查", "审核", "评估", "review", "check", "audit"],
        "problem_solving": ["问题", "解决", "方案", "怎么办", "如何解决", "problem", "solve", "fix"],
        "chat": ["聊天", "对话", "闲聊", "chat", "talk", "conversation"]
    }

    # 实体识别模式
    ENTITY_PATTERNS = {
        "language": ["python", "javascript", "java", "c++", "go", "rust", "typescript", "js", "py"],
        "format": ["markdown", "json", "xml", "html", "csv", "表格", "列表", "报告"],
        "domain": ["技术", "商业", "金融", "医疗", "教育", "法律", "科学", "艺术"]
    }

    def __init__(self):
        self._custom_intents: Dict[str, List[str]] = {}

    def register_intent_keywords(self, intent: str, keywords: List[str]):
        """注册自定义意图关键词"""
        self._custom_intents[intent] = keywords

    def classify(self, text: str) -> IntentResult:
        """对文本进行意图分类"""
        if not text:
            return IntentResult(primary_intent="unknown", confidence=0.0)

        text_lower = text.lower()
        text_no_space = text.replace(" ", "")
        text_lower_nospace = text_lower.replace(" ", "")

        intent_scores: Dict[str, float] = {}
        matched_keywords: Dict[str, List[str]] = {}

        # 计算每个意图的得分
        all_intents = {**self.INTENT_KEYWORDS, **self._custom_intents}
        for intent, keywords in all_intents.items():
            score = 0.0
            matched = []
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in text_lower or keyword_lower in text_lower_nospace:
                    # 完整匹配
                    score += 1.0
                    matched.append(keyword)
                elif keyword_lower in text_lower_nospace:
                    # 无空格匹配
                    score += 0.8
                    matched.append(keyword)

            if matched:
                # 根据匹配密度调整分数
                density = len(matched) / len(keywords) if keywords else 0
                intent_scores[intent] = score * (1 + density * 0.5)

        # 排序并选择最佳意图
        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)

        if sorted_intents:
            top_intent, top_score = sorted_intents[0]
            primary = top_intent
            secondary = [i[0] for i in sorted_intents[1:4] if i[1] > 0.5]
            confidence = min(top_score / 3.0, 1.0)
        else:
            primary = "chat"
            secondary = []
            confidence = 0.5

        # 识别实体
        entities = self._extract_entities(text)

        # 识别情感
        sentiment = self._analyze_sentiment(text)

        # 识别主题
        topic = self._identify_topic(text, primary)

        return IntentResult(
            primary_intent=primary,
            secondary_intents=secondary,
            entities=entities,
            sentiment=sentiment,
            confidence=confidence,
            keywords=matched_keywords.get(primary, []),
            topic=topic
        )

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """提取实体"""
        entities: Dict[str, List[str]] = {}
        text_lower = text.lower()

        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            matched = [p for p in patterns if p in text_lower]
            if matched:
                entities[entity_type] = matched

        return entities

    def _analyze_sentiment(self, text: str) -> str:
        """简单情感分析"""
        positive = ["好", "棒", "优秀", "喜欢", "谢谢", "很好", "期待", "完美"]
        negative = ["问题", "错误", "失败", "糟糕", "不喜欢", "困扰", "困难", "麻烦"]

        pos_count = sum(1 for w in positive if w in text)
        neg_count = sum(1 for w in negative if w in text)

        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"

    def _identify_topic(self, text: str, intent: str) -> str:
        """识别主题"""
        # 基于意图和关键词识别主题
        topic_keywords = {
            "技术": ["代码", "程序", "系统", "软件", "api", "技术", "computer", "tech"],
            "商业": ["商业", "市场", "客户", "销售", "business", "market", "sales"],
            "金融": ["投资", "股票", "财务", "金融", "finance", "investment", "stock"],
            "教育": ["学习", "教育", "课程", "学生", "教育", "learning", "education"],
            "生活": ["生活", "日常", "家庭", "life", "daily", "home"]
        }

        for topic, keywords in topic_keywords.items():
            if any(k in text.lower() for k in keywords):
                return topic

        return "general"


class PatternMatcher:
    """模式匹配引擎"""

    def __init__(self, resolver: VariableResolver = None):
        self._resolver = resolver or VariableResolver()
        self._intent_classifier = IntentClassifier()
        self._match_cache: Dict[str, List[MatchResult]] = {}
        self._cache_lock = threading.Lock()

    def set_intent_classifier(self, classifier: IntentClassifier):
        """设置意图分类器"""
        self._intent_classifier = classifier

    def match(
        self,
        patterns: List[MessagePattern],
        context: ResolverContext,
        threshold: float = 0.5
    ) -> List[MatchResult]:
        """匹配最佳模式"""
        if not patterns or not context.user_input:
            return []

        results = []
        for pattern in patterns:
            if not pattern.enabled:
                continue

            match_result = self._match_pattern(pattern, context)
            if match_result and match_result.confidence >= threshold:
                results.append(match_result)

        # 按置信度排序
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def _match_pattern(
        self,
        pattern: MessagePattern,
        context: ResolverContext
    ) -> Optional[MatchResult]:
        """匹配单个模式"""
        trigger = pattern.trigger
        user_input = context.user_input

        if trigger.type == TriggerType.MANUAL:
            # 手动模式不自动匹配
            return None

        confidence = 0.0
        matched_conditions = []
        matched_keywords = []
        reasoning = []

        # 关键词匹配
        if trigger.type == TriggerType.KEYWORD and trigger.keywords:
            kw_matches = self._match_keywords(user_input, trigger.keywords)
            if kw_matches:
                matched_keywords = kw_matches
                keyword_score = len(kw_matches) / len(trigger.keywords)
                confidence += keyword_score * 0.6
                reasoning.append(f"关键词匹配: {kw_matches}")

        # 条件匹配
        if trigger.conditions:
            for condition in trigger.conditions:
                if self._match_condition(condition, context):
                    matched_conditions.append(condition.field)
                    confidence += condition.confidence * 0.3

        # 上下文匹配
        if trigger.type == TriggerType.CONTEXT:
            context_score = self._match_context(pattern, context)
            if context_score > 0:
                confidence += context_score * 0.4
                reasoning.append(f"上下文匹配度: {context_score:.2f}")

        # 基于意图的匹配
        intent_result = self._intent_classifier.classify(user_input)
        pattern_intent = self._infer_pattern_intent(pattern)
        if pattern_intent == intent_result.primary_intent:
            confidence += 0.2
            reasoning.append(f"意图匹配: {pattern_intent}")

        if confidence > 0:
            return MatchResult(
                pattern=pattern,
                confidence=min(confidence, 1.0),
                match_type=self._get_match_type(trigger.type),
                matched_keywords=matched_keywords,
                matched_conditions=matched_conditions,
                reasoning="; ".join(reasoning)
            )

        return None

    def _match_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """匹配关键词"""
        text_lower = text.lower()
        text_nospace = text_lower.replace(" ", "")
        matched = []

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in text_lower or kw_lower in text_nospace:
                matched.append(kw)

        return matched

    def _match_condition(
        self,
        condition: TriggerCondition,
        context: ResolverContext
    ) -> bool:
        """匹配触发条件"""
        field = condition.field
        operator = condition.operator
        value = condition.value

        # 获取字段值
        if field == "content":
            field_value = context.user_input
        elif field == "length":
            field_value = len(context.user_input)
        elif field == "history_length":
            field_value = len(context.conversation_history)
        else:
            field_value = getattr(context, field, "")

        # 执行比较
        return self._compare_values(field_value, operator, value)

    def _compare_values(self, field_value: Any, operator: OperatorType, target_value: Any) -> bool:
        """比较值"""
        if isinstance(operator, str):
            operator = OperatorType(operator)

        try:
            if operator == OperatorType.EQUALS:
                return str(field_value) == str(target_value)
            elif operator == OperatorType.NOT_EQUALS:
                return str(field_value) != str(target_value)
            elif operator == OperatorType.CONTAINS:
                return str(target_value) in str(field_value)
            elif operator == OperatorType.NOT_CONTAINS:
                return str(target_value) not in str(field_value)
            elif operator == OperatorType.STARTS_WITH:
                return str(field_value).startswith(str(target_value))
            elif operator == OperatorType.ENDS_WITH:
                return str(field_value).endswith(str(target_value))
            elif operator == OperatorType.REGEX:
                return bool(re.search(str(target_value), str(field_value)))
            elif operator == OperatorType.GREATER_THAN:
                return float(field_value) > float(target_value)
            elif operator == OperatorType.LESS_THAN:
                return float(field_value) < float(target_value)
            elif operator == OperatorType.GREATER_EQUAL:
                return float(field_value) >= float(target_value)
            elif operator == OperatorType.LESS_EQUAL:
                return float(field_value) <= float(target_value)
            elif operator == OperatorType.IN:
                return str(field_value) in (target_value if isinstance(target_value, list) else [target_value])
            elif operator == OperatorType.NOT_IN:
                return str(field_value) not in (target_value if isinstance(target_value, list) else [target_value])
        except (ValueError, TypeError):
            pass

        return False

    def _match_context(self, pattern: MessagePattern, context: ResolverContext) -> float:
        """匹配上下文"""
        # 简单的上下文匹配
        score = 0.0

        # 检查模式标签与输入的关联
        pattern_tags = set(pattern.tags)
        if pattern_tags:
            # 计算标签与输入的相似度
            input_words = set(context.user_input.lower().split())
            overlap = len(pattern_tags & input_words)
            if pattern_tags:
                score += overlap / len(pattern_tags)

        return min(score, 1.0)

    def _infer_pattern_intent(self, pattern: MessagePattern) -> str:
        """推断模式意图"""
        # 从模式名称和标签推断意图
        name_lower = pattern.name.lower()
        tags_lower = [t.lower() for t in pattern.tags]

        for intent, keywords in IntentClassifier.INTENT_KEYWORDS.items():
            if any(k in name_lower for k in keywords):
                return intent
            if any(k in t for t in tags_lower for k in keywords):
                return intent

        return "general"

    def _get_match_type(self, trigger_type: TriggerType) -> str:
        """获取匹配类型"""
        type_map = {
            TriggerType.AUTO: "auto",
            TriggerType.MANUAL: "manual",
            TriggerType.KEYWORD: "keyword",
            TriggerType.CONTEXT: "context",
            TriggerType.SCHEDULE: "schedule"
        }
        return type_map.get(trigger_type, "unknown")

    def recommend(
        self,
        patterns: List[MessagePattern],
        context: ResolverContext,
        limit: int = 5
    ) -> List[MatchResult]:
        """推荐最佳匹配模式"""
        matches = self.match(patterns, context, threshold=0.3)
        return matches[:limit]

    def similarity_score(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        return SequenceMatcher(None, text1, text2).ratio()

    def find_similar_patterns(
        self,
        patterns: List[MessagePattern],
        query: str,
        limit: int = 5
    ) -> List[Tuple[MessagePattern, float]]:
        """查找相似模式"""
        scores = []
        for pattern in patterns:
            # 基于名称和描述计算相似度
            name_sim = self.similarity_score(query, pattern.name)
            desc_sim = self.similarity_score(query, pattern.description) * 0.5
            tags_sim = max(
                [self.similarity_score(query, tag) for tag in pattern.tags] or [0]
            ) * 0.3
            total_sim = name_sim + desc_sim + tags_sim
            scores.append((pattern, total_sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:limit]


class PatternRecommender:
    """模式推荐器"""

    def __init__(self, matcher: PatternMatcher):
        self._matcher = matcher

    def recommend_by_intent(
        self,
        patterns: List[MessagePattern],
        intent: IntentResult,
        context: ResolverContext
    ) -> List[MatchResult]:
        """基于意图推荐"""
        # 首先进行意图匹配
        results = []
        for pattern in patterns:
            if not pattern.enabled:
                continue

            pattern_intent = self._matcher._infer_pattern_intent(pattern)
            confidence = 0.0
            reasoning = []

            # 主意图匹配
            if pattern_intent == intent.primary_intent:
                confidence += 0.5
                reasoning.append(f"主意图匹配: {pattern_intent}")

            # 次意图匹配
            if pattern_intent in intent.secondary_intents:
                confidence += 0.2
                reasoning.append(f"次意图匹配: {pattern_intent}")

            # 标签匹配
            for tag in pattern.tags:
                if tag.lower() in intent.keywords:
                    confidence += 0.1

            # 实体匹配
            for entity_type, entities in intent.entities.items():
                if any(e in pattern.tags for e in entities):
                    confidence += 0.1

            if confidence > 0.2:
                results.append(MatchResult(
                    pattern=pattern,
                    confidence=min(confidence, 1.0),
                    match_type="intent",
                    reasoning="; ".join(reasoning)
                ))

        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def recommend_by_history(
        self,
        patterns: List[MessagePattern],
        recent_pattern_ids: List[str]
    ) -> List[MatchResult]:
        """基于历史推荐"""
        results = []
        for pattern in patterns:
            if not pattern.enabled:
                continue

            # 计算使用频率
            if pattern.id in recent_pattern_ids:
                idx = recent_pattern_ids.index(pattern.id)
                confidence = 1.0 / (idx + 1)  # 最近使用的权重更高
            else:
                confidence = 0.1 * (pattern.metadata.usage_count / 100)  # 使用次数加权

            if confidence > 0.05:
                results.append(MatchResult(
                    pattern=pattern,
                    confidence=confidence,
                    match_type="history",
                    reasoning=f"历史使用模式 (权重: {confidence:.2f})"
                ))

        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def recommend_cold_start(
        self,
        patterns: List[MessagePattern],
        context: ResolverContext
    ) -> List[MatchResult]:
        """冷启动推荐（无历史数据时）"""
        results = []

        # 推荐最受欢迎的系统模式
        system_patterns = [p for p in patterns if p.is_system]
        system_patterns.sort(key=lambda p: p.metadata.popularity, reverse=True)

        for i, pattern in enumerate(system_patterns[:5]):
            confidence = 0.5 - (i * 0.1)  # 递减置信度
            results.append(MatchResult(
                pattern=pattern,
                confidence=confidence,
                match_type="popular",
                reasoning=f"热门系统模式 #{i+1}"
            ))

        return results


# 全局实例
_matcher_instance = None


def get_pattern_matcher(resolver: VariableResolver = None) -> PatternMatcher:
    """获取模式匹配器实例"""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = PatternMatcher(resolver)
    return _matcher_instance


def get_intent_classifier() -> IntentClassifier:
    """获取意图分类器"""
    return IntentClassifier()
