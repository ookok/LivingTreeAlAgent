"""
Self-Awareness System - 自我意识系统
核心模块：镜像测试、组件扫描、问题检测、自动修复
"""

from .mirror_launcher import MirrorLauncher, MirrorInstance
from .component_scanner import ComponentScanner, UIComponent
from .problem_detector import ProblemDetector, ProblemReport
from .hotfix_engine import HotFixEngine, FixResult

__all__ = [
    'MirrorLauncher',
    'MirrorInstance',
    'ComponentScanner',
    'UIComponent',
    'ProblemDetector',
    'ProblemReport',
    'HotFixEngine',
    'FixResult',
]

__version__ = '0.1.0'
