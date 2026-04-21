"""
AI聊天插件

功能：
- 与AI对话
- 对话历史管理
- 多模型切换
- 快捷命令

视图模式：停靠窗口（Dockable）- 适合侧边栏参考
"""

from .ai_chat_plugin import AIChatPlugin

__all__ = ['AIChatPlugin']