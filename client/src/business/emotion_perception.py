"""
情绪感知模块 - Emotion Perception Module
===========================================

使用LLM准确识别用户情绪，为思考模式选择提供依据。

功能：
1. 使用LLM识别用户情绪（类型 + 强度）
2. 支持多种情绪模型（简单/详细）
3. 情绪历史追踪
4. 与思考模式控制器集成

Author: LivingTreeAI Team
Date: 2026-04-27
"""

import json
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============= 情绪类型定义 =============

class EmotionCategory(Enum):
    """情绪大类"""
    POSITIVE = "positive"      # 正面情绪
    NEGATIVE = "negative"      # 负面情绪
    NEUTRAL = "neutral"       # 中性情绪
    CONFUSED = "confused"      # 困惑情绪


class EmotionType(Enum):
    """详细情绪类型"""
    # 正面情绪
    JOY = ("joy", EmotionCategory.POSITIVE, "喜悦")
    HAPPY = ("happy", EmotionCategory.POSITIVE, "开心")
    SATISFIED = ("satisfied", EmotionCategory.POSITIVE, "满意")
    EXCITED = ("excited", EmotionCategory.POSITIVE, "兴奋")
    RELIEVED = ("relieved", EmotionCategory.POSITIVE, "释然")
    
    # 负面情绪
    ANGER = ("anger", EmotionCategory.NEGATIVE, "愤怒")
    ANXIOUS = ("anxious", EmotionCategory.NEGATIVE, "焦虑")
    FRUSTRATED = ("frustrated", EmotionCategory.NEGATIVE, "沮丧")
    DISAPPOINTED = ("disappointed", EmotionCategory.NEGATIVE, "失望")
    WORRIED = ("worried", EmotionCategory.NEGATIVE, "担忧")
    
    # 困惑情绪
    CONFUSED = ("confused", EmotionCategory.CONFUSED, "困惑")
    LOST = ("lost", EmotionCategory.CONFUSED, "迷茫")
    HELPLESS = ("helpless", EmotionCategory.CONFUSED, "无助")
    
    # 中性情绪
    NEUTRAL = ("neutral", EmotionCategory.NEUTRAL, "中性")
    CALM = ("calm", EmotionCategory.NEUTRAL, "平静")
    
    def __init__(self, value: str, category: EmotionCategory, chinese: str):
        self._value_ = value
        self.category = category
        self.chinese = chinese


# ============= 数据类 =============

@dataclass
class EmotionResult:
    """情绪识别结果"""
    emotion_type: EmotionType           # 情绪类型
    intensity: float                    # 强度 (0.0 - 1.0)
    confidence: float                   # 置信度 (0.0 - 1.0)
    reasoning: str = ""                 # 推理过程
    secondary_emotions: List[str] = field(default_factory=list)  # 次要情绪
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "emotion_type": self.emotion_type.value,
            "emotion_chinese": self.emotion_type.chinese,
            "category": self.emotion_type.category.value,
            "intensity": self.intensity,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "secondary_emotions": self.secondary_emotions,
        }
    
    def should_adjust_thinking(self) -> bool:
        """是否需要调整思考模式"""
        # 高强度情绪需要。 rospy调整
        if self.intensity > 0.6:
            return True
        
        # 特定情绪类型需要调整
        if self.emotion_type in [
            EmotionType.ANGER, EmotionType.ANXIOUS,
            EmotionType.CONFUSED, EmotionType.HELPLESS
        ]:
            return True
        
        return False
    
    def get_suggested_thinking_mode(self) -> str:
        """获取建议的思考模式"""
        if self.emotion_type.category == EmotionCategory.NEGATIVE:
            if self.intensity > 0.7:
                return "analytical"  # 高强度负面情绪 → 分析式
            else:
                return "guided"      # 低强度负面情绪 → 引导式
        
        elif self.emotion_type.category == EmotionCategory.CONFUSED:
            return "guided"          # 困惑情绪 → 引导式
        
        elif self.emotion_type.category == EmotionCategory.POSITIVE:
            return "immersive"       # 正面情绪 → 沉浸式
        
        else:
            return "immersive"       # 默认 → 沉浸式


# ============= 情绪感知器 =============

