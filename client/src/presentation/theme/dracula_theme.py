"""
Dracula Theme - 现代化深色主题

基于 Dracula UI 框架: https://github.com/Wanderson-Magalhaes/Modern_GUI_PyDracula_PySide6_or_PyQt6
"""

from dataclasses import dataclass


@dataclass
class DraculaColors:
    """Dracula 主题颜色定义"""
    
    BG_MAIN = "#282a36"
    BG_SECONDARY = "#44475a"
    BG_TERTIARY = "#343746"
    BG_CARD = "#343746"
    
    BORDER = "#44475a"
    BORDER_LIGHT = "#55576a"
    
    TEXT_PRIMARY = "#f8f8f2"
    TEXT_SECONDARY = "#bd93f9"
    TEXT_TERTIARY = "#6272a4"
    TEXT_PLACEHOLDER = "#6272a4"
    
    PRIMARY = "#bd93f9"
    PRIMARY_HOVER = "#d4b8ff"
    PRIMARY_LIGHT = "#3d345a"
    
    SUCCESS = "#50fa7b"
    WARNING = "#ffb86c"
    ERROR = "#ff5555"
    INFO = "#8be9fd"
    
    CYAN = "#8be9fd"
    GREEN = "#50fa7b"
    ORANGE = "#ffb86c"
    PINK = "#ff79c6"
    PURPLE = "#bd93f9"
    RED = "#ff5555"
    YELLOW = "#f1fa8c"


class DraculaTheme:
    """Dracula 主题"""
    BG_MAIN = DraculaColors.BG_MAIN
    BG_SECONDARY = DraculaColors.BG_SECONDARY
    BG_TERTIARY = DraculaColors.BG_TERTIARY
    BG_CARD = DraculaColors.BG_CARD
    
    BORDER = DraculaColors.BORDER
    BORDER_LIGHT = DraculaColors.BORDER_LIGHT
    
    TEXT_PRIMARY = DraculaColors.TEXT_PRIMARY
    TEXT_SECONDARY = DraculaColors.TEXT_SECONDARY
    TEXT_TERTIARY = DraculaColors.TEXT_TERTIARY
    TEXT_PLACEHOLDER = DraculaColors.TEXT_PLACEHOLDER
    
    PRIMARY = DraculaColors.PRIMARY
    PRIMARY_HOVER = DraculaColors.PRIMARY_HOVER
    PRIMARY_LIGHT = DraculaColors.PRIMARY_LIGHT
    
    SUCCESS = DraculaColors.SUCCESS
    WARNING = DraculaColors.WARNING
    ERROR = DraculaColors.ERROR
    INFO = DraculaColors.INFO


DRACULA = DraculaTheme()


def get_dracula_stylesheet() -> str:
    """获取 Dracula 主题完整样式表"""
    c = DRACULA
    
    return f"""
    QMainWindow {{
        background-color: {c.BG_MAIN};
        color: {c.TEXT_PRIMARY};
        font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
        font-size: 14px;
    }}
    
    QWidget {{
        background-color: {c.BG_MAIN};
        color: {c.TEXT_PRIMARY};
    }}
    
    QPushButton {{
        background-color: {c.BG_SECONDARY};
        border: 2px solid {c.BORDER};
        border-radius: 8px;
        color: {c.TEXT_PRIMARY};
        padding: 10px 20px;
        font-weight: 500;
    }}
    
    QPushButton:hover {{
        background-color: {c.BG_TERTIARY};
        border-color: {c.PRIMARY};
        color: {c.PRIMARY};
    }}
    
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {c.BG_SECONDARY};
        border: 2px solid {c.BORDER};
        border-radius: 8px;
        padding: 12px 16px;
        color: {c.TEXT_PRIMARY};
        font-size: 14px;
    }}
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {c.PRIMARY};
    }}
    
    QFrame {{
        background-color: {c.BG_MAIN};
    }}
    
    QScrollBar:vertical {{
        background-color: {c.BG_SECONDARY};
        width: 8px;
        border-radius: 4px;
    }}
    
    QScrollBar::handle {{
        background-color: {c.BORDER_LIGHT};
        border-radius: 4px;
    }}
    
    QScrollBar::handle:hover {{
        background-color: {c.PRIMARY};
    }}
    
    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0px;
    }}
    
    QMenu {{
        background-color: {c.BG_SECONDARY};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        padding: 8px;
    }}
    
    QMenu::item {{
        color: {c.TEXT_PRIMARY};
        padding: 8px 24px;
        border-radius: 4px;
    }}
    
    QMenu::item:hover {{
        background-color: {c.PRIMARY_LIGHT};
        color: {c.PRIMARY};
    }}
    """