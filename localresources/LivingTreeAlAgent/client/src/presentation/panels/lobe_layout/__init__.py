"""
Lobe 风格布局组件库

提供 LobeHub 风格的三栏式 AI 助手界面

组件：
- LobeStyleWindow: 主窗口
- SessionNavWidget: 会话导航
- ChatAreaWidget: 聊天工作区
- ToolboxDrawerWidget: 技能抽屉
- StatusFlowBar: 状态流条
- SkillToggleBinding: 技能开关绑定

使用示例：
    from ui.lobe_layout import LobeStyleWindow

    window = LobeStyleWindow()
    window.show()
"""

from .lobe_models import (
    SessionType,
    SkillCategory,
    SkillBinding,
    SessionConfig,
    ChatMessage,
    StatusFlowStep,
    LobeSession,
    SESSION_PRESETS,
    SKILL_PRESETS,
)

from .session_nav import SessionNavWidget
from .chat_area import ChatAreaWidget, StatusFlowBar, ChatBubbleWidget
from .toolbox_drawer import ToolboxDrawerWidget, SkillToggle
from .skill_binding import (
    RelayConfig,
    SkillToggleBinding,
    LobeMessageProcessor,
)

from .lobe_window import LobeStyleWindow

__all__ = [
    # 模型
    "SessionType",
    "SkillCategory",
    "SkillBinding",
    "SessionConfig",
    "ChatMessage",
    "StatusFlowStep",
    "LobeSession",
    "SESSION_PRESETS",
    "SKILL_PRESETS",

    # 组件
    "SessionNavWidget",
    "ChatAreaWidget",
    "StatusFlowBar",
    "ChatBubbleWidget",
    "ToolboxDrawerWidget",
    "SkillToggle",

    # 绑定逻辑
    "RelayConfig",
    "SkillToggleBinding",
    "LobeMessageProcessor",

    # 主窗口
    "LobeStyleWindow",
]
