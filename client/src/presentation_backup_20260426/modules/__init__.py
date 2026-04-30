"""
模块面板包
"""

from .presentation.modules.deep_search_panel import DeepSearchPanel
from .presentation.modules.knowledge_base_panel import KnowledgeBasePanel
from .presentation.modules.expert_training_panel import ExpertTrainingPanel
from .presentation.modules.smart_ide_panel import SmartIDEPanel
from .presentation.modules.smart_writing_panel import SmartWritingPanel

__all__ = [
    "DeepSearchPanel",
    "KnowledgeBasePanel",
    "ExpertTrainingPanel",
    "SmartIDEPanel",
    "SmartWritingPanel",
]
