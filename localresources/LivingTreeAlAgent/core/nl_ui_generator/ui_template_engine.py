"""
UI Template Engine - UI模板引擎
================================

管理和操作UI模板，支持模板的创建、修改、组合和渲染。

模板结构:
    {
        "id": "panel_id",
        "name": "面板名称",
        "layout": "vertical|horizontal|grid",
        "components": [...],
        "slots": {...},
        "styles": {...}
    }
"""

import json
import uuid
from typing import Optional, Callable, Any, Protocol
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import copy


class LayoutType(Enum):
    """布局类型"""
    VERTICAL = "vertical"      # 垂直布局
    HORIZONTAL = "horizontal"  # 水平布局
    GRID = "grid"              # 网格布局
    ABSOLUTE = "absolute"      # 绝对定位
    FLEX = "flex"              # 弹性布局


class ComponentType(Enum):
    """组件类型"""
    BUTTON = "button"
    INPUT = "input"
    TEXT = "text"
    IMAGE = "image"
    CONTAINER = "container"
    LIST = "list"
    TABLE = "table"
    CARD = "card"
    MODAL = "modal"
    TOAST = "toast"
    DIVIDER = "divider"
    SPACER = "spacer"
    CUSTOM = "custom"


@dataclass
class Position:
    """位置信息"""
    x: int = 0
    y: int = 0


@dataclass
class Size:
    """尺寸信息"""
    width: int = 100
    height: int = 40


@dataclass
class ComponentStyle:
    """组件样式"""
    # 基础样式
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    border_color: Optional[str] = None
    border_width: int = 0
    border_radius: int = 0

    # 间距
    margin: int = 0
    padding: int = 8

    # 字体
    font_size: int = 14
    font_weight: str = "normal"
    font_family: str = "Microsoft YaHei"

    # 对齐
    align: str = "left"       # left/center/right
    valign: str = "middle"    # top/middle/bottom

    # 特效
    opacity: float = 1.0
    shadow: bool = False

    def to_dict(self) -> dict:
        """转换为字典"""
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "ComponentStyle":
        """从字典创建"""
        if data is None:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class TemplateComponent:
    """模板组件定义"""
    id: str
    type: ComponentType
    name: str = ""

    # 内容
    text: str = ""
    placeholder: str = ""
    icon: str = ""
    value: Any = None

    # 位置和尺寸
    position: Position = field(default_factory=Position)
    size: Size = field(default_factory=Size)

    # 样式
    style: ComponentStyle = field(default_factory=ComponentStyle)

    # 动作
    action: Optional[str] = None  # 动作ID
    action_params: dict = field(default_factory=dict)

    # 状态
    visible: bool = True
    enabled: bool = True

    # 子组件
    children: list["TemplateComponent"] = field(default_factory=list)

    # 元数据
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.name:
            self.name = self.id

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, ComponentType) else self.type,
            "name": self.name,
            "text": self.text,
            "placeholder": self.placeholder,
            "icon": self.icon,
            "value": self.value,
            "position": {"x": self.position.x, "y": self.position.y} if isinstance(self.position, Position) else self.position,
            "size": {"width": self.size.width, "height": self.size.height} if isinstance(self.size, Size) else self.size,
            "style": self.style.to_dict() if isinstance(self.style, ComponentStyle) else self.style,
            "action": self.action,
            "action_params": self.action_params,
            "visible": self.visible,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }
        if self.children:
            result["children"] = [c.to_dict() if isinstance(c, TemplateComponent) else c for c in self.children]
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "TemplateComponent":
        """从字典创建"""
        if data is None:
            return None

        position = data.get("position", {})
        if isinstance(position, dict):
            position = Position(x=position.get("x", 0), y=position.get("y", 0))

        size = data.get("size", {})
        if isinstance(size, dict):
            size = Size(width=size.get("width", 100), height=size.get("height", 40))

        style = data.get("style", {})
        if isinstance(style, dict):
            style = ComponentStyle.from_dict(style)

        component_type = data.get("type", "button")
        if isinstance(component_type, str):
            try:
                component_type = ComponentType(component_type)
            except ValueError:
                component_type = ComponentType.CUSTOM

        children = []
        for child in data.get("children", []):
            if isinstance(child, dict):
                children.append(cls.from_dict(child))

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=component_type,
            name=data.get("name", ""),
            text=data.get("text", ""),
            placeholder=data.get("placeholder", ""),
            icon=data.get("icon", ""),
            value=data.get("value"),
            position=position,
            size=size,
            style=style,
            action=data.get("action"),
            action_params=data.get("action_params", {}),
            visible=data.get("visible", True),
            enabled=data.get("enabled", True),
            children=children,
            metadata=data.get("metadata", {}),
        )


@dataclass
class ComponentSlot:
    """组件插槽"""
    name: str
    allowed_types: list[str] = field(default_factory=list)  # 允许的组件类型
    max_items: int = -1  # -1表示无限制
    default_component: Optional[str] = None


