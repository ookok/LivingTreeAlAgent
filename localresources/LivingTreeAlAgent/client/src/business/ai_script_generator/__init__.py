"""
AI Script Generator - 智能脚本生成系统
=======================================

核心理念：从"工具"到"伙伴"，用户用自然语言描述需求，AI生成可执行脚本

三层架构：
1. 自然语言交互层 - 意图识别、需求解析
2. AI代码生成引擎 - 上下文感知、安全生成
3. 可执行沙箱环境 - 隔离执行、热重载

模块组成：
- script_engine.py: AI脚本生成核心引擎
- script_sandbox.py: 安全脚本执行沙箱
- script_market.py: 脚本市场与分享系统

Author: Hermes Desktop Team
"""

from .script_engine import (
    AIScriptEngine,
    IntentRecognizer,
    SecurityChecker,
    AICodeGenerator,
    ScriptType,
    GenerationStatus,
    ExecutionStatus,
    SafetyLevel,
    IntentResult,
    CodeContext,
    GenerationRequest,
    ScriptCode,
    GenerationResult,
    ExecutionResult,
    get_ai_script_engine,
)

from .script_sandbox import (
    ScriptSandbox,
    SandboxExecutor,
    SandboxConfig,
    ResourceLimit,
    SandboxPermission,
    create_safe_sandbox,
    get_script_sandbox,
)

from .script_market import (
    ScriptMarket,
    ScriptMetadata,
    ScriptPackage,
    ContributorStats,
    BUILTIN_SCRIPTS,
    get_script_market,
)

__version__ = '1.0.0'
__author__ = 'Hermes Desktop Team'

__all__ = [
    # 脚本引擎
    'AIScriptEngine',
    'IntentRecognizer',
    'SecurityChecker',
    'AICodeGenerator',
    'ScriptType',
    'GenerationStatus',
    'ExecutionStatus',
    'SafetyLevel',
    'IntentResult',
    'CodeContext',
    'GenerationRequest',
    'ScriptCode',
    'GenerationResult',
    'ExecutionResult',
    'get_ai_script_engine',
    # 沙箱
    'ScriptSandbox',
    'SandboxExecutor',
    'SandboxConfig',
    'ResourceLimit',
    'SandboxPermission',
    'create_safe_sandbox',
    'get_script_sandbox',
    # 市场
    'ScriptMarket',
    'ScriptMetadata',
    'ScriptPackage',
    'ContributorStats',
    'BUILTIN_SCRIPTS',
    'get_script_market',
]
