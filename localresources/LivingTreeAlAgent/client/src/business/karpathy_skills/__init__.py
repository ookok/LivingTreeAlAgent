"""
Andrej Karpathy Skills 集成

基于 github.com/forrestchang/andrej-karpathy-skills
提供 Karpathy 编程最佳实践的技能系统
"""

from .karpathy_engine import (
    KarpathyEngine,
    KarpathyConfig,
    get_karpathy_engine,
)

from .skill_configs import (
    CodeReviewSkill,
    TestGeneratorSkill,
    RefactorAdvisorSkill,
    DocWriterSkill,
    PerformanceOptimizerSkill,
    KarpathySkillRegistry,
    get_karpathy_registry,
)

from .integration import (
    KarpathyIntegration,
    get_karpathy_integration,
    integrate_karpathy_skills,
)

from .workflow import (
    KarpathyWorkflow,
    KarpathyTask,
    get_karpathy_workflow,
)

from .models import (
    KarpathySkill,
    SkillConfig,
    ReviewResult,
    TestResult,
    RefactorSuggestion,
    DocResult,
)

__all__ = [
    # 核心引擎
    "KarpathyEngine",
    "KarpathyConfig",
    "get_karpathy_engine",
    
    # 技能配置
    "CodeReviewSkill",
    "TestGeneratorSkill",
    "RefactorAdvisorSkill",
    "DocWriterSkill",
    "PerformanceOptimizerSkill",
    "KarpathySkillRegistry",
    "get_karpathy_registry",
    
    # 集成
    "KarpathyIntegration",
    "get_karpathy_integration",
    "integrate_karpathy_skills",
    
    # 工作流
    "KarpathyWorkflow",
    "KarpathyTask",
    "get_karpathy_workflow",
    
    # 模型
    "KarpathySkill",
    "SkillConfig",
    "ReviewResult",
    "TestResult",
    "RefactorSuggestion",
    "DocResult",
]