@dataclass
class UITemplate:
    """UI模板定义"""
    id: str
    name: str
    description: str = ""

    # 布局
    layout: LayoutType = LayoutType.VERTICAL
    layout_config: dict = field(default_factory=dict)

    # 组件
    components: list[TemplateComponent] = field(default_factory=list)

    # 插槽
    slots: dict[str, ComponentSlot] = field(default_factory=dict)

    # 样式
    container_style: ComponentStyle = field(default_factory=ComponentStyle)
    styles: dict = field(default_factory=dict)

    # 元数据
    version: str = "1.0.0"
    author: str = "system"
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "layout": self.layout.value if isinstance(self.layout, LayoutType) else self.layout,
            "layout_config": self.layout_config,
            "components": [c.to_dict() if isinstance(c, TemplateComponent) else c for c in self.components],
            "slots": {
                name: {
                    "name": slot.name,
                    "allowed_types": slot.allowed_types,
                    "max_items": slot.max_items,
                    "default_component": slot.default_component,
                }
                for name, slot in self.slots.items()
            },
            "container_style": self.container_style.to_dict() if isinstance(self.container_style, ComponentStyle) else self.container_style,
            "styles": self.styles,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UITemplate":
        """从字典创建"""
        if data is None:
            return None

        layout = data.get("layout", "vertical")
        if isinstance(layout, str):
            try:
                layout = LayoutType(layout)
            except ValueError:
                layout = LayoutType.VERTICAL

        container_style = data.get("container_style", {})
        if isinstance(container_style, dict):
            container_style = ComponentStyle.from_dict(container_style)

        components = []
        for comp in data.get("components", []):
            if isinstance(comp, dict):
                components.append(TemplateComponent.from_dict(comp))

        slots = {}
        for name, slot_data in data.get("slots", {}).items():
            if isinstance(slot_data, dict):
                slots[name] = ComponentSlot(
                    name=slot_data.get("name", name),
                    allowed_types=slot_data.get("allowed_types", []),
                    max_items=slot_data.get("max_items", -1),
                    default_component=slot_data.get("default_component"),
                )

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Unnamed"),
            description=data.get("description", ""),
            layout=layout,
            layout_config=data.get("layout_config", {}),
            components=components,
            slots=slots,
            container_style=container_style,
            styles=data.get("styles", {}),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "system"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

    def clone(self) -> "UITemplate":
        """创建深拷贝"""
        return UITemplate.from_dict(copy.deepcopy(self.to_dict()))

    def find_component(self, component_id: str) -> Optional[TemplateComponent]:
        """根据ID查找组件"""
        for comp in self.components:
            if comp.id == component_id:
                return comp
            # 递归查找子组件
            found = self._find_in_children(comp, component_id)
            if found:
                return found
        return None

    def _find_in_children(self, parent: TemplateComponent, component_id: str) -> Optional[TemplateComponent]:
        """在子组件中递归查找"""
        for child in parent.children:
            if child.id == component_id:
                return child
            found = self._find_in_children(child, component_id)
            if found:
                return found
        return None

    def add_component(self, component: TemplateComponent, slot: Optional[str] = None, index: int = -1):
        """添加组件"""
        if slot and slot in self.slots:
            # 添加到指定插槽
            slot_def = self.slots[slot]
            if slot_def.max_items > 0 and len(self.components) >= slot_def.max_items:
                raise ValueError(f"Slot '{slot}' is full")

        if index < 0 or index >= len(self.components):
            self.components.append(component)
        else:
            self.components.insert(index, component)

    def remove_component(self, component_id: str) -> bool:
        """移除组件"""
        for i, comp in enumerate(self.components):
            if comp.id == component_id:
                self.components.pop(i)
                return True
            if self._remove_from_children(comp, component_id):
                return True
        return False

    def _remove_from_children(self, parent: TemplateComponent, component_id: str) -> bool:
        """从子组件中移除"""
        for i, child in enumerate(parent.children):
            if child.id == component_id:
                parent.children.pop(i)
                return True
            if self._remove_from_children(child, component_id):
                return True
        return False


