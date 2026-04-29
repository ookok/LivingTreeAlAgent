# -*- coding: utf-8 -*-
"""
UI Descriptor - UI描述符协议

定义AI生成UI的数据结构规范，支持JSON Schema格式。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import json


class WidgetType(Enum):
    """控件类型枚举"""
    # 输入控件
    TEXT_INPUT = "text_input"
    EMAIL_INPUT = "email_input"
    PASSWORD_INPUT = "password_input"
    NUMBER_INPUT = "number_input"
    TEXT_AREA = "text_area"
    
    # 选择控件
    CHECKBOX = "checkbox"
    RADIO_GROUP = "radio_group"
    DROPDOWN = "dropdown"
    SWITCH = "switch"
    SLIDER = "slider"
    
    # 日期时间
    DATE_PICKER = "date_picker"
    TIME_PICKER = "time_picker"
    DATETIME_PICKER = "datetime_picker"
    
    # 文件
    FILE_UPLOAD = "file_upload"
    IMAGE_UPLOAD = "image_upload"
    
    # 按钮
    BUTTON = "button"
    SUBMIT_BUTTON = "submit_button"
    ICON_BUTTON = "icon_button"
    
    # 容器
    FORM = "form"
    CARD = "card"
    GROUP = "group"
    DIVIDER = "divider"
    
    # 展示
    LABEL = "label"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LINK = "link"
    IMAGE = "image"
    PROGRESS_BAR = "progress_bar"
    
    # 列表
    LIST = "list"
    TABLE = "table"
    TREE = "tree"
    
    # 布局
    ROW = "row"
    COLUMN = "column"
    GRID = "grid"
    TABS = "tabs"
    
    # 反馈
    ALERT = "alert"
    TOAST = "toast"
    MODAL = "modal"
    SPINNER = "spinner"


@dataclass
class ValidationRule:
    """验证规则"""
    rule_type: str = ""  # required, min, max, pattern, custom
    value: Any = None
    message: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "rule_type": self.rule_type,
            "value": self.value,
            "message": self.message
        }


@dataclass
class Option:
    """选项定义"""
    value: str
    label: str
    disabled: bool = False
    selected: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "value": self.value,
            "label": self.label,
            "disabled": self.disabled,
            "selected": self.selected
        }


@dataclass
class WidgetDescriptor:
    """
    控件描述符
    
    Attributes:
        type: 控件类型 (WidgetType)
        id: 唯一标识符
        label: 显示标签
        placeholder: 占位文本
        default_value: 默认值
        required: 是否必填
        disabled: 是否禁用
        visible: 是否可见
        options: 选项列表 (用于select/radio/checkbox)
        validations: 验证规则列表
        attributes: 扩展属性
        children: 子控件 (用于容器类)
        layout: 布局配置
    """
    type: str
    id: str = ""
    label: str = ""
    placeholder: str = ""
    default_value: Any = None
    required: bool = False
    disabled: bool = False
    visible: bool = True
    
    # 选择类控件选项
    options: List[Option] = field(default_factory=list)
    
    # 验证规则
    validations: List[ValidationRule] = field(default_factory=list)
    
    # 扩展属性
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # 容器类子控件
    children: List['WidgetDescriptor'] = field(default_factory=list)
    
    # 布局配置
    span: int = 1  # 跨列数
    order: int = 0  # 排序顺序
    
    def __post_init__(self):
        if not self.id:
            self.id = f"widget_{id(self)}"
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "type": self.type,
            "id": self.id,
            "label": self.label,
            "placeholder": self.placeholder,
            "default_value": self.default_value,
            "required": self.required,
            "disabled": self.disabled,
            "visible": self.visible,
            "options": [opt.to_dict() if isinstance(opt, Option) else opt for opt in self.options],
            "validations": [v.to_dict() if isinstance(v, ValidationRule) else v for v in self.validations],
            "attributes": self.attributes,
            "children": [c.to_dict() if isinstance(c, WidgetDescriptor) else c for c in self.children],
            "span": self.span,
            "order": self.order,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'WidgetDescriptor':
        """从字典创建"""
        # 处理 options
        options = []
        for opt in data.get('options', []):
            if isinstance(opt, Option):
                options.append(opt)
            elif isinstance(opt, dict):
                options.append(Option(**opt))
        
        # 处理 validations
        validations = []
        for val in data.get('validations', []):
            if isinstance(val, ValidationRule):
                validations.append(val)
            elif isinstance(val, dict):
                validations.append(ValidationRule(**val))
        
        # 处理 children
        children = []
        for child in data.get('children', []):
            if isinstance(child, WidgetDescriptor):
                children.append(child)
            elif isinstance(child, dict):
                children.append(cls.from_dict(child))
        
        return cls(
            type=data.get('type', 'text_input'),
            id=data.get('id', ''),
            label=data.get('label', ''),
            placeholder=data.get('placeholder', ''),
            default_value=data.get('default_value'),
            required=data.get('required', False),
            disabled=data.get('disabled', False),
            visible=data.get('visible', True),
            options=options,
            validations=validations,
            attributes=data.get('attributes', {}),
            children=children,
            span=data.get('span', 1),
            order=data.get('order', 0),
        )


@dataclass
class FormDescriptor:
    """
    表单描述符
    
    Attributes:
        title: 表单标题
        description: 表单描述
        widgets: 控件列表
        layout_type: 布局类型 (vertical/horizontal/grid)
        show_cancel: 是否显示取消按钮
        show_reset: 是否显示重置按钮
        submit_label: 提交按钮文本
    """
    title: str = ""
    description: str = ""
    widgets: List[WidgetDescriptor] = field(default_factory=list)
    layout_type: str = "vertical"  # vertical, horizontal, grid, flow
    show_cancel: bool = True
    show_reset: bool = True
    submit_label: str = "提交"
    cancel_label: str = "取消"
    action: str = ""  # 表单提交地址
    
    def to_dict(self) -> Dict:
        return {
            "type": "form",
            "title": self.title,
            "description": self.description,
            "widgets": [w.to_dict() if isinstance(w, WidgetDescriptor) else w for w in self.widgets],
            "layout_type": self.layout_type,
            "show_cancel": self.show_cancel,
            "show_reset": self.show_reset,
            "submit_label": self.submit_label,
            "cancel_label": self.cancel_label,
            "action": self.action,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FormDescriptor':
        widgets = []
        for w in data.get('widgets', []):
            if isinstance(w, WidgetDescriptor):
                widgets.append(w)
            elif isinstance(w, dict):
                widgets.append(WidgetDescriptor.from_dict(w))
        
        return cls(
            title=data.get('title', ''),
            description=data.get('description', ''),
            widgets=widgets,
            layout_type=data.get('layout_type', 'vertical'),
            show_cancel=data.get('show_cancel', True),
            show_reset=data.get('show_reset', True),
            submit_label=data.get('submit_label', '提交'),
            cancel_label=data.get('cancel_label', '取消'),
            action=data.get('action', ''),
        )


@dataclass
class UIDescriptor:
    """
    UI描述符 - 顶层数据结构
    
    支持多种UI类型:
    - form: 表单
    - card: 卡片
    - alert: 提示框
    - list: 列表
    - custom: 自定义组合
    """
    ui_type: str = "form"
    title: str = ""
    description: str = ""
    widgets: List[WidgetDescriptor] = field(default_factory=list)
    children: List[Union['UIDescriptor', FormDescriptor]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 布局配置
    layout_type: str = "flow"  # flow, grid, vertical, horizontal
    columns: int = 3  # 流式布局列数
    responsive_breakpoints: Dict[str, int] = field(default_factory=lambda: {
        "large": 1200,
        "medium": 800,
        "small": 600
    })
    
    # 样式配置
    theme: str = "default"  # default, compact, spacious
    accent_color: str = "#2196F3"
    
    def to_dict(self) -> Dict:
        return {
            "ui_type": self.ui_type,
            "title": self.title,
            "description": self.description,
            "widgets": [w.to_dict() if isinstance(w, WidgetDescriptor) else w for w in self.widgets],
            "children": [c.to_dict() if isinstance(c, (UIDescriptor, FormDescriptor)) else c for c in self.children],
            "metadata": self.metadata,
            "layout_type": self.layout_type,
            "columns": self.columns,
            "responsive_breakpoints": self.responsive_breakpoints,
            "theme": self.theme,
            "accent_color": self.accent_color,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UIDescriptor':
        widgets = []
        for w in data.get('widgets', []):
            if isinstance(w, WidgetDescriptor):
                widgets.append(w)
            elif isinstance(w, dict):
                widgets.append(WidgetDescriptor.from_dict(w))
        
        children = []
        for c in data.get('children', []):
            if isinstance(c, (UIDescriptor, FormDescriptor)):
                children.append(c)
            elif isinstance(c, dict):
                if c.get('type') == 'form':
                    children.append(FormDescriptor.from_dict(c))
                else:
                    children.append(cls.from_dict(c))
        
        return cls(
            ui_type=data.get('ui_type', 'form'),
            title=data.get('title', ''),
            description=data.get('description', ''),
            widgets=widgets,
            children=children,
            metadata=data.get('metadata', {}),
            layout_type=data.get('layout_type', 'flow'),
            columns=data.get('columns', 3),
            responsive_breakpoints=data.get('responsive_breakpoints', {
                "large": 1200,
                "medium": 800,
                "small": 600
            }),
            theme=data.get('theme', 'default'),
            accent_color=data.get('accent_color', '#2196F3'),
        )
    
    def to_json(self, indent: int = 2) -> str:
        """序列化为JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'UIDescriptor':
        """从JSON解析"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_all_widgets(self) -> List[WidgetDescriptor]:
        """获取所有控件（包括嵌套）"""
        result = list(self.widgets)
        for child in self.children:
            if isinstance(child, UIDescriptor):
                result.extend(child.get_all_widgets())
            elif isinstance(child, FormDescriptor):
                result.extend(child.widgets)
        return result
    
    def get_widget_by_id(self, widget_id: str) -> Optional[WidgetDescriptor]:
        """根据ID获取控件"""
        for widget in self.get_all_widgets():
            if widget.id == widget_id:
                return widget
        return None


# ============ 工具函数 ============

def create_form_descriptor(
    title: str = "",
    widgets: List[WidgetDescriptor] = None,
    layout_type: str = "vertical"
) -> FormDescriptor:
    """快速创建表单描述符"""
    return FormDescriptor(
        title=title,
        widgets=widgets or [],
        layout_type=layout_type
    )


def create_widget(
    widget_type: str,
    label: str = "",
    field: str = "",
    required: bool = False,
    **kwargs
) -> WidgetDescriptor:
    """快速创建控件描述符"""
    return WidgetDescriptor(
        type=widget_type,
        id=field or f"field_{widget_type}_{id({})}",
        label=label,
        required=required,
        **kwargs
    )


def create_text_input(label: str, field: str, required: bool = False, **kwargs) -> WidgetDescriptor:
    """创建文本输入框"""
    return create_widget("text_input", label, field, required, **kwargs)


def create_email_input(label: str, field: str, required: bool = False, **kwargs) -> WidgetDescriptor:
    """创建邮箱输入框"""
    return create_widget("email_input", label, field, required, **kwargs)


def create_password_input(label: str, field: str, required: bool = False, **kwargs) -> WidgetDescriptor:
    """创建密码输入框"""
    return create_widget("password_input", label, field, required, **kwargs)


def create_dropdown(
    label: str,
    field: str,
    options: List[tuple],
    required: bool = False,
    **kwargs
) -> WidgetDescriptor:
    """创建下拉选择框"""
    return WidgetDescriptor(
        type="dropdown",
        id=field,
        label=label,
        required=required,
        options=[Option(value=v, label=l) for v, l in options],
        **kwargs
    )


def create_checkbox(label: str, field: str, default_value: bool = False, **kwargs) -> WidgetDescriptor:
    """创建复选框"""
    return WidgetDescriptor(
        type="checkbox",
        id=field,
        label=label,
        default_value=default_value,
        **kwargs
    )


def create_radio_group(
    label: str,
    field: str,
    options: List[str],
    required: bool = False,
    **kwargs
) -> WidgetDescriptor:
    """创建单选组"""
    return WidgetDescriptor(
        type="radio_group",
        id=field,
        label=label,
        required=required,
        options=[Option(value=opt, label=opt) for opt in options],
        **kwargs
    )


def create_button(label: str, button_type: str = "button", **kwargs) -> WidgetDescriptor:
    """创建按钮"""
    widget_type = f"{button_type}_button" if button_type != "button" else "button"
    return WidgetDescriptor(type=widget_type, label=label, **kwargs)


def create_submit_button(label: str = "提交") -> WidgetDescriptor:
    """创建提交按钮"""
    return WidgetDescriptor(type="submit_button", label=label)


def create_heading(text: str, level: int = 1) -> WidgetDescriptor:
    """创建标题"""
    return WidgetDescriptor(
        type="heading",
        label=text,
        attributes={"level": level}
    )
