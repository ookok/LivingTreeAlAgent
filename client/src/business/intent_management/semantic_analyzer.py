"""
Deep Semantic Analyzer

深度语义感知系统，提供多维度语义分析、逻辑形式转换、上下文建模能力。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SemanticRole(Enum):
    """语义角色"""
    AGENT = "agent"           # 施事（动作的执行者）
    PATIENT = "patient"       # 受事（动作的承受者）
    INSTRUMENT = "instrument" # 工具（动作的工具）
    LOCATION = "location"     # 地点
    TIME = "time"             # 时间
    GOAL = "goal"             # 目标
    SOURCE = "source"         # 来源


class SentimentType(Enum):
    """情感类型"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class DomainType(Enum):
    """领域类型"""
    TECHNOLOGY = "technology"
    LIFESTYLE = "lifestyle"
    ENTERTAINMENT = "entertainment"
    BUSINESS = "business"
    EDUCATION = "education"
    HEALTH = "health"
    OTHER = "other"


class ComplexityLevel(Enum):
    """复杂程度"""
    SIMPLE = "simple"         # 简单（单句，无嵌套）
    MEDIUM = "medium"         # 中等（多句，有简单嵌套）
    COMPLEX = "complex"       # 复杂（多句，有复杂嵌套）
    HIGHLY_COMPLEX = "highly_complex"  # 高度复杂（多意图、条件逻辑）


@dataclass
class SemanticRoleLabel:
    """语义角色标注"""
    role: SemanticRole
    text: str
    start: int
    end: int
    confidence: float


@dataclass
class SemanticAnalysis:
    """语义分析结果"""
    text: str
    roles: List[SemanticRoleLabel] = field(default_factory=list)
    sentiment: SentimentType = SentimentType.NEUTRAL
    sentiment_score: float = 0.0
    domain: DomainType = DomainType.OTHER
    domain_confidence: float = 0.0
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    implicit_intents: List[str] = field(default_factory=list)
    key_concepts: List[str] = field(default_factory=list)


@dataclass
class LogicalForm:
    """逻辑形式"""
    predicate: str
    arguments: List[Dict[str, Any]] = field(default_factory=list)
    operators: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)


@dataclass
class ContextModel:
    """上下文模型"""
    conversation_id: str
    topics: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    intent_history: List[str] = field(default_factory=list)
    user_profile: Optional[Dict[str, Any]] = None
    turn_count: int = 0


