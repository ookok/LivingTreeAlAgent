"""
Emotional Resonance - 情感共振
==============================

通信时不仅传递文字，更传递情感状态

核心概念：
- 情感向量 (Emotion Vector)
- 共振效应 (Resonance Effect)
- 情感同步 (Emotional Sync)

Author: LivingTreeAI Community
"""

import asyncio
import time
import hashlib
import math
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, List, Dict, Tuple
from enum import Enum


class EmotionType(Enum):
    """情感类型"""
    JOY = "joy"           # 喜悦
    SADNESS = "sadness"   # 悲伤
    ANGER = "anger"       # 愤怒
    CALM = "calm"         # 平静
    EXCITEMENT = "excitement"  # 兴奋
    FEAR = "fear"         # 恐惧
    SURPRISE = "surprise" # 惊讶
    DISGUST = "disgust"   # 厌恶
    NEUTRAL = "neutral"   # 中性


@dataclass
class EmotionVector:
    """
    情感向量

    五维情感空间：
    - valence: 效价 (-1 负面 到 +1 正面)
    - arousal: 唤醒度 (0 平静 到 +1 激动)
    - dominance: 主导性 (0 顺从 到 +1 主导)
    - intensity: 强度 (0 无 到 +1 强烈)
    - duration: 持续性 (0 短暂 到 +1 持久)
    """

    valence: float = 0.0      # -1 to 1
    arousal: float = 0.0      # 0 to 1
    dominance: float = 0.5    # 0 to 1
    intensity: float = 0.5    # 0 to 1
    duration: float = 0.5     # 0 to 1

    # 简化的五维向量（用于UI展示）
    joy: float = 0.0
    sadness: float = 0.0
    anger: float = 0.0
    calm: float = 0.0
    excitement: float = 0.0

    def to_list(self) -> List[float]:
        """转换为列表"""
        return [
            self.valence,
            self.arousal,
            self.dominance,
            self.intensity,
            self.duration,
        ]

    def to_simple_list(self) -> List[float]:
        """转换为简化列表"""
        return [self.joy, self.sadness, self.anger, self.calm, self.excitement]

    def magnitude(self) -> float:
        """计算情感强度"""
        return math.sqrt(sum(x * x for x in self.to_list()))

    def dominant_emotion(self) -> EmotionType:
        """获取主导情感"""
        emotions = {
            EmotionType.JOY: self.joy,
            EmotionType.SADNESS: self.sadness,
            EmotionType.ANGER: self.anger,
            EmotionType.CALM: self.calm,
            EmotionType.EXCITEMENT: self.excitement,
        }
        return max(emotions.items(), key=lambda x: x[1])[0]

    @classmethod
    def from_text_analysis(cls, text: str) -> "EmotionVector":
        """从文本分析情感（简化实现）"""
        vector = cls()

        # 简化关键词匹配
        positive_words = ["好", "棒", "赞", "优秀", "喜欢", "开心", "great", "good", "excellent"]
        negative_words = ["差", "烂", "垃圾", "讨厌", "不喜欢", "bad", "terrible", "hate"]
        excited_words = ["激动", "兴奋", "太棒了", "amazing", "awesome", "wow"]
        calm_words = ["平静", "淡定", "还好", "ok", "okay", "fine"]

        text_lower = text.lower()

        for word in positive_words:
            if word in text_lower:
                vector.valence = min(1.0, vector.valence + 0.2)
                vector.joy = min(1.0, vector.joy + 0.2)

        for word in negative_words:
            if word in text_lower:
                vector.valence = max(-1.0, vector.valence - 0.2)
                vector.sadness = min(1.0, vector.sadness + 0.2)

        for word in excited_words:
            if word in text_lower:
                vector.arousal = min(1.0, vector.arousal + 0.3)
                vector.excitement = min(1.0, vector.excitement + 0.3)

        for word in calm_words:
            if word in text_lower:
                vector.calm = min(1.0, vector.calm + 0.2)

        return vector

    @classmethod
    def neutral(cls) -> "EmotionVector":
        """创建中性情感"""
        vector = cls()
        vector.calm = 0.8
        return vector


@dataclass
class ResonanceEffect:
    """共振效果"""
    source_emotion: EmotionVector
    target_emotion: EmotionVector
    resonance_strength: float  # 0-1
    propagation_depth: int = 1


