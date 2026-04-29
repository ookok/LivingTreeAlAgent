# -*- coding: utf-8 -*-
"""
LivingTree UI Settings Module

Application settings and constants.
"""

class Settings:
    """Application settings for PyDracula-based UI"""

    # APP SETTINGS
    ENABLE_CUSTOM_TITLE_BAR = True
    MENU_WIDTH = 240
    LEFT_BOX_WIDTH = 240
    RIGHT_BOX_WIDTH = 240
    TIME_ANIMATION = 500

    # BTNS LEFT AND RIGHT BOX COLORS
    BTN_LEFT_BOX_COLOR = "background-color: rgb(44, 49, 58);"
    BTN_RIGHT_BOX_COLOR = "background-color: #ff79c6;"

    # LIGHT THEME COLORS
    BTN_LEFT_BOX_COLOR_LIGHT = "background-color: #6272a4;"
    BTN_RIGHT_BOX_COLOR_LIGHT = "background-color: #ff79c6;"

    # MENU SELECTED STYLESHEET - DARK
    MENU_SELECTED_STYLESHEET = """
    border-left: 22px solid qlineargradient(spread:pad, x1:0.034, y1:0, x2:0.216, y2:0, stop:0.499 rgba(255, 121, 198, 255), stop:0.5 rgba(85, 170, 255, 0));
    background-color: rgb(40, 44, 52);
    """

    # MENU SELECTED STYLESHEET - LIGHT
    MENU_SELECTED_STYLESHEET_LIGHT = """
    border-left: 22px solid qlineargradient(spread:pad, x1:0.034, y1:0, x2:0.216, y2:0, stop:0.499 rgba(255, 121, 198, 255), stop:0.5 rgba(85, 170, 255, 0));
    background-color: rgb(189, 147, 249);
    color: #f8f8f2;
    """

    # Theme paths
    THEME_DARK = "themes/py_dracula_dark.qss"
    THEME_LIGHT = "themes/py_dracula_light.qss"
