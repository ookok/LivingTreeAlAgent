"""
创作工作室 (Creative Studio)
============================

核心理念：浏览器即创作沙盒，AI 深度嵌入浏览器运行时环境。

模块结构：
- WebCoEditor: 网页内嵌的实时 AI 协同编辑器
- ComponentMarket: AI 组件市场（Web Components）
- AIConsole: AI 命令行（Console 2.0）
- CollaborativeCanvas: P2P 实时协作画布
- GameAI: HTML5 游戏与 AI 深度融合
- AIExtension: 浏览器插件形态的 AI 创作助手
"""

from .web_co_editor import (
    WebCoEditor,
    EditorState,
    Suggestion,
    create_web_co_editor,
)
from .component_market import (
    ComponentMarket,
    AIComponent,
    ComponentTemplate,
    create_component_market,
)
from .ai_console import (
    AIConsole,
    ConsoleCommand,
    ConsoleResult,
    create_ai_console,
)
from .collaborative_canvas import (
    CollaborativeCanvas,
    CanvasState,
    CanvasElement,
    create_collaborative_canvas,
)
from .game_ai import (
    GameAI,
    AINPC,
    DynamicStory,
    HotReloader,
    create_game_ai,
)
from .ai_extension import (
    AIExtension,
    ExtensionManifest,
    InjectionScript,
    create_ai_extension,
)

__all__ = [
    # 网页协同编辑器
    "WebCoEditor",
    "EditorState",
    "Suggestion",
    "create_web_co_editor",
    # AI 组件市场
    "ComponentMarket",
    "AIComponent",
    "ComponentTemplate",
    "create_component_market",
    # AI 命令行
    "AIConsole",
    "ConsoleCommand",
    "ConsoleResult",
    "create_ai_console",
    # 协作画布
    "CollaborativeCanvas",
    "CanvasState",
    "CanvasElement",
    "create_collaborative_canvas",
    # 游戏 AI
    "GameAI",
    "AINPC",
    "DynamicStory",
    "HotReloader",
    "create_game_ai",
    # AI 扩展
    "AIExtension",
    "ExtensionManifest",
    "InjectionScript",
    "create_ai_extension",
]