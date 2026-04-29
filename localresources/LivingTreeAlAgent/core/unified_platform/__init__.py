"""
Unified Platform - 统一内容发布平台
====================================

整合邮件、博客、论坛三大内置平台，支持富文本发布和数字分身自动发布。

功能模块：
1. RichTextEditor - 富文本编辑器
2. UnifiedPublisher - 统一发布器
3. AutoPublisher - 数字分身自动发布
4. PlatformHub - 平台调度中心
5. HermesMessageHub - Hermes 统一消息中心

支持三端：
- 桌面端 (PyQt6)
- Web 端 (React)
- 移动端 (Flutter/小程序)

Author: Hermes Desktop Team
"""

from .rich_text_editor import RichTextContent, RichTextEditor
from .unified_publisher import UnifiedPublisher, PublishTarget, PublishResult
from .auto_publisher import AutoPublisher, PublishingSchedule, ContentTemplate
from .platform_hub import PlatformHub, PlatformType
from .hermes_message_hub import (
    HermesMessageHub,
    UnifiedMessage,
    ContentItem,
    MessageSource,
    MessageIntent
)

__all__ = [
    # Rich Text
    "RichTextContent",
    "RichTextEditor",
    # Publisher
    "UnifiedPublisher",
    "PublishTarget",
    "PublishResult",
    # Auto Publisher
    "AutoPublisher",
    "PublishingSchedule",
    "ContentTemplate",
    # Hub
    "PlatformHub",
    "PlatformType",
    # Message Hub
    "HermesMessageHub",
    "UnifiedMessage",
    "ContentItem",
    "MessageSource",
    "MessageIntent",
]
