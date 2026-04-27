"""
Self-Awareness System - 自我意识系统
核心模块：镜像测试、组件扫描、问题检测、自动修复、自我监控
"""

from .mirror_launcher import MirrorLauncher, MirrorInstance
from .component_scanner import ComponentScanner, UIComponent, ScanResult, ComponentType
from .problem_detector import ProblemDetector, ProblemReport, ProblemSeverity
from .hotfix_engine import HotFixEngine, FixResult, FixStrategy
from .self_awareness_system import SelfAwarenessSystem, SystemState
from .auto_tester import AutoTester, TestCase, TestResult
from .root_cause_tracer import RootCauseTracer, RootCause
from .deployment_manager import DeploymentManager, DeploymentRecord, DeploymentStatus
from .backup_manager import BackupManager, BackupRecord, BackupStatus

__all__ = [
    'MirrorLauncher',
    'MirrorInstance',
    'ComponentScanner',
    'UIComponent',
    'ScanResult',
    'ComponentType',
    'ProblemDetector',
    'ProblemReport',
    'ProblemSeverity',
    'HotFixEngine',
    'FixResult',
    'FixStrategy',
    'SelfAwarenessSystem',
    'SystemState',
    'AutoTester',
    'TestCase',
    'TestResult',
    'RootCauseTracer',
    'RootCause',
    'DeploymentManager',
    'DeploymentRecord',
    'DeploymentStatus',
    'BackupManager',
    'BackupRecord',
    'BackupStatus',
]


__version__ = '1.0.0'
