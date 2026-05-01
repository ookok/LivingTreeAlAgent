"""
上下文感知路由（ContextAwareRouting）

根据对话历史长度、token数量、对话状态自动选择最优模型。

功能：
1. 对话历史分析
2. Token 数量感知
3. 对话状态追踪
4. 动态模型选择

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import json
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """对话状态"""
    INITIAL = "initial"           # 初始状态
    ACTIVE = "active"             # 活跃对话
    LONG_RUNNING = "long_running" # 长时间对话
    COMPLEX = "complex"           # 复杂对话
    SIMPLE = "simple"             # 简单对话
    CODE_FOCUSED = "code_focused" # 代码聚焦
    KNOWLEDGE_QUERY = "knowledge_query"  # 知识查询


@dataclass
class ContextAnalysis:
    """上下文分析结果"""
    total_tokens: int
    message_count: int
    avg_message_length: int
    max_message_length: int
    conversation_state: ConversationState
    required_tier: str
    confidence: float
    features: Dict[str, float] = field(default_factory=dict)


class ContextAwareRouting:
    """
    上下文感知路由器
    
    根据对话历史和当前状态智能选择模型层级。
    """
    
    def __init__(self, model_router):
        """
        初始化上下文感知路由器
        
        Args:
            model_router: GlobalModelRouter 实例
        """
        self.model_router = model_router
        
        # Token 阈值配置
        self.token_thresholds = {
            "L0": 512,
            "L1": 1024,
            "L2": 2048,
            "L3": 4096,
            "L4": 8192,
        }
        
        # 消息数量阈值
        self.message_thresholds = {
            "short": 5,
            "medium": 15,
            "long": 30,
        }
        
        logger.info("ContextAwareRouting 初始化完成")
    
    def analyze_context(self, messages: List[Dict[str, Any]]) -> ContextAnalysis:
        """
        分析对话上下文
        
        Args:
            messages: 消息列表，每条消息包含 role 和 content
        
        Returns:
            ContextAnalysis 分析结果
        """
        if not messages:
            return ContextAnalysis(
                total_tokens=0,
                message_count=0,
                avg_message_length=0,
                max_message_length=0,
                conversation_state=ConversationState.INITIAL,
                required_tier="L0",
                confidence=0.9,
                features={}
            )
        
        features = {}
        
        # 1. 计算 token 统计
        total_tokens = 0
        message_lengths = []
        
        for msg in messages:
            content = msg.get("content", "")
            length = len(content)
            message_lengths.append(length)
            total_tokens += int(length * 1.5)  # 粗略估算
        
        message_count = len(messages)
        avg_message_length = sum(message_lengths) / message_count if message_count > 0 else 0
        max_message_length = max(message_lengths) if message_lengths else 0
        
        features["total_tokens"] = min(total_tokens / 16384, 1.0)
        features["message_count"] = min(message_count / 50, 1.0)
        features["avg_length"] = min(avg_message_length / 500, 1.0)
        features["max_length"] = min(max_message_length / 2000, 1.0)
        
        # 2. 检测对话状态
        state = self._detect_conversation_state(messages, features)
        
        # 3. 确定需要的层级
        required_tier = self._determine_tier(total_tokens, message_count, state)
        
        # 4. 计算置信度
        confidence = self._calculate_confidence(features)
        
        return ContextAnalysis(
            total_tokens=total_tokens,
            message_count=message_count,
            avg_message_length=int(avg_message_length),
            max_message_length=max_message_length,
            conversation_state=state,
            required_tier=required_tier,
            confidence=confidence,
            features=features
        )
    
    def _detect_conversation_state(self, messages: List[Dict[str, Any]], 
                                    features: Dict[str, float]) -> ConversationState:
        """检测对话状态"""
        content = " ".join(msg.get("content", "") for msg in messages).lower()
        
        # 检测代码相关内容
        code_keywords = ["代码", "编程", "python", "java", "javascript", "function", "def", "class"]
        has_code = any(kw in content for kw in code_keywords)
        features["has_code"] = 1.0 if has_code else 0.0
        
        # 检测知识查询
        knowledge_keywords = ["什么是", "定义", "解释", "说明", "原理", "为什么"]
        has_knowledge = any(kw in content for kw in knowledge_keywords)
        features["has_knowledge"] = 1.0 if has_knowledge else 0.0
        
        # 检测长对话
        is_long = features["message_count"] > 0.6  # > 30 条消息
        
        # 检测复杂对话
        is_complex = features["max_length"] > 0.5  # > 1000 字符
        
        # 根据特征确定状态
        if has_code:
            return ConversationState.CODE_FOCUSED
        elif has_knowledge:
            return ConversationState.KNOWLEDGE_QUERY
        elif is_long:
            return ConversationState.LONG_RUNNING
        elif is_complex:
            return ConversationState.COMPLEX
        elif features["message_count"] < 0.1:  # < 5 条消息
            return ConversationState.SIMPLE
        else:
            return ConversationState.ACTIVE
    
    def _determine_tier(self, total_tokens: int, message_count: int, 
                        state: ConversationState) -> str:
        """根据上下文确定模型层级"""
        # 基于 token 数量的基础层级
        base_tier = "L0"
        for tier, threshold in sorted(self.token_thresholds.items(), key=lambda x: x[1]):
            if total_tokens <= threshold:
                base_tier = tier
                break
        
        # 根据对话状态调整
        tier_num = int(base_tier[1:])
        
        if state == ConversationState.CODE_FOCUSED:
            tier_num = min(tier_num + 1, 4)
        elif state == ConversationState.KNOWLEDGE_QUERY:
            tier_num = max(tier_num, 1)
        elif state == ConversationState.LONG_RUNNING:
            tier_num = min(tier_num + 1, 4)
        elif state == ConversationState.COMPLEX:
            tier_num = min(tier_num + 2, 4)
        
        return f"L{tier_num}"
    
    def _calculate_confidence(self, features: Dict[str, float]) -> float:
        """计算分析置信度"""
        indicators = [
            features.get("total_tokens", 0.5),
            features.get("message_count", 0.5),
            features.get("avg_length", 0.5),
        ]
        return sum(indicators) / len(indicators)
    
    def suggest_tier(self, messages: List[Dict[str, Any]], 
                     task_complexity: Optional[str] = None) -> str:
        """
        建议模型层级
        
        Args:
            messages: 消息列表
            task_complexity: 任务复杂度（可选）
        
        Returns:
            建议的层级（如 "L2"）
        """
        analysis = self.analyze_context(messages)
        suggested_tier = analysis.required_tier
        
        # 如果有额外的任务复杂度信息，进行调整
        if task_complexity:
            complexity_map = {
                "trivial": 0,
                "simple": 0,
                "medium": 1,
                "complex": 2,
                "advanced": 2,
                "expert": 3,
            }
            adjustment = complexity_map.get(task_complexity.lower(), 0)
            tier_num = min(int(suggested_tier[1:]) + adjustment, 4)
            suggested_tier = f"L{tier_num}"
        
        logger.info(f"上下文感知路由建议: {suggested_tier} (状态: {analysis.conversation_state.value})")
        
        return suggested_tier
    
    def get_routing_explanation(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取路由决策解释"""
        analysis = self.analyze_context(messages)
        
        return {
            "total_tokens": analysis.total_tokens,
            "message_count": analysis.message_count,
            "avg_message_length": analysis.avg_message_length,
            "conversation_state": analysis.conversation_state.value,
            "suggested_tier": analysis.required_tier,
            "confidence": round(analysis.confidence, 2),
            "features": {k: round(v, 2) for k, v in analysis.features.items()},
        }