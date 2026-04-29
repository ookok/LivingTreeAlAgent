# -*- coding: utf-8 -*-
"""
Widget Factory - 控件工厂

将UI描述符转换为实际的Qt控件。
支持PySide6和PyQt6。
"""

import logging
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass

# Qt imports with fallback
try:
    from PySide6.QtCore import Qt, Signal, QDate, QTime, QDateTime
    from PySide6.QtWidgets import (
        QWidget, QLabel, QLineEdit, QTextEdit, QPlainTextEdit,
        QComboBox, QCheckBox, QRadioButton, QButtonGroup,
        QPushButton, QSlider, QSpinBox, QDoubleSpinBox,
        QGroupBox, QFrame,QVBoxLayout, QHBoxLayout, QFormLayout,
        QFileDialog, QProgressBar, QDialog, QDialogButtonBox,
        QTabWidget, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
        QScrollArea, QSizePolicy, QApplication
    )
    from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
    QT_BINDING = "PySide6"
except ImportError:
    from PyQt6.QtCore import Qt, QDate, QTime, QDateTime, pyqtSignal as Signal
    from PyQt6.QtWidgets import (
        QWidget, QLabel, QLineEdit, QTextEdit, QPlainTextEdit,
        QComboBox, QCheckBox, QRadioButton, QButtonGroup,
        QPushButton, QSlider, QSpinBox, QDoubleSpinBox,
        QGroupBox, QFrame, QVBoxLayout, QHBoxLayout, QFormLayout,
        QFileDialog, QProgressBar, QDialog, QDialogButtonBox,
        QTabWidget, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
        QScrollArea, QSizePolicy, QApplication
    )
    from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
    QT_BINDING = "PyQt6"

from .ui_descriptor import WidgetDescriptor, Option, ValidationRule

logger = logging.getLogger(__name__)


@dataclass
class WidgetResult:
    """控件创建结果"""
    widget: QWidget
    descriptor: WidgetDescriptor
    layout_widget: Optional[QWidget] = None  # 包含标签的布局容器
    validators: List[Callable] = None
    
    def __post_init__(self):
        if self.validators is None:
            self.validators = []


