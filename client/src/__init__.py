"""
LivingTreeAI - 客户端入口包

生命主干 (The Trunk) - 一切功能的承载主体
"""

__version__ = "2.0.0"
__author__ = "LivingTreeAI Team"

from .presentation.main_window import MainWindow
from .business.assembler import RootAssemblyGarden
from .infrastructure.config import load_config

__all__ = [
    "MainWindow",
    "RootAssemblyGarden",
    "load_config",
]
