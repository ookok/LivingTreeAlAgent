"""
Superpowers 框架集成

基于 github.com/obra/superpowers
可组合的技能系统和结构化工作流
"""

from .superpowers_engine import (
    SuperpowersEngine,
    SuperpowersConfig,
    get_superpowers_engine,
)

from .skills import (
    Skill,
    SkillRegistry,
    SkillExecutor,
    get_skill_registry,
    get_skill_executor,
)

from .subagent import (
    SubAgent,
    SubAgentManager,
    ParallelDispatcher,
    get_subagent_manager,
    get_parallel_dispatcher,
)

from .tdd_workflow import (
    TDDWorkflow,
    TestCase,
    TestRunner,
    get_tdd_workflow,
)

from .trigger_system import (
    TriggerSystem,
    ContextAnalyzer,
    get_trigger_system,
    get_context_analyzer,
)

from .workflow import (
    Workflow,
    WorkflowManager,
    Plan,
    Task,
    get_workflow_manager,
)

from .models import (
    SkillDefinition,
    AgentConfig,
    WorkflowState,
    TaskStatus,
)

from .integration import (
    SuperpowersIntegration,
    get_superpowers_integration,
    integrate_superpowers,
)

__all__ = [
    # 核心引擎
    "SuperpowersEngine",
    "SuperpowersConfig",
    "get_superpowers_engine",
    
    # 技能系统
    "Skill",
    "SkillRegistry",
    "SkillExecutor",
    "get_skill_registry",
    "get_skill_executor",
    
    # 子代理
    "SubAgent",
    "SubAgentManager",
    "ParallelDispatcher",
    "get_subagent_manager",
    "get_parallel_dispatcher",
    
    # TDD 工作流
    "TDDWorkflow",
    "TestCase",
    "TestRunner",
    "get_tdd_workflow",
    
    # 触发系统
    "TriggerSystem",
    "ContextAnalyzer",
    "get_trigger_system",
    "get_context_analyzer",
    
    # 工作流
    "Workflow",
    "WorkflowManager",
    "Plan",
    "Task",
    "get_workflow_manager",
    
    # 模型
    "SkillDefinition",
    "AgentConfig",
    "WorkflowState",
    "TaskStatus",
    
    # 集成
    "SuperpowersIntegration",
    "get_superpowers_integration",
    "integrate_superpowers",
]