class UITemplateEngine:
    """UI模板引擎"""

    # 内置模板
    BUILTIN_TEMPLATES = {
        "button": {
            "id": "builtin_button",
            "name": "按钮",
            "components": [
                {
                    "id": "btn",
                    "type": "button",
                    "text": "按钮",
                    "size": {"width": 100, "height": 40},
                    "style": {
                        "background_color": "#007acc",
                        "text_color": "#ffffff",
                        "border_radius": 4,
                        "padding": 10,
                    }
                }
            ]
        },
        "input": {
            "id": "builtin_input",
            "name": "输入框",
            "components": [
                {
                    "id": "input",
                    "type": "input",
                    "placeholder": "请输入...",
                    "size": {"width": 200, "height": 40},
                    "style": {
                        "border_color": "#cccccc",
                        "border_width": 1,
                        "border_radius": 4,
                        "padding": 8,
                    }
                }
            ]
        },
        "card": {
            "id": "builtin_card",
            "name": "卡片",
            "layout": "vertical",
            "components": [
                {
                    "id": "card_container",
                    "type": "container",
                    "size": {"width": 300, "height": 200},
                    "style": {
                        "background_color": "#ffffff",
                        "border_color": "#e0e0e0",
                        "border_width": 1,
                        "border_radius": 8,
                        "padding": 16,
                        "shadow": True,
                    },
                    "children": [
                        {
                            "id": "card_title",
                            "type": "text",
                            "text": "标题",
                            "style": {"font_size": 16, "font_weight": "bold", "margin": "0 0 8px 0"}
                        },
                        {
                            "id": "card_content",
                            "type": "text",
                            "text": "内容区域",
                            "style": {"font_size": 14, "text_color": "#666666"}
                        }
                    ]
                }
            ]
        },
        "simple_panel": {
            "id": "builtin_simple_panel",
            "name": "简单面板",
            "layout": "vertical",
            "components": [
                {
                    "id": "panel_header",
                    "type": "text",
                    "text": "面板标题",
                    "style": {"font_size": 18, "font_weight": "bold", "margin": "0 0 16px 0"}
                },
                {
                    "id": "panel_content",
                    "type": "container",
                    "style": {"padding": 8},
                    "children": []
                }
            ],
            "slots": {
                "body": {
                    "name": "body",
                    "allowed_types": ["button", "input", "text", "container"],
                    "max_items": -1
                }
            }
        },
    }

    def __init__(self):
        self.templates: dict[str, UITemplate] = {}
        self.user_templates: dict[str, UITemplate] = {}  # 用户自定义模板
        self._load_builtin_templates()

    def _load_builtin_templates(self):
        """加载内置模板"""
        for template_id, template_data in self.BUILTIN_TEMPLATES.items():
            template = UITemplate.from_dict(template_data)
            self.templates[template_id] = template

    def register_template(self, template: UITemplate, user_template: bool = False):
        """注册模板"""
        if user_template:
            self.user_templates[template.id] = template
        else:
            self.templates[template.id] = template

    def get_template(self, template_id: str) -> Optional[UITemplate]:
        """获取模板"""
        if template_id in self.templates:
            return self.templates[template_id]
        if template_id in self.user_templates:
            return self.user_templates[template_id]
        return None

    def create_from_template(self, template_id: str, overrides: dict = None) -> Optional[TemplateComponent]:
        """
        从模板创建组件

        Args:
            template_id: 模板ID
            overrides: 属性覆盖

        Returns:
            创建的组件，或None
        """
        template = self.get_template(template_id)
        if not template:
            return None

        # 深拷贝组件
        component = TemplateComponent.from_dict(template.components[0].to_dict()) if template.components else None

        if component and overrides:
            self._apply_overrides(component, overrides)

        return component

    def _apply_overrides(self, component: TemplateComponent, overrides: dict):
        """应用属性覆盖"""
        for key, value in overrides.items():
            if hasattr(component, key):
                setattr(component, key, value)

    def create_button(
        self,
        text: str = "按钮",
        action: Optional[str] = None,
        style: dict = None,
        position: dict = None,
        size: dict = None,
    ) -> TemplateComponent:
        """快速创建按钮"""
        return TemplateComponent(
            id=f"btn_{uuid.uuid4().hex[:8]}",
            type=ComponentType.BUTTON,
            text=text,
            action=action,
            style=ComponentStyle.from_dict(style or {}),
            position=Position(**position) if position else Position(),
            size=Size(**size) if size else Size(),
        )

    def create_input(
        self,
        placeholder: str = "请输入...",
        value: Any = None,
        style: dict = None,
        position: dict = None,
        size: dict = None,
    ) -> TemplateComponent:
        """快速创建输入框"""
        return TemplateComponent(
            id=f"input_{uuid.uuid4().hex[:8]}",
            type=ComponentType.INPUT,
            placeholder=placeholder,
            value=value,
            style=ComponentStyle.from_dict(style or {}),
            position=Position(**position) if position else Position(),
            size=Size(**size) if size else Size(width=200, height=40),
        )

    def create_text(
        self,
        text: str = "",
        style: dict = None,
        position: dict = None,
    ) -> TemplateComponent:
        """快速创建文本"""
        return TemplateComponent(
            id=f"text_{uuid.uuid4().hex[:8]}",
            type=ComponentType.TEXT,
            text=text,
            style=ComponentStyle.from_dict(style or {}),
            position=Position(**position) if position else Position(),
        )

    def render_to_dict(self, template: UITemplate) -> dict:
        """渲染模板为字典（用于前端）"""
        return template.to_dict()

    def export_template(self, template_id: str) -> Optional[str]:
        """导出模板为JSON字符串"""
        template = self.get_template(template_id)
        if template:
            return json.dumps(template.to_dict(), ensure_ascii=False, indent=2)
        return None

    def import_template(self, json_str: str, user_template: bool = True) -> Optional[UITemplate]:
        """从JSON导入模板"""
        try:
            data = json.loads(json_str)
            template = UITemplate.from_dict(data)
            self.register_template(template, user_template)
            return template
        except Exception:
            return None


# 全局单例
_template_engine: Optional[UITemplateEngine] = None


def get_template_engine() -> UITemplateEngine:
    """获取模板引擎单例"""
    global _template_engine
    if _template_engine is None:
        _template_engine = UITemplateEngine()
    return _template_engine