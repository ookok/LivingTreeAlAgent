# -*- coding: utf-8 -*-
"""
动作处理器 - Intent → Action Mapping
=====================================

将解析后的 IntentType 映射到具体的动作处理器。
每个处理器负责执行一类意图。

扩展方式：
1. 继承 BaseActionHandler
2. 实现 handle() 方法
3. 注册到 ActionHandlerRegistry
"""

from .base import BaseActionHandler, ActionContext, ActionResult, LLMClient, LLMError, get_llm_client
from .code_handler import CodeGenerationHandler
from .code_handler import CodeReviewHandler
from .code_handler import CodeDebugHandler
from .knowledge_handler import KnowledgeQueryHandler
from .knowledge_handler import ConceptExplainerHandler
from .file_handler import FileOperationHandler

__all__ = [
    'BaseActionHandler',
    'ActionContext',
    'ActionResult',
    'LLMClient',
    'LLMError',
    'get_llm_client',
    'CodeGenerationHandler',
    'CodeReviewHandler',
    'CodeDebugHandler',
    'KnowledgeQueryHandler',
    'ConceptExplainerHandler',
    'FileOperationHandler',
]
