"""
通用组件库 - 统一导出

使用方式：
    from client.src.presentation.components import PrimaryButton, SearchInput, InfoCard
"""

from .buttons import PrimaryButton, SecondaryButton, IconButton, DangerButton
from .inputs import PrimaryLineEdit, SearchInput, PrimaryTextEdit, LabeledInput
from .cards import Card, InfoCard, StatsCard, ActionCard
from .dialogs import DialogService, BaseDialog, ConfirmDialog

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
]
