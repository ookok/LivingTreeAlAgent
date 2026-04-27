"""
A2UI 范式 - AI 增强的自适应用户界面

核心设计理念：
1. 自适应 - 根据系统状态和用户需求自动调整 UI
2. 智能降级 - 当核心服务不可用时提供优雅的降级方案
3. 按需加载 - 仅加载当前需要的 UI 组件
4. 实时反馈 - 所有操作都有进度提示和状态反馈
5. 快捷配置 - 所有配置调用都有快捷修改功能
"""

from .core import A2UIManager, A2UIPanel, A2UIConfig
from .loader import UILoader, UILoaderManager
from .fallback import FallbackManager
from .progress import ProgressManager
from .config import ConfigQuickEdit, ConfigQuickEditManager

__all__ = [
    "A2UIManager",
    "A2UIPanel",
    "A2UIConfig",
    "UILoader",
    "UILoaderManager",
    "FallbackManager",
    "ProgressManager",
    "ConfigQuickEdit",
    "ConfigQuickEditManager"
]
