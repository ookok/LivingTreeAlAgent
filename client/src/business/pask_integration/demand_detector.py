"""
Demand Detector - 需求检测器

实现 DD-MM-PAS 范式中的 Demand Detection 组件。

使用 IntentFlow 模型从流式上下文中检测用户意图和潜在需求。
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
import json


@dataclass
class DetectedIntent:
    """检测到的意图"""
    intent_type: str  # 意图类型
    confidence: float  # 置信度 (0-1)
    context: str  # 上下文描述
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type,
            "confidence": self.confidence,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class LatentNeed:
    """潜在需求"""
    need_id: str
    description: str
    urgency: float  # 紧急程度 (0-1)
    importance: float  # 重要性 (0-1)
    detected_at: datetime = field(default_factory=datetime.now)
    related_intents: List[str] = field(default_factory=list)
    
    def priority(self) -> float:
        """计算优先级"""
        return (self.urgency + self.importance) / 2
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "need_id": self.need_id,
            "description": self.description,
            "urgency": self.urgency,
            "importance": self.importance,
            "priority": self.priority(),
            "detected_at": self.detected_at.isoformat(),
            "related_intents": self.related_intents
        }


class IntentFlow:
    """IntentFlow 模型 - 流式意图检测"""
    
    def __init__(self, threshold: float = 0.7):
        self._threshold = threshold
        self._intent_patterns = {
            "question": ["?", "如何", "什么", "怎么", "为什么", "能否", "是否"],
            "request": ["帮我", "请", "需要", "想要", "希望", "想"],
            "statement": ["我", "我觉得", "我认为", "今天", "最近"],
            "command": ["打开", "关闭", "启动", "停止", "执行"],
            "complaint": ["不好", "不行", "错误", "问题", "失败"],
            "praise": ["好", "不错", "优秀", "满意"],
            "clarification": ["什么意思", "解释一下", "说明", "详情"],
            "planning": ["计划", "安排", "日程", "会议", "时间"],
            "search": ["搜索", "查找", "查询", "了解"],
            "learning": ["学习", "教程", "课程", "培训"]
        }
        self._logger = logger.bind(component="IntentFlow")
    
    def detect_intent(self, text: str) -> List[DetectedIntent]:
        """
        检测文本中的意图
        
        Args:
            text: 输入文本
            
        Returns:
            检测到的意图列表
        """
        results = []
        text_lower = text.lower()
        
        for intent_type, patterns in self._intent_patterns.items():
            matched_patterns = []
            for pattern in patterns:
                if pattern in text_lower:
                    matched_patterns.append(pattern)
            
            if matched_patterns:
                # 计算置信度：匹配的模式数 / 总模式数 * 文本匹配程度
                confidence = min(1.0, len(matched_patterns) / len(patterns))
                
                # 根据匹配长度调整置信度
                for pattern in matched_patterns:
                    if len(pattern) >= 2:
                        confidence += 0.05
                
                confidence = min(1.0, confidence)
                
                if confidence >= self._threshold:
                    results.append(DetectedIntent(
                        intent_type=intent_type,
                        confidence=confidence,
                        context=text[:50],
                        metadata={"matched_patterns": matched_patterns}
                    ))
        
        # 按置信度排序
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        return results
    
    def detect_latent_needs(self, conversation_history: List[str]) -> List[LatentNeed]:
        """
        从对话历史中检测潜在需求
        
        Args:
            conversation_history: 对话历史列表
            
        Returns:
            潜在需求列表
        """
        needs = []
        
        # 分析对话模式
        patterns = []
        for text in conversation_history:
            intents = self.detect_intent(text)
            patterns.extend([i.intent_type for i in intents])
        
        # 检测潜在需求
        if patterns.count("question") >= 2:
            needs.append(LatentNeed(
                need_id=self._generate_id(),
                description="用户可能需要详细的信息解答",
                urgency=0.3,
                importance=0.7,
                related_intents=["question"]
            ))
        
        if patterns.count("request") >= 2:
            needs.append(LatentNeed(
                need_id=self._generate_id(),
                description="用户有多个任务请求，可能需要任务管理帮助",
                urgency=0.5,
                importance=0.6,
                related_intents=["request"]
            ))
        
        if patterns.count("planning") >= 2:
            needs.append(LatentNeed(
                need_id=self._generate_id(),
                description="用户正在进行计划安排，可能需要日程管理",
                urgency=0.4,
                importance=0.8,
                related_intents=["planning"]
            ))
        
        if patterns.count("complaint") >= 2:
            needs.append(LatentNeed(
                need_id=self._generate_id(),
                description="用户遇到问题，可能需要技术支持",
                urgency=0.8,
                importance=0.7,
                related_intents=["complaint"]
            ))
        
        # 按优先级排序
        needs.sort(key=lambda x: x.priority(), reverse=True)
        
        return needs
    
    def _generate_id(self) -> str:
        import uuid
        return f"need_{uuid.uuid4()[:8]}"


class DemandDetector:
    """需求检测器 - 整合意图检测和需求推断"""
    
    def __init__(self):
        self._intent_flow = IntentFlow()
        self._conversation_history: List[str] = []
        self._max_history_length = 50
        self._logger = logger.bind(component="DemandDetector")
    
    def process_message(self, message: str) -> Dict[str, Any]:
        """
        处理消息，检测意图和潜在需求
        
        Args:
            message: 用户消息
            
        Returns:
            检测结果
        """
        # 添加到历史
        self._conversation_history.append(message)
        self._trim_history()
        
        # 检测意图
        intents = self._intent_flow.detect_intent(message)
        
        # 检测潜在需求（基于历史）
        latent_needs = self._intent_flow.detect_latent_needs(self._conversation_history)
        
        return {
            "message": message,
            "intents": [i.to_dict() for i in intents],
            "latent_needs": [n.to_dict() for n in latent_needs],
            "history_length": len(self._conversation_history)
        }
    
    def get_latent_needs(self) -> List[LatentNeed]:
        """获取当前检测到的潜在需求"""
        return self._intent_flow.detect_latent_needs(self._conversation_history)
    
    def get_intents(self, text: str) -> List[DetectedIntent]:
        """获取文本的意图"""
        return self._intent_flow.detect_intent(text)
    
    def clear_history(self):
        """清除对话历史"""
        self._conversation_history.clear()
        self._logger.debug("对话历史已清除")
    
    def _trim_history(self):
        """修剪历史记录"""
        while len(self._conversation_history) > self._max_history_length:
            self._conversation_history.pop(0)
    
    def set_history_length(self, length: int):
        """设置历史长度"""
        self._max_history_length = length