class DeepSemanticAnalyzer:
    """
    深度语义感知系统
    
    核心功能：
    - 语义角色标注
    - 情感分析
    - 领域识别
    - 复杂程度评估
    - 隐含意图挖掘
    - 逻辑形式转换
    - 上下文建模
    """
    
    def __init__(self):
        """初始化语义分析器"""
        self._entity_recognizer = None
        
        self._init_dependencies()
        logger.info("DeepSemanticAnalyzer 初始化完成")
    
    def _init_dependencies(self):
        """初始化依赖模块"""
        try:
            from ..entity_management import get_entity_recognizer
            self._entity_recognizer = get_entity_recognizer()
            logger.info("依赖模块加载成功")
        except ImportError as e:
            logger.warning(f"依赖模块加载失败: {e}")
    
    def analyze(self, text: str) -> SemanticAnalysis:
        """
        多维度语义分析
        
        Args:
            text: 输入文本
            
        Returns:
            SemanticAnalysis 语义分析结果
        """
        analysis = SemanticAnalysis(text=text)
        
        # 语义角色标注
        analysis.roles = self._label_semantic_roles(text)
        
        # 情感分析
        sentiment_result = self._analyze_sentiment(text)
        analysis.sentiment = sentiment_result["type"]
        analysis.sentiment_score = sentiment_result["score"]
        
        # 领域识别
        domain_result = self._identify_domain(text)
        analysis.domain = domain_result["type"]
        analysis.domain_confidence = domain_result["confidence"]
        
        # 复杂程度评估
        analysis.complexity = self._assess_complexity(text)
        
        # 隐含意图挖掘
        analysis.implicit_intents = self._mine_implicit_intents(text)
        
        # 关键概念提取
        analysis.key_concepts = self._extract_key_concepts(text)
        
        return analysis
    
    def _label_semantic_roles(self, text: str) -> List[SemanticRoleLabel]:
        """
        语义角色标注
        
        Args:
            text: 输入文本
            
        Returns:
            List 语义角色标注列表
        """
        roles = []
        
        # 规则匹配语义角色
        patterns = {
            SemanticRole.AGENT: ["我", "我们", "你", "他", "她", "它", "他们", "谁"],
            SemanticRole.PATIENT: ["问题", "错误", "事情", "任务", "工作", "东西"],
            SemanticRole.INSTRUMENT: ["用", "通过", "使用", "借助"],
            SemanticRole.LOCATION: ["在", "到", "从", "位于"],
            SemanticRole.TIME: ["现在", "今天", "明天", "昨天", "最近", "之前"],
            SemanticRole.GOAL: ["为了", "目的是", "想要"],
            SemanticRole.SOURCE: ["来自", "从", "源于"],
        }
        
        for role, keywords in patterns.items():
            for keyword in keywords:
                if keyword in text:
                    idx = text.index(keyword)
                    roles.append(SemanticRoleLabel(
                        role=role,
                        text=keyword,
                        start=idx,
                        end=idx + len(keyword),
                        confidence=0.7,
                    ))
        
        return roles
    
    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        情感分析
        
        Args:
            text: 输入文本
            
        Returns:
            Dict 情感分析结果
        """
        positive_words = ["好", "不错", "太棒", "感谢", "谢谢", "喜欢", "满意"]
        negative_words = ["问题", "错误", "失败", "不行", "糟糕", "麻烦", "难"]
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return {"type": SentimentType.POSITIVE, "score": min(positive_count * 0.3, 1.0)}
        elif negative_count > positive_count:
            return {"type": SentimentType.NEGATIVE, "score": min(negative_count * 0.3, 1.0)}
        else:
            return {"type": SentimentType.NEUTRAL, "score": 0.0}
    
    def _identify_domain(self, text: str) -> Dict[str, Any]:
        """
        领域识别
        
        Args:
            text: 输入文本
            
        Returns:
            Dict 领域识别结果
        """
        domain_keywords = {
            DomainType.TECHNOLOGY: ["编程", "代码", "软件", "算法", "框架", "API", "开发"],
            DomainType.LIFESTYLE: ["生活", "美食", "旅行", "购物", "健康"],
            DomainType.ENTERTAINMENT: ["电影", "游戏", "音乐", "娱乐"],
            DomainType.BUSINESS: ["公司", "市场", "营销", "商业", "投资"],
            DomainType.EDUCATION: ["学习", "教育", "课程", "考试", "学校"],
            DomainType.HEALTH: ["健康", "医疗", "疾病", "治疗"],
        }
        
        scores = {}
        for domain, keywords in domain_keywords.items():
            scores[domain] = sum(1 for keyword in keywords if keyword in text)
        
        if not scores or max(scores.values()) == 0:
            return {"type": DomainType.OTHER, "confidence": 0.0}
        
        max_domain = max(scores, key=scores.get)
        max_count = scores[max_domain]
        
        return {
            "type": max_domain,
            "confidence": min(max_count * 0.2, 1.0),
        }
    
    def _assess_complexity(self, text: str) -> ComplexityLevel:
        """
        复杂程度评估
        
        Args:
            text: 输入文本
            
        Returns:
            ComplexityLevel 复杂程度
        """
        # 基于句子数量和特殊字符判断
        sentence_count = text.count("。") + text.count("？") + text.count("！")
        conditional_count = text.count("如果") + text.count("假设") + text.count("否则")
        nested_count = text.count("(") + text.count("【") + text.count("「")
        
        if sentence_count <= 1 and conditional_count == 0:
            return ComplexityLevel.SIMPLE
        elif sentence_count <= 3 and conditional_count <= 1:
            return ComplexityLevel.MEDIUM
        elif sentence_count <= 5 or conditional_count <= 2:
            return ComplexityLevel.COMPLEX
        else:
            return ComplexityLevel.HIGHLY_COMPLEX
    
    def _mine_implicit_intents(self, text: str) -> List[str]:
        """
        挖掘隐含意图
        
        Args:
            text: 输入文本
            
        Returns:
            List 隐含意图列表
        """
        implicit_intents = []
        
        intent_patterns = {
            "need_explanation": ["为什么", "什么意思", "解释一下"],
            "need_example": ["举个例子", "例如", "比如"],
            "need_summary": ["总结一下", "概括", "要点"],
            "need_step_by_step": ["步骤", "如何", "怎么"],
            "need_evaluation": ["怎么样", "评价", "好不好"],
        }
        
        for intent, patterns in intent_patterns.items():
            if any(pattern in text for pattern in patterns):
                implicit_intents.append(intent)
        
        return implicit_intents
    
    def _extract_key_concepts(self, text: str) -> List[str]:
        """
        提取关键概念
        
        Args:
            text: 输入文本
            
        Returns:
            List 关键概念列表
        """
        concepts = []
        
        if self._entity_recognizer:
            result = self._entity_recognizer.recognize(text)
            for entity in result.entities:
                if entity.entity_type.value not in ["date", "number", "email", "phone", "url"]:
                    concepts.append(entity.text)
        
        return concepts[:10]  # 最多返回10个
    
    def semantic_parsing(self, text: str) -> LogicalForm:
        """
        将自然语言转换为逻辑形式
        
        Args:
            text: 输入文本
            
        Returns:
            LogicalForm 逻辑形式
        """
        # 简单实现：提取谓词和参数
        predicate = "unknown"
        arguments = []
        operators = []
        constraints = []
        
        # 识别谓词（动词）
        verbs = ["做", "解决", "处理", "创建", "分析", "理解", "解释", "生成"]
        for verb in verbs:
            if verb in text:
                predicate = verb
                break
        
        # 识别参数
        if self._entity_recognizer:
            result = self._entity_recognizer.recognize(text)
            for entity in result.entities:
                arguments.append({
                    "type": entity.entity_type.value,
                    "value": entity.text,
                })
        
        # 识别操作符
        if "和" in text:
            operators.append("AND")
        if "或" in text or "或者" in text:
            operators.append("OR")
        if "不" in text or "不是" in text:
            operators.append("NOT")
        
        # 识别约束
        if "必须" in text:
            constraints.append("required")
        if "大约" in text or "大概" in text:
            constraints.append("approximate")
        
        return LogicalForm(
            predicate=predicate,
            arguments=arguments,
            operators=operators,
            constraints=constraints,
        )
    
    def context_modeling(self, dialog_history: List[Dict[str, str]]) -> ContextModel:
        """
        建立对话上下文模型
        
        Args:
            dialog_history: 对话历史
            
        Returns:
            ContextModel 上下文模型
        """
        model = ContextModel(
            conversation_id="",
            topics=[],
            entities=[],
            intent_history=[],
            turn_count=len(dialog_history),
        )
        
        # 提取实体
        if self._entity_recognizer:
            all_text = " ".join(turn.get("text", "") for turn in dialog_history)
            result = self._entity_recognizer.recognize(all_text)
            model.entities = [{
                "text": e.text,
                "type": e.entity_type.value,
            } for e in result.entities]
        
        # 提取主题（基于高频实体）
        entity_counts = {}
        for entity in model.entities:
            entity_counts[entity["text"]] = entity_counts.get(entity["text"], 0) + 1
        
        # 取出现次数最多的3个作为主题
        sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
        model.topics = [e[0] for e in sorted_entities[:3]]
        
        # 提取意图历史
        for turn in dialog_history:
            if "intent" in turn:
                model.intent_history.append(turn["intent"])
        
        return model


# 全局语义分析器实例
_analyzer_instance = None

def get_deep_semantic_analyzer() -> DeepSemanticAnalyzer:
    """获取全局深度语义分析器实例"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = DeepSemanticAnalyzer()
    return _analyzer_instance