class EmotionPerception:
    """
    情绪感知器
    
    使用LLM识别用户情绪，支持：
    1. 单轮情绪识别
    2. 多轮对话情绪追踪
    3. 情绪强度评估
    """
    
    # 情绪识别Prompt模板
    EMOTION_PROMPT_TEMPLATE = """分析以下用户消息的情绪状态。

用户消息："{user_message}"

请按以下JSON格式输出分析结果：
```json
{{
    "emotion_type": "情绪类型（从以下选择：joy, happy, satisfied, excited, relieved, anger, anxious, frustrated, disappointed, worried, confused, lost, helpless, neutral, calm）",
    "intensity": 0.8,
    "confidence": 0.9,
    "reasoning": "推理过程（为什么判断为这个情绪）",
    "secondary_emotions": ["次要情绪1", "次要情绪2"]
}}
```

要求：
1. intensity: 情绪强度 (0.0-1.0)，0.0表示没有该情绪，1.0表示非常强烈
2. confidence: 置信度 (0.0-1.0)，表示判断的把握程度
3. 只输出JSON，不要输出其他内容
"""
    
    def __init__(self, use_llm: bool = True):
        """
        初始化情绪感知器
        
        Args:
            use_llm: 是否使用LLM进行情绪识别（如果False，使用关键词匹配）
        """
        self.use_llm = use_llm
        self.emotion_history: List[EmotionResult] = []
        self._model_router = None
        
        # 关键词匹配词典（fallback）
        self._keyword_dict = {
            EmotionType.ANGER: ["愤怒", "生气", "气死", "讨厌", "烦死了", "shit", "fuck", "hate"],
            EmotionType.ANXIOUS: ["焦虑", "担心", "害怕", "紧张", "不安", "worried", "anxious"],
            EmotionType.CONFUSED: ["困惑", "不懂", "迷茫", "不知道", "疑惑", "confused", "don't know"],
            EmotionType.HELPLESS: ["无助", "没办法", "怎么办", "救救我", "helpless"],
            EmotionType.JOY: ["开心", "高兴", "棒", "太好了", "happy", "great", "excellent"],
            EmotionType.SATISFIED: ["满意", "不错", "还好", "satisfied", "okay"],
            EmotionType.EXCITED: ["激动", "兴奋", "太棒了", "wow", "amazing", "awesome"],
        }
    
    def _get_model_router(self):
        """延迟加载GlobalModelRouter"""
        if self._model_router is None:
            try:
                from business.global_model_router import GlobalModelRouter
                self._model_router = GlobalModelRouter()
            except ImportError as e:
                logger.warning(f"无法导入GlobalModelRouter: {e}")
                self.use_llm = False
        return self._model_router
    
    async def perceive(self, user_message: str, context: Optional[List[dict]] = None) -> EmotionResult:
        """
        识别用户情绪
        
        Args:
            user_message: 用户消息
            context: 对话上下文（可选，用于多轮情绪追踪）
            
        Returns:
            EmotionResult: 情绪识别结果
        """
        if self.use_llm:
            try:
                return await self._perceive_with_llm(user_message)
            except Exception as e:
                logger.warning(f"LLM情绪识别失败，使用关键词匹配: {e}")
                return self._perceive_with_keywords(user_message)
        else:
            return self._perceive_with_keywords(user_message)
    
    async def _perceive_with_llm(self, user_message: str) -> EmotionResult:
        """使用LLM识别情绪"""
        router = self._get_model_router()
        if router is None:
            return self._perceive_with_keywords(user_message)
        
        # 构造Prompt
        prompt = self.EMOTION_PROMPT_TEMPLATE.format(user_message=user_message)
        
        # 调用LLM
        from business.global_model_router import ModelCapability
        response = await router.call_model(
            capability=ModelCapability.CHAT,
            prompt=prompt,
            system_prompt="你是一个情绪识别专家。只输出JSON，不要输出其他内容。",
            strategy=router.RoutingStrategy.SPEED  # 使用快速策略
        )
        
        # 解析响应
        try:
            # 提取JSON
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                raise ValueError("未找到JSON")
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            # 转换为EmotionResult
            emotion_type_str = data.get("emotion_type", "neutral")
            try:
                emotion_type = EmotionType(emotion_type_str)
            except ValueError:
                emotion_type = EmotionType.NEUTRAL
            
            result = EmotionResult(
                emotion_type=emotion_type,
                intensity=float(data.get("intensity", 0.5)),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                secondary_emotions=data.get("secondary_emotions", [])
            )
            
            # 记录历史
            self.emotion_history.append(result)
            if len(self.emotion_history) > 50:
                self.emotion_history.pop(0)
            
            logger.info(f"[情绪感知] 识别结果: {result.to_dict()}")
            
            return result
            
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}, 响应: {response}")
            return self._perceive_with_keywords(user_message)
    
    def _perceive_with_keywords(self, user_message: str) -> EmotionResult:
        """使用关键词匹配识别情绪（Fallback）"""
        message_lower = user_message.lower()
        
        # 统计各情绪的关键词出现次数
        emotion_scores = {}
        for emotion_type, keywords in self._keyword_dict.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in message_lower:
                    score += 1
            if score > 0:
                emotion_scores[emotion_type] = score
        
        # 选择得分最高的情绪
        if emotion_scores:
            best_emotion = max(emotion_scores.items(), key=lambda x: x[1])[0]
            intensity = min(1.0, emotion_scores[best_emotion] * 0.3)
            return EmotionResult(
                emotion_type=best_emotion,
                intensity=intensity,
                confidence=0.6,  # 关键词匹配置信度较低
                reasoning=f"关键词匹配: {emotion_scores}"
            )
        
        # 默认：中性
        return EmotionResult(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.0,
            confidence=0.5,
            reasoning="未匹配到关键词"
        )
    
    def get_emotion_trend(self, window: int = 5) -> Optional[str]:
        """
        获取情绪趋势
        
        Args:
            window: 查看最近N轮对话
            
        Returns:
            趋势描述: "improving", "declining", "stable", None（数据不足）
        """
        if len(self.emotion_history) < 2:
            return None
        
        recent = self.emotion_history[-window:]
        
        # 计算负面情绪占比
        negative_count = sum(
            1 for r in recent 
            if r.emotion_type.category == EmotionCategory.NEGATIVE
        )
        
        if len(recent) >= 3:
            first_half = recent[:len(recent)//2]
            second_half = recent[len(recent)//2:]
            
            first_negative = sum(
                1 for r in first_half 
                if r.emotion_type.category == EmotionCategory.NEGATIVE
            ) / len(first_half)
            
            second_negative = sum(
                1 for r in second_half 
                if r.emotion_type.category == EmotionCategory.NEGATIVE
            ) / len(second_half)
            
            if second_negative < first_negative - 0.2:
                return "improving"
            elif second_negative > first_negative + 0.2:
                return "declining"
            else:
                return "stable"
        
        return "stable"


# ============= 便捷函数 =============

_emotion_perception_instance = None

def get_emotion_perception(use_llm: bool = True) -> EmotionPerception:
    """获取情绪感知器实例（单例）"""
    global _emotion_perception_instance
    if _emotion_perception_instance is None:
        _emotion_perception_instance = EmotionPerception(use_llm=use_llm)
    return _emotion_perception_instance


async def perceive_emotion(user_message: str, context: Optional[List[dict]] = None) -> dict:
    """
    便捷函数：识别用户情绪
    
    Args:
        user_message: 用户消息
        context: 对话上下文
        
    Returns:
        情绪识别结果字典
    """
    perception = get_emotion_perception()
    result = await perception.perceive(user_message, context)
    return result.to_dict()


# ============= 测试代码 =============

if __name__ == "__main__":
    import asyncio
    
    async def test_emotion_perception():
        """测试情绪感知功能"""
        print("🧪 测试情绪感知模块")
        print("=" * 60)
        
        perception = EmotionPerception(use_llm=False)  # 使用关键词匹配
        
        test_messages = [
            "你们这个系统太垃圾了！",
            "我有点困惑，不知道该怎么填写",
            "太好了！终于成功了！",
            "帮我看看这个项目的情况",
            "我很担心这个结果会不会不通过",
        ]
        
        for msg in test_messages:
            print(f"\n用户消息: {msg}")
            result = await perception.perceive(msg)
            print(f"识别结果: {result.to_dict()}")
            print(f"建议思考模式: {result.get_suggested_thinking_mode()}")
        
        print("\n✅ 测试完成！")
    
    asyncio.run(test_emotion_perception())
