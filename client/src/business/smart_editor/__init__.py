"""
Smart Editor - 统一AI增强编辑器
=============================

核心理念："一个编辑器，解决所有输入问题"

无论用户是要写配置、记笔记、填表单、写代码，还是与AI对话，
都用这同一个编辑器，获得一致的AI增强体验。

架构:
    editor_core.py      - 编辑器核心，多模式支持
    ai_operations.py    - AI操作引擎
    context_engine.py   - 上下文感知引擎
    completion_engine.py - 智能补全引擎
    theme_layout.py     - 主题和布局系统
    editor_window.py    - PyQt UI窗口
"""

from .editor_core import (
    SmartEditor,
    EditorMode,
    EditorConfig,
    TextRange,
    EditOperation,
    get_editor,
)

from .ai_operations import (
    AIOperationType,
    AIOperationResult,
    get_ai_operator,
    sync_get_ai_operator,
)

from .context_engine import (
    ContextType,
    EditorContext,
    get_context_engine,
)

from .completion_engine import (
    CompletionItem,
    CompletionKind,
    get_completion_engine,
)

from .theme_layout import (
    ThemeType,
    LayoutType,
    ThemeSystem,
    LayoutManager,
    EditorTheme,
    get_theme_system,
    get_layout_manager,
)

from .editor_window import (
    SmartEditorWidget,
    EditorWindow,
)

__version__ = "1.0.0"

__all__ = [
    # 编辑器核心
    "SmartEditor",
    "EditorMode",
    "EditorConfig",
    "TextRange",
    "EditOperation",
    "get_editor",

    # AI操作
    "AIOperationType",
    "AIOperationResult",
    "get_ai_operator",
    "sync_get_ai_operator",

    # 上下文
    "ContextType",
    "EditorContext",
    "get_context_engine",

    # 补全
    "CompletionItem",
    "CompletionKind",
    "get_completion_engine",

    # 主题和布局
    "ThemeType",
    "LayoutType",
    "ThemeSystem",
    "LayoutManager",
    "EditorTheme",
    "get_theme_system",
    "get_layout_manager",

    # UI
    "SmartEditorWidget",
    "EditorWindow",
]