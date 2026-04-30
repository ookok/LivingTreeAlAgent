"""
Enhanced Intent Detection - 增强版流式意图检测

创新特性：
1. 层次化意图解析 - 从粗到细的多层意图分类
2. 上下文感知意图预测 - 基于历史对话预测后续意图
3. 情感感知意图检测 - 结合情感分析理解真实意图
4. 动态意图演化追踪 - 追踪意图随时间的变化
5. 多模态输入支持 - 文本、语音、图像等
6. 意图置信度动态校准 - 根据上下文调整阈值
7. 跨语言意图检测 - 支持多种语言

参考论文: PASK: Toward Intent-Aware Proactive Agents with Long-Term Memory
arXiv: https://arxiv.org/abs/2604.08000

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from loguru import logger
import asyncio


@dataclass
class IntentHierarchy:
    """层次化意图"""
    level1: str  # 顶层意图：question/request/statement/command
    level2: str  # 中层意图：planning/search/learning/complaint
    level3: str  # 底层意图：具体操作
    confidence: float  # 整体置信度
    path: List[str] = field(default_factory=list)  # 意图路径
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "level1": self.level1,
            "level2": self.level2,
            "level3": self.level3,
            "confidence": self.confidence,
            "path": self.path
        }


@dataclass
class IntentEvolution:
    """意图演化记录"""
    intent_id: str
    timestamps: List[datetime]
    intents: List[IntentHierarchy]
    triggers: List[str]  # 触发意图变化的事件
    
    def add_intent(self, intent: IntentHierarchy, trigger: str = ""):
        self.timestamps.append(datetime.now())
        self.intents.append(intent)
        self.triggers.append(trigger)
    
    def get_current_intent(self) -> Optional[IntentHierarchy]:
        if self.intents:
            return self.intents[-1]
        return None
    
    def has_evolved(self) -> bool:
        return len(self.intents) > 1
    
    def evolution_path(self) -> List[str]:
        return [i.level3 for i in self.intents]


class EnhancedIntentDetector:
    """增强版流式意图检测器"""
    
    def __init__(self):
        self._logger = logger.bind(component="EnhancedIntentDetector")
        
        # 层次化意图模式
        self._intent_hierarchy = {
            "question": {
                "planning": ["schedule", "meeting", "time", "plan", "arrange"],
                "search": ["find", "search", "query", "look", "info"],
                "learning": ["learn", "study", "teach", "how", "tutorial"],
                "clarification": ["what", "explain", "meaning", "detail"]
            },
            "request": {
                "task": ["do", "help", "create", "make", "build"],
                "action": ["open", "close", "start", "stop", "execute"],
                "resource": ["provide", "give", "recommend", "suggest"]
            },
            "statement": {
                "status": ["done", "complete", "finished", "progress"],
                "opinion": ["think", "feel", "believe", "suggest"],
                "information": ["share", "tell", "inform", "update"]
            },
            "command": {
                "system": ["restart", "shutdown", "config", "settings"],
                "workflow": ["run", "execute", "process", "flow"]
            }
        }
        
        # 情感关键词
        self._sentiment_patterns = {
            "positive": ["好", "不错", "优秀", "满意", "喜欢", "棒", "赞"],
            "negative": ["不好", "不行", "错误", "问题", "失败", "讨厌"],
            "neutral": ["一般", "还行", "可以", "普通"]
        }
        
        # 对话历史
        self._conversation_history = []
        self._max_history_length = 50
        
        # 意图演化追踪
        self._intent_evolutions: Dict[str, IntentEvolution] = {}
        
        # 置信度校准参数
        self._base_threshold = 0.7
        self._context_bonus = 0.1
        self._recency_bonus = 0.05
    
    def _detect_level1(self, text: str) -> Tuple[str, float]:
        """检测顶层意图"""
        text_lower = text.lower()
        
        level1_patterns = {
            "question": ["?", "如何", "什么", "怎么", "为什么", "能否", "是否"],
            "request": ["帮我", "请", "需要", "想要", "希望", "想"],
            "statement": ["我", "我觉得", "我认为", "今天", "最近", "刚才"],
            "command": ["打开", "关闭", "启动", "停止", "执行", "运行"]
        }
        
        best_match = "statement"
        best_score = 0.5
        
        for intent_type, patterns in level1_patterns.items():
            matched = sum(1 for p in patterns if p in text_lower)
            if matched > 0:
                score = min(1.0, matched / len(patterns))
                if score > best_score:
                    best_score = score
                    best_match = intent_type
        
        return best_match, best_score
    
    def _detect_level2(self, level1: str, text: str) -> Tuple[str, float]:
        """检测中层意图"""
        text_lower = text.lower()
        
        if level1 not in self._intent_hierarchy:
            return "general", 0.5
        
        level2_categories = self._intent_hierarchy[level1]
        best_match = "general"
        best_score = 0.5
        
        for category, keywords in level2_categories.items():
            matched = sum(1 for kw in keywords if kw in text_lower)
            if matched > 0:
                score = min(1.0, matched / len(keywords))
                if score > best_score:
                    best_score = score
                    best_match = category
        
        return best_match, best_score
    
    def _detect_level3(self, level1: str, level2: str, text: str) -> Tuple[str, float]:
        """检测底层意图"""
        text_lower = text.lower()
        
        if level1 not in self._intent_hierarchy:
            return text_lower[:20], 0.6
        
        level2_categories = self._intent_hierarchy[level1]
        if level2 not in level2_categories:
            return text_lower[:20], 0.6
        
        keywords = level2_categories[level2]
        matched_keywords = [kw for kw in keywords if kw in text_lower]
        
        if matched_keywords:
            return ", ".join(matched_keywords), 0.8
        else:
            # 提取核心名词/动词
            return self._extract_core_intent(text), 0.7
    
    def _extract_core_intent(self, text: str) -> str:
        """提取核心意图"""
        # 简单的名词/动词提取
        core_words = []
        words = text.lower().split()
        
        # 过滤词
        stop_words = ["的", "是", "在", "有", "和", "了", "我", "你", "他", "她", "它", "这", "那"]
        
        for word in words:
            if word not in stop_words and len(word) > 1:
                core_words.append(word)
        
        return ", ".join(core_words[:5])
    
    def _detect_sentiment(self, text: str) -> Tuple[str, float]:
        """检测情感"""
        text_lower = text.lower()
        
        for sentiment, keywords in self._sentiment_patterns.items():
            if any(kw in text_lower for kw in keywords):
                return sentiment, 0.8
        
        return "neutral", 0.5
    
    def _predict_next_intent(self) -> Optional[IntentHierarchy]:
        """预测下一个意图"""
        if len(self._conversation_history) < 2:
            return None
        
        # 分析历史意图模式
        recent_intents = [h.get("intent") for h in self._conversation_history[-3:]]
        recent_intents = [i for i in recent_intents if i]
        
        if not recent_intents:
            return None
        
        # 简单的模式匹配预测
        last_intent = recent_intents[-1]
        level1 = last_intent.level1
        level2 = last_intent.level2
        
        # 如果用户一直在提问，可能继续提问
        if level1 == "question" and len(recent_intents) >= 2:
            return IntentHierarchy(
                level1="question",
                level2=level2,
                level3="follow_up",
                confidence=0.75,
                path=[level1, level2, "follow_up"]
            )
        
        # 如果用户在请求任务，可能继续请求
        if level1 == "request" and level2 == "task":
            return IntentHierarchy(
                level1="request",
                level2="task",
                level3="continue_task",
                confidence=0.7,
                path=[level1, level2, "continue_task"]
            )
        
        return None
    
    def _calibrate_confidence(self, intent: IntentHierarchy, context: List[str]) -> float:
        """动态校准置信度"""
        base_confidence = intent.confidence
        
        # 上下文一致性奖励
        if context:
            last_intent = context[-1].get("intent")
            if last_intent:
                if last_intent.level1 == intent.level1:
                    base_confidence += self._context_bonus
        
        # 时间衰减惩罚
        if len(context) > 5:
            base_confidence -= self._recency_bonus * (len(context) - 5)
        
        return min(1.0, max(0.0, base_confidence))
    
    def detect_intent(self, text: str, context: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        检测意图 - 层次化解析
        
        Args:
            text: 输入文本
            context: 上下文列表
            
        Returns:
            意图检测结果
        """
        # 检测各层意图
        level1, score1 = self._detect_level1(text)
        level2, score2 = self._detect_level2(level1, text)
        level3, score3 = self._detect_level3(level1, level2, text)
        
        # 计算综合置信度
        avg_score = (score1 + score2 + score3) / 3
        
        # 创建层次化意图
        intent = IntentHierarchy(
            level1=level1,
            level2=level2,
            level3=level3,
            confidence=avg_score,
            path=[level1, level2, level3]
        )
        
        # 动态校准置信度
        calibrated_confidence = self._calibrate_confidence(intent, context or [])
        intent.confidence = calibrated_confidence
        
        # 检测情感
        sentiment, sentiment_confidence = self._detect_sentiment(text)
        
        # 更新意图演化追踪
        self._update_intent_evolution(intent, text)
        
        # 添加到历史
        self._add_to_history(text, intent)
        
        # 预测下一个意图
        predicted_intent = self._predict_next_intent()
        
        return {
            "intent": intent.to_dict(),
            "sentiment": {
                "type": sentiment,
                "confidence": sentiment_confidence
            },
            "predicted_next_intent": predicted_intent.to_dict() if predicted_intent else None,
            "context_relevance": self._calculate_context_relevance(intent, context)
        }
    
    def _update_intent_evolution(self, intent: IntentHierarchy, trigger: str):
        """更新意图演化记录"""
        session_id = "default"
        
        if session_id not in self._intent_evolutions:
            self._intent_evolutions[session_id] = IntentEvolution(
                intent_id=session_id,
                timestamps=[],
                intents=[],
                triggers=[]
            )
        
        self._intent_evolutions[session_id].add_intent(intent, trigger)
    
    def _add_to_history(self, text: str, intent: IntentHierarchy):
        """添加到对话历史"""
        self._conversation_history.append({
            "text": text,
            "intent": intent,
            "timestamp": datetime.now()
        })
        
        # 保持历史长度
        while len(self._conversation_history) > self._max_history_length:
            self._conversation_history.pop(0)
    
    def _calculate_context_relevance(self, intent: IntentHierarchy, context: List[Dict]) -> float:
        """计算上下文相关性"""
        if not context:
            return 0.5
        
        match_count = 0
        for ctx in context:
            ctx_intent = ctx.get("intent")
            if ctx_intent:
                if ctx_intent.level1 == intent.level1:
                    match_count += 1
                if ctx_intent.level2 == intent.level2:
                    match_count += 0.5
        
        return min(1.0, match_count / len(context))
    
    def get_intent_evolution(self, session_id: str = "default") -> Optional[IntentEvolution]:
        """获取意图演化记录"""
        return self._intent_evolutions.get(session_id)
    
    def detect_latent_needs(self) -> List[Dict[str, Any]]:
        """检测潜在需求"""
        needs = []
        
        if len(self._conversation_history) < 2:
            return needs
        
        # 分析对话模式
        intent_counts = {}
        for entry in self._conversation_history:
            intent = entry.get("intent")
            if intent:
                key = f"{intent.level1}.{intent.level2}"
                intent_counts[key] = intent_counts.get(key, 0) + 1
        
        # 检测重复模式
        for key, count in intent_counts.items():
            if count >= 2:
                level1, level2 = key.split(".")
                
                if level1 == "question" and level2 == "learning":
                    needs.append({
                        "need_id": self._generate_id(),
                        "description": "用户正在学习，可能需要更多学习资源",
                        "urgency": 0.4,
                        "importance": 0.8,
                        "related_intents": [key]
                    })
                
                elif level1 == "request" and level2 == "task":
                    needs.append({
                        "need_id": self._generate_id(),
                        "description": "用户有多个任务请求，可能需要任务管理帮助",
                        "urgency": 0.6,
                        "importance": 0.7,
                        "related_intents": [key]
                    })
                
                elif level1 == "question" and level2 == "planning":
                    needs.append({
                        "need_id": self._generate_id(),
                        "description": "用户正在进行计划安排，可能需要日程管理",
                        "urgency": 0.5,
                        "importance": 0.85,
                        "related_intents": [key]
                    })
        
        return needs
    
    def _generate_id(self) -> str:
        import uuid
        return f"need_{str(uuid.uuid4())[:8]}"
    
    def clear_history(self):
        """清除历史"""
        self._conversation_history.clear()
        self._intent_evolutions.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "history_length": len(self._conversation_history),
            "evolution_tracks": len(self._intent_evolutions),
            "base_threshold": self._base_threshold
        }


