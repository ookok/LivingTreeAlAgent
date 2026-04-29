# -*- coding: utf-8 -*-
"""
AI Flow Layout UI System - AI驱动的流式布局UI系统

支持将AI的自然语言响应转换为可交互的GUI界面。

核心模块:
- ui_descriptor: UI描述符协议
- semantic_parser: 语义解析器
- widget_factory: 控件工厂
- flow_layout_engine: 流式布局引擎
- ai_layout_binding: AI布局绑定
"""

from .ui_descriptor import UIDescriptor, WidgetDescriptor, FormDescriptor
from .semantic_parser import SemanticParser
from .widget_factory import WidgetFactory
from .flow_layout_engine import FlowLayoutEngine, FlowLayout
from .ai_layout_binding import AILayoutBinding

__all__ = [
    'UIDescriptor', 'WidgetDescriptor', 'FormDescriptor',
    'SemanticParser',
    'WidgetFactory',
    'FlowLayoutEngine', 'FlowLayout',
    'AILayoutBinding',
]
