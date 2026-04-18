"""
Panels - 功能面板
"""

from .knowledge_grove_panel import KnowledgeGrovePanel
from .form_filler_panel import FormFillerPanel
from .easter_egg_panel import EasterEggDiscoveryPanel, EasterEggCard
from .input_memory_panel import InputMemoryPanel, HourDistributionChart, get_input_memory_panel

__all__ = [
    'KnowledgeGrovePanel',
    'FormFillerPanel',
    'EasterEggDiscoveryPanel',
    'EasterEggCard',
    'InputMemoryPanel',
    'HourDistributionChart',
    'get_input_memory_panel',
]
