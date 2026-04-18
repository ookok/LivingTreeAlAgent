"""
Infrastructure Layer - 基础设施层

沃土库 (The Soil Bank) - 记忆与知识的基底
"""

from .config import load_config
from .database import get_db

__all__ = ["load_config", "get_db"]
