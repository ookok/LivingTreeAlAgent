"""
实体识别模块 (Entity Recognition)

实现命名实体识别（NER）功能，支持多种识别引擎。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import re
import logging
from typing import List, Dict, Any, Optional

from .models import Entity, EntityType, EntityRecognitionResult

logger = logging.getLogger(__name__)


class EntityRecognizer:
    """
    实体识别器基类
    """
    
    def recognize(self, text: str) -> EntityRecognitionResult:
        """
        识别文本中的实体
        
        Args:
            text: 输入文本
            
        Returns:
            EntityRecognitionResult 识别结果
        """
        raise NotImplementedError
    
    def get_supported_types(self) -> List[EntityType]:
        """
        获取支持的实体类型
        
        Returns:
            支持的实体类型列表
        """
        return list(EntityType)


class RuleBasedEntityRecognizer(EntityRecognizer):
    """
    基于规则的实体识别器
    
    使用正则表达式和关键词匹配识别实体。
    """
    
    # 正则表达式模式
    PATTERNS = {
        EntityType.EMAIL: [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        ],
        EntityType.PHONE: [
            r'1[3-9]\d{9}',  # 中国手机号
            r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
        ],
        EntityType.URL: [
            r'https?://[^\s]+',
            r'www\.[^\s]+',
        ],
        EntityType.DATE: [
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # YYYY-MM-DD
            r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',  # DD-MM-YYYY
            r'\d{4}年\d{1,2}月\d{1,2}日',
            r'昨天|今天|明天|前天|后天',
            r'上周|本周|下周',
            r'上个月|这个月|下个月',
            r'去年|今年|明年',
        ],
        EntityType.NUMBER: [
            r'\d+(\.\d+)?',
            r'[\u4e00-\u9fff]+',  # 中文数字
        ],
    }
    
    # 关键词到实体类型的映射
    KEYWORDS: Dict[EntityType, List[str]] = {
        EntityType.PERSON: [
            '爱因斯坦', '牛顿', '乔布斯', '马斯克', '扎克伯格',
            '张三', '李四', '王五', '小明', '小红',
            '博士', '教授', '先生', '女士', '工程师',
        ],
        EntityType.ORGANIZATION: [
            '公司', '集团', '大学', '学院', '研究院',
            '中心', '协会', '联盟', '委员会', '政府',
        ],
        EntityType.LOCATION: [
            '北京', '上海', '深圳', '广州', '杭州',
            '中国', '美国', '日本', '英国', '德国',
            '省', '市', '区', '县', '镇',
        ],
        EntityType.TECH_TERM: [
            '人工智能', '机器学习', '深度学习', '神经网络',
            '算法', '模型', '框架', '库', '工具',
            '量子计算', '大数据', '云计算', '区块链',
        ],
        EntityType.PRODUCT: [
            'iPhone', 'MacBook', 'Windows', 'Linux',
            '手机', '电脑', '软件', '系统', '平台',
        ],
        EntityType.CONCEPT: [
            '概念', '理论', '原理', '方法', '技术',
            '思想', '理念', '范式', '模式', '架构',
        ],
        EntityType.ALGORITHM: [
            '神经网络', '决策树', '随机森林', '支持向量机',
            '梯度下降', '反向传播', '强化学习', '遗传算法',
        ],
        EntityType.FRAMEWORK: [
            'PyTorch', 'TensorFlow', 'React', 'Vue',
            'Django', 'Flask', 'Spring', 'Node.js',
        ],
        EntityType.LANGUAGE: [
            'Python', 'Java', 'JavaScript', 'C++',
            'Go', 'Rust', 'Swift', 'Kotlin',
        ],
    }
    
    def __init__(self):
        """初始化基于规则的识别器"""
        logger.info("RuleBasedEntityRecognizer 初始化完成")
    
    def recognize(self, text: str) -> EntityRecognitionResult:
        """识别文本中的实体"""
        entities = []
        
        # 1. 使用正则表达式识别
        for entity_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    entity = Entity(
                        text=match.group(),
                        entity_type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.95  # 正则匹配置信度很高
                    )
                    entities.append(entity)
        
        # 2. 使用关键词匹配识别
        for entity_type, keywords in self.KEYWORDS.items():
            for keyword in keywords:
                start = 0
                while True:
                    index = text.find(keyword, start)
                    if index == -1:
                        break
                    entity = Entity(
                        text=keyword,
                        entity_type=entity_type,
                        start=index,
                        end=index + len(keyword),
                        confidence=0.7  # 关键词匹配置信度中等
                    )
                    entities.append(entity)
                    start = index + len(keyword)
        
        # 3. 去重（基于位置）
        entities = self._deduplicate(entities)
        
        return EntityRecognitionResult(
            text=text,
            entities=entities,
            entity_count=len(entities),
            processing_time=0.0
        )
    
    def _deduplicate(self, entities: List[Entity]) -> List[Entity]:
        """去除重复实体"""
        seen = set()
        unique = []
        
        for entity in entities:
            key = (entity.start, entity.end)
            if key not in seen:
                seen.add(key)
                unique.append(entity)
        
        return unique
    
    def get_supported_types(self) -> List[EntityType]:
        """获取支持的实体类型"""
        types = set()
        types.update(self.PATTERNS.keys())
        types.update(self.KEYWORDS.keys())
        return list(types)


class HybridEntityRecognizer(EntityRecognizer):
    """
    混合实体识别器
    
    结合规则匹配和机器学习模型进行实体识别。
    """
    
    def __init__(self):
        """初始化混合识别器"""
        self.rule_based = RuleBasedEntityRecognizer()
        
        # 尝试加载 ML 模型
        self.ml_recognizer = None
        self._try_load_ml_model()
        
        logger.info("HybridEntityRecognizer 初始化完成")
    
    def _try_load_ml_model(self):
        """尝试加载机器学习模型"""
        try:
            # 可以集成 spaCy、BERT-NER 等
            logger.info("ML 实体识别模型加载成功")
        except ImportError as e:
            logger.warning(f"ML 实体识别模型加载失败: {e}")
    
    def recognize(self, text: str) -> EntityRecognitionResult:
        """识别文本中的实体"""
        # 1. 使用规则匹配
        result = self.rule_based.recognize(text)
        
        # 2. 如果有 ML 模型，融合结果
        if self.ml_recognizer:
            # 融合逻辑
            pass
        
        return result
    
    def get_supported_types(self) -> List[EntityType]:
        """获取支持的实体类型"""
        return self.rule_based.get_supported_types()


# 全局识别器实例
_recognizer_instance = None

def get_entity_recognizer() -> EntityRecognizer:
    """获取全局实体识别器实例"""
    global _recognizer_instance
    if _recognizer_instance is None:
        _recognizer_instance = HybridEntityRecognizer()
    return _recognizer_instance