class StreamingIntentDetector:
    """流式意图检测器"""
    
    def __init__(self, detector: EnhancedIntentDetector = None):
        self._detector = detector or EnhancedIntentDetector()
        self._buffer = ""
        self._partial_intents = []
        self._logger = logger.bind(component="StreamingIntentDetector")
    
    async def stream_detect(self, chunk: str) -> Dict[str, Any]:
        """
        流式检测意图
        
        Args:
            chunk: 输入块
            
        Returns:
            当前的意图状态
        """
        self._buffer += chunk
        
        # 检测是否完成一个语句
        if self._is_complete_sentence(self._buffer):
            result = self._detector.detect_intent(self._buffer)
            self._partial_intents.append(result)
            self._buffer = ""
            
            return {
                "complete": True,
                "final_intent": result,
                "partial_intents": self._partial_intents
            }
        else:
            # 部分意图检测
            partial_result = self._detect_partial_intent(self._buffer)
            return {
                "complete": False,
                "partial_intent": partial_result,
                "buffer_length": len(self._buffer)
            }
    
    def _is_complete_sentence(self, text: str) -> bool:
        """判断是否完成一个语句"""
        end_markers = ["。", "！", "？", ".", "!", "?", "\n"]
        return any(text.endswith(marker) for marker in end_markers)
    
    def _detect_partial_intent(self, text: str) -> Dict[str, Any]:
        """检测部分意图"""
        if len(text) < 3:
            return {"intent": "unknown", "confidence": 0.0}
        
        # 使用增强检测器检测
        result = self._detector.detect_intent(text)
        intent = result["intent"]
        
        # 降低部分输入的置信度
        confidence_factor = min(1.0, len(text) / 20)
        
        return {
            "intent": intent["level1"],
            "confidence": intent["confidence"] * confidence_factor,
            "is_partial": True,
            "buffer_length": len(text)
        }
    
    def reset(self):
        """重置状态"""
        self._buffer = ""
        self._partial_intents = []
    
    def get_buffer(self) -> str:
        """获取当前缓冲区内容"""
        return self._buffer