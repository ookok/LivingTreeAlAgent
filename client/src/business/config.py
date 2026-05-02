"""
Config — Re-export from livingtree.infrastructure.config

Full migration complete. All config features available via LTAIConfig.
"""

from livingtree.infrastructure.config import (
    LTAIConfig,
    get_config,
    config as _lt_config,
)

# Compatibility — old unified config API
class UnifiedConfig:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = get_config()
        return cls._instance

    def get(self, path: str, default=None):
        config = get_config()
        keys = path.split(".")
        obj = config
        for k in keys:
            if hasattr(obj, k):
                obj = getattr(obj, k)
            elif isinstance(obj, dict) and k in obj:
                obj = obj[k]
            else:
                return default
        return obj


class NanochatConfig:
    pass


class OptimalConfig:
    pass


def get_config_dir():
    from pathlib import Path
    return Path.home() / ".livingtree"


__all__ = [
    "UnifiedConfig", "NanochatConfig", "OptimalConfig",
    "get_config", "get_config_dir",
]
