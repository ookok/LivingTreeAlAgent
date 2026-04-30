"""主题系统 - 支持多种主题切换和自定义主题"""

from PyQt6.QtCore import QObject, pyqtSignal
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class ThemeColors:
    """主题颜色定义"""
    primary: str = "#6366f1"
    secondary: str = "#8b5cf6"
    background: str = "#ffffff"
    surface: str = "#f9fafb"
    border: str = "#e5e7eb"
    text: str = "#111827"
    text_secondary: str = "#6b7280"
    success: str = "#10b981"
    warning: str = "#f59e0b"
    error: str = "#ef4444"

@dataclass
class FontConfig:
    """字体配置"""
    family: str = "Inter"
    size: int = 14
    title_size: int = 18
    code_size: int = 13

class ThemeSystem(QObject):
    """主题系统"""
    
    theme_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._themes = {
            'light': self._create_light_theme(),
            'dark': self._create_dark_theme(),
        }
        self._current_theme = 'light'
    
    def _create_light_theme(self) -> Dict[str, Any]:
        """创建亮色主题"""
        return {
            'colors': ThemeColors(
                primary="#6366f1",
                secondary="#8b5cf6",
                background="#ffffff",
                surface="#f9fafb",
                border="#e5e7eb",
                text="#111827",
                text_secondary="#6b7280",
            ),
            'font': FontConfig(),
            'stylesheets': {
                'window': """
                    QMainWindow {
                        background: #ffffff;
                    }
                """,
                'panel': """
                    QFrame {
                        background: #f9fafb;
                        border: 1px solid #e5e7eb;
                        border-radius: 8px;
                    }
                """,
                'button': """
                    QPushButton {
                        background: #6366f1;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 8px 16px;
                    }
                    QPushButton:hover {
                        background: #4f46e5;
                    }
                """
            }
        }
    
    def _create_dark_theme(self) -> Dict[str, Any]:
        """创建暗色主题"""
        return {
            'colors': ThemeColors(
                primary="#818cf8",
                secondary="#a78bfa",
                background="#0d1117",
                surface="#161b22",
                border="#30363d",
                text="#e6edf3",
                text_secondary="#8b949e",
            ),
            'font': FontConfig(),
            'stylesheets': {
                'window': """
                    QMainWindow {
                        background: #0d1117;
                    }
                """,
                'panel': """
                    QFrame {
                        background: #161b22;
                        border: 1px solid #30363d;
                        border-radius: 8px;
                    }
                """,
                'button': """
                    QPushButton {
                        background: #818cf8;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 8px 16px;
                    }
                    QPushButton:hover {
                        background: #6366f1;
                    }
                """
            }
        }
    
    def apply_theme(self, theme_name: str):
        """应用主题"""
        if theme_name not in self._themes:
            return
        
        self._current_theme = theme_name
        self.theme_changed.emit(theme_name)
    
    def create_custom_theme(self, colors: ThemeColors):
        """创建自定义主题"""
        self._themes['custom'] = {
            'colors': colors,
            'font': FontConfig(),
            'stylesheets': self._generate_stylesheets(colors),
        }
    
    def _generate_stylesheets(self, colors: ThemeColors) -> Dict[str, str]:
        """生成样式表"""
        return {
            'window': f"""
                QMainWindow {{
                    background: {colors.background};
                }}
            """,
            'panel': f"""
                QFrame {{
                    background: {colors.surface};
                    border: 1px solid {colors.border};
                    border-radius: 8px;
                }}
            """,
            'button': f"""
                QPushButton {{
                    background: {colors.primary};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                }}
            """
        }
    
    def get_current_theme(self) -> Dict[str, Any]:
        """获取当前主题"""
        return self._themes.get(self._current_theme, self._themes['light'])
    
    def get_colors(self) -> ThemeColors:
        """获取颜色配置"""
        return self.get_current_theme()['colors']
    
    def get_stylesheet(self, component: str) -> str:
        """获取组件样式表"""
        return self.get_current_theme()['stylesheets'].get(component, '')
    
    def get_available_themes(self) -> list:
        """获取可用主题列表"""
        return list(self._themes.keys())

_theme_system = None

def get_theme_system() -> ThemeSystem:
    """获取主题系统实例"""
    global _theme_system
    if _theme_system is None:
        _theme_system = ThemeSystem()
    return _theme_system