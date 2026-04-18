"""
Karpathy Skills - 工程师行为准则模块
源于 Andrej Karpathy 的工程师素养准则，注入到 Hermes Agent 的系统级约束
"""

from .rules import (
    KARPATHY_RULES_TEXT,
    AmbiguitySignal,
    AmbiguityDetector,
    get_detector,
)
from .prompt_builder import (
    AgentPromptBuilder,
    AgentType,
    build_karpathy_agent_prompt,
    get_builder,
    get_code_architect_prompt,
    get_debug_specialist_prompt,
    get_code_generator_prompt,
    get_refactor_prompt,
)
from .interaction import (
    AmbiguityResolver,
    AmbiguityDialog,
    ResolverContext,
    get_resolver_context,
)

__all__ = [
    # Rules
    "KARPATHY_RULES_TEXT",
    "AmbiguitySignal",
    "AmbiguityDetector",
    "get_detector",
    # Prompt Builder
    "AgentPromptBuilder",
    "AgentType",
    "build_karpathy_agent_prompt",
    "get_builder",
    "get_code_architect_prompt",
    "get_debug_specialist_prompt",
    "get_code_generator_prompt",
    "get_refactor_prompt",
    # Interaction
    "AmbiguityResolver",
    "AmbiguityDialog",
    "ResolverContext",
    "get_resolver_context",
]