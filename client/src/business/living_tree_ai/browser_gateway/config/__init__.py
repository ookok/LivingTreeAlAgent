"""
配置管理系统

借鉴 qutebrowser 的配置管理，为 AI 增强浏览器提供配置功能
"""

from .config_manager import ConfigManager, get_config_manager
from .config_types import ConfigType, ConfigValue
from .config_validator import ConfigValidator

__all__ = [
    "ConfigManager",
    "get_config_manager",
    "ConfigType",
    "ConfigValue",
    "ConfigValidator"
]
