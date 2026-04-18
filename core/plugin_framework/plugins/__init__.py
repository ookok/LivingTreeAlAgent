"""
插件目录 - Plugins

内置示例插件
"""

from .knowledge_base.knowledge_base_plugin import KnowledgeBasePlugin
from .ai_chat.ai_chat_plugin import AIChatPlugin
from .im_client.im_client_plugin import IMClientPlugin

__all__ = [
    'KnowledgeBasePlugin',
    'AIChatPlugin',
    'IMClientPlugin',
]