"""Configuration layer for the LivingTree digital life form.

Provides LTAIConfig – a unified, dataclass-based configuration system that
replaces the legacy NanochatConfig/OptimalConfig/UnifiedConfig triplicate.
Loads from YAML files with environment variable overrides.
"""

from .settings import (
    LTAIConfig,
    ModelConfig,
    CellConfig,
    NetworkConfig,
    KnowledgeConfig,
    ObservabilityConfig,
    EvolutionConfig,
    SafetyConfig,
    ExecutionConfig,
    DocEngineConfig,
    APIConfig,
    get_config,
    reload_config,
)
from .secrets import SecretVault, get_secret_vault

__all__ = [
    "LTAIConfig",
    "ModelConfig",
    "CellConfig",
    "NetworkConfig",
    "KnowledgeConfig",
    "ObservabilityConfig",
    "EvolutionConfig",
    "SafetyConfig",
    "ExecutionConfig",
    "DocEngineConfig",
    "APIConfig",
    "get_config",
    "reload_config",
    "SecretVault",
    "get_secret_vault",
]
