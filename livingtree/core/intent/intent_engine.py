"""
意图识别引擎类型定义

用于 livingtree 的意图识别、分类和优先级管理

从 client.src.business.intent_engine 迁移而来
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class IntentType(Enum):
    QUESTION = "question"
    COMMAND = "command"
    CREATION = "creation"
    ANALYSIS = "analysis"
    SEARCH = "search"
    CONVERSATION = "conversation"
    TRANSLATION = "translation"
    CODING = "coding"
    UNKNOWN = "unknown"


class IntentPriority(Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class Intent:
    intent_type: IntentType
    content: str = ""
    confidence: float = 0.0
    priority: IntentPriority = IntentPriority.MEDIUM
    entities: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_input: Optional[str] = None
    trace: Optional[List[str]] = None

    def to_dict(self) -> dict:
        return {
            "type": self.intent_type.value,
            "content": self.content,
            "confidence": self.confidence,
            "priority": self.priority.value,
            "entities": self.entities,
        }


class IntentEngine:

    def __init__(self):
        self._intents: List[Intent] = []

    def parse(self, text: str) -> Intent:
        text_lower = text.lower()

        if any(k in text_lower for k in ["创建", "新建", "生成", "写", "设计"]):
            intent_type = IntentType.CREATION
        elif any(k in text_lower for k in ["分析", "评估", "检查", "审查"]):
            intent_type = IntentType.ANALYSIS
        elif any(k in text_lower for k in ["搜索", "查找", "查询", "找"]):
            intent_type = IntentType.SEARCH
        elif any(k in text_lower for k in ["翻译", "转换"]):
            intent_type = IntentType.TRANSLATION
        elif any(k in text_lower for k in ["代码", "编程", "实现", "函数"]):
            intent_type = IntentType.CODING
        elif any(k in text_lower for k in ["哪里", "怎么", "什么", "为什么", "如何"]):
            intent_type = IntentType.QUESTION
        else:
            intent_type = IntentType.CONVERSATION

        intent = Intent(
            intent_type=intent_type,
            content=text,
            confidence=0.8,
            raw_input=text,
        )
        self._intents.append(intent)
        return intent

    def get_recent_intents(self, n: int = 5) -> List[Intent]:
        return self._intents[-n:]


__all__ = ["IntentType", "IntentPriority", "Intent", "IntentEngine"]
