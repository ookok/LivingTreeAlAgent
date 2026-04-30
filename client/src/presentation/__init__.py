"""
Presentation Layer - UI展示层

包含所有UI组件、面板和服务
"""

# 组件
from .components import (
    MessageBubble,
    CodeMessageBubble,
    ImageMessageBubble,
    MessageType,
    ContextPanel,
    SmartCodeEditor,
    SmartInputField,
)

# 面板
from .panels import (
    ChatWindow,
    IDEWindow,
    PreviewPanel,
)

# 服务
from .services import (
    ThemeSystem,
    get_theme_system,
    ThemeColors,
    FontConfig,
    I18nService,
    get_i18n_service,
)

__all__ = [
    # 组件
    'MessageBubble',
    'CodeMessageBubble',
    'ImageMessageBubble',
    'MessageType',
    'ContextPanel',
    'SmartCodeEditor',
    'SmartInputField',
    
    # 面板
    'ChatWindow',
    'IDEWindow',
    'PreviewPanel',
    
    # 服务
    'ThemeSystem',
    'get_theme_system',
    'ThemeColors',
    'FontConfig',
    'I18nService',
    'get_i18n_service',
]