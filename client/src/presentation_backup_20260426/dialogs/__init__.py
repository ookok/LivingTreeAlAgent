"""
对话框包
"""

from .presentation.dialogs.auth_dialog import LoginDialog, RegisterDialog
from .presentation.dialogs.settings_dialog import SystemSettingsDialog, UserSettingsDialog

__all__ = [
    "LoginDialog",
    "RegisterDialog", 
    "SystemSettingsDialog",
    "UserSettingsDialog",
]
