"""
IntentEngine - 意图驱动引擎
核心模块：意图解析、分类、执行、桥接

快速开始：
    from core.intent_engine import IntentEngine

    engine = IntentEngine()
    intent = engine.parse("帮我写一个排序算法，用Python")

    # ✅ 解析意图（已有能力）
    print(intent.intent_type)    # CODE_GENERATION
    print(intent.tech_stack)     # ['python']
    print(intent.action)         # 编写

    # ✅ 执行意图（新增能力！）
    from core.intent_engine.intent_action_bridge import IntentActionBridge
    bridge = IntentActionBridge(engine)
    result = bridge.execute(intent)
    print(result.output)          # 生成的排序算法代码

    # ✅ 或者更简洁：一站式 parse_and_execute
    result = bridge.parse_and_execute("解释一下什么是装饰器")
    print(result.output)          # 装饰器的概念解释
"""

from .intent_parser import IntentParser
from .intent_classifier import IntentClassifier
from .intent_executor import IntentExecutor
from .intent_cache import IntentCache
from .intent_result import IntentResult, IntentStatus
from .intent_types import Intent, IntentType

# 意图→执行桥接器
from .intent_action_bridge import IntentActionBridge, get_bridge

# 动作处理器（可扩展）
from .action_handlers import (
    BaseActionHandler,
    ActionContext,
    ActionResult,
    CodeGenerationHandler,
    CodeReviewHandler,
    CodeDebugHandler,
    KnowledgeQueryHandler,
    ConceptExplainerHandler,
    FileOperationHandler,
)

__all__ = [
    # 核心引擎
    'IntentParser',
    'IntentClassifier',
    'IntentExecutor',
    'IntentCache',
    'IntentResult',
    'IntentStatus',
    'Intent',
    'IntentType',
    # 桥接器
    'IntentActionBridge',
    'get_bridge',
    # 处理器
    'BaseActionHandler',
    'ActionContext',
    'ActionResult',
    'CodeGenerationHandler',
    'CodeReviewHandler',
    'CodeDebugHandler',
    'KnowledgeQueryHandler',
    'ConceptExplainerHandler',
    'FileOperationHandler',
]

__version__ = '1.0.0'
