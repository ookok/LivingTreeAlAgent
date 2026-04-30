"""
增强意图分类系统 (Enhanced Intent Classification System)

参考Rasa的实现方式，提供：
1. 多意图识别
2. 实体识别
3. 置信度阈值处理
4. 可配置的训练数据
5. 支持同义词和正则匹配

核心组件：
- IntentClassifier: 意图分类器主类
- EntityRecognizer: 实体识别器
- TrainingData: 训练数据管理
- ConfidenceProcessor: 置信度处理器
"""

import re
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger
from collections import defaultdict

# 导入统一意图定义
from business.intent_definitions import Intent


@dataclass
class IntentResult:
    """意图识别结果"""
    intent: str
    confidence: float
    entities: List[Dict] = field(default_factory=list)
    text: str = ""
    language: str = "zh"


@dataclass
class EntityMatch:
    """实体匹配结果"""
    entity: str
    value: str
    start: int
    end: int
    confidence: float = 1.0
    entity_type: str = "general"


@dataclass
class TrainingExample:
    """训练示例"""
    text: str
    intent: str
    entities: List[Dict] = field(default_factory=list)


class TrainingData:
    """训练数据管理（类似Rasa的nlu.yml）"""
    
    def __init__(self, data_path: str = None):
        self._logger = logger.bind(component="TrainingData")
        self._examples: List[TrainingExample] = []
        self._intent_examples: Dict[str, List[str]] = defaultdict(list)
        self._synonyms: Dict[str, str] = {}
        self._regex_features: List[Dict] = []
        
        if data_path:
            self.load_from_file(data_path)
        
        self._logger.info(f"训练数据加载完成: {len(self._examples)} 条示例")
    
    def load_from_file(self, file_path: str):
        """从文件加载训练数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 加载意图示例
                if "nlu" in data:
                    for item in data["nlu"]:
                        intent = item.get("intent")
                        examples = item.get("examples", [])
                        for example in examples:
                            self.add_example(example, intent)
                
                # 加载同义词
                if "synonyms" in data:
                    self._synonyms.update(data["synonyms"])
                
                # 加载正则特征
                if "regex_features" in data:
                    self._regex_features.extend(data["regex_features"])
            
            self._logger.info(f"从 {file_path} 加载训练数据")
        except Exception as e:
            self._logger.warning(f"加载训练数据失败: {e}")
    
    def add_example(self, text: str, intent: str, entities: List[Dict] = None):
        """添加训练示例"""
        example = TrainingExample(text=text, intent=intent, entities=entities or [])
        self._examples.append(example)
        self._intent_examples[intent].append(text)
    
    def get_intent_examples(self, intent: str) -> List[str]:
        """获取指定意图的示例"""
        return self._intent_examples.get(intent, [])
    
    def get_intents(self) -> List[str]:
        """获取所有意图"""
        return list(self._intent_examples.keys())
    
    def get_synonym(self, word: str) -> str:
        """获取同义词"""
        return self._synonyms.get(word.lower(), word)
    
    def match_regex(self, text: str) -> List[Dict]:
        """匹配正则特征"""
        matches = []
        for feature in self._regex_features:
            pattern = feature.get("pattern")
            name = feature.get("name")
            if pattern:
                for match in re.finditer(pattern, text):
                    matches.append({
                        "name": name,
                        "value": match.group(),
                        "start": match.start(),
                        "end": match.end()
                    })
        return matches


class EntityRecognizer:
    """实体识别器"""
    
    def __init__(self):
        self._logger = logger.bind(component="EntityRecognizer")
        self._entity_patterns: Dict[str, List[str]] = defaultdict(list)
        self._predefined_entities = {
            "number": r'\d+(\.\d+)?',
            "date": r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
            "time": r'\d{1,2}:\d{2}(:\d{2})?',
            "email": r'[\w.-]+@[\w.-]+\.\w+',
            "url": r'https?://[\w.-]+(/[\w./-]*)?'
        }
    
    def add_entity_pattern(self, entity_type: str, pattern: str):
        """添加实体模式"""
        self._entity_patterns[entity_type].append(pattern)
    
    def recognize(self, text: str) -> List[EntityMatch]:
        """识别文本中的实体"""
        entities = []
        
        # 识别预定义实体类型
        for entity_type, pattern in self._predefined_entities.items():
            for match in re.finditer(pattern, text):
                entities.append(EntityMatch(
                    entity=entity_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    entity_type=entity_type
                ))
        
        # 识别自定义实体模式
        for entity_type, patterns in self._entity_patterns.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    entities.append(EntityMatch(
                        entity=entity_type,
                        value=match.group(),
                        start=match.start(),
                        end=match.end(),
                        confidence=0.85,
                        entity_type=entity_type
                    ))
        
        return entities


class ConfidenceProcessor:
    """置信度处理器"""
    
    def __init__(self, thresholds: Dict = None):
        self._logger = logger.bind(component="ConfidenceProcessor")
        
        # 默认阈值配置（参考Rasa）
        self._thresholds = thresholds or {
            "intent_confidence_threshold": 0.7,
            "entity_confidence_threshold": 0.7,
            "fallback_intent": Intent.NLU_FALLBACK.value,
            "ambiguity_threshold": 0.1  # 意图之间的最小置信度差
        }
    
    def process(self, intents: List[Tuple[str, float]]) -> Tuple[str, float]:
        """处理意图置信度"""
        if not intents:
            return self._thresholds["fallback_intent"], 0.0
        
        # 排序意图
        intents.sort(key=lambda x: x[1], reverse=True)
        
        top_intent, top_confidence = intents[0]
        
        # 检查置信度阈值
        if top_confidence < self._thresholds["intent_confidence_threshold"]:
            return self._thresholds["fallback_intent"], top_confidence
        
        # 检查歧义
        if len(intents) > 1:
            second_intent, second_confidence = intents[1]
            if top_confidence - second_confidence < self._thresholds["ambiguity_threshold"]:
                self._logger.debug(f"检测到意图歧义: {top_intent} vs {second_intent}")
        
        return top_intent, top_confidence
    
    def set_threshold(self, key: str, value: float):
        """设置阈值"""
        if key in self._thresholds:
            self._thresholds[key] = value


class EnhancedIntentClassifier:
    """增强意图分类器（参考Rasa实现）"""
    
    def __init__(self, training_data_path: str = None):
        self._logger = logger.bind(component="EnhancedIntentClassifier")
        
        # 组件初始化
        self._training_data = TrainingData(training_data_path)
        self._entity_recognizer = EntityRecognizer()
        self._confidence_processor = ConfidenceProcessor()
        
        # 意图关键词（使用统一意图定义）
        self._intent_keywords = Intent.get_intent_keywords()
        
        # 否定词（降低置信度）
        self._negative_keywords = ["不", "不要", "无", "没有", "不是", "无法"]
        
        self._logger.info("增强意图分类器初始化完成")
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简单实现）"""
        words1 = set(text1.lower())
        words2 = set(text2.lower())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _match_intent(self, query: str) -> List[Tuple[str, float]]:
        """匹配意图"""
        intents = []
        query_lower = query.lower()
        
        # 1. 基于关键词的匹配
        for intent, keywords in self._intent_keywords.items():
            score = 0.0
            matched_keywords = 0
            
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    score += 0.2
                    matched_keywords += 1
            
            if matched_keywords > 0:
                intents.append((intent, min(score, 0.9)))
        
        # 2. 基于训练示例的匹配
        for intent, examples in self._training_data._intent_examples.items():
            for example in examples:
                similarity = self._calculate_similarity(query, example)
                if similarity > 0.3:
                    if intent not in [i[0] for i in intents]:
                        intents.append((intent, similarity))
                    else:
                        # 更新现有意图的分数
                        for i, (existing_intent, existing_score) in enumerate(intents):
                            if existing_intent == intent:
                                intents[i] = (intent, max(existing_score, similarity))
        
        # 3. 正则匹配
        regex_matches = self._training_data.match_regex(query)
        for match in regex_matches:
            intent = match.get("name")
            if intent and intent not in [i[0] for i in intents]:
                intents.append((intent, 0.7))
        
        # 4. 应用否定词惩罚
        negative_count = sum(1 for kw in self._negative_keywords if kw in query_lower)
        intents = [(intent, max(0.0, score - negative_count * 0.15)) for intent, score in intents]
        
        return intents
    
    def classify(self, query: str) -> IntentResult:
        """分类意图（主方法）"""
        # 1. 匹配意图
        intents = self._match_intent(query)
        
        # 2. 处理置信度
        intent, confidence = self._confidence_processor.process(intents)
        
        # 3. 识别实体
        entities = self._entity_recognizer.recognize(query)
        
        # 4. 应用同义词替换
        processed_query = query
        for entity in entities:
            synonym = self._training_data.get_synonym(entity.value)
            if synonym != entity.value:
                entity.value = synonym
        
        # 5. 构建结果
        result = IntentResult(
            intent=intent,
            confidence=confidence,
            entities=[{
                "entity": e.entity,
                "value": e.value,
                "start": e.start,
                "end": e.end,
                "confidence": e.confidence,
                "entity_type": e.entity_type
            } for e in entities],
            text=processed_query
        )
        
        self._logger.debug(f"意图分类结果: {intent} (置信度: {confidence:.2f})")
        
        return result
    
    def classify_multi_intent(self, query: str, top_n: int = 3) -> List[Dict]:
        """多意图识别"""
        intents = self._match_intent(query)
        intents.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for intent, confidence in intents[:top_n]:
            if confidence >= 0.3:
                results.append({
                    "intent": intent,
                    "confidence": confidence,
                    "entities": []
                })
        
        return results
    
    def add_training_example(self, text: str, intent: str, entities: List[Dict] = None):
        """添加训练示例"""
        self._training_data.add_example(text, intent, entities)
        self._logger.debug(f"添加训练示例: '{text}' -> {intent}")
    
    def set_threshold(self, key: str, value: float):
        """设置置信度阈值"""
        self._confidence_processor.set_threshold(key, value)
    
    def get_intents(self) -> List[str]:
        """获取所有意图"""
        return list(self._intent_keywords.keys()) + self._training_data.get_intents()


