"""
主题管理系统 - 统一管理浅色/深色主题
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor, QPalette


class ThemeManager(QObject):
    """主题管理器"""
    
    # 信号：主题切换
    theme_changed = pyqtSignal(str)  # theme_name
    
    # 预定义主题
    THEMES = {
        "light": {
            "name": "浅色主题",
            "primary": "#10B981",      # 主色调
            "primary_hover": "#059669",
            "primary_light": "#E8F5E9",
            
            "bg_main": "#FFFFFF",       # 主背景
            "bg_secondary": "#F8FAFC",  # 次要背景
            "bg_tertiary": "#F5F5F5",   # 第三背景
            
            "border": "#E8E8E8",        # 边框
            "border_hover": "#D0D0D0",
            
            "text_primary": "#333333",  # 主文字
            "text_secondary": "#666666",
            "text_tertiary": "#888888",
            "text_placeholder": "#999999",
            
            "success": "#10B981",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "info": "#3B82F6",
            
            "card_bg": "#FFFFFF",
            "card_hover": "#F0FDF4",
        },
        "dark": {
            "name": "深色主题",
            "primary": "#10B981",
            "primary_hover": "#34D399",
            "primary_light": "#064E3B",
            
            "bg_main": "#0D0D0D",
            "bg_secondary": "#1A1A1A",
            "bg_tertiary": "#252525",
            
            "border": "#333333",
            "border_hover": "#444444",
            
            "text_primary": "#FFFFFF",
            "text_secondary": "#A0A0A0",
            "text_tertiary": "#666666",
            "text_placeholder": "#555555",
            
            "success": "#10B981",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "info": "#3B82F6",
            
            "card_bg": "#1A1A1A",
            "card_hover": "#222222",
        },
        "blue": {
            "name": "蓝色主题",
            "primary": "#3B82F6",
            "primary_hover": "#2563EB",
            "primary_light": "#DBEAFE",
            
            "bg_main": "#FFFFFF",
            "bg_secondary": "#F8FAFC",
            "bg_tertiary": "#F0F9FF",
            
            "border": "#E0E7EF",
            "border_hover": "#C0D0E0",
            
            "text_primary": "#1E3A5F",
            "text_secondary": "#4A6FA5",
            "text_tertiary": "#7B9FCC",
            "text_placeholder": "#99B3CC",
            
            "success": "#10B981",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "info": "#3B82F6",
            
            "card_bg": "#FFFFFF",
            "card_hover": "#EFF6FF",
        },
    }
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
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
                with open(config_path, 'r', encoding='utf-8') as f:
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
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"theme": self._current_theme}, f)
        except Exception:
            pass
    
    @property
    def current_theme(self) -> str:
        return self._current_theme
    
    @property
    def colors(self) -> dict:
        """获取当前主题颜色"""
        return self.THEMES.get(self._current_theme, self.THEMES["light"])
    
    def set_theme(self, theme_name: str):
        """切换主题"""
        if theme_name in self.THEMES:
            self._current_theme = theme_name
            self._save_theme()
            self.theme_changed.emit(theme_name)
    
    def get_stylesheet(self, widget_name: str = "") -> str:
        """获取组件样式表"""
        c = self.colors
        
        base_styles = f"""
            /* 全局变量 */
            --primary: {c['primary']};
            --primary-hover: {c['primary_hover']};
            --primary-light: {c['primary_light']};
            
            --bg-main: {c['bg_main']};
            --bg-secondary: {c['bg_secondary']};
            --bg-tertiary: {c['bg_tertiary']};
            
            --border: {c['border']};
            --border-hover: {c['border_hover']};
            
            --text-primary: {c['text_primary']};
            --text-secondary: {c['text_secondary']};
            --text-tertiary: {c['text_tertiary']};
            --text-placeholder: {c['text_placeholder']};
            
            --success: {c['success']};
            --warning: {c['warning']};
            --error: {c['error']};
            --info: {c['info']};
            
            --card-bg: {c['card_bg']};
            --card-hover: {c['card_hover']};
        """
        
        return base_styles
    
    def get_widget_styles(self) -> dict:
        """获取各组件的统一样式"""
        c = self.colors
        
        return {
            "button_primary": f"""
                QPushButton {{
                    background: {c['primary']};
                    border: none;
                    border-radius: 8px;
                    color: #FFFFFF;
                    padding: 8px 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {c['primary_hover']};
                }}
                QPushButton:disabled {{
                    background: {c['border']};
                    color: {c['text_tertiary']};
                }}
            """,
            "button_secondary": f"""
                QPushButton {{
                    background: {c['bg_tertiary']};
                    border: 1px solid {c['border']};
                    border-radius: 8px;
                    color: {c['text_primary']};
                    padding: 8px 16px;
                }}
                QPushButton:hover {{
                    border-color: {c['primary']};
                    color: {c['primary']};
                }}
            """,
            "input": f"""
                QTextEdit, QLineEdit {{
                    background: {c['bg_tertiary']};
                    border: 1px solid {c['border']};
                    border-radius: 8px;
                    padding: 10px 14px;
                    color: {c['text_primary']};
                    font-size: 14px;
                }}
                QTextEdit:focus, QLineEdit:focus {{
                    border: 1px solid {c['primary']};
                    background: {c['bg_main']};
                }}
                QTextEdit::placeholder, QLineEdit::placeholder {{
                    color: {c['text_placeholder']};
                }}
            """,
            "card": f"""
                QFrame {{
                    background: {c['card_bg']};
                    border: 1px solid {c['border']};
                    border-radius: 12px;
                }}
                QFrame:hover {{
                    border-color: {c['primary']};
                }}
            """,
            "scrollbar": f"""
                QScrollBar:vertical {{
                    background: {c['bg_secondary']};
                    width: 8px;
                    border-radius: 4px;
                }}
                QScrollBar::handle {{
                    background: {c['border']};
                    border-radius: 4px;
                }}
                QScrollBar::handle:hover {{
                    background: {c['text_tertiary']};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """,
            "panel": f"""
                background: {c['bg_main']};
                border: 1px solid {c['border']};
                border-radius: 12px;
            """,
        }
    
    def apply_to_widget(self, widget, style_type: str = "panel"):
        """应用主题到组件"""
        styles = self.get_widget_styles()
        if style_type in styles:
            widget.setStyleSheet(styles[style_type])
    
    def get_search_progress_style(self) -> str:
        """获取搜索进度条样式"""
        c = self.colors
        return f"""
            QProgressBar {{
                background: {c['bg_tertiary']};
                border: none;
                border-radius: 4px;
                height: 6px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {c['primary']};
                border-radius: 4px;
            }}
        """
    
    def get_source_button_style(self, active: bool = False) -> str:
        """获取源选择按钮样式"""
        c = self.colors
        if active:
            return f"""
                QPushButton {{
                    background: {c['primary']};
                    border: 1px solid {c['primary']};
                    border-radius: 8px;
                    color: #FFFFFF;
                    padding: 8px 16px;
                    font-weight: bold;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background: {c['bg_secondary']};
                    border: 1px solid {c['border']};
                    border-radius: 8px;
                    color: {c['text_secondary']};
                    padding: 8px 16px;
                }}
                QPushButton:hover {{
                    border-color: {c['primary']};
                    color: {c['text_primary']};
                }}
            """


# 全局实例
theme_manager = ThemeManager()
