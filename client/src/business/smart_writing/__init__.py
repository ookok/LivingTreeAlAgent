"""
智能写作系统
Smart Writing System

双引擎驱动的智能写作解决方案：
- 咨询模式：高效、结构化、专业
- 创作模式：沉浸、创意、表达

核心模块：
- dual_engine: 双引擎核心架构
- consulting_mode: 咨询模式
- creative_mode: 创作模式
- ai_collaborator: AI协作系统
- context_aware: 上下文感知
"""

from client.src.business.smart_writing.dual_engine import (
    DualEngineCore,
    WritingMode,
    AILevel,
    WritingProfile,
    WritingContext,
    WritingTask,
    WritingResponse,
    get_dual_engine,
)

from client.src.business.smart_writing.consulting_mode import (
    ConsultingMode,
    ConsultingFramework,
    DocumentType,
    ConsultingProject,
    SectionTemplate,
)

from client.src.business.smart_writing.creative_mode import (
    CreativeMode,
    WritingGenre,
    NarrativeVoice,
    EmotionalTone,
    CharacterProfile,
    PlotFragment,
    WorldBuilding,
    CreativeProject,
    InspirationEngine,
)

from client.src.business.smart_writing.ai_collaborator import (
    AICollaborator,
    AITask,
    AIResponse,
    AILevel as AICollaboratorLevel,
    TaskPriority,
    ModelConfig,
)

from client.src.business.smart_writing.context_aware import (
    ContextAwareSystem,
    WritingPhase,
    TimeOfDay,
    FatigueLevel,
    EmotionalState,
    ContextSnapshot,
    AdaptiveStrategy,
)

__all__ = [
    # 核心
    "DualEngineCore",
    "WritingMode",
    "AILevel",
    "WritingProfile",
    "WritingContext",
    "WritingTask",
    "WritingResponse",
    "get_dual_engine",
    
    # 咨询模式
    "ConsultingMode",
    "ConsultingFramework",
    "DocumentType",
    "ConsultingProject",
    "SectionTemplate",
    
    # 创作模式
    "CreativeMode",
    "WritingGenre",
    "NarrativeVoice",
    "EmotionalTone",
    "CharacterProfile",
    "PlotFragment",
    "WorldBuilding",
    "CreativeProject",
    "InspirationEngine",
    
    # AI协作
    "AICollaborator",
    "AITask",
    "AIResponse",
    "AICollaboratorLevel",
    "TaskPriority",
    "ModelConfig",
    
    # 上下文感知
    "ContextAwareSystem",
    "WritingPhase",
    "TimeOfDay",
    "FatigueLevel",
    "EmotionalState",
    "ContextSnapshot",
    "AdaptiveStrategy",
]
