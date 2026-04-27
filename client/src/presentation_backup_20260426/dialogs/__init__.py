"""
对话框包
"""

from client.src.presentation.dialogs.auth_dialog import LoginDialog, RegisterDialog
from client.src.presentation.dialogs.settings_dialog import SystemSettingsDialog, UserSettingsDialog

__all__ = [
    "LoginDialog",
    "RegisterDialog", 
    "SystemSettingsDialog",
    "UserSettingsDialog",
]
