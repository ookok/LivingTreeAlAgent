"""
UI Components - 通用 UI 组件库
"""

from .spinner import QSpinner
from .card import QCardWidget
from .gauge import QGauge

# 流式输出组件
from .streaming_output import (
    StreamingOutputWidget,
    StreamingTextBrowser,
    StreamingEngine,
    ThinkingPanel,
    MarkdownHighlighter,
    CodeBlockHighlighter,
    StreamingType,
    StreamChunk,
    ThinkingStep,
)

# 意图工作台
from .intent_workspace import (
    IntentWorkspace,
    IntentAnalyzer,
    IntentType,
    WorkMode,
)

# 代码差异高亮
from .diff_viewer import (
    DiffViewer,
    SideBySideDiffViewer,
    InlineDiffViewer,
    DiffCalculator,
    DiffSyntaxHighlighter,
    DiffType,
)

# 追问面板 (Phase 2 新增)
from .guidance_panel import (
    GuidancePanel,
    GuidanceButton,
    GuidanceCard,
    GuidanceManager,
    GuidanceItem,
    GuidanceDisplayMode,
    GuidancePosition,
    create_guidance_panel,
    quick_guidance_response,
    DARK_THEME_STYLES,
    LIGHT_THEME_STYLES,
)

__all__ = [
    # 基础组件
    "QSpinner",
    "QCardWidget",
    "QGauge",
    # 流式输出
    "StreamingOutputWidget",
    "StreamingTextBrowser",
    "StreamingEngine",
    "ThinkingPanel",
    "MarkdownHighlighter",
    "CodeBlockHighlighter",
    "StreamingType",
    "StreamChunk",
    "ThinkingStep",
    # 意图工作台
    "IntentWorkspace",
    "IntentAnalyzer",
    "IntentType",
    "WorkMode",
    # 差异高亮
    "DiffViewer",
    "SideBySideDiffViewer",
    "InlineDiffViewer",
    "DiffCalculator",
    "DiffSyntaxHighlighter",
    "DiffType",
    # 追问面板
    "GuidancePanel",
    "GuidanceButton",
    "GuidanceCard",
    "GuidanceManager",
    "GuidanceItem",
    "GuidanceDisplayMode",
    "GuidancePosition",
    "create_guidance_panel",
    "quick_guidance_response",
    "DARK_THEME_STYLES",
    "LIGHT_THEME_STYLES",
]