"""
Self-Awareness System - 自我意识系统 (向后兼容层)

⚠️ 已迁移至 livingtree.core.self_awareness
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.core.self_awareness import (
    SelfAwarenessSystem, SystemState,
    MirrorLauncher, MirrorInstance,
    ComponentScanner, UIComponent, ScanResult, ComponentType,
    ProblemDetector, ProblemReport, ProblemSeverity,
    HotFixEngine, FixResult, FixStrategy,
    AutoTester, TestCase, TestResult,
    RootCauseTracer, RootCause,
    DeploymentManager, DeploymentRecord, DeploymentStatus,
    BackupManager, BackupRecord, BackupStatus,
    SelfReflection, ReflectionResult,
    GoalManager, Goal,
    AutonomyController, AutonomyLevel, AutonomyPolicy,
)

__all__ = [
    'SelfAwarenessSystem', 'SystemState',
    'MirrorLauncher', 'MirrorInstance',
    'ComponentScanner', 'UIComponent', 'ScanResult', 'ComponentType',
    'ProblemDetector', 'ProblemReport', 'ProblemSeverity',
    'HotFixEngine', 'FixResult', 'FixStrategy',
    'AutoTester', 'TestCase', 'TestResult',
    'RootCauseTracer', 'RootCause',
    'DeploymentManager', 'DeploymentRecord', 'DeploymentStatus',
    'BackupManager', 'BackupRecord', 'BackupStatus',
    'SelfReflection', 'ReflectionResult',
    'GoalManager', 'Goal',
    'AutonomyController', 'AutonomyLevel', 'AutonomyPolicy',
]

__version__ = '2.0.0'
