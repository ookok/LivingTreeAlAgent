"""
统一主题管理器 - 合并原有2个ThemeManager定义

使用单例模式，全局唯一实例。
支持浅色/深色/蓝色三种主题，可扩展。
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from .colors import LIGHT, DARK, LightTheme, DarkTheme


class ThemeManager(QObject):
    """
    统一主题管理器（单例）

    原有代码中有2个ThemeManager定义：
    - presentation/theme.py 中的 ThemeManager
    - presentation/widgets/aidock.py 中的 ThemeManager
    现在合并为一个，统一维护。
    """
    theme_changed = pyqtSignal(str)  # theme_name

    # 预定义主题
    THEMES = {
        "light": {
            "name": "浅色主题",
            "cls": LightTheme,
            "obj": LIGHT,
        },
        "dark": {
            "name": "深色主题",
            "cls": DarkTheme,
            "obj": DARK,
        },
        "blue": {
            "name": "蓝色主题",
            "cls": LightTheme,  # 基于浅色，但primary改为蓝色
            "obj": None,  # 动态创建
        },
    }

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        self._current_theme = "light"
        self._load_saved_theme()

    def _load_saved_theme(self):
        """加载保存的主题"""
        try:
            import json
            import os
            config_path = os.path.expanduser("~/.workbuddy/theme_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    theme = config.get("theme", "light")
                    if theme in self.THEMES:
                        self._current_theme = theme
        except Exception:
            pass

    def _save_theme(self):
        """保存主题配置"""
        try:
            import json
            import os
            config_dir = os.path.expanduser("~/.workbuddy")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "theme_config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"theme": self._current_theme}, f)
        except Exception:
            pass

    @property
    def current_theme(self) -> str:
        return self._current_theme

    @property
    def colors(self) -> object:
        """获取当前主题颜色对象"""
        theme_info = self.THEMES.get(self._current_theme)
        if theme_info:
            obj = theme_info["obj"]
            if obj is None:
                # 动态创建（如蓝色主题）
                obj = self._create_theme_object(self._current_theme)
                self.THEMES[self._current_theme]["obj"] = obj
            return obj
        return LIGHT

    def _create_theme_object(self, theme_name: str) -> object:
        """动态创建主题对象"""
        if theme_name == "blue":
            # 蓝色主题：基于浅色，修改primary
            class BlueTheme(LightTheme):
                PRIMARY = "#3B82F6"
                PRIMARY_HOVER = "#2563EB"
                PRIMARY_LIGHT = "#DBEAFE"
            return BlueTheme()
        return LIGHT

    def set_theme(self, theme_name: str):
        """切换主题"""
        if theme_name in self.THEMES:
            self._current_theme = theme_name
            self._save_theme()
            self.theme_changed.emit(theme_name)

    def get_stylesheet(self) -> str:
        """获取全局样式表（CSS变量）"""
        c = self.colors
        return f"""
            /* 全局变量 */
            * {{
                --primary: {c.PRIMARY};
                --primary-hover: {c.PRIMARY_HOVER};
                --primary-light: {c.PRIMARY_LIGHT};

                --bg-main: {c.BG_MAIN};
                --bg-secondary: {c.BG_SECONDARY};
                --bg-tertiary: {c.BG_TERTIARY};

                --border: {c.BORDER};
                --border-hover: {c.BORDER_HOVER};

                --text-primary: {c.TEXT_PRIMARY};
                --text-secondary: {c.TEXT_SECONDARY};
                --text-tertiary: {c.TEXT_TERTIARY};
                --text-placeholder: {c.TEXT_PLACEHOLDER};

                --success: {c.SUCCESS};
                --warning: {c.WARNING};
                --error: {c.ERROR};
                --info: {c.INFO};

                --card-bg: {c.CARD_BG};
                --card-hover: {c.CARD_HOVER};
            }}
        """

    def get_widget_style(self, widget_type: str) -> str:
        """
        获取组件样式
        widget_type: 'button_primary' | 'button_secondary' | 'input' | 'card' | 'scrollbar' | 'panel'
        """
        c = self.colors

        styles = {
            "button_primary": f"""
                QPushButton {{
                    background: {c.PRIMARY};
                    border: none;
                    border-radius: 8px;
                    color: #FFFFFF;
                    padding: 8px 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {c.PRIMARY_HOVER};
                }}
                QPushButton:disabled {{
                    background: {c.BORDER};
                    color: {c.TEXT_TERTIARY};
                }}
            """,
            "button_secondary": f"""
                QPushButton {{
                    background: {c.BG_TERTIARY};
                    border: 1px solid {c.BORDER};
                    border-radius: 8px;
                    color: {c.TEXT_PRIMARY};
                    padding: 8px 16px;
                }}
                QPushButton:hover {{
                    border-color: {c.PRIMARY};
                    color: {c.PRIMARY};
                }}
            """,
            "input": f"""
                QLineEdit, QTextEdit {{
                    background: {c.BG_TERTIARY};
                    border: 1px solid {c.BORDER};
                    border-radius: 8px;
                    padding: 10px 14px;
                    color: {c.TEXT_PRIMARY};
                    font-size: 14px;
                }}
                QLineEdit:focus, QTextEdit:focus {{
                    border: 1px solid {c.PRIMARY};
                    background: {c.BG_MAIN};
                }}
                QLineEdit::placeholder, QTextEdit::placeholder {{
                    color: {c.TEXT_PLACEHOLDER};
                }}
            """,
            "card": f"""
                QFrame {{
                    background: {c.CARD_BG};
                    border: 1px solid {c.BORDER};
                    border-radius: 12px;
                }}
                QFrame:hover {{
                    border-color: {c.PRIMARY};
                }}
            """,
            "scrollbar": f"""
                QScrollBar:vertical {{
                    background: {c.BG_SECONDARY};
                    width: 8px;
                    border-radius: 4px;
                }}
                QScrollBar::handle {{
                    background: {c.BORDER};
                    border-radius: 4px;
                }}
                QScrollBar::handle:hover {{
                    background: {c.TEXT_TERTIARY};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """,
            "panel": f"""
                background: {c.BG_MAIN};
                border: 1px solid {c.BORDER};
                border-radius: 12px;
            """,
        }

        return styles.get(widget_type, "")

    def apply_to_widget(self, widget, widget_type: str = "panel"):
        """应用主题到组件"""
        style = self.get_widget_style(widget_type)
        widget.setStyleSheet(style)

    def get_search_progress_style(self) -> str:
        """搜索进度条样式"""
        c = self.colors
        return f"""
            QProgressBar {{
                background: {c.BG_TERTIARY};
                border: none;
                border-radius: 4px;
                height: 6px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {c.PRIMARY};
                border-radius: 4px;
            }}
        """

    def get_source_button_style(self, active: bool = False) -> str:
        """源选择按钮样式"""
        c = self.colors
        if active:
            return f"""
                QPushButton {{
                    background: {c.PRIMARY};
                    border: 1px solid {c.PRIMARY};
                    border-radius: 8px;
                    color: #FFFFFF;
                    padding: 8px 16px;
                    font-weight: bold;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background: {c.BG_SECONDARY};
                    border: 1px solid {c.BORDER};
                    border-radius: 8px;
                    color: {c.TEXT_SECONDARY};
                    padding: 8px 16px;
                }}
                QPushButton:hover {{
                    border-color: {c.PRIMARY};
                    color: {c.TEXT_PRIMARY};
                }}
            """


# 全局唯一实例
theme_manager = ThemeManager()
