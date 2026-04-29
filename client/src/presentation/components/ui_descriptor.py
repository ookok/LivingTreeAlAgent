"""
UI描述符协议 - 定义数据结构

定义AI响应生成UI的标准化描述格式，支持渐进式UI渲染和需求澄清。

核心概念：
- UIDescriptor: UI描述符基类
- ControlType: 控件类型枚举
- LayoutType: 布局类型枚举
- UIComponent: 组件描述
- FormField: 表单字段描述
- ActionButton: 操作按钮描述
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import json


class ControlType(Enum):
    """控件类型枚举"""
    # 基础控件
    LABEL = "label"
    TEXT = "text"
    TEXTAREA = "textarea"
    PASSWORD = "password"
    NUMBER = "number"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SELECT = "select"
    BUTTON = "button"
    
    # 布局控件
    CONTAINER = "container"
    ROW = "row"
    COLUMN = "column"
    CARD = "card"
    TABS = "tabs"
    
    # 数据展示
    TABLE = "table"
    LIST = "list"
    CHART = "chart"
    PROGRESS = "progress"
    
    # 特殊控件
    IMAGE = "image"
    AVATAR = "avatar"
    SEPARATOR = "separator"
    SPACER = "spacer"
    
    # 对话相关
    MESSAGE = "message"
    QUICK_REPLY = "quick_reply"
    FORM = "form"
    CLARIFICATION = "clarification"


class LayoutType(Enum):
    """布局类型枚举"""
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    GRID = "grid"
    FLEX = "flex"
    STACK = "stack"


class ActionType(Enum):
    """操作类型枚举"""
    SUBMIT = "submit"
    CANCEL = "cancel"
    CLICK = "click"
    LINK = "link"
    CALL_API = "call_api"
    RUN_TOOL = "run_tool"
    NEXT_STEP = "next_step"
    PREV_STEP = "prev_step"
    FINISH = "finish"
    RESET = "reset"


class ValidationRule:
    """验证规则"""
    def __init__(
        self,
        required: bool = False,
        min_length: int = 0,
        max_length: int = 0,
        pattern: str = "",
        min_value: float = None,
        max_value: float = None,
        error_message: str = ""
    ):
        self.required = required
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern
        self.min_value = min_value
        self.max_value = max_value
        self.error_message = error_message
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "required": self.required,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "pattern": self.pattern,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationRule':
        return cls(
            required=data.get("required", False),
            min_length=data.get("min_length", 0),
            max_length=data.get("max_length", 0),
            pattern=data.get("pattern", ""),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            error_message=data.get("error_message", "")
        )


@dataclass
class FormField:
    """表单字段描述"""
    name: str
    label: str
    control_type: ControlType
    placeholder: str = ""
    value: Any = None
    options: List[Dict[str, Any]] = field(default_factory=list)
    validation: Optional[ValidationRule] = None
    required: bool = False
    disabled: bool = False
    hidden: bool = False
    help_text: str = ""
    tooltip: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "control_type": self.control_type.value,
            "placeholder": self.placeholder,
            "value": self.value,
            "options": self.options,
            "validation": self.validation.to_dict() if self.validation else None,
            "required": self.required,
            "disabled": self.disabled,
            "hidden": self.hidden,
            "help_text": self.help_text,
            "tooltip": self.tooltip
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FormField':
        control_type = ControlType(data.get("control_type", "text"))
        validation_data = data.get("validation")
        validation = ValidationRule.from_dict(validation_data) if validation_data else None
        
        return cls(
            name=data["name"],
            label=data["label"],
            control_type=control_type,
            placeholder=data.get("placeholder", ""),
            value=data.get("value"),
            options=data.get("options", []),
            validation=validation,
            required=data.get("required", False),
            disabled=data.get("disabled", False),
            hidden=data.get("hidden", False),
            help_text=data.get("help_text", ""),
            tooltip=data.get("tooltip", "")
        )


@dataclass
class ActionButton:
    """操作按钮描述"""
    label: str
    action_type: ActionType
    action_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    variant: str = "primary"  # primary, secondary, danger, success
    disabled: bool = False
    icon: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "action_type": self.action_type.value,
            "action_id": self.action_id,
            "payload": self.payload,
            "variant": self.variant,
            "disabled": self.disabled,
            "icon": self.icon
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionButton':
        action_type = ActionType(data.get("action_type", "click"))
        return cls(
            label=data["label"],
            action_type=action_type,
            action_id=data.get("action_id", ""),
            payload=data.get("payload", {}),
            variant=data.get("variant", "primary"),
            disabled=data.get("disabled", False),
            icon=data.get("icon", "")
        )


@dataclass
class UIComponent:
    """UI组件描述"""
    id: str
    type: ControlType
    label: str = ""
    value: Any = None
    placeholder: str = ""
    options: List[Dict[str, Any]] = field(default_factory=list)
    children: List['UIComponent'] = field(default_factory=list)
    layout: LayoutType = LayoutType.VERTICAL
    layout_config: Dict[str, Any] = field(default_factory=dict)
    style: Dict[str, str] = field(default_factory=dict)
    actions: List[ActionButton] = field(default_factory=list)
    form_fields: List[FormField] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    visible: bool = True
    enabled: bool = True
    tooltip: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "value": self.value,
            "placeholder": self.placeholder,
            "options": self.options,
            "children": [child.to_dict() for child in self.children],
            "layout": self.layout.value,
            "layout_config": self.layout_config,
            "style": self.style,
            "actions": [action.to_dict() for action in self.actions],
            "form_fields": [field.to_dict() for field in self.form_fields],
            "data": self.data,
            "visible": self.visible,
            "enabled": self.enabled,
            "tooltip": self.tooltip
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UIComponent':
        control_type = ControlType(data.get("type", "container"))
        layout_type = LayoutType(data.get("layout", "vertical"))
        
        children = []
        for child_data in data.get("children", []):
            children.append(cls.from_dict(child_data))
        
        actions = []
        for action_data in data.get("actions", []):
            actions.append(ActionButton.from_dict(action_data))
        
        form_fields = []
        for field_data in data.get("form_fields", []):
            form_fields.append(FormField.from_dict(field_data))
        
        return cls(
            id=data["id"],
            type=control_type,
            label=data.get("label", ""),
            value=data.get("value"),
            placeholder=data.get("placeholder", ""),
            options=data.get("options", []),
            children=children,
            layout=layout_type,
            layout_config=data.get("layout_config", {}),
            style=data.get("style", {}),
            actions=actions,
            form_fields=form_fields,
            data=data.get("data", {}),
            visible=data.get("visible", True),
            enabled=data.get("enabled", True),
            tooltip=data.get("tooltip", "")
        )
    
    def add_child(self, child: 'UIComponent'):
        """添加子组件"""
        self.children.append(child)
    
    def find_component(self, component_id: str) -> Optional['UIComponent']:
        """查找组件"""
        if self.id == component_id:
            return self
        for child in self.children:
            found = child.find_component(component_id)
            if found:
                return found
        return None


@dataclass
class ClarificationOption:
    """需求澄清选项"""
    id: str
    label: str
    value: Any = None
    is_default: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "value": self.value,
            "is_default": self.is_default
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClarificationOption':
        return cls(
            id=data["id"],
            label=data["label"],
            value=data.get("value"),
            is_default=data.get("is_default", False)
        )


@dataclass
class ClarificationRequest:
    """需求澄清请求"""
    id: str
    question: str
    options: List[ClarificationOption] = field(default_factory=list)
    required: bool = True
    allow_custom: bool = False
    placeholder: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "options": [opt.to_dict() for opt in self.options],
            "required": self.required,
            "allow_custom": self.allow_custom,
            "placeholder": self.placeholder
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClarificationRequest':
        options = []
        for opt_data in data.get("options", []):
            options.append(ClarificationOption.from_dict(opt_data))
        
        return cls(
            id=data["id"],
            question=data["question"],
            options=options,
            required=data.get("required", True),
            allow_custom=data.get("allow_custom", False),
            placeholder=data.get("placeholder", "")
        )


@dataclass
class UIResponse:
    """AI生成的UI响应"""
    content: str = ""
    components: List[UIComponent] = field(default_factory=list)
    clarifications: List[ClarificationRequest] = field(default_factory=list)
    requires_input: bool = False
    next_step: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "components": [comp.to_dict() for comp in self.components],
            "clarifications": [clar.to_dict() for clar in self.clarifications],
            "requires_input": self.requires_input,
            "next_step": self.next_step,
            "context": self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UIResponse':
        components = []
        for comp_data in data.get("components", []):
            components.append(UIComponent.from_dict(comp_data))
        
        clarifications = []
        for clar_data in data.get("clarifications", []):
            clarifications.append(ClarificationRequest.from_dict(clar_data))
        
        return cls(
            content=data.get("content", ""),
            components=components,
            clarifications=clarifications,
            requires_input=data.get("requires_input", False),
            next_step=data.get("next_step"),
            context=data.get("context", {})
        )
    
    def to_json(self, indent: int = 2) -> str:
        """转为JSON字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'UIResponse':
        """从JSON字符串解析"""
        data = json.loads(json_str)
        return cls.from_dict(data)


