"""语义分析创新模块 - 多粒度语义理解与领域自适应"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio

class SentimentType(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

class DomainType(Enum):
    GENERAL = "general"
    TECHNICAL = "technical"
    FINANCIAL = "financial"
    MEDICAL = "medical"
    EDUCATIONAL = "educational"

@dataclass
class SemanticAnalysisResult:
    """语义分析结果"""
    entities: List[Dict[str, Any]]
    sentiment: SentimentType
    sentiment_intensity: float
    topics: List[str]
    domain: DomainType
    domain_confidence: float
    key_phrases: List[str]

class MultiGranularitySemanticAnalyzer:
    """多粒度语义分析器"""
    
    def __init__(self):
        self._entity_patterns = {
            'person': ['姓名', '谁', '他', '她', '他们'],
            'location': ['哪里', '地点', '位置', '地址'],
            'time': ['何时', '时间', '日期', '今天', '明天'],
            'number': ['多少', '几个', '数量', '价格'],
        }
    
    def analyze(self, text: str) -> Dict[str, Any]:
        """多粒度分析"""
        return {
            'word_level': self._analyze_words(text),
            'phrase_level': self._analyze_phrases(text),
            'sentence_level': self._analyze_sentences(text),
            'paragraph_level': self._analyze_paragraphs(text)
        }
    
    def _analyze_words(self, text: str) -> List[Dict[str, str]]:
        """词级分析 - 实体识别"""
        entities = []
        
        for entity_type, patterns in self._entity_patterns.items():
            for pattern in patterns:
                if pattern in text:
                    entities.append({'type': entity_type, 'value': pattern})
        
        return entities
    
    def _analyze_phrases(self, text: str) -> List[str]:
        """短语级分析 - 关键词提取"""
        keywords = []
        
        important_words = ['需要', '想要', '帮助', '创建', '分析', '搜索', '学习']
        for word in important_words:
            if word in text:
                keywords.append(word)
        
        return keywords
    
    def _analyze_sentences(self, text: str) -> Dict[str, Any]:
        """句子级分析"""
        sentences = text.split('。')
        return {
            'sentence_count': len([s for s in sentences if s.strip()]),
            'avg_length': len(text) / max(1, len(sentences))
        }
    
    def _analyze_paragraphs(self, text: str) -> Dict[str, Any]:
        """段落级分析 - 主题建模"""
        topics = []
        
        topic_keywords = {
            '技术': ['代码', '程序', '开发', '软件', 'Python', 'AI', '机器学习'],
            '财务': ['钱', '价格', '成本', '预算', '收入', '支出'],
            '健康': ['健康', '身体', '疾病', '治疗', '医院'],
            '教育': ['学习', '课程', '知识', '学校', '培训'],
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text for keyword in keywords):
                topics.append(topic)
        
        return {'topics': topics}

class EmotionalSemanticAnalyzer:
    """情感语义分析器"""
    
    def __init__(self):
        self._positive_words = ['高兴', '开心', '喜欢', '好', '棒', '优秀', '满意']
        self._negative_words = ['难过', '伤心', '讨厌', '坏', '差', '糟糕', '失望']
    
    def analyze(self, text: str) -> Dict[str, Any]:
        """分析情感语义"""
        positive_count = sum(1 for word in self._positive_words if word in text)
        negative_count = sum(1 for word in self._negative_words if word in text)
        
        if positive_count > negative_count:
            sentiment = SentimentType.POSITIVE
            intensity = positive_count / (positive_count + negative_count + 1)
        elif negative_count > positive_count:
            sentiment = SentimentType.NEGATIVE
            intensity = negative_count / (positive_count + negative_count + 1)
        else:
            sentiment = SentimentType.NEUTRAL
            intensity = 0.5
        
        return {
            'sentiment': sentiment,
            'intensity': intensity,
            'context': self._analyze_context(text)
        }
    
    def _analyze_context(self, text: str) -> Dict[str, Any]:
        """分析情感上下文"""
        return {
            'is_question': text.endswith('?') or text.endswith('？'),
            'is_command': text.endswith('!') or text.endswith('！'),
            'length': len(text)
        }

class DomainAdaptiveSemanticAnalyzer:
    """领域自适应语义分析器"""
    
    def __init__(self):
        self._domain_keywords: Dict[DomainType, List[str]] = {
            DomainType.TECHNICAL: ['代码', '程序', 'API', '框架', '开发', '部署'],
            DomainType.FINANCIAL: ['股票', '基金', '投资', '收益', '风险', '财务'],
            DomainType.MEDICAL: ['疾病', '治疗', '药物', '医生', '诊断', '健康'],
            DomainType.EDUCATIONAL: ['学习', '课程', '考试', '知识', '培训', '学校'],
        }
    
    def analyze(self, text: str, domain: Optional[DomainType] = None) -> SemanticAnalysisResult:
        """领域特定语义分析"""
        if domain is None:
            domain = self._detect_domain(text)
        
        domain_confidence = self._calculate_domain_confidence(text, domain)
        
        entities = self._extract_entities(text, domain)
        sentiment_analysis = EmotionalSemanticAnalyzer().analyze(text)
        topics = self._extract_topics(text, domain)
        key_phrases = self._extract_key_phrases(text, domain)
        
        return SemanticAnalysisResult(
            entities=entities,
            sentiment=sentiment_analysis['sentiment'],
            sentiment_intensity=sentiment_analysis['intensity'],
            topics=topics,
            domain=domain,
            domain_confidence=domain_confidence,
            key_phrases=key_phrases
        )
    
    def _detect_domain(self, text: str) -> DomainType:
        """检测领域"""
        max_count = 0
        detected_domain = DomainType.GENERAL
        
        for domain, keywords in self._domain_keywords.items():
            count = sum(1 for keyword in keywords if keyword in text)
            if count > max_count:
                max_count = count
                detected_domain = domain
        
        return detected_domain
    
    def _calculate_domain_confidence(self, text: str, domain: DomainType) -> float:
        """计算领域置信度"""
        keywords = self._domain_keywords.get(domain, [])
        if not keywords:
            return 0.5
        
        matches = sum(1 for keyword in keywords if keyword in text)
        return min(1.0, matches / len(keywords))
    
    def _extract_entities(self, text: str, domain: DomainType) -> List[Dict[str, Any]]:
        """提取实体"""
        entities = []
        
        if domain == DomainType.TECHNICAL:
            tech_keywords = ['Python', 'JavaScript', 'API', 'HTTP', 'JSON']
            for keyword in tech_keywords:
                if keyword in text:
                    entities.append({'type': 'technology', 'value': keyword})
        
        return entities
    
    def _extract_topics(self, text: str, domain: DomainType) -> List[str]:
        """提取主题"""
        return [domain.value]
    
    def _extract_key_phrases(self, text: str, domain: DomainType) -> List[str]:
        """提取关键词"""
        return [word for word in text.split() if len(word) > 2]

# 全局单例
_multi_granularity_analyzer = MultiGranularitySemanticAnalyzer()
_emotional_analyzer = EmotionalSemanticAnalyzer()
_domain_adaptive_analyzer = DomainAdaptiveSemanticAnalyzer()

def get_multi_granularity_semantic_analyzer() -> MultiGranularitySemanticAnalyzer:
    return _multi_granularity_analyzer

def get_emotional_semantic_analyzer() -> EmotionalSemanticAnalyzer:
    return _emotional_analyzer

def get_domain_adaptive_semantic_analyzer() -> DomainAdaptiveSemanticAnalyzer:
    return _domain_adaptive_analyzer