# 单例模式
_intent_classifier_instance = None

def get_intent_classifier(training_data_path: str = None) -> EnhancedIntentClassifier:
    """获取增强意图分类器实例"""
    global _intent_classifier_instance
    if _intent_classifier_instance is None:
        _intent_classifier_instance = EnhancedIntentClassifier(training_data_path)
    return _intent_classifier_instance


if __name__ == "__main__":
    print("=" * 60)
    print("增强意图分类器测试")
    print("=" * 60)
    
    # 初始化分类器
    classifier = EnhancedIntentClassifier()
    
    # 添加训练示例
    classifier.add_training_example("帮我写一个Python函数", "code_generation")
    classifier.add_training_example("如何修复Unicode错误？", "error_recovery")
    classifier.add_training_example("什么是机器学习？", "query_knowledge")
    
    # 测试意图分类
    test_queries = [
        "你好！",
        "帮我写一个Python函数来计算斐波那契数列",
        "如何修复代码中的错误？",
        "不要帮我写代码",
        "什么是人工智能？",
        "谢谢！",
        "再见"
    ]
    
    print("\n[1] 意图分类测试")
    for query in test_queries:
        result = classifier.classify(query)
        print(f'"{query}"')
        print(f'  -> 意图: {result.intent}, 置信度: {result.confidence:.2f}')
        if result.entities:
            print(f'  -> 实体: {result.entities}')
    
    # 测试多意图识别
    print("\n[2] 多意图识别测试")
    query = "帮我写代码并解释一下"
    results = classifier.classify_multi_intent(query)
    print(f'"{query}"')
    for i, result in enumerate(results):
        print(f'  {i+1}. 意图: {result["intent"]}, 置信度: {result["confidence"]:.2f}')
    
    # 测试实体识别
    print("\n[3] 实体识别测试")
    test_texts = [
        "明天下午3:30开会",
        "邮箱是 test@example.com",
        "访问 https://example.com",
        "价格是 99.99 元"
    ]
    for text in test_texts:
        result = classifier.classify(text)
        print(f'"{text}"')
        print(f'  -> 实体: {result.entities}')
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)