class EmotionalEncoder:
    """
    情感编码器

    功能：
    1. 情感向量编码
    2. 情感解码
    3. 共振计算
    4. UI 效果生成
    """

    # 共振阈值
    RESONANCE_THRESHOLD = 0.3

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 当前情感状态
        self.current_emotion = EmotionVector.neutral()

        # 情感历史
        self.emotion_history: List[EmotionVector] = []

        # 网络函数
        self._send_func = send_func

        # 回调
        self._on_resonance: Optional[Callable] = None
        self._on_emotion_change: Optional[Callable] = None

    # ========== 编码 ==========

    def encode_with_emotion(
        self,
        text: str,
        emotion: Optional[EmotionVector] = None,
    ) -> dict:
        """
        用情感编码信息

        Returns:
            编码后的消息
        """
        # 如果没有提供情感，从文本分析
        if emotion is None:
            emotion = EmotionVector.from_text_analysis(text)

        # 计算情感哈希（用于快速匹配）
        emotion_hash = self._hash_emotion(emotion)

        # 编码消息
        message = {
            "type": "emotional_message",
            "text": text,
            "emotion": {
                "valence": emotion.valence,
                "arousal": emotion.arousal,
                "dominance": emotion.dominance,
                "intensity": emotion.intensity,
                "duration": emotion.duration,
                "simple": emotion.to_simple_list(),
                "hash": emotion_hash,
            },
            "timestamp": time.time(),
            "sender": self.node_id,
        }

        return message

    def _hash_emotion(self, emotion: EmotionVector) -> str:
        """计算情感哈希"""
        data = ",".join([f"{x:.2f}" for x in emotion.to_list()])
        return hashlib.sha256(data.encode()).hexdigest()[:8]

    # ========== 解码 ==========

    def decode_emotion(self, message: dict) -> Tuple[str, EmotionVector]:
        """解码情感消息"""
        text = message.get("text", "")
        emotion_data = message.get("emotion", {})

        emotion = EmotionVector(
            valence=emotion_data.get("valence", 0),
            arousal=emotion_data.get("arousal", 0),
            dominance=emotion_data.get("dominance", 0.5),
            intensity=emotion_data.get("intensity", 0.5),
            duration=emotion_data.get("duration", 0.5),
        )

        # 恢复简单向量
        simple = emotion_data.get("simple", [0, 0, 0, 0.8, 0])
        emotion.joy = simple[0]
        emotion.sadness = simple[1]
        emotion.anger = simple[2]
        emotion.calm = simple[3]
        emotion.excitement = simple[4]

        return text, emotion

    # ========== 共振计算 ==========

    def calculate_resonance(
        self,
        emotion1: EmotionVector,
        emotion2: EmotionVector,
    ) -> float:
        """
        计算两个情感的共振强度

        Returns:
            共振强度 0-1
        """
        # 使用余弦相似度
        v1 = emotion1.to_list()
        v2 = emotion2.to_list()

        dot = sum(a * b for a, b in zip(v1, v2))
        mag1 = math.sqrt(sum(a * a for a in v1))
        mag2 = math.sqrt(sum(b * b for b in v2))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        similarity = dot / (mag1 * mag2)

        # 转换为 0-1 范围
        resonance = (similarity + 1) / 2

        return max(0, min(1, resonance))

    async def receive_emotional_message(self, message: dict):
        """接收情感消息"""
        text, emotion = self.decode_emotion(message)
        sender = message.get("sender", "unknown")

        # 计算与当前情感的共振
        resonance = self.calculate_resonance(self.current_emotion, emotion)

        effect = ResonanceEffect(
            source_emotion=emotion,
            target_emotion=self.current_emotion,
            resonance_strength=resonance,
        )

        # 更新当前情感（轻微趋近）
        self._update_current_emotion(emotion)

        # 记录历史
        self.emotion_history.append(emotion)
        if len(self.emotion_history) > 100:
            self.emotion_history.pop(0)

        # 触发共振回调
        if resonance > self.RESONANCE_THRESHOLD and self._on_resonance:
            await self._on_resonance(effect, text, sender)

        # 触发情感变化回调
        if self._on_emotion_change:
            await self._on_emotion_change(emotion, text)

    def _update_current_emotion(self, received: EmotionVector, factor: float = 0.1):
        """更新当前情感（平滑趋近）"""
        self.current_emotion.valence += (received.valence - self.current_emotion.valence) * factor
        self.current_emotion.arousal += (received.arousal - self.current_emotion.arousal) * factor
        self.current_emotion.dominance += (received.dominance - self.current_emotion.dominance) * factor

        # 更新简单向量
        self.current_emotion.joy += (received.joy - self.current_emotion.joy) * factor
        self.current_emotion.sadness += (received.sadness - self.current_emotion.sadness) * factor
        self.current_emotion.anger += (received.anger - self.current_emotion.anger) * factor
        self.current_emotion.calm += (received.calm - self.current_emotion.calm) * factor
        self.current_emotion.excitement += (received.excitement - self.current_emotion.excitement) * factor

    # ========== UI 效果生成 ==========

    def get_ui_effect(self, emotion: EmotionVector) -> dict:
        """
        获取UI效果参数

        用于前端根据情感渲染效果
        """
        dominant = emotion.dominant_emotion()

        effects = {
            "color": self._emotion_to_color(emotion),
            "animation": self._emotion_to_animation(emotion),
            "vibration": emotion.intensity if emotion.arousal > 0.7 else 0,
            "sound": self._emotion_to_sound(emotion),
            "background": self._emotion_to_background(emotion),
        }

        return effects

    def _emotion_to_color(self, emotion: EmotionVector) -> str:
        """情感转颜色"""
        if emotion.anger > 0.5:
            return "#FF4444"  # 红色
        elif emotion.joy > 0.5:
            return "#FFD700"  # 金色
        elif emotion.calm > 0.5:
            return "#4CAF50"  # 绿色
        elif emotion.sadness > 0.5:
            return "#2196F3"  # 蓝色
        elif emotion.excitement > 0.5:
            return "#FF9800"  # 橙色
        return "#9E9E9E"  # 灰色

    def _emotion_to_animation(self, emotion: EmotionVector) -> str:
        """情感转动画"""
        if emotion.intensity > 0.7:
            if emotion.arousal > 0.7:
                return "pulse_fast"  # 快脉冲
            else:
                return "glow"  # 发光
        elif emotion.intensity > 0.4:
            return "breathe"  # 呼吸
        return "none"

    def _emotion_to_sound(self, emotion: EmotionVector) -> Optional[str]:
        """情感转音效（人耳不可闻超声波）"""
        if emotion.intensity < 0.3:
            return None

        # 生成不可闻超声波
        frequency = 20000 + emotion.valence * 5000  # 20-25kHz
        return f"ultrasonic_{int(frequency)}"

    def _emotion_to_background(self, emotion: EmotionVector) -> str:
        """情感转背景"""
        base_color = self._emotion_to_color(emotion)
        if emotion.intensity > 0.7:
            return f"{base_color}20"  # 添加透明度
        return "transparent"

    # ========== 发送 ==========

    async def send_emotional_message(
        self,
        target_peer: str,
        text: str,
        emotion: Optional[EmotionVector] = None,
    ):
        """发送情感消息"""
        message = self.encode_with_emotion(text, emotion)

        if self._send_func:
            await self._send_func(target_peer, message)

    # ========== 回调设置 ==========

    def set_resonance_callback(self, callback: Callable):
        self._on_resonance = callback

    def set_emotion_change_callback(self, callback: Callable):
        self._on_emotion_change = callback

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "current_emotion": {
                "valence": f"{self.current_emotion.valence:.2f}",
                "arousal": f"{self.current_emotion.arousal:.2f}",
                "dominant": self.current_emotion.dominant_emotion().value,
                "simple": self.current_emotion.to_simple_list(),
            },
            "history_length": len(self.emotion_history),
            "ui_effect": self.get_ui_effect(self.current_emotion),
        }


# 全局单例
_emotion_instance: Optional[EmotionalEncoder] = None


def get_emotional_encoder(node_id: str = "local") -> EmotionalEncoder:
    """获取情感编码器单例"""
    global _emotion_instance
    if _emotion_instance is None:
        _emotion_instance = EmotionalEncoder(node_id)
    return _emotion_instance