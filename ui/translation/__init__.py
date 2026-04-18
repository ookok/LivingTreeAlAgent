"""
Translation UI - 翻译 PyQt6 UI 模块

使用方式:
    from ui.translation import TranslationPanel

    panel = TranslationPanel()
"""

from .translation_panel import TranslationPanel, get_translation_panel

__all__ = ["TranslationPanel", "get_translation_panel"]
