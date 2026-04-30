"""意图识别创新模块 - 多模态意图融合与上下文追踪"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import time

class IntentType(Enum):
    SEARCH = "search"
    CREATE = "create"
    ANALYZE = "analyze"
    ASSIST = "assist"
    LEARN = "learn"
    SETTINGS = "settings"
    UNKNOWN = "unknown"

class ModalityType(Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    GESTURE = "gesture"

@dataclass
class IntentScore:
    """意图得分"""
    intent_type: IntentType
    confidence: float
    modality: ModalityType

@dataclass
class IntentResult:
    """意图识别结果"""
    intent: IntentType
    confidence: float
    sub_intents: List['IntentResult'] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    source_modality: ModalityType = ModalityType.TEXT

class MultiModalIntentFusion:
    """多模态意图融合引擎"""
    
    def __init__(self):
        self._modality_weights = {
            ModalityType.TEXT: 1.0,
            ModalityType.VOICE: 0.8,
            ModalityType.IMAGE: 0.6,
            ModalityType.GESTURE: 0.4
        }
    
    async def recognize(self, inputs: Dict[ModalityType, Any]) -> IntentResult:
        """融合多模态输入识别意图"""
        intent_scores = []
        
        for modality, data in inputs.items():
            score = await self._recognize_single_modality(modality, data)
            if score:
                intent_scores.append(score)
        
        fused_intent = self._fuse_intents(intent_scores)
        
        return IntentResult(
            intent=fused_intent.intent_type,
            confidence=fused_intent.confidence,
            source_modality=fused_intent.modality,
            sub_intents=self._extract_sub_intents(fused_intent.intent_type)
        )
    
    async def _recognize_single_modality(self, modality: ModalityType, data: Any) -> Optional[IntentScore]:
        """识别单模态意图"""
        if modality == ModalityType.TEXT:
            return self._recognize_text(str(data))
        elif modality == ModalityType.VOICE:
            return self._recognize_voice(data)
        elif modality == ModalityType.IMAGE:
            return self._recognize_image(data)
        elif modality == ModalityType.GESTURE:
            return self._recognize_gesture(data)
        return None
    
    def _recognize_text(self, text: str) -> IntentScore:
        """识别文本意图"""
        text_lower = text.lower()
        
        intent_mapping = [
            ("搜索", IntentType.SEARCH),
            ("查找", IntentType.SEARCH),
            ("查询", IntentType.SEARCH),
            ("帮我", IntentType.ASSIST),
            ("创建", IntentType.CREATE),
            ("生成", IntentType.CREATE),
            ("分析", IntentType.ANALYZE),
            ("总结", IntentType.ANALYZE),
            ("学习", IntentType.LEARN),
            ("设置", IntentType.SETTINGS),
        ]
        
        for keyword, intent_type in intent_mapping:
            if keyword in text_lower:
                return IntentScore(
                    intent_type=intent_type,
                    confidence=min(0.95, 0.7 + len(keyword) * 0.05),
                    modality=ModalityType.TEXT
                )
        
        return IntentScore(
            intent_type=IntentType.UNKNOWN,
            confidence=0.5,
            modality=ModalityType.TEXT
        )
    
    def _recognize_voice(self, data: Any) -> IntentScore:
        """识别语音意图（简化版）"""
        return IntentScore(
            intent_type=IntentType.UNKNOWN,
            confidence=0.3,
            modality=ModalityType.VOICE
        )
    
    def _recognize_image(self, data: Any) -> IntentScore:
        """识别图像意图（简化版）"""
        return IntentScore(
            intent_type=IntentType.UNKNOWN,
            confidence=0.2,
            modality=ModalityType.IMAGE
        )
    
    def _recognize_gesture(self, data: Any) -> IntentScore:
        """识别手势意图（简化版）"""
        return IntentScore(
            intent_type=IntentType.UNKNOWN,
            confidence=0.15,
            modality=ModalityType.GESTURE
        )
    
    def _fuse_intents(self, scores: List[IntentScore]) -> IntentScore:
        """融合多个模态的意图识别结果"""
        if not scores:
            return IntentScore(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                modality=ModalityType.TEXT
            )
        
        intent_counts: Dict[IntentType, float] = {}
        
        for score in scores:
            weight = self._modality_weights.get(score.modality, 1.0)
            weighted_score = score.confidence * weight
            
            if score.intent_type not in intent_counts:
                intent_counts[score.intent_type] = 0.0
            intent_counts[score.intent_type] += weighted_score
        
        max_intent = max(intent_counts, key=intent_counts.get)
        max_score = intent_counts[max_intent] / len(scores)
        
        source_modality = scores[0].modality
        
        return IntentScore(
            intent_type=max_intent,
            confidence=min(1.0, max_score),
            modality=source_modality
        )
    
    def _extract_sub_intents(self, intent_type: IntentType) -> List['IntentResult']:
        """提取子意图"""
        sub_intents = []
        
        if intent_type == IntentType.SEARCH:
            sub_intents.append(IntentResult(intent=IntentType.SEARCH, confidence=0.9))
        
        elif intent_type == IntentType.CREATE:
            sub_intents.append(IntentResult(intent=IntentType.CREATE, confidence=0.9))
            sub_intents.append(IntentResult(intent=IntentType.ANALYZE, confidence=0.8))
        
        return sub_intents

class ContextualIntentTracker:
    """上下文感知意图追踪器"""
    
    def __init__(self):
        self._intent_history: Dict[str, List[Dict[str, Any]]] = {}
    
    def track(self, user_id: str, intent: IntentType, context: Dict[str, Any]) -> Optional[IntentType]:
        """追踪意图演变"""
        if user_id not in self._intent_history:
            self._intent_history[user_id] = []
        
        self._intent_history[user_id].append({
            'intent': intent,
            'context': context,
            'timestamp': time.time()
        })
        
        if len(self._intent_history[user_id]) > 50:
            self._intent_history[user_id] = self._intent_history[user_id][-50:]
        
        return self._predict_next_intent(user_id)
    
    def _predict_next_intent(self, user_id: str) -> Optional[IntentType]:
        """预测用户下一步意图"""
        history = self._intent_history.get(user_id, [])
        if len(history) < 3:
            return None
        
        recent_intents = [h['intent'] for h in history[-3:]]
        if len(set(recent_intents)) == 1:
            return recent_intents[-1]
        
        return None
    
    def get_history(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户意图历史"""
        return self._intent_history.get(user_id, [])
    
    def clear_history(self, user_id: str):
        """清除用户意图历史"""
        if user_id in self._intent_history:
            del self._intent_history[user_id]

# 全局单例
_multi_modal_intent_fusion = MultiModalIntentFusion()
_contextual_intent_tracker = ContextualIntentTracker()

def get_multi_modal_intent_fusion() -> MultiModalIntentFusion:
    return _multi_modal_intent_fusion

def get_contextual_intent_tracker() -> ContextualIntentTracker:
    return _contextual_intent_tracker