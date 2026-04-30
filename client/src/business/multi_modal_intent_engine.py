"""多模态意图理解引擎 - 跨模态语义融合与上下文感知意图追踪"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio

class InputType(Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    FILE = "file"
    EVENT = "event"

@dataclass
class InputData:
    """输入数据"""
    type: InputType
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

@dataclass
class Intent:
    """意图定义"""
    type: str
    confidence: float
    parameters: Dict[str, Any] = field(default_factory=dict)
    sub_intents: List['Intent'] = field(default_factory=list)
    context: Optional[Dict[str, Any]] = None

class IntentionTracker:
    """意图追踪器"""
    
    def __init__(self):
        self._history = {}
    
    def track(self, user_id: str, intent: Intent) -> Intent:
        """追踪用户意图演变"""
        if user_id not in self._history:
            self._history[user_id] = []
        
        self._history[user_id].append(intent)
        
        if len(self._history[user_id]) > 10:
            self._history[user_id] = self._history[user_id][-10:]
        
        return intent
    
    def get_history(self, user_id: str) -> List[Intent]:
        """获取用户意图历史"""
        return self._history.get(user_id, [])
    
    def predict_next_intent(self, user_id: str) -> Optional[str]:
        """预测用户下一步意图"""
        history = self._history.get(user_id, [])
        if len(history) < 2:
            return None
        
        recent_types = [h.type for h in history[-3:]]
        if len(set(recent_types)) == 1:
            return recent_types[-1]
        
        return None

class SemanticFusion:
    """语义融合器"""
    
    async def fuse(self, inputs: List[InputData]) -> Dict[str, Any]:
        """融合多模态语义"""
        fused = {
            "text_content": "",
            "visual_content": [],
            "audio_content": [],
            "file_content": [],
            "events": [],
            "combined_semantics": []
        }
        
        for input_data in inputs:
            if input_data.type == InputType.TEXT:
                fused["text_content"] += str(input_data.content) + " "
            elif input_data.type == InputType.IMAGE:
                fused["visual_content"].append(input_data.content)
            elif input_data.type == InputType.VOICE:
                fused["audio_content"].append(input_data.content)
            elif input_data.type == InputType.FILE:
                fused["file_content"].append(input_data.content)
            elif input_data.type == InputType.EVENT:
                fused["events"].append(input_data.content)
        
        fused["combined_semantics"] = self._combine_semantics(fused)
        
        return fused
    
    def _combine_semantics(self, data: Dict[str, Any]) -> List[str]:
        """组合语义信息"""
        semantics = []
        
        if data["text_content"]:
            semantics.append(f"文本: {data['text_content']}")
        
        if data["visual_content"]:
            semantics.append(f"图片数量: {len(data['visual_content'])}")
        
        if data["audio_content"]:
            semantics.append(f"音频数量: {len(data['audio_content'])}")
        
        if data["file_content"]:
            semantics.append(f"文件数量: {len(data['file_content'])}")
        
        if data["events"]:
            semantics.append(f"事件数量: {len(data['events'])}")
        
        return semantics

class MultiModalIntentEngine:
    """多模态意图理解引擎"""
    
    def __init__(self):
        self._intention_tracker = IntentionTracker()
        self._semantic_fusion = SemanticFusion()
        self._initialized = False
    
    async def initialize(self):
        """初始化引擎"""
        self._initialized = True
    
    async def understand(self, inputs: List[InputData], user_id: str = "default") -> Intent:
        """理解多模态输入"""
        if not self._initialized:
            await self.initialize()
        
        fused_semantics = await self._semantic_fusion.fuse(inputs)
        
        intent = self._parse_intent(fused_semantics)
        
        tracked_intent = self._intention_tracker.track(user_id, intent)
        
        return tracked_intent
    
    def _parse_intent(self, semantics: Dict[str, Any]) -> Intent:
        """解析意图"""
        text = semantics.get("text_content", "").lower()
        
        intent_mapping = [
            ("搜索", "search"),
            ("查找", "search"),
            ("查询", "search"),
            ("帮我", "assist"),
            ("创建", "create"),
            ("生成", "generate"),
            ("分析", "analyze"),
            ("总结", "summarize"),
            ("写", "write"),
            ("代码", "code"),
            ("文件", "file"),
            ("工具", "tool"),
            ("记忆", "memory"),
            ("学习", "learn"),
            ("设置", "settings"),
        ]
        
        intent_type = "unknown"
        confidence = 0.7
        
        for keyword, itype in intent_mapping:
            if keyword in text:
                intent_type = itype
                confidence = min(0.95, confidence + 0.1)
                break
        
        parameters = self._extract_parameters(text)
        
        return Intent(
            type=intent_type,
            confidence=confidence,
            parameters=parameters,
            sub_intents=self._decompose_intent(intent_type, parameters),
            context={"semantics": semantics}
        )
    
    def _extract_parameters(self, text: str) -> Dict[str, Any]:
        """提取参数"""
        params = {}
        
        if "文件" in text:
            params["target"] = "file"
        
        if "代码" in text:
            params["target"] = "code"
        
        if "报告" in text:
            params["target"] = "report"
        
        return params
    
    def _decompose_intent(self, intent_type: str, parameters: Dict[str, Any]) -> List[Intent]:
        """分解意图"""
        sub_intents = []
        
        if intent_type == "search":
            sub_intents.append(Intent(type="search_query", confidence=0.9))
            sub_intents.append(Intent(type="search_filter", confidence=0.8))
        
        elif intent_type == "create":
            sub_intents.append(Intent(type="create_plan", confidence=0.9))
            sub_intents.append(Intent(type="create_execute", confidence=0.85))
        
        elif intent_type == "analyze":
            sub_intents.append(Intent(type="analyze_input", confidence=0.9))
            sub_intents.append(Intent(type="analyze_process", confidence=0.85))
            sub_intents.append(Intent(type="analyze_output", confidence=0.8))
        
        return sub_intents
    
    def get_intention_history(self, user_id: str) -> List[Intent]:
        """获取用户意图历史"""
        return self._intention_tracker.get_history(user_id)
    
    def predict_next_intent(self, user_id: str) -> Optional[str]:
        """预测用户下一步意图"""
        return self._intention_tracker.predict_next_intent(user_id)

_intent_engine_instance = None

def get_multi_modal_intent_engine() -> MultiModalIntentEngine:
    """获取多模态意图引擎实例"""
    global _intent_engine_instance
    if _intent_engine_instance is None:
        _intent_engine_instance = MultiModalIntentEngine()
    return _intent_engine_instance