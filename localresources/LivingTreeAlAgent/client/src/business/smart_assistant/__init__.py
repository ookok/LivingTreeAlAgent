"""
智能客户端AI助手系统

将AI助手从"问答机"升级为"软件导航员"，提供：
1. 应用知识图谱
2. 深度链接与路由系统
3. AI意图识别与动作映射
4. 动态指引系统
5. 文档与配置集成
"""

from .models import (
    IntentType,
    SecondaryIntent,
    IntentResult,
    NavigationResult,
    UserContext,
    ConversationContext,
    GuideLevel,
    ComponentType,
    LinkType,
    UIPage,
    UIComponent,
    OperationStep,
    OperationPath,
    Route,
    GuideStep,
    Guide,
)

from .knowledge_graph import KnowledgeGraph, get_knowledge_graph
from .intent_recognizer import IntentRecognizer, get_intent_recognizer
from .guide_system import GuideSystem, get_guide_system, GuideState
from .smart_assistant import (
    SmartAssistant,
    get_smart_assistant,
    process_query,
    navigate_to,
    start_tutorial,
)

__all__ = [
    # 模型
    "IntentType",
    "SecondaryIntent", 
    "IntentResult",
    "NavigationResult",
    "UserContext",
    "ConversationContext",
    "GuideState",
    "GuideLevel",
    "ComponentType",
    "LinkType",
    "UIPage",
    "UIComponent",
    "OperationStep",
    "OperationPath",
    "Route",
    "GuideStep",
    "Guide",
    
    # 核心组件
    "KnowledgeGraph",
    "get_knowledge_graph",
    "IntentRecognizer",
    "get_intent_recognizer",
    "GuideSystem",
    "get_guide_system",
    
    # 主类
    "SmartAssistant",
    "get_smart_assistant",
    
    # 便捷函数
    "process_query",
    "navigate_to",
    "start_tutorial",
]
