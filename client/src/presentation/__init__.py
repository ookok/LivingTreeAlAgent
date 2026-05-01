"""
Presentation Layer - 表示层

功能：
1. UI组件管理
2. Web UI集成
3. QWebChannel通信
"""

from .main_window import MainWindow, run_app
from .web_ui.web_channel_backend import WebChannelBackend

__all__ = [
    'MainWindow',
    'run_app',
    'WebChannelBackend',
]