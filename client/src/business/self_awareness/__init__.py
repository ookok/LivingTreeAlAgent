"""
Self-Awareness System - 自我意识系统
核心模块：镜像测试、组件扫描、问题检测、自动修复、自我监控、自我反思、目标管理、自主控制

核心能力：
1. 自我监控 - 零干扰后台监控
2. 自我诊断 - 自动检测问题
3. 自我修复 - 自动修复部署
4. 自我反思 - 元认知能力
5. 自我进化 - 自主学习优化
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
from .self_reflection import SelfReflection, ReflectionResult
from .goal_manager import GoalManager, Goal
from .autonomy_controller import AutonomyController, AutonomyLevel, AutonomyPolicy

__all__ = [
    # 核心系统
    'SelfAwarenessSystem',
    'SystemState',
    
    # 基础组件
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
    
    # 自我意识组件
    'SelfReflection',
    'ReflectionResult',
    'GoalManager',
    'Goal',
    'AutonomyController',
    'AutonomyLevel',
    'AutonomyPolicy',
]


__version__ = '2.0.0'
