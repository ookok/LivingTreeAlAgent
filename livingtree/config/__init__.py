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
from .config_security import sanitize_project_config, validate_project_config, is_safe_config_key
from .config_editor import ConfigSchemaEditor, ConfigField
from .project_scaffold import ProjectScaffold, ProjectProfile, ProjectSkills, PROJECT_SCAFFOLD

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
    "sanitize_project_config",
    "validate_project_config",
    "is_safe_config_key",
    "ConfigSchemaEditor",
    "ConfigField",
    "ProjectScaffold",
    "ProjectProfile",
    "ProjectSkills",
    "PROJECT_SCAFFOLD",
]
