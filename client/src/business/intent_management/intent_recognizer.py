"""
Smart Intent Recognizer

智能意图识别引擎，支持四级递进式意图识别、上下文消歧、自适应置信度阈值。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RecognitionLevel(Enum):
    """识别级别"""
    L0 = "direct_match"     # 精确匹配
    L1 = "keyword"          # 关键词匹配
    L2 = "semantic"         # 语义相似
    L3 = "context"          # 上下文分析
    L4 = "entity_enhanced"  # 实体增强


@dataclass
class DialogContext:
    """对话上下文"""
    conversation_id: str
    history: List[Dict[str, str]] = field(default_factory=list)
    current_topic: Optional[str] = None
    user_profile: Optional[Dict[str, Any]] = None
    session_start_time: str = ""


@dataclass
class IntentCandidate:
    """意图候选"""
    intent_id: str
    name: str
    confidence: float
    level: RecognitionLevel
    matched_pattern: Optional[str] = None


@dataclass
class IntentResult:
    """意图识别结果"""
    intent_id: str
    name: str
    confidence: float
    level: RecognitionLevel
    candidates: List[IntentCandidate] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: Optional[str] = None


class SmartIntentRecognizer:
    """
    智能意图识别引擎
    
    四级递进式意图识别：
    L1: 关键词匹配（快速）
    L2: 语义相似度（向量检索）
    L3: 上下文分析（历史对话）
    L4: 实体增强（结合知识图谱）
    """
    
    def __init__(self):
        """初始化意图识别器"""
        self._intent_hub = None
        self._entity_recognizer = None
        self._vector_store = None
        
        self._confidence_threshold = 0.6
        self._dynamic_threshold_enabled = True
        
        self._init_dependencies()
        logger.info("SmartIntentRecognizer 初始化完成")
    
    def _init_dependencies(self):
        """初始化依赖模块"""
        try:
            from .intent_hub import UnifiedIntentHub, get_unified_intent_hub
            from ..entity_management import get_entity_recognizer
            from ..fusion_rag.smart_vector_store import get_smart_vector_store
            
            self._intent_hub = get_unified_intent_hub()
            self._entity_recognizer = get_entity_recognizer()
            self._vector_store = get_smart_vector_store()
            
            logger.info("依赖模块加载成功")
        except ImportError as e:
            logger.warning(f"依赖模块加载失败: {e}")
    
    def recognize(self, query: str, context: Optional[DialogContext] = None) -> IntentResult:
        """
        识别意图
        
        Args:
            query: 用户查询
            context: 对话上下文
            
        Returns:
            IntentResult 识别结果
        """
        candidates = []
        
        # L1: 关键词匹配
        l1_candidates = self._level_1_keyword_match(query)
        candidates.extend(l1_candidates)
        
        # L2: 语义相似度匹配
        l2_candidates = self._level_2_semantic_match(query)
        candidates.extend(l2_candidates)
        
        # L3: 上下文分析
        if context:
            l3_candidates = self._level_3_context_analysis(query, context)
            candidates.extend(l3_candidates)
        
        # L4: 实体增强
        l4_candidates = self._level_4_entity_enhanced(query)
        candidates.extend(l4_candidates)
        
        # 融合候选
        result = self._fuse_candidates(candidates, query)
        
        # 上下文消歧
        if context and len(result.candidates) > 1:
            result = self.disambiguate(query, result, context)
        
        return result
    
    def _level_1_keyword_match(self, query: str) -> List[IntentCandidate]:
        """
        L1: 关键词匹配
        
        使用意图中心的模式匹配功能
        """
        if not self._intent_hub:
            return []
        
        matches = self._intent_hub.match_intent(query)
        candidates = []
        
        for match in matches:
            candidates.append(IntentCandidate(
                intent_id=match["intent_id"],
                name=match["name"],
                confidence=match["confidence"],
                level=RecognitionLevel.L1,
            ))
        
        return candidates
    
    def _level_2_semantic_match(self, query: str) -> List[IntentCandidate]:
        """
        L2: 语义相似度匹配
        
        使用向量检索查找相似的意图定义
        """
        if not self._vector_store:
            return []
        
        # 简化实现：返回空列表
        # 实际实现中会使用向量存储检索相似意图
        return []
    
    def _level_3_context_analysis(self, query: str, context: DialogContext) -> List[IntentCandidate]:
        """
        L3: 上下文分析
        
        结合历史对话分析意图
        """
        candidates = []
        
        # 分析对话历史
        if context.history:
            # 检查是否有重复或相关的意图
            recent_intents = [turn.get("intent") for turn in context.history[-5:]]
            
            # 如果最近有技术问题，当前查询更可能也是技术问题
            if any("tech_question" in str(ri) for ri in recent_intents if ri):
                candidates.append(IntentCandidate(
                    intent_id="tech_question",
                    name="技术问题咨询",
                    confidence=0.7,
                    level=RecognitionLevel.L3,
                ))
        
        # 检查当前话题
        if context.current_topic:
            # 根据当前话题推断意图
            topic_intent_map = {
                "技术": "tech_question",
                "编程": "tech_question",
                "聊天": "chat",
                "创作": "creative",
            }
            
            for topic, intent_id in topic_intent_map.items():
                if topic in context.current_topic:
                    intent = self._intent_hub.get_intent(intent_id) if self._intent_hub else None
                    if intent:
                        candidates.append(IntentCandidate(
                            intent_id=intent_id,
                            name=intent.name,
                            confidence=0.65,
                            level=RecognitionLevel.L3,
                        ))
        
        return candidates
    
    def _level_4_entity_enhanced(self, query: str) -> List[IntentCandidate]:
        """
        L4: 实体增强
        
        结合实体识别结果增强意图识别
        """
        if not self._entity_recognizer:
            return []
        
        candidates = []
        
        # 识别实体
        result = self._entity_recognizer.recognize(query)
        
        # 根据实体类型推断意图
        entity_type_intent_map = {
            "tech_term": "tech_question",
            "algorithm": "tech_question",
            "framework": "tech_question",
            "language": "tech_question",
            "product": "general_qa",
            "person": "general_qa",
            "organization": "general_qa",
        }
        
        for entity in result.entities:
            intent_id = entity_type_intent_map.get(entity.entity_type.value)
            if intent_id:
                intent = self._intent_hub.get_intent(intent_id) if self._intent_hub else None
                if intent:
                    candidates.append(IntentCandidate(
                        intent_id=intent_id,
                        name=intent.name,
                        confidence=0.6 + entity.confidence * 0.2,
                        level=RecognitionLevel.L4,
                    ))
        
        return candidates
    
    def _fuse_candidates(self, candidates: List[IntentCandidate], query: str) -> IntentResult:
        """
        融合候选意图
        
        Args:
            candidates: 候选意图列表
            query: 用户查询
            
        Returns:
            IntentResult 融合后的结果
        """
        if not candidates:
            return IntentResult(
                intent_id="unknown",
                name="未知意图",
                confidence=0.0,
                level=RecognitionLevel.L0,
            )
        
        # 按意图ID分组并计算平均置信度
        intent_scores = {}
        for candidate in candidates:
            if candidate.intent_id not in intent_scores:
                intent_scores[candidate.intent_id] = {"total": 0, "count": 0, "candidates": []}
            intent_scores[candidate.intent_id]["total"] += candidate.confidence
            intent_scores[candidate.intent_id]["count"] += 1
            intent_scores[candidate.intent_id]["candidates"].append(candidate)
        
        # 计算平均置信度
        avg_scores = []
        for intent_id, data in intent_scores.items():
            avg_confidence = data["total"] / data["count"]
            avg_scores.append({
                "intent_id": intent_id,
                "confidence": avg_confidence,
                "candidates": data["candidates"],
            })
        
        # 排序
        avg_scores.sort(key=lambda x: x["confidence"], reverse=True)
        
        top_score = avg_scores[0]
        intent = self._intent_hub.get_intent(top_score["intent_id"]) if self._intent_hub else None
        
        # 识别实体
        entities = []
        if self._entity_recognizer:
            result = self._entity_recognizer.recognize(query)
            entities = [{
                "text": e.text,
                "type": e.entity_type.value,
                "confidence": e.confidence,
            } for e in result.entities]
        
        return IntentResult(
            intent_id=top_score["intent_id"],
            name=intent.name if intent else top_score["intent_id"],
            confidence=top_score["confidence"],
            level=top_score["candidates"][0].level,
            candidates=top_score["candidates"],
            entities=entities,
        )
    
    def disambiguate(self, query: str, result: IntentResult, context: DialogContext) -> IntentResult:
        """
        基于上下文的意图消歧
        
        Args:
            query: 用户查询
            result: 当前识别结果
            context: 对话上下文
            
        Returns:
            IntentResult 消歧后的结果
        """
        if len(result.candidates) <= 1:
            return result
        
        # 分析上下文，选择最可能的意图
        # 这里简化实现，返回原结果
        return result
    
    def calibrate_threshold(self, success_rate: float):
        """
        动态校准置信度阈值
        
        Args:
            success_rate: 当前成功率
        """
        if not self._dynamic_threshold_enabled:
            return
        
        # 根据成功率调整阈值
        if success_rate > 0.9:
            self._confidence_threshold = 0.5
        elif success_rate > 0.7:
            self._confidence_threshold = 0.6
        elif success_rate > 0.5:
            self._confidence_threshold = 0.7
        else:
            self._confidence_threshold = 0.8
        
        logger.info(f"置信度阈值已调整为: {self._confidence_threshold}")
    
    def set_threshold(self, threshold: float):
        """
        设置置信度阈值
        
        Args:
            threshold: 阈值 (0-1)
        """
        self._confidence_threshold = max(0.0, min(1.0, threshold))
        self._dynamic_threshold_enabled = False
    
    def enable_dynamic_threshold(self, enable: bool = True):
        """
        启用/禁用动态阈值调整
        
        Args:
            enable: 是否启用
        """
        self._dynamic_threshold_enabled = enable
    
    def get_threshold(self) -> float:
        """获取当前置信度阈值"""
        return self._confidence_threshold


# 全局意图识别器实例
_recognizer_instance = None

def get_smart_intent_recognizer() -> SmartIntentRecognizer:
    """获取全局智能意图识别器实例"""
    global _recognizer_instance
    if _recognizer_instance is None:
        _recognizer_instance = SmartIntentRecognizer()
    return _recognizer_instance