"""
PyQt6 Test Commander - PyQt6测试指挥官
核心模块：AI驱动的UI测试控制台
"""

from .test_console import AITestCommander, TestTask
from .external_controller import ExternalAppController, ControlStrategy
from .screen_monitor import ScreenMonitor, VisualElement
from .test_executor import TestExecutor, TestResult

__all__ = [
    'AITestCommander',
    'TestTask',
    'ExternalAppController',
    'ControlStrategy',
    'ScreenMonitor',
    'VisualElement',
    'TestExecutor',
    'TestResult',
]

__version__ = '0.1.0'
