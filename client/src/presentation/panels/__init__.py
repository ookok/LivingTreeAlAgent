"""
面板模块

包含聊天窗口、IDE窗口等主要面板
"""

# 原有面板（保留兼容）
from .chat_window import (
    ChatWindow,
)

from .ide_window import (
    IDEWindow,
    PreviewPanel,
)

# 新统一面板（整合业务逻辑和现代化UI）
from .unified_chat_panel import (
    UnifiedChatPanel,
)

from .unified_ide_panel import (
    UnifiedIDEPanel,
)

__all__ = [
    # 原有面板（保留兼容）
    'ChatWindow',
    'IDEWindow',
    'PreviewPanel',
    
    # 新统一面板
    'UnifiedChatPanel',
    'UnifiedIDEPanel',
]