"""
Natural Language UI Generator - 自然语言驱动的动态UI生成系统
============================================================

核心理念：用自然语言"编程"你的界面

三层架构:
    intent_parser.py         - 自然语言意图理解
    ui_template_engine.py    - UI模板引擎
    action_repository.py     - 动作仓库
    ai_code_generator.py     - AI代码生成
    script_sandbox.py        - 沙箱执行
    ui_realtime_preview.py   - 实时预览
    change_history.py        - 变更历史
    security_auditor.py      - 安全审计
    hot_reload_manager.py    - 热重载管理
    component_registry.py    - 组件注册表

用户只需要说"我想在主页加个按钮，点击清理缓存"，
系统就会自动生成并部署这个功能。
"""

from .intent_parser import (
    IntentParser,
    Intent,
    IntentType,
    IntentPattern,
    get_intent_parser,
)

from .ui_template_engine import (
    UITemplateEngine,
    UITemplate,
    TemplateComponent,
    ComponentSlot,
    get_template_engine,
)

from .action_repository import (
    ActionRepository,
    Action,
    ActionDefinition,
    get_action_repository,
)

from .ai_code_generator import (
    AICodeGenerator,
    GeneratedCode,
    CodeGenerationContext,
    get_code_generator,
)

from .script_sandbox import (
    ScriptSandbox,
    SandboxResult,
    SecurityError,
    get_sandbox,
)

from .ui_realtime_preview import (
    UIRealtimePreview,
    PreviewChange,
    PreviewResult,
    get_preview,
)

from .change_history import (
    ChangeHistory,
    ChangeRecord,
    ChangeType,
    get_change_history,
)

from .security_auditor import (
    SecurityAuditor,
    AuditResult,
    SecurityRule,
    Violation,
    get_security_auditor,
)

from .hot_reload_manager import (
    HotReloadManager,
    ReloadEvent,
    get_hot_reload_manager,
)

from .component_registry import (
    ComponentRegistry,
    ComponentDefinition,
    DynamicComponent,
    get_component_registry,
)

from .nl_ui_manager import (
    NLUIDriver,
    NLUIRequest,
    NLUIResponse,
    get_nl_ui_driver,
)

__version__ = "1.0.0"

__all__ = [
    # 意图理解
    "IntentParser",
    "Intent",
    "IntentType",
    "IntentPattern",
    "get_intent_parser",

    # 模板引擎
    "UITemplateEngine",
    "UITemplate",
    "TemplateComponent",
    "ComponentSlot",
    "get_template_engine",

    # 动作仓库
    "ActionRepository",
    "Action",
    "ActionDefinition",
    "get_action_repository",

    # AI代码生成
    "AICodeGenerator",
    "GeneratedCode",
    "CodeGenerationContext",
    "get_code_generator",

    # 沙箱
    "ScriptSandbox",
    "SandboxResult",
    "SecurityError",
    "get_sandbox",

    # 实时预览
    "UIRealtimePreview",
    "PreviewChange",
    "PreviewResult",
    "get_preview",

    # 变更历史
    "ChangeHistory",
    "ChangeRecord",
    "ChangeType",
    "get_change_history",

    # 安全审计
    "SecurityAuditor",
    "AuditResult",
    "SecurityRule",
    "Violation",
    "get_security_auditor",

    # 热重载
    "HotReloadManager",
    "ReloadEvent",
    "get_hot_reload_manager",

    # 组件注册
    "ComponentRegistry",
    "ComponentDefinition",
    "DynamicComponent",
    "get_component_registry",

    # NL UI管理器
    "NLUIDriver",
    "NLUIRequest",
    "NLUIResponse",
    "get_nl_ui_driver",
]