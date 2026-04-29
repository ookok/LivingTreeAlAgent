"""
Intelligent Diagnosis System - 智能日志诊断与自愈系统
=====================================================

核心理念：从"记录发生了什么"到"自动解决什么问题"

三层日志架构：
1. 技术层 - 开发者视角，详细技术细节
2. 诊断层 - 系统自诊断视角，结构化问题分析
3. 用户层 - 普通用户视角，自然语言描述

技术选型（复用优先）：
- loguru: 增强日志 (已选型)
- structlog: 结构化日志
- python-json-logger: JSON格式日志
- elasticsearch: 日志存储检索 (可选)

模块结构：
├── structured_logger.py    - 结构化日志记录器
├── error_classifier.py     - 错误分类引擎
├── diagnosis_engine.py      - 智能诊断引擎
├── auto_fix.py             - 自动修复系统
├── nlg_generator.py        - 自然语言生成
├── task_monitor.py         - 任务健康监控
└── dashboard.py            - 可视化仪表板

Author: LivingTreeAI Community
Version: 1.0.0
"""

__version__ = "1.0.0"

from .structured_logger import (
    StructuredLogger,
    LogLevel,
    ErrorCategory,
    get_logger,
    generate_trace_id,
)
from .error_classifier import ErrorClassifier, classify_error
from .diagnosis_engine import (
    DiagnosisEngine,
    DiagnosisResult,
    get_diagnosis_engine,
)
from .auto_fix import AutoFixSystem, FixStrategy, get_fix_system
from .nlg_generator import (
    NLGGenerator,
    UserLevel,
    generate_user_friendly_error,
)
from .task_monitor import (
    TaskMonitor,
    HealthStatus,
    get_task_monitor,
)
from .dashboard import DiagnosisDashboard, generate_dashboard_html

__all__ = [
    # 结构化日志
    "StructuredLogger",
    "LogLevel",
    "ErrorCategory",
    "get_logger",
    "generate_trace_id",
    # 错误分类
    "ErrorClassifier",
    "classify_error",
    # 诊断引擎
    "DiagnosisEngine",
    "DiagnosisResult",
    "get_diagnosis_engine",
    # 自动修复
    "AutoFixSystem",
    "FixStrategy",
    "get_fix_system",
    # 自然语言生成
    "NLGGenerator",
    "UserLevel",
    "generate_user_friendly_error",
    # 任务监控
    "TaskMonitor",
    "HealthStatus",
    "get_task_monitor",
]