class UIDescriptorProtocol:
    """UI描述符协议 - 提供标准的序列化/反序列化方法"""
    
    @staticmethod
    def serialize(component: Union[UIComponent, UIResponse]) -> str:
        """序列化UI组件或响应"""
        if isinstance(component, UIComponent):
            return json.dumps(component.to_dict(), indent=2, ensure_ascii=False)
        elif isinstance(component, UIResponse):
            return component.to_json()
        return ""
    
    @staticmethod
    def deserialize(json_str: str) -> Union[UIComponent, UIResponse]:
        """反序列化JSON为UI组件或响应"""
        try:
            data = json.loads(json_str)
            if "content" in data and "components" in data:
                return UIResponse.from_dict(data)
            elif "id" in data and "type" in data:
                return UIComponent.from_dict(data)
            return None
        except json.JSONDecodeError:
            return None
    
    @staticmethod
    def create_simple_text(label: str, value: str = "") -> UIComponent:
        """创建简单文本组件"""
        return UIComponent(
            id=f"text_{hash(label)}",
            type=ControlType.TEXT,
            label=label,
            value=value
        )
    
    @staticmethod
    def create_button(label: str, action_id: str, variant: str = "primary") -> UIComponent:
        """创建按钮组件"""
        action = ActionButton(
            label=label,
            action_type=ActionType.CLICK,
            action_id=action_id,
            variant=variant
        )
        return UIComponent(
            id=f"btn_{hash(label)}",
            type=ControlType.BUTTON,
            label=label,
            actions=[action]
        )
    
    @staticmethod
    def create_form(fields: List[FormField], actions: List[ActionButton]) -> UIComponent:
        """创建表单组件"""
        return UIComponent(
            id="form_container",
            type=ControlType.FORM,
            form_fields=fields,
            actions=actions
        )
    
    @staticmethod
    def create_clarification(question: str, options: List[str]) -> ClarificationRequest:
        """创建澄清请求"""
        clarification_options = []
        for i, opt in enumerate(options):
            clarification_options.append(ClarificationOption(
                id=f"opt_{i}",
                label=opt,
                value=opt,
                is_default=(i == 0)
            ))
        
        return ClarificationRequest(
            id=f"clar_{hash(question)}",
            question=question,
            options=clarification_options
        )