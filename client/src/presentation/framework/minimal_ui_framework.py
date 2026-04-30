"""
极简UI框架 - Minimal UI Framework

遵循极简设计原则：
- 简洁的视觉风格
- 扁平化设计
- 清晰的层次结构
- 充足的留白
- 柔和的色彩搭配
- 流畅的动画效果
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QLayout, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QPalette, QFont


class ColorScheme(Enum):
    """极简配色方案"""
    PRIMARY = "#3B82F6"      # 蓝色主色调
    PRIMARY_HOVER = "#2563EB"
    SECONDARY = "#64748B"    # 灰色辅助色
    BACKGROUND = "#FAFAFA"   # 浅灰背景
    SURFACE = "#FFFFFF"      # 白色表面
    BORDER = "#E5E7EB"      # 边框色
    TEXT_PRIMARY = "#1F2937" # 主文本色
    TEXT_SECONDARY = "#6B7280" # 次要文本色
    SUCCESS = "#10B981"      # 成功色
    WARNING = "#F59E0B"      # 警告色
    ERROR = "#EF4444"        # 错误色
    INFO = "#06B6D4"         # 信息色


class Typography(Enum):
    """字体规范"""
    HEADING_1 = {"size": 24, "weight": "bold"}
    HEADING_2 = {"size": 20, "weight": "bold"}
    HEADING_3 = {"size": 16, "weight": "medium"}
    BODY_LARGE = {"size": 14, "weight": "normal"}
    BODY_MEDIUM = {"size": 13, "weight": "normal"}
    BODY_SMALL = {"size": 12, "weight": "normal"}
    CAPTION = {"size": 11, "weight": "normal"}


@dataclass
class Spacing:
    """间距规范"""
    NONE = 0
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class MinimalWidget(QWidget):
    """极简UI控件基类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_minimal_style()
    
    def _setup_minimal_style(self):
        """设置极简样式"""
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {ColorScheme.BACKGROUND.value};
                font-family: 'Segoe UI', 'PingFang SC', -apple-system, sans-serif;
            }}
        """)
    
    def set_palette_color(self, role: QPalette.ColorRole, color: ColorScheme):
        """设置调色板颜色"""
        palette = self.palette()
        palette.setColor(role, QColor(color.value))
        self.setPalette(palette)


class MinimalFrame(QFrame):
    """极简框架容器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_minimal_frame()
    
    def _setup_minimal_frame(self):
        """设置极简框架样式"""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ColorScheme.SURFACE.value};
                border: 1px solid {ColorScheme.BORDER.value};
                border-radius: 12px;
            }}
        """)


class MinimalLayout:
    """极简布局工具类"""
    
    @staticmethod
    def create_vertical(parent: QWidget, spacing: int = Spacing.MD) -> QVBoxLayout:
        """创建垂直布局"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(spacing)
        return layout
    
    @staticmethod
    def create_horizontal(parent: QWidget, spacing: int = Spacing.MD) -> QHBoxLayout:
        """创建水平布局"""
        layout = QHBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(spacing)
        return layout
    
    @staticmethod
    def create_grid(parent: QWidget, rows: int = 1, cols: int = 1) -> QGridLayout:
        """创建网格布局"""
        layout = QGridLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)
        return layout
    
    @staticmethod
    def add_spacer(layout: QLayout, orientation: Qt.Orientation = Qt.Orientation.Vertical):
        """添加空白间隔"""
        if orientation == Qt.Orientation.Vertical:
            spacer = QSpacerItem(0, Spacing.MD, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        else:
            spacer = QSpacerItem(Spacing.MD, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addItem(spacer)


class MinimalStyle:
    """极简样式生成器"""
    
    @staticmethod
    def button(
        variant: str = "primary",
        size: str = "md",
        rounded: bool = True
    ) -> str:
        """生成按钮样式"""
        colors = {
            "primary": {
                "bg": ColorScheme.PRIMARY.value,
                "hover": ColorScheme.PRIMARY_HOVER.value,
                "text": "#FFFFFF"
            },
            "secondary": {
                "bg": ColorScheme.SURFACE.value,
                "hover": ColorScheme.BORDER.value,
                "text": ColorScheme.TEXT_PRIMARY.value
            },
            "success": {
                "bg": ColorScheme.SUCCESS.value,
                "hover": "#059669",
                "text": "#FFFFFF"
            },
            "warning": {
                "bg": ColorScheme.WARNING.value,
                "hover": "#D97706",
                "text": "#FFFFFF"
            },
            "error": {
                "bg": ColorScheme.ERROR.value,
                "hover": "#DC2626",
                "text": "#FFFFFF"
            }
        }
        
        sizes = {
            "sm": "padding: 4px 12px; font-size: 12px;",
            "md": "padding: 8px 16px; font-size: 14px;",
            "lg": "padding: 12px 24px; font-size: 16px;"
        }
        
        color = colors.get(variant, colors["primary"])
        border_radius = "border-radius: 8px;" if rounded else ""
        
        return f"""
            QPushButton {{
                background-color: {color["bg"]};
                color: {color["text"]};
                border: none;
                {border_radius}
                {sizes.get(size, sizes["md"])}
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {color["hover"]};
            }}
            QPushButton:pressed {{
                opacity: 0.9;
            }}
            QPushButton:disabled {{
                background-color: {ColorScheme.BORDER.value};
                color: {ColorScheme.TEXT_SECONDARY.value};
            }}
        """
    
    @staticmethod
    def input_field(rounded: bool = True) -> str:
        """生成输入框样式"""
        border_radius = "border-radius: 8px;" if rounded else ""
        
        return f"""
            QLineEdit, QTextEdit {{
                background-color: {ColorScheme.SURFACE.value};
                border: 1px solid {ColorScheme.BORDER.value};
                {border_radius}
                padding: 8px 12px;
                font-size: 14px;
                color: {ColorScheme.TEXT_PRIMARY.value};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {ColorScheme.PRIMARY.value};
                outline: none;
            }}
            QLineEdit::placeholder, QTextEdit::placeholder {{
                color: {ColorScheme.TEXT_SECONDARY.value};
            }}
        """
    
    @staticmethod
    def card(elevated: bool = False) -> str:
        """生成卡片样式"""
        border_width = "2px" if elevated else "1px"
        
        return f"""
            QFrame {{
                background-color: {ColorScheme.SURFACE.value};
                border: {border_width} solid {ColorScheme.BORDER.value};
                border-radius: 12px;
                padding: {Spacing.LG}px;
            }}
        """
    
    @staticmethod
    def text(color: ColorScheme = ColorScheme.TEXT_PRIMARY) -> str:
        """生成文本样式"""
        return f"color: {color.value};"
    
    @staticmethod
    def heading(level: int = 1) -> str:
        """生成标题样式"""
        sizes = {1: "24px", 2: "20px", 3: "16px"}
        return f"font-size: {sizes.get(level, sizes[1])}; font-weight: bold; color: {ColorScheme.TEXT_PRIMARY.value};"


class MinimalContainer(QWidget):
    """极简容器组件"""
    
    def __init__(self, parent=None, padding: int = Spacing.LG):
        super().__init__(parent)
        self._padding = padding
        self._layout = MinimalLayout.create_vertical(self)
        self._setup_style()
    
    def _setup_style(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {ColorScheme.BACKGROUND.value};
                padding: {self._padding}px;
            }}
        """)
    
    def layout(self) -> QVBoxLayout:
        return self._layout


class MinimalCard(MinimalFrame):
    """极简卡片组件"""
    
    def __init__(self, parent=None, elevated: bool = False):
        super().__init__(parent)
        self._elevated = elevated
        self._layout = MinimalLayout.create_vertical(self)
        self._layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        self._setup_card_style()
    
    def _setup_card_style(self):
        self.setStyleSheet(MinimalStyle.card(elevated=self._elevated))
    
    def layout(self) -> QVBoxLayout:
        return self._layout


class UIComponentFactory:
    """UI组件工厂 - 生成极简风格的UI组件"""
    
    @staticmethod
    def create_button(
        parent: QWidget,
        text: str,
        variant: str = "primary",
        size: str = "md",
        on_click: Optional[Callable] = None
    ):
        """创建按钮"""
        from PyQt6.QtWidgets import QPushButton
        
        btn = QPushButton(text, parent)
        btn.setStyleSheet(MinimalStyle.button(variant=variant, size=size))
        
        if on_click:
            btn.clicked.connect(on_click)
        
        return btn
    
    @staticmethod
    def create_label(
        parent: QWidget,
        text: str,
        color: ColorScheme = ColorScheme.TEXT_PRIMARY,
        font_size: int = 14
    ):
        """创建标签"""
        from PyQt6.QtWidgets import QLabel
        
        label = QLabel(text, parent)
        label.setStyleSheet(f"""
            QLabel {{
                color: {color.value};
                font-size: {font_size}px;
            }}
        """)
        label.setWordWrap(True)
        
        return label
    
    @staticmethod
    def create_input(
        parent: QWidget,
        placeholder: str = "",
        text: str = ""
    ):
        """创建输入框"""
        from PyQt6.QtWidgets import QLineEdit
        
        input_field = QLineEdit(parent)
        input_field.setPlaceholderText(placeholder)
        input_field.setText(text)
        input_field.setStyleSheet(MinimalStyle.input_field())
        
        return input_field
    
    @staticmethod
    def create_textarea(
        parent: QWidget,
        placeholder: str = "",
        text: str = "",
        rows: int = 4
    ):
        """创建文本域"""
        from PyQt6.QtWidgets import QTextEdit
        
        textarea = QTextEdit(parent)
        textarea.setPlaceholderText(placeholder)
        textarea.setText(text)
        textarea.setStyleSheet(MinimalStyle.input_field())
        textarea.setMaximumHeight(rows * 28)
        
        return textarea
    
    @staticmethod
    def create_divider(parent: QWidget, vertical: bool = False):
        """创建分隔线"""
        from PyQt6.QtWidgets import QFrame
        
        divider = QFrame(parent)
        if vertical:
            divider.setFrameShape(QFrame.Shape.VLine)
        else:
            divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet(f"color: {ColorScheme.BORDER.value};")
        
        return divider
    
    @staticmethod
    def create_spacer(parent: QWidget, vertical: bool = True):
        """创建空白间隔"""
        if vertical:
            return QSpacerItem(0, Spacing.LG, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        else:
            return QSpacerItem(Spacing.LG, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)


# 导出接口
__all__ = [
    "ColorScheme",
    "Typography",
    "Spacing",
    "MinimalWidget",
    "MinimalFrame",
    "MinimalLayout",
    "MinimalStyle",
    "MinimalContainer",
    "MinimalCard",
    "UIComponentFactory"
]