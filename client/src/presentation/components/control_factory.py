"""
控件工厂 - 将UI描述转为Qt控件

负责将UI描述符转换为实际的Qt Widget控件，支持各种控件类型和布局。
"""

from typing import Dict, Any, Optional, List, Callable
from loguru import logger

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit, QPushButton,
    QCheckBox, QRadioButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QHBoxLayout, QVBoxLayout, QGridLayout, QFormLayout,
    QFrame, QScrollArea, QTabWidget, QProgressBar,
    QTableWidget, QTableWidgetItem, QListWidget, QListWidgetItem,
    QGroupBox, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPalette, QColor

from .ui_descriptor import (
    UIComponent, ControlType, LayoutType, ActionType,
    FormField, ActionButton, ClarificationRequest
)


class ControlFactory:
    """
    控件工厂
    
    负责将UIComponent转换为Qt Widget控件
    """
    
    def __init__(self):
        self._logger = logger.bind(component="ControlFactory")
        self._widget_cache: Dict[str, QWidget] = {}
        self._action_handlers: Dict[str, Callable] = {}
    
    def create_widget(self, component: UIComponent, parent: QWidget = None) -> QWidget:
        """
        根据UIComponent创建Qt Widget
        
        Args:
            component: UI组件描述
            parent: 父控件
            
        Returns:
            创建的Qt Widget
        """
        widget = self._create_control(component, parent)
        
        if widget:
            # 设置样式
            self._apply_style(widget, component)
            
            # 设置属性
            self._apply_properties(widget, component)
            
            # 缓存控件
            self._widget_cache[component.id] = widget
            
            self._logger.debug(f"创建控件: {component.id} -> {widget.__class__.__name__}")
        
        return widget
    
    def _create_control(self, component: UIComponent, parent: QWidget = None) -> Optional[QWidget]:
        """根据控件类型创建控件"""
        control_type = component.type
        
        # 基础控件
        if control_type == ControlType.LABEL:
            return self._create_label(component, parent)
        elif control_type == ControlType.TEXT:
            return self._create_text_field(component, parent)
        elif control_type == ControlType.TEXTAREA:
            return self._create_textarea(component, parent)
        elif control_type == ControlType.PASSWORD:
            return self._create_password_field(component, parent)
        elif control_type == ControlType.NUMBER:
            return self._create_number_field(component, parent)
        elif control_type == ControlType.CHECKBOX:
            return self._create_checkbox(component, parent)
        elif control_type == ControlType.RADIO:
            return self._create_radio_group(component, parent)
        elif control_type == ControlType.SELECT:
            return self._create_combobox(component, parent)
        elif control_type == ControlType.BUTTON:
            return self._create_button(component, parent)
        
        # 布局控件
        elif control_type == ControlType.CONTAINER:
            return self._create_container(component, parent)
        elif control_type == ControlType.ROW:
            return self._create_row(component, parent)
        elif control_type == ControlType.COLUMN:
            return self._create_column(component, parent)
        elif control_type == ControlType.CARD:
            return self._create_card(component, parent)
        elif control_type == ControlType.TABS:
            return self._create_tabs(component, parent)
        
        # 数据展示
        elif control_type == ControlType.TABLE:
            return self._create_table(component, parent)
        elif control_type == ControlType.LIST:
            return self._create_list(component, parent)
        elif control_type == ControlType.PROGRESS:
            return self._create_progress(component, parent)
        
        # 特殊控件
        elif control_type == ControlType.IMAGE:
            return self._create_image(component, parent)
        elif control_type == ControlType.AVATAR:
            return self._create_avatar(component, parent)
        elif control_type == ControlType.SEPARATOR:
            return self._create_separator(component, parent)
        elif control_type == ControlType.SPACER:
            return self._create_spacer(component, parent)
        
        # 对话相关
        elif control_type == ControlType.MESSAGE:
            return self._create_message_bubble(component, parent)
        elif control_type == ControlType.QUICK_REPLY:
            return self._create_quick_reply(component, parent)
        elif control_type == ControlType.FORM:
            return self._create_form(component, parent)
        elif control_type == ControlType.CLARIFICATION:
            return self._create_clarification(component, parent)
        
        self._logger.warning(f"未知控件类型: {control_type}")
        return None
    
    def _create_label(self, component: UIComponent, parent: QWidget = None) -> QLabel:
        """创建标签"""
        label = QLabel(component.label or str(component.value or ""), parent)
        label.setWordWrap(True)
        return label
    
    def _create_text_field(self, component: UIComponent, parent: QWidget = None) -> QLineEdit:
        """创建文本输入框"""
        field = QLineEdit(parent)
        field.setPlaceholderText(component.placeholder)
        if component.value is not None:
            field.setText(str(component.value))
        return field
    
    def _create_textarea(self, component: UIComponent, parent: QWidget = None) -> QTextEdit:
        """创建文本域"""
        area = QTextEdit(parent)
        area.setPlaceholderText(component.placeholder)
        if component.value is not None:
            area.setText(str(component.value))
        return area
    
    def _create_password_field(self, component: UIComponent, parent: QWidget = None) -> QLineEdit:
        """创建密码输入框"""
        field = QLineEdit(parent)
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText(component.placeholder)
        return field
    
    def _create_number_field(self, component: UIComponent, parent: QWidget = None) -> QWidget:
        """创建数字输入框"""
        field = QSpinBox(parent)
        if component.options:
            # 尝试获取范围
            for opt in component.options:
                if "min" in opt:
                    field.setMinimum(opt["min"])
                if "max" in opt:
                    field.setMaximum(opt["max"])
                if "step" in opt:
                    field.setSingleStep(opt["step"])
        if component.value is not None:
            field.setValue(int(component.value))
        return field
    
    def _create_checkbox(self, component: UIComponent, parent: QWidget = None) -> QCheckBox:
        """创建复选框"""
        checkbox = QCheckBox(component.label, parent)
        if component.value is not None:
            checkbox.setChecked(bool(component.value))
        return checkbox
    
    def _create_radio_group(self, component: UIComponent, parent: QWidget = None) -> QWidget:
        """创建单选按钮组"""
        group = QGroupBox(component.label, parent)
        layout = QVBoxLayout(group)
        
        for opt in component.options:
            radio = QRadioButton(opt.get("label", str(opt.get("value"))), group)
            if opt.get("selected", False):
                radio.setChecked(True)
            layout.addWidget(radio)
        
        return group
    
    def _create_combobox(self, component: UIComponent, parent: QWidget = None) -> QComboBox:
        """创建下拉框"""
        combo = QComboBox(parent)
        for opt in component.options:
            combo.addItem(opt.get("label", str(opt.get("value"))), opt.get("value"))
        if component.value is not None:
            index = combo.findData(component.value)
            if index >= 0:
                combo.setCurrentIndex(index)
        return combo
    
    def _create_button(self, component: UIComponent, parent: QWidget = None) -> QPushButton:
        """创建按钮"""
        button = QPushButton(component.label, parent)
        
        # 设置按钮变体样式
        variant = component.data.get("variant", "primary")
        self._style_button(button, variant)
        
        # 绑定点击事件
        if component.actions:
            action = component.actions[0]
            button.clicked.connect(lambda: self._handle_action(action))
        
        return button
    
    def _style_button(self, button: QPushButton, variant: str):
        """设置按钮样式"""
        styles = {
            "primary": """
                QPushButton {
                    background-color: #2563eb;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
                QPushButton:pressed {
                    background-color: #1e40af;
                }
            """,
            "secondary": """
                QPushButton {
                    background-color: #64748b;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #475569;
                }
            """,
            "danger": """
                QPushButton {
                    background-color: #dc2626;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #b91c1c;
                }
            """,
            "success": """
                QPushButton {
                    background-color: #16a34a;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #15803d;
                }
            """
        }
        
        button.setStyleSheet(styles.get(variant, styles["primary"]))
    
    def _create_container(self, component: UIComponent, parent: QWidget = None) -> QWidget:
        """创建容器"""
        container = QWidget(parent)
        self._create_layout(container, component)
        return container
    
    def _create_row(self, component: UIComponent, parent: QWidget = None) -> QWidget:
        """创建行布局容器"""
        container = QWidget(parent)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(component.layout_config.get("spacing", 8))
        
        for child in component.children:
            child_widget = self.create_widget(child, container)
            if child_widget:
                layout.addWidget(child_widget)
        
        return container
    
    def _create_column(self, component: UIComponent, parent: QWidget = None) -> QWidget:
        """创建列布局容器"""
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(component.layout_config.get("spacing", 8))
        
        for child in component.children:
            child_widget = self.create_widget(child, container)
            if child_widget:
                layout.addWidget(child_widget)
        
        return container
    
    def _create_card(self, component: UIComponent, parent: QWidget = None) -> QFrame:
        """创建卡片"""
        card = QFrame(parent)
        card.setStyleSheet("""
            QFrame {
                background-color: #2d2d44;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        if component.label:
            title = QLabel(component.label)
            title.setStyleSheet("font-size: 14px; font-weight: bold; color: white;")
            layout.addWidget(title)
        
        for child in component.children:
            child_widget = self.create_widget(child, card)
            if child_widget:
                layout.addWidget(child_widget)
        
        return card
    
    def _create_tabs(self, component: UIComponent, parent: QWidget = None) -> QTabWidget:
        """创建标签页"""
        tabs = QTabWidget(parent)
        
        for child in component.children:
            child_widget = self.create_widget(child, tabs)
            if child_widget:
                tabs.addTab(child_widget, child.label or child.id)
        
        return tabs
    
    def _create_table(self, component: UIComponent, parent: QWidget = None) -> QTableWidget:
        """创建表格"""
        data = component.data.get("rows", [])
        headers = component.data.get("headers", [])
        
        table = QTableWidget(len(data), len(headers), parent)
        table.setHorizontalHeaderLabels(headers)
        
        for row, row_data in enumerate(data):
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                table.setItem(row, col, item)
        
        table.resizeColumnsToContents()
        return table
    
    def _create_list(self, component: UIComponent, parent: QWidget = None) -> QListWidget:
        """创建列表"""
        list_widget = QListWidget(parent)
        
        for opt in component.options:
            item = QListWidgetItem(opt.get("label", str(opt.get("value"))))
            list_widget.addItem(item)
        
        return list_widget
    
    def _create_progress(self, component: UIComponent, parent: QWidget = None) -> QProgressBar:
        """创建进度条"""
        progress = QProgressBar(parent)
        progress.setValue(component.value or 0)
        
        if component.label:
            progress.setFormat(f"{component.label}: %p%")
        
        return progress
    
    def _create_image(self, component: UIComponent, parent: QWidget = None) -> QLabel:
        """创建图片控件"""
        label = QLabel(parent)
        # TODO: 实际加载图片
        label.setText(f"🖼️ {component.label}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label
    
    def _create_avatar(self, component: UIComponent, parent: QWidget = None) -> QLabel:
        """创建头像"""
        avatar = QLabel(parent)
        avatar.setStyleSheet("""
            QLabel {
                background-color: #2563eb;
                border-radius: 20px;
                font-size: 24px;
            }
        """)
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setText(component.label or "👤")
        return avatar
    
    def _create_separator(self, component: UIComponent, parent: QWidget = None) -> QFrame:
        """创建分隔线"""
        line = QFrame(parent)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #3d3d54;")
        return line
    
    def _create_spacer(self, component: UIComponent, parent: QWidget = None) -> QSpacerItem:
        """创建间隔"""
        return QSpacerItem(
            component.layout_config.get("width", 8),
            component.layout_config.get("height", 8),
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Minimum
        )
    
    def _create_message_bubble(self, component: UIComponent, parent: QWidget = None) -> QFrame:
        """创建消息气泡"""
        bubble = QFrame(parent)
        bubble.setStyleSheet("""
            QFrame {
                background-color: #2d2d44;
                border-radius: 16px;
                padding: 12px 16px;
            }
        """)
        
        layout = QVBoxLayout(bubble)
        
        content = QLabel(component.label or str(component.value or ""))
        content.setWordWrap(True)
        layout.addWidget(content)
        
        return bubble
    
    def _create_quick_reply(self, component: UIComponent, parent: QWidget = None) -> QWidget:
        """创建快捷回复按钮组"""
        container = QWidget(parent)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        for opt in component.options:
            btn = QPushButton(opt.get("label", str(opt.get("value"))))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: white;
                    border: none;
                    border-radius: 20px;
                    padding: 6px 16px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
            """)
            btn.clicked.connect(lambda checked, opt=opt: self._handle_quick_reply(opt))
            layout.addWidget(btn)
        
        return container
    
    def _create_form(self, component: UIComponent, parent: QWidget = None) -> QWidget:
        """创建表单"""
        form = QWidget(parent)
        layout = QFormLayout(form)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 创建表单字段
        for field in component.form_fields:
            label = QLabel(field.label)
            if field.required:
                label.setText(f"{field.label} *")
            
            widget = self._create_field_widget(field, form)
            layout.addRow(label, widget)
        
        # 添加操作按钮
        if component.actions:
            button_layout = QHBoxLayout()
            button_layout.setSpacing(8)
            
            for action in component.actions:
                btn = QPushButton(action.label)
                self._style_button(btn, action.variant)
                btn.clicked.connect(lambda checked, action=action: self._handle_action(action))
                button_layout.addWidget(btn)
            
            layout.addRow("", button_layout)
        
        return form
    
    def _create_field_widget(self, field: FormField, parent: QWidget = None) -> QWidget:
        """根据字段类型创建控件"""
        if field.control_type == ControlType.TEXT:
            widget = QLineEdit(parent)
            widget.setPlaceholderText(field.placeholder)
        elif field.control_type == ControlType.TEXTAREA:
            widget = QTextEdit(parent)
            widget.setPlaceholderText(field.placeholder)
        elif field.control_type == ControlType.PASSWORD:
            widget = QLineEdit(parent)
            widget.setEchoMode(QLineEdit.EchoMode.Password)
            widget.setPlaceholderText(field.placeholder)
        elif field.control_type == ControlType.NUMBER:
            widget = QSpinBox(parent)
        elif field.control_type == ControlType.CHECKBOX:
            widget = QCheckBox(parent)
        elif field.control_type == ControlType.SELECT:
            widget = QComboBox(parent)
            for opt in field.options:
                widget.addItem(opt.get("label", str(opt.get("value"))), opt.get("value"))
        else:
            widget = QLineEdit(parent)
        
        if field.value is not None:
            if hasattr(widget, "setText"):
                widget.setText(str(field.value))
            elif hasattr(widget, "setValue"):
                widget.setValue(field.value)
        
        widget.setEnabled(not field.disabled)
        widget.setVisible(not field.hidden)
        
        return widget
    
    def _create_clarification(self, component: UIComponent, parent: QWidget = None) -> QWidget:
        """创建澄清请求控件"""
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        
        # 问题标签
        question_label = QLabel(component.label)
        question_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #e0e0e0;")
        layout.addWidget(question_label)
        
        # 选项按钮
        options_layout = QVBoxLayout()
        options_layout.setSpacing(8)
        
        for opt in component.options:
            btn = QPushButton(opt.label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d44;
                    color: white;
                    border: 1px solid #3d3d54;
                    border-radius: 8px;
                    padding: 10px 16px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #3d3d54;
                    border-color: #2563eb;
                }
                QPushButton:checked {
                    background-color: #2563eb;
                    border-color: #2563eb;
                }
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, opt=opt: self._handle_clarification(opt))
            options_layout.addWidget(btn)
        
        layout.addLayout(options_layout)
        
        return container
    
    def _create_layout(self, widget: QWidget, component: UIComponent):
        """为容器创建布局"""
        layout_type = component.layout
        
        if layout_type == LayoutType.HORIZONTAL:
            layout = QHBoxLayout(widget)
        elif layout_type == LayoutType.VERTICAL:
            layout = QVBoxLayout(widget)
        elif layout_type == LayoutType.GRID:
            layout = QGridLayout(widget)
        else:
            layout = QVBoxLayout(widget)
        
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(component.layout_config.get("spacing", 8))
        
        # 添加子控件
        for child in component.children:
            child_widget = self.create_widget(child, widget)
            if child_widget:
                if isinstance(child_widget, QSpacerItem):
                    layout.addItem(child_widget)
                else:
                    layout.addWidget(child_widget)
    
    def _apply_style(self, widget: QWidget, component: UIComponent):
        """应用样式"""
        if component.style:
            style_str = "; ".join([f"{k}: {v}" for k, v in component.style.items()])
            widget.setStyleSheet(style_str)
    
    def _apply_properties(self, widget: QWidget, component: UIComponent):
        """应用属性"""
        widget.setVisible(component.visible)
        widget.setEnabled(component.enabled)
        
        if component.tooltip:
            widget.setToolTip(component.tooltip)
        
        if hasattr(widget, "setFixedSize"):
            width = component.layout_config.get("width")
            height = component.layout_config.get("height")
            if width and height:
                widget.setFixedSize(width, height)
            elif width:
                widget.setFixedWidth(width)
            elif height:
                widget.setFixedHeight(height)
    
    def _handle_action(self, action: ActionButton):
        """处理操作按钮点击"""
        self._logger.info(f"处理操作: {action.action_type.value} - {action.action_id}")
        
        if action.action_id in self._action_handlers:
            handler = self._action_handlers[action.action_id]
            handler(action.payload)
    
    def _handle_quick_reply(self, option: Dict[str, Any]):
        """处理快捷回复"""
        self._logger.info(f"快捷回复: {option}")
        
        # 触发回调
        if "quick_reply" in self._action_handlers:
            self._action_handlers["quick_reply"](option)
    
    def _handle_clarification(self, option: Dict[str, Any]):
        """处理澄清选择"""
        self._logger.info(f"澄清选择: {option}")
        
        if "clarification" in self._action_handlers:
            self._action_handlers["clarification"](option)
    
    def register_action_handler(self, action_id: str, handler: Callable):
        """注册操作处理器"""
        self._action_handlers[action_id] = handler
    
    def get_widget(self, component_id: str) -> Optional[QWidget]:
        """获取缓存的控件"""
        return self._widget_cache.get(component_id)
    
    def clear_cache(self):
        """清空控件缓存"""
        self._widget_cache.clear()