class WidgetFactory:
    """
    控件工厂
    
    根据WidgetDescriptor创建Qt控件实例。
    支持所有主流Qt控件类型。
    """
    
    # 控件类型到创建函数的映射
    _widget_creators: Dict[str, Callable] = {}
    
    def __init__(self, parent: QWidget = None):
        self._parent = parent
        self._theme = self._get_default_theme()
        self._font_family = "Microsoft YaHei" if QT_BINDING == "PySide6" else "Microsoft YaHei"
        self._font_size = 12
        self._accent_color = "#2196F3"
        self._error_color = "#F44336"
        self._success_color = "#4CAF50"
        
        # 注册默认创建器
        self._register_default_creators()
    
    def _get_default_theme(self) -> Dict[str, Any]:
        """获取默认主题"""
        return {
            "background": "#1E1E1E" if QT_BINDING == "PySide6" else "#1E1E1E",
            "foreground": "#FFFFFF",
            "border": "#3C3C3C",
            "accent": "#2196F3",
            "error": "#F44336",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "input_bg": "#2D2D2D",
            "input_border": "#404040",
        }
    
    def _register_default_creators(self):
        """注册默认控件创建函数"""
        creators = {
            # 基础控件
            "text_input": self._create_line_edit,
            "email_input": self._create_email_input,
            "password_input": self._create_password_input,
            "number_input": self._create_number_input,
            "text_area": self._create_text_area,
            
            # 选择控件
            "dropdown": self._create_dropdown,
            "checkbox": self._create_checkbox,
            "radio_group": self._create_radio_group,
            "switch": self._create_switch,
            "slider": self._create_slider,
            
            # 日期时间
            "date_picker": self._create_date_picker,
            "time_picker": self._create_time_picker,
            "datetime_picker": self._create_datetime_picker,
            
            # 文件
            "file_upload": self._create_file_upload,
            "image_upload": self._create_image_upload,
            
            # 按钮
            "button": self._create_button,
            "submit_button": self._create_submit_button,
            "icon_button": self._create_icon_button,
            
            # 容器
            "form": self._create_form_container,
            "card": self._create_card,
            "group": self._create_group,
            "divider": self._create_divider,
            
            # 展示
            "label": self._create_label,
            "heading": self._create_heading,
            "paragraph": self._create_paragraph,
            "link": self._create_link,
            "image": self._create_image,
            "progress_bar": self._create_progress_bar,
            
            # 列表
            "list": self._create_list,
            "table": self._create_table,
            "tabs": self._create_tabs,
            
            # 反馈
            "alert": self._create_alert,
            "spinner": self._create_spinner,
        }
        
        self._widget_creators.update(creators)
    
    def register_creator(self, widget_type: str, creator: Callable):
        """注册自定义控件创建函数"""
        self._widget_creators[widget_type] = creator
    
    def create(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """
        根据描述符创建控件
        
        Args:
            descriptor: 控件描述符
            
        Returns:
            WidgetResult: 控件创建结果
        """
        widget_type = descriptor.type
        
        if widget_type not in self._widget_creators:
            logger.warning(f"Unknown widget type: {widget_type}, falling back to text_input")
            widget_type = "text_input"
        
        try:
            creator = self._widget_creators[widget_type]
            result = creator(descriptor)
            
            # 应用通用样式
            if result.widget:
                self._apply_base_style(result.widget, descriptor)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to create widget {widget_type}: {e}")
            # 返回一个错误标签作为后备
            error_widget = QLabel(f"Error: {widget_type}")
            return WidgetResult(widget=error_widget, descriptor=descriptor)
    
    def create_many(self, descriptors: List[WidgetDescriptor]) -> List[WidgetResult]:
        """批量创建控件"""
        return [self.create(desc) for desc in descriptors]
    
    def _apply_base_style(self, widget: QWidget, descriptor: WidgetDescriptor):
        """应用基础样式"""
        # 设置禁用状态
        if descriptor.disabled:
            widget.setEnabled(False)
        
        # 设置可见性
        if not descriptor.visible:
            widget.setVisible(False)
        
        # 设置工具提示
        if descriptor.label:
            widget.setToolTip(descriptor.label)
    
    # ============ 输入控件创建函数 ============
    
    def _create_line_edit(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建文本输入框"""
        widget = QLineEdit(self._parent)
        widget.setPlaceholderText(descriptor.placeholder or f"请输入{descriptor.label}")
        
        if descriptor.default_value:
            widget.setText(str(descriptor.default_value))
        
        # 应用样式
        widget.setStyleSheet(f'''
            QLineEdit {{
                background-color: {self._theme['input_bg']};
                border: 1px solid {self._theme['input_border']};
                border-radius: 4px;
                padding: 8px 12px;
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
                font-family: "{self._font_family}";
            }}
            QLineEdit:focus {{
                border: 1px solid {self._accent_color};
            }}
            QLineEdit:disabled {{
                background-color: {self._theme['background']};
                color: #666;
            }}
        ''')
        
        # 创建带标签的容器
        container = self._wrap_with_label(widget, descriptor)
        
        # 添加验证器
        validators = []
        for rule in descriptor.validations:
            validator = self._create_validator(rule)
            if validator:
                validators.append(validator)
                widget.textChanged.connect(lambda t, v=validator, w=widget: 
                    self._validate_and_style(w, v))
        
        return WidgetResult(
            widget=widget,
            descriptor=descriptor,
            layout_widget=container,
            validators=validators
        )
    
    def _create_email_input(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建邮箱输入框"""
        result = self._create_line_edit(descriptor)
        
        # 添加邮箱验证器
        from PyQt6.QtGui import QRegularExpressionValidator
        from PyQt6.QtCore import QRegularExpression
        
        email_validator = QRegularExpressionValidator(
            QRegularExpression(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
            result.widget
        ) if QT_BINDING == "PyQt6" else None
        
        if email_validator:
            result.widget.setValidator(email_validator)
            result.validators.append(email_validator)
        
        return result
    
    def _create_password_input(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建密码输入框"""
        result = self._create_line_edit(descriptor)
        result.widget.setEchoMode(QLineEdit.Password)
        result.widget.setStyleSheet(result.widget.styleSheet() + '''
            QLineEdit {
                font-family: "Consolas", "Courier New", monospace;
            }
        ''')
        return result
    
    def _create_number_input(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建数字输入框"""
        # 使用SpinBox
        min_val = descriptor.attributes.get('min', 0)
        max_val = descriptor.attributes.get('max', 999999)
        step = descriptor.attributes.get('step', 1)
        decimals = descriptor.attributes.get('decimals', 0)
        
        if decimals > 0:
            widget = QDoubleSpinBox(self._parent)
            widget.setDecimals(decimals)
            widget.setSingleStep(float(step))
        else:
            widget = QSpinBox(self._parent)
            widget.setSingleStep(step)
        
        widget.setRange(min_val, max_val)
        widget.setValue(int(descriptor.default_value) if descriptor.default_value else min_val)
        
        # 样式
        widget.setStyleSheet(f'''
            QSpinBox, QDoubleSpinBox {{
                background-color: {self._theme['input_bg']};
                border: 1px solid {self._theme['input_border']};
                border-radius: 4px;
                padding: 8px 12px;
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
            }}
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border: 1px solid {self._accent_color};
            }}
        ''')
        
        container = self._wrap_with_label(widget, descriptor)
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=container)
    
    def _create_text_area(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建多行文本域"""
        widget = QPlainTextEdit(self._parent)
        widget.setPlaceholderText(descriptor.placeholder or f"请输入{descriptor.label}")
        
        if descriptor.default_value:
            widget.setPlainText(str(descriptor.default_value))
        
        # 设置最小高度
        min_height = descriptor.attributes.get('min_height', 100)
        widget.setMinimumHeight(min_height)
        
        widget.setStyleSheet(f'''
            QPlainTextEdit {{
                background-color: {self._theme['input_bg']};
                border: 1px solid {self._theme['input_border']};
                border-radius: 4px;
                padding: 8px 12px;
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
                font-family: "{self._font_family}";
            }}
            QPlainTextEdit:focus {{
                border: 1px solid {self._accent_color};
            }}
        ''')
        
        container = self._wrap_with_label(widget, descriptor)
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=container)
    
    # ============ 选择控件创建函数 ============
    
    def _create_dropdown(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建下拉选择框"""
        widget = QComboBox(self._parent)
        widget.setPlaceholderText(descriptor.placeholder or "请选择")
        
        # 添加选项
        for opt in descriptor.options:
            widget.addItem(opt.label, opt.value)
            if opt.disabled:
                widget.model().item(widget.count() - 1).setEnabled(False)
            if opt.selected or (descriptor.default_value == opt.value):
                widget.setCurrentIndex(widget.count() - 1)
        
        widget.setStyleSheet(f'''
            QComboBox {{
                background-color: {self._theme['input_bg']};
                border: 1px solid {self._theme['input_border']};
                border-radius: 4px;
                padding: 8px 12px;
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
            }}
            QComboBox:focus {{
                border: 1px solid {self._accent_color};
            }}
            QComboBox::dropDown {{
                border: none;
                background: transparent;
            }}
            QComboBox::downArrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {self._theme['foreground']};
                margin-right: 10px;
            }}
        ''')
        
        container = self._wrap_with_label(widget, descriptor)
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=container)
    
    def _create_checkbox(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建复选框"""
        widget = QCheckBox(descriptor.label or "选项", self._parent)
        
        if descriptor.default_value:
            widget.setChecked(bool(descriptor.default_value))
        
        widget.setStyleSheet(f'''
            QCheckBox {{
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {self._theme['input_border']};
                border-radius: 3px;
                background-color: {self._theme['input_bg']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self._accent_color};
                border-color: {self._accent_color};
            }}
        ''')
        
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_radio_group(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建单选按钮组"""
        container = QWidget(self._parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)
        
        # 标签
        if descriptor.label:
            label = QLabel(descriptor.label, container)
            label.setStyleSheet(f'''
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
                font-weight: bold;
            ''')
            layout.addWidget(label)
        
        # 按钮组
        button_group = QButtonGroup(container)
        
        radio_style = f'''
            QRadioButton {{
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {self._theme['input_border']};
                border-radius: 9px;
                background-color: {self._theme['input_bg']};
            }}
            QRadioButton::indicator:checked {{
                background-color: {self._accent_color};
                border-color: {self._accent_color};
            }}
        '''
        
        default_checked = descriptor.default_value
        
        for i, opt in enumerate(descriptor.options):
            radio = QRadioButton(opt.label, container)
            radio.setStyleSheet(radio_style)
            radio.setData(opt.value)
            button_group.addButton(radio, i)
            
            if opt.selected or (default_checked == opt.value):
                radio.setChecked(True)
            
            layout.addWidget(radio)
        
        layout.addStretch()
        
        # 存储按钮组引用
        container.button_group = button_group
        
        return WidgetResult(widget=container, descriptor=descriptor, layout_widget=container)
    
    def _create_switch(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建开关"""
        widget = QCheckBox(descriptor.label or "开关", self._parent)
        widget.setCheckable(True)
        
        if descriptor.default_value:
            widget.setChecked(bool(descriptor.default_value))
        
        widget.setStyleSheet(f'''
            QCheckBox {{
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
            }}
            QCheckBox::indicator {{
                width: 40px;
                height: 20px;
                border-radius: 10px;
                background-color: {self._theme['input_border']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self._accent_color};
            }}
        ''')
        
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_slider(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建滑块"""
        widget = QSlider(Qt.Horizontal, self._parent)
        
        min_val = descriptor.attributes.get('min', 0)
        max_val = descriptor.attributes.get('max', 100)
        widget.setRange(min_val, max_val)
        widget.setValue(int(descriptor.default_value) if descriptor.default_value else min_val)
        
        widget.setStyleSheet(f'''
            QSlider {{
                height: 30px;
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background-color: {self._theme['input_border']};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                background-color: {self._accent_color};
                border-radius: 8px;
                margin: -5px 0;
            }}
        ''')
        
        container = self._wrap_with_label(widget, descriptor)
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=container)
    
    # ============ 日期时间控件 ============
    
    def _create_date_picker(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建日期选择器"""
        widget = QLineEdit(self._parent)
        widget.setReadOnly(True)
        widget.setPlaceholderText(descriptor.placeholder or "选择日期")
        
        if descriptor.default_value:
            widget.setText(str(descriptor.default_value))
        
        widget.setStyleSheet(f'''
            QLineEdit {{
                background-color: {self._theme['input_bg']};
                border: 1px solid {self._theme['input_border']};
                border-radius: 4px;
                padding: 8px 12px;
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
            }}
        ''')
        
        container = self._wrap_with_label(widget, descriptor)
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=container)
    
    def _create_time_picker(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建时间选择器"""
        return self._create_date_picker(descriptor)  # 简化实现
    
    def _create_datetime_picker(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建日期时间选择器"""
        return self._create_date_picker(descriptor)  # 简化实现
    
    # ============ 文件上传 ============
    
    def _create_file_upload(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建文件上传"""
        container = QWidget(self._parent)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        widget = QLineEdit(self._parent)
        widget.setReadOnly(True)
        widget.setPlaceholderText(descriptor.placeholder or "选择文件...")
        
        btn = QPushButton("选择文件", self._parent)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self._open_file_dialog(widget))
        
        layout.addWidget(widget, 1)
        layout.addWidget(btn)
        
        container = self._wrap_with_label(container, descriptor)
        return WidgetResult(widget=container, descriptor=descriptor, layout_widget=container)
    
    def _create_image_upload(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建图片上传"""
        return self._create_file_upload(descriptor)  # 简化实现
    
    def _open_file_dialog(self, line_edit: QLineEdit):
        """打开文件对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self._parent,
            "选择文件",
            "",
            "所有文件 (*.*)"
        )
        if file_path:
            line_edit.setText(file_path)
    
    # ============ 按钮 ============
    
    def _create_button(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建按钮"""
        widget = QPushButton(descriptor.label or "按钮", self._parent)
        widget.setCursor(Qt.PointingHandCursor)
        
        widget.setStyleSheet(f'''
            QPushButton {{
                background-color: {self._theme['input_border']};
                color: {self._theme['foreground']};
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: {self._font_size}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self._accent_color};
            }}
            QPushButton:pressed {{
                background-color: {self._accent_color};
            }}
        ''')
        
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_submit_button(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建提交按钮"""
        result = self._create_button(descriptor)
        result.widget.setText(descriptor.label or "提交")
        result.widget.setStyleSheet(result.widget.styleSheet().replace(
            self._theme['input_border'],
            self._accent_color
        ))
        return result
    
    def _create_icon_button(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建图标按钮"""
        return self._create_button(descriptor)  # 简化实现
    
    # ============ 容器控件 ============
    
    def _create_form_container(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建表单容器"""
        widget = QWidget(self._parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_card(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建卡片"""
        widget = QFrame(self._parent)
        widget.setFrameShape(QFrame.StyledPanel)
        widget.setStyleSheet(f'''
            QFrame {{
                background-color: {self._theme['background']};
                border: 1px solid {self._theme['border']};
                border-radius: 8px;
                padding: 16px;
            }}
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_group(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建分组"""
        widget = QGroupBox(descriptor.label or "", self._parent)
        widget.setStyleSheet(f'''
            QGroupBox {{
                color: {self._theme['foreground']};
                font-size: {self._font_size + 1}px;
                font-weight: bold;
                border: 1px solid {self._theme['border']};
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }}
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_divider(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建分隔线"""
        widget = QFrame(self._parent)
        widget.setFrameShape(QFrame.HLine)
        widget.setStyleSheet(f'''
            QFrame {{
                border: none;
                border-top: 1px solid {self._theme['border']};
                margin: 12px 0;
            }}
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    # ============ 展示控件 ============
    
    def _create_label(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建标签"""
        widget = QLabel(descriptor.label or "", self._parent)
        widget.setStyleSheet(f'''
            color: {self._theme['foreground']};
            font-size: {self._font_size}px;
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_heading(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建标题"""
        level = descriptor.attributes.get('level', 1)
        font_sizes = {1: 24, 2: 20, 3: 18, 4: 16, 5: 14, 6: 12}
        font_size = font_sizes.get(level, 18)
        
        widget = QLabel(descriptor.label or "", self._parent)
        widget.setStyleSheet(f'''
            color: {self._theme['foreground']};
            font-size: {font_size}px;
            font-weight: bold;
            padding: 8px 0;
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_paragraph(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建段落"""
        widget = QLabel(descriptor.label or "", self._parent)
        widget.setWordWrap(True)
        widget.setStyleSheet(f'''
            color: {self._theme['foreground']};
            font-size: {self._font_size}px;
            line-height: 1.6;
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_link(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建链接"""
        widget = QLabel(f'<a href="{descriptor.attributes.get("href", "#")}">{descriptor.label}</a>', self._parent)
        widget.setStyleSheet(f'''
            color: {self._accent_color};
            font-size: {self._font_size}px;
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_image(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建图片"""
        widget = QLabel(self._parent)
        pixmap = QPixmap(descriptor.attributes.get('src', ''))
        if not pixmap.isNull():
            widget.setPixmap(pixmap)
            widget.setScaledContents(True)
        widget.setStyleSheet(f'''
            background-color: {self._theme['background']};
            border-radius: 4px;
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_progress_bar(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建进度条"""
        widget = QProgressBar(self._parent)
        
        if descriptor.default_value is not None:
            widget.setValue(int(descriptor.default_value))
        
        widget.setStyleSheet(f'''
            QProgressBar {{
                background-color: {self._theme['input_bg']};
                border: none;
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {self._accent_color};
                border-radius: 4px;
            }}
        ''')
        
        container = self._wrap_with_label(widget, descriptor)
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=container)
    
    # ============ 列表控件 ============
    
    def _create_list(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建列表"""
        widget = QListWidget(self._parent)
        widget.setStyleSheet(f'''
            QListWidget {{
                background-color: {self._theme['input_bg']};
                border: 1px solid {self._theme['border']};
                border-radius: 4px;
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
            }}
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_table(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建表格"""
        from PyQt6.QtWidgets import QTableWidget
        
        widget = QTableWidget(self._parent)
        widget.setStyleSheet(f'''
            QTableWidget {{
                background-color: {self._theme['input_bg']};
                border: 1px solid {self._theme['border']};
                border-radius: 4px;
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
            }}
            QHeaderView::section {{
                background-color: {self._theme['background']};
                color: {self._theme['foreground']};
                padding: 8px;
                border: none;
                font-weight: bold;
            }}
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_tabs(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建标签页"""
        widget = QTabWidget(self._parent)
        widget.setStyleSheet(f'''
            QTabWidget {{
                background-color: {self._theme['background']};
            }}
            QTabBar::tab {{
                background-color: {self._theme['input_bg']};
                color: {self._theme['foreground']};
                padding: 8px 16px;
                border: none;
            }}
            QTabBar::tab:selected {{
                background-color: {self._accent_color};
            }}
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    # ============ 反馈控件 ============
    
    def _create_alert(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建提示框"""
        alert_types = {
            "info": self._accent_color,
            "success": self._success_color,
            "warning": "#FF9800",
            "error": self._error_color
        }
        color = alert_types.get(descriptor.attributes.get("type", "info"), self._accent_color)
        
        widget = QLabel(descriptor.label or "", self._parent)
        widget.setWordWrap(True)
        widget.setStyleSheet(f'''
            QLabel {{
                background-color: {color}22;
                border-left: 4px solid {color};
                border-radius: 4px;
                padding: 12px;
                color: {self._theme['foreground']};
                font-size: {self._font_size}px;
            }}
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    def _create_spinner(self, descriptor: WidgetDescriptor) -> WidgetResult:
        """创建加载动画"""
        widget = QLabel("⏳ 加载中...", self._parent)
        widget.setAlignment(Qt.AlignCenter)
        widget.setStyleSheet(f'''
            QLabel {{
                color: {self._accent_color};
                font-size: {self._font_size}px;
            }}
        ''')
        return WidgetResult(widget=widget, descriptor=descriptor, layout_widget=widget)
    
    # ============ 辅助函数 ============
    
    def _wrap_with_label(self, widget: QWidget, descriptor: WidgetDescriptor) -> QWidget:
        """用标签包装控件"""
        if not descriptor.label:
            return widget
        
        container = QWidget(self._parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        label = QLabel(descriptor.label, container)
        label.setStyleSheet(f'''
            color: {self._theme['foreground']};
            font-size: {self._font_size}px;
            font-weight: bold;
        ''')
        
        # 添加必填标识
        if descriptor.required:
            required_label = QLabel('<span style="color: #F44336;">*</span>', container)
            label_layout = QHBoxLayout()
            label_layout.addWidget(label)
            label_layout.addWidget(required_label)
            label_layout.addStretch()
            layout.addLayout(label_layout)
        else:
            layout.addWidget(label)
        
        layout.addWidget(widget)
        
        return container
    
    def _create_validator(self, rule: ValidationRule) -> Optional[Any]:
        """创建验证器"""
        if rule.rule_type == "required":
            def validator(value):
                return bool(value and str(value).strip())
            return validator
        
        if rule.rule_type == "min":
            def validator(value):
                try:
                    return float(value) >= float(rule.value)
                except:
                    return False
            return validator
        
        if rule.rule_type == "max":
            def validator(value):
                try:
                    return float(value) <= float(rule.value)
                except:
                    return False
            return validator
        
        if rule.rule_type == "pattern":
            import re
            pattern = re.compile(rule.value)
            def validator(value):
                return bool(pattern.match(str(value)))
            return validator
        
        return None
    
    def _validate_and_style(self, widget: QLineEdit, validator: Callable):
        """验证并更新样式"""
        text = widget.text()
        is_valid = validator(text)
        
        if text:  # 只在有内容时验证
            if is_valid:
                widget.setStyleSheet(widget.styleSheet().replace(
                    self._error_color, self._theme['input_border']))
            else:
                widget.setStyleSheet(widget.styleSheet().replace(
                    self._theme['input_border'], self._error_color))
    
    # ============ 数据获取/设置 ============
    
    @staticmethod
    def get_value(widget: QWidget, descriptor: WidgetDescriptor) -> Any:
        """获取控件值"""
        if isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        elif isinstance(widget, QComboBox):
            return widget.currentData()
        elif isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QSlider):
            return widget.value()
        elif isinstance(widget, QSpinBox):
            return widget.value()
        elif isinstance(widget, QButtonGroup):
            checked = widget.checkedButton()
            if checked:
                return checked.data()
            return None
        elif hasattr(widget, 'button_group'):  # Radio group container
            return widget.button_group.checkedButton().data() if widget.button_group.checkedButton() else None
        
        return None
    
    @staticmethod
    def set_value(widget: QWidget, descriptor: WidgetDescriptor, value: Any):
        """设置控件值"""
        if isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, QPlainTextEdit):
            widget.setPlainText(str(value))
        elif isinstance(widget, QComboBox):
            for i in range(widget.count()):
                if widget.itemData(i) == value:
                    widget.setCurrentIndex(i)
                    break
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, (QSpinBox, QSlider)):
            widget.setValue(int(value))
        elif isinstance(widget, QButtonGroup):
            for btn in widget.buttons():
                if btn.data() == value:
                    btn.setChecked(True)
                    break
        elif hasattr(widget, 'button_group'):
            for btn in widget.button_group.buttons():
                if btn.data() == value:
                    btn.setChecked(True)
                    break
    
    @staticmethod
    def collect_form_data(
        widget_results: List[WidgetResult]
    ) -> Dict[str, Any]:
        """收集表单数据"""
        data = {}
        for result in widget_results:
            value = WidgetFactory.get_value(result.widget, result.descriptor)
            if value is not None:
                data[result.descriptor.id] = value
        return data
    
    @staticmethod
    def validate_form(
        widget_results: List[WidgetResult]
    ) -> tuple[bool, Dict[str, str]]:
        """验证表单"""
        errors = {}
        
        for result in widget_results:
            desc = result.descriptor
            
            # 检查必填
            if desc.required:
                value = WidgetFactory.get_value(result.widget, desc)
                if not value or (isinstance(value, str) and not value.strip()):
                    errors[desc.id] = f"{desc.label} 为必填项"
                    continue
            
            # 执行自定义验证
            for validator in result.validators:
                value = WidgetFactory.get_value(result.widget, desc)
                if not validator(value):
                    error_msg = next(
                        (v.message for v in desc.validations if v.rule_type == "required"),
                        "验证失败"
                    )
                    errors[desc.id] = error_msg
                    break
        
        return len(errors) == 0, errors
