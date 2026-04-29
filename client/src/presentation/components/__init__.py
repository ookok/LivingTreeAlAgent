"""
通用组件库 - 统一导出

使用方式：
    from client.src.presentation.components import PrimaryButton, SearchInput, InfoCard
    from client.src.presentation.components import UIDescriptorProtocol, SemanticParser, ControlFactory
    from client.src.presentation.components import FilePreviewer, URLPreviewer, CodeHighlighterWidget
    from client.src.presentation.components import StreamingThoughtWidget, ThinkingIndicator
"""

from .buttons import PrimaryButton, SecondaryButton, IconButton, DangerButton
from .inputs import PrimaryLineEdit, SearchInput, PrimaryTextEdit, LabeledInput
from .cards import Card, InfoCard, StatsCard, ActionCard
from .dialogs import DialogService, BaseDialog, ConfirmDialog
from .command_palette import CommandPalette, Command, CommandCategory
from .ui_descriptor import (
    UIDescriptorProtocol, UIComponent, UIResponse,
    ControlType, LayoutType, ActionType,
    FormField, ActionButton, ClarificationRequest,
    ClarificationOption, ValidationRule
)
from .semantic_parser import SemanticParser
from .control_factory import ControlFactory
from .layout_engine import LayoutEngine
from .markdown_renderer import MarkdownRenderer
from .code_highlighter import CodeHighlighterWidget, CodeBlockRenderer, SyntaxHighlighter, highlight_code
from .file_previewer import FilePreviewer, URLPreviewer, preview_file_or_url
from .streaming_thought import (
    StreamingThoughtWidget, ThinkingIndicator, ToolCallAnimation,
    DataFlowAnimation, ProgressRing, create_thinking_bubble, create_tool_call_animation
)

__all__ = [
    # 按钮
    "PrimaryButton",
    "SecondaryButton",
    "IconButton",
    "DangerButton",
    # 输入框
    "PrimaryLineEdit",
    "SearchInput",
    "PrimaryTextEdit",
    "LabeledInput",
    # 卡片
    "Card",
    "InfoCard",
    "StatsCard",
    "ActionCard",
    # 对话框
    "DialogService",
    "BaseDialog",
    "ConfirmDialog",
    # 命令面板
    "CommandPalette",
    "Command",
    "CommandCategory",
    # UI描述符协议
    "UIDescriptorProtocol",
    "UIComponent",
    "UIResponse",
    "ControlType",
    "LayoutType",
    "ActionType",
    "FormField",
    "ActionButton",
    "ClarificationRequest",
    "ClarificationOption",
    "ValidationRule",
    # 语义解析器
    "SemanticParser",
    # 控件工厂
    "ControlFactory",
    # 布局引擎
    "LayoutEngine",
    # Markdown渲染器
    "MarkdownRenderer",
    # 代码高亮
    "CodeHighlighterWidget",
    "CodeBlockRenderer",
    "SyntaxHighlighter",
    "highlight_code",
    # 文件预览
    "FilePreviewer",
    "URLPreviewer",
    "preview_file_or_url",
    # 流式思考
    "StreamingThoughtWidget",
    "ThinkingIndicator",
    "ToolCallAnimation",
    "DataFlowAnimation",
    "ProgressRing",
    "create_thinking_bubble",
    "create_tool_call_animation",
]
