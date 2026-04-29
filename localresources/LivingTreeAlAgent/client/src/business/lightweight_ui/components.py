"""
响应式组件库

轻量级、高性能组件实现，支持多种类型组件
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

from .models import (
    ComponentType, ComponentStyle, AnimationConfig,
    AnimationType, ComponentEvent
)


class ButtonVariant(Enum):
    """按钮变体"""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    OUTLINE = "outline"
    GHOST = "ghost"
    DANGER = "danger"


class InputType(Enum):
    """输入框类型"""
    TEXT = "text"
    PASSWORD = "password"
    EMAIL = "email"
    NUMBER = "number"
    SEARCH = "search"
    TEL = "tel"
    URL = "url"


class SelectMode(Enum):
    """选择模式"""
    SINGLE = "single"
    MULTIPLE = "multiple"
    TAGS = "tags"


@dataclass
class ComponentProps:
    """组件属性"""
    # 基础属性
    id: str = ""
    class_name: str = ""
    style: Dict[str, str] = field(default_factory=dict)
    disabled: bool = False
    readonly: bool = False
    visible: bool = True
    
    # 内容
    text: str = ""
    value: Any = None
    placeholder: str = ""
    
    # 状态
    loading: bool = False
    error: Optional[str] = None
    success: bool = False
    
    # 图标
    icon: Optional[str] = None
    icon_position: str = "left"
    
    # 动画
    animation: Optional[AnimationConfig] = None
    
    # 元数据
    tooltip: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LightweightButton:
    """轻量级按钮组件"""
    
    def __init__(self, text: str = "", variant: ButtonVariant = ButtonVariant.PRIMARY,
                 size: str = "medium", on_click: Optional[Callable] = None, **kwargs):
        self.props = ComponentProps(text=text, **kwargs)
        self.variant = variant
        self.size = size
        self.on_click = on_click
        self._hovered = False
        self._pressed = False
    
    def render(self) -> Dict[str, Any]:
        base_class = f"lw-btn lw-btn-{self.variant.value} lw-btn-{self.size}"
        if self.props.class_name:
            base_class += f" {self.props.class_name}"
        if self.props.disabled or self.props.loading:
            base_class += " lw-disabled"
        
        style = self.props.style.copy()
        if self._hovered and not self.props.disabled:
            style["opacity"] = "0.9"
        
        return {
            "type": "button",
            "class": base_class,
            "style": style,
            "children": self._render_content(),
            "disabled": self.props.disabled or self.props.loading,
            "on_click": self.on_click,
        }
    
    def _render_content(self) -> List:
        content = []
        if self.props.loading:
            content.append({"type": "span", "class": "lw-spinner"})
        if self.props.icon and self.props.icon_position == "left":
            content.append({"type": "i", "class": f"lw-icon {self.props.icon}"})
        content.append(self.props.text)
        if self.props.icon and self.props.icon_position == "right":
            content.append({"type": "i", "class": f"lw-icon {self.props.icon}"})
        return content


class LightweightInput:
    """轻量级输入框组件"""
    
    def __init__(self, input_type: InputType = InputType.TEXT, value: str = "",
                 placeholder: str = "", on_change: Optional[Callable] = None,
                 validator: Optional[Callable] = None, **kwargs):
        self.props = ComponentProps(value=value, placeholder=placeholder, **kwargs)
        self.input_type = input_type
        self.on_change = on_change
        self.validator = validator
        self._focused = False
        self._error_message = None
    
    def render(self) -> Dict[str, Any]:
        base_class = "lw-input"
        if self.props.class_name:
            base_class += f" {self.props.class_name}"
        if self._focused:
            base_class += " lw-focused"
        if self._error_message:
            base_class += " lw-error"
        
        return {
            "type": "div",
            "class": "lw-input-wrapper",
            "children": [{
                "type": "input",
                "class": base_class,
                "attrs": {
                    "type": self.input_type.value,
                    "value": self.props.value,
                    "placeholder": self.props.placeholder,
                    "disabled": self.props.disabled,
                },
                "on_focus": lambda: setattr(self, "_focused", True),
                "on_blur": lambda: setattr(self, "_focused", False),
            }]
        }


class LightweightSelect:
    """轻量级选择器组件"""
    
    def __init__(self, options: List[Dict] = None, value: Any = None,
                 mode: SelectMode = SelectMode.SINGLE, searchable: bool = False,
                 on_change: Optional[Callable] = None, placeholder: str = "请选择", **kwargs):
        self.props = ComponentProps(value=value, placeholder=placeholder, **kwargs)
        self.options = options or []
        self.mode = mode
        self.searchable = searchable
        self.on_change = on_change
        self._is_open = False
        self._search_text = ""
    
    def render(self) -> Dict[str, Any]:
        base_class = "lw-select"
        if self.props.class_name:
            base_class += f" {self.props.class_name}"
        if self._is_open:
            base_class += " lw-open"
        
        wrapper = {
            "type": "div",
            "class": base_class,
            "children": [{
                "type": "div",
                "class": "lw-select-trigger",
                "children": [self._get_display_text()],
                "on_click": self._toggle,
            }]
        }
        
        if self._is_open:
            options_list = {
                "type": "div",
                "class": "lw-select-options",
                "children": self._render_options(),
            }
            wrapper["children"].append(options_list)
        
        return wrapper
    
    def _render_options(self) -> List[Dict]:
        result = []
        for i, option in enumerate(self.options):
            is_selected = option.get("value") == self.props.value
            option_class = "lw-select-option"
            if is_selected:
                option_class += " lw-selected"
            
            result.append({
                "type": "div",
                "class": option_class,
                "children": [option.get("label", str(option.get("value")))],
                "attrs": {"data-value": option.get("value")},
                "on_click": lambda _, opt=option: self._select_option(opt),
            })
        return result
    
    def _get_display_text(self) -> str:
        if self.props.value is None:
            return self.props.placeholder
        for option in self.options:
            if option.get("value") == self.props.value:
                return option.get("label", str(self.props.value))
        return str(self.props.value)
    
    def _select_option(self, option: Dict):
        self.props.value = option.get("value")
        self._is_open = False
        if self.on_change:
            self.on_change(self.props.value)
    
    def _toggle(self):
        self._is_open = not self._is_open


class LightweightCard:
    """轻量级卡片组件"""
    
    def __init__(self, title: str = "", content: Any = None, footer: Any = None,
                 hoverable: bool = False, on_click: Optional[Callable] = None, **kwargs):
        self.props = ComponentProps(**kwargs)
        self.title = title
        self.content = content
        self.footer = footer
        self.hoverable = hoverable
        self.on_click = on_click
        self._hovered = False
    
    def render(self) -> Dict[str, Any]:
        base_class = "lw-card"
        if self.props.class_name:
            base_class += f" {self.props.class_name}"
        if self.hoverable:
            base_class += " lw-hoverable"
        
        card = {"type": "div", "class": base_class, "children": []}
        
        if self.title:
            card["children"].append({
                "type": "div",
                "class": "lw-card-header",
                "children": [{"type": "h3", "class": "lw-card-title", "children": [self.title]}]
            })
        
        if self.content:
            card["children"].append({
                "type": "div",
                "class": "lw-card-content",
                "children": [self.content] if isinstance(self.content, str) else self.content
            })
        
        if self.footer:
            card["children"].append({
                "type": "div",
                "class": "lw-card-footer",
                "children": [self.footer] if isinstance(self.footer, str) else self.footer
            })
        
        if self.on_click:
            card["on_click"] = self.on_click
        
        return card


class LightweightModal:
    """轻量级模态框组件"""
    
    def __init__(self, title: str = "", content: Any = None, footer: Any = None,
                 closable: bool = True, mask_closeable: bool = True,
                 width: str = "500px", on_close: Optional[Callable] = None, **kwargs):
        self.props = ComponentProps(**kwargs)
        self.title = title
        self.content = content
        self.footer = footer
        self.closable = closable
        self.mask_closeable = mask_closeable
        self.width = width
        self.on_close = on_close
        self._visible = False
    
    def render(self) -> Dict[str, Any]:
        if not self._visible:
            return {"type": "div", "class": "", "children": []}
        
        modal = {
            "type": "div",
            "class": "lw-modal-container",
            "children": [
                {"type": "div", "class": "lw-modal-mask"},
                {
                    "type": "div",
                    "class": "lw-modal",
                    "style": {"width": self.width},
                    "children": []
                }
            ]
        }
        
        if self.title or self.closable:
            header = {
                "type": "div",
                "class": "lw-modal-header",
                "children": [{"type": "span", "class": "lw-modal-title", "children": [self.title]}]
            }
            if self.closable:
                header["children"].append({
                    "type": "button",
                    "class": "lw-modal-close",
                    "children": ["×"],
                    "on_click": self.close,
                })
            modal["children"][1]["children"].append(header)
        
        modal["children"][1]["children"].append({
            "type": "div",
            "class": "lw-modal-content",
            "children": [self.content] if isinstance(self.content, str) else self.content
        })
        
        if self.footer:
            modal["children"][1]["children"].append({
                "type": "div",
                "class": "lw-modal-footer",
                "children": [self.footer] if isinstance(self.footer, str) else self.footer
            })
        
        return modal
    
    def open(self):
        self._visible = True
    
    def close(self):
        self._visible = False
        if self.on_close:
            self.on_close()


class LightweightToast:
    """轻量级提示组件"""
    
    def __init__(self, message: str, toast_type: str = "info", duration: int = 3000,
                 closable: bool = True, position: str = "bottom-right"):
        self.id = f"toast_{id(self)}"
        self.message = message
        self.toast_type = toast_type
        self.duration = duration
        self.closable = closable
        self.position = position
        self._visible = True
    
    def render(self) -> Dict[str, Any]:
        return {
            "type": "div",
            "class": f"lw-toast lw-toast-{self.toast_type} lw-toast-{self.position}",
            "children": [{"type": "span", "class": "lw-toast-content", "children": [self.message]}]
        }


class LightweightProgress:
    """轻量级进度条组件"""
    
    def __init__(self, value: float = 0, max: float = 100, show_text: bool = True,
                 stroke_width: int = 8, size: str = "medium", progress_type: str = "linear",
                 status: str = "normal", **kwargs):
        self.props = ComponentProps(**kwargs)
        self.value = value
        self.max = max
        self.show_text = show_text
        self.stroke_width = stroke_width
        self.size = size
        self.progress_type = progress_type
        self.status = status
    
    def render(self) -> Dict[str, Any]:
        percentage = min(100, max(0, self.value / self.max * 100))
        
        if self.progress_type == "linear":
            return {
                "type": "div",
                "class": f"lw-progress lw-progress-{self.size} lw-progress-{self.status}",
                "children": [
                    {
                        "type": "div",
                        "class": "lw-progress-track",
                        "style": {"height": f"{self.stroke_width}px"},
                        "children": [{
                            "type": "div",
                            "class": "lw-progress-bar",
                            "style": {"width": f"{percentage}%", "height": f"{self.stroke_width}px"},
                        }]
                    }
                ] + ([{
                    "type": "span",
                    "class": "lw-progress-text",
                    "children": [f"{percentage:.0f}%"]
                }] if self.show_text else [])
            }
        else:
            diameter = {"small": 40, "medium": 80, "large": 120}.get(self.size, 80)
            radius = (diameter - self.stroke_width) / 2
            circumference = 2 * 3.14159 * radius
            
            return {
                "type": "div",
                "class": "lw-progress-circular",
                "style": {"width": f"{diameter}px", "height": f"{diameter}px"},
                "children": [
                    {
                        "type": "svg",
                        "attrs": {"viewBox": f"0 0 {diameter} {diameter}"},
                        "children": [
                            {"type": "circle", "attrs": {"cx": diameter/2, "cy": diameter/2, "r": radius, "fill": "none", "stroke": "#eee", "stroke-width": self.stroke_width}},
                            {"type": "circle", "attrs": {"cx": diameter/2, "cy": diameter/2, "r": radius, "fill": "none", "stroke": "currentColor", "stroke-width": self.stroke_width, "stroke-dasharray": str(circumference), "stroke-dashoffset": str(circumference * (1 - percentage / 100)), "transform": f"rotate(-90 {diameter/2} {diameter/2})"}}
                        ]
                    }
                ] + ([{
                    "type": "span",
                    "class": "lw-progress-text",
                    "children": [f"{percentage:.0f}%"]
                }] if self.show_text else [])
            }


class LightweightList:
    """轻量级列表组件"""
    
    def __init__(self, items: List[Any] = None, render_item: Optional[Callable] = None,
                 key_field: str = "id", selectable: bool = False,
                 on_select: Optional[Callable] = None, virtual_scroll: bool = True,
                 item_height: int = 50, **kwargs):
        self.props = ComponentProps(**kwargs)
        self.items = items or []
        self.render_item = render_item
        self.key_field = key_field
        self.selectable = selectable
        self.on_select = on_select
        self.virtual_scroll = virtual_scroll
        self.item_height = item_height
        self._selected_keys: Set[str] = set()
    
    def render(self) -> Dict[str, Any]:
        base_class = "lw-list"
        if self.props.class_name:
            base_class += f" {self.props.class_name}"
        
        return {
            "type": "div",
            "class": base_class,
            "children": [
                self._render_item(item, i)
                for i, item in enumerate(self.items)
            ]
        }
    
    def _render_item(self, item: Any, index: int) -> Dict[str, Any]:
        key = str(item.get(self.key_field, index) if isinstance(item, dict) else index)
        item_class = "lw-list-item"
        if key in self._selected_keys:
            item_class += " lw-selected"
        
        return {
            "type": "div",
            "class": item_class,
            "children": self._get_item_content(item),
            "attrs": {"data-key": key},
            "on_click": lambda _: self._on_select(key),
        }
    
    def _get_item_content(self, item: Any) -> List:
        if self.render_item:
            return [self.render_item(item)]
        elif isinstance(item, str):
            return [item]
        elif isinstance(item, dict):
            return [item.get("label", str(item))]
        return [str(item)]
    
    def _on_select(self, key: str):
        if key in self._selected_keys:
            self._selected_keys.remove(key)
        else:
            self._selected_keys.add(key)
        if self.on_select:
            self.on_select(list(self._selected_keys))


class LightweightTable:
    """轻量级表格组件"""
    
    def __init__(self, columns: List[Dict] = None, data: List[Dict] = None,
                 sortable: bool = False, pagination: bool = False,
                 page_size: int = 20, **kwargs):
        self.props = ComponentProps(**kwargs)
        self.columns = columns or []
        self.data = data or []
        self.sortable = sortable
        self.pagination = pagination
        self.page_size = page_size
        self._current_page = 1
        self._sort_field = None
        self._sort_order = "asc"
    
    def render(self) -> Dict[str, Any]:
        display_data = self.data
        
        if self.pagination:
            start = (self._current_page - 1) * self.page_size
            display_data = self.data[start:start + self.page_size]
        
        total_pages = max(1, (len(self.data) + self.page_size - 1) // self.page_size)
        
        return {
            "type": "div",
            "class": "lw-table-wrapper",
            "children": [
                {
                    "type": "table",
                    "class": "lw-table",
                    "children": [
                        self._render_header(),
                        {"type": "tbody", "children": [self._render_row(row, i) for i, row in enumerate(display_data)]}
                    ]
                }
            ] + ([self._render_pagination(total_pages)] if self.pagination else [])
        }
    
    def _render_header(self) -> Dict[str, Any]:
        return {
            "type": "thead",
            "children": [{
                "type": "tr",
                "children": [
                    {
                        "type": "th",
                        "class": f"lw-th {'lw-sortable' if self.sortable else ''}",
                        "children": [col.get("title", col.get("field", ""))],
                    }
                    for col in self.columns
                ]
            }]
        }
    
    def _render_row(self, row: Dict, index: int) -> Dict[str, Any]:
        return {
            "type": "tr",
            "class": "lw-tr",
            "children": [
                {"type": "td", "class": "lw-td", "children": [str(row.get(col.get("field", ""), ""))]}
                for col in self.columns
            ]
        }
    
    def _render_pagination(self, total_pages: int) -> Dict[str, Any]:
        return {
            "type": "div",
            "class": "lw-pagination",
            "children": [
                {"type": "button", "class": "lw-page-btn", "children": ["上一页"], "on_click": lambda: setattr(self, "_current_page", max(1, self._current_page - 1))},
                {"type": "span", "class": "lw-page-info", "children": [f"{self._current_page} / {total_pages}"]},
                {"type": "button", "class": "lw-page-btn", "children": ["下一页"], "on_click": lambda: setattr(self, "_current_page", min(total_pages, self._current_page + 1))}
            ]
        }


__all__ = [
    "ComponentProps",
    "ButtonVariant",
    "InputType",
    "SelectMode",
    "LightweightButton",
    "LightweightInput",
    "LightweightSelect",
    "LightweightCard",
    "LightweightModal",
    "LightweightToast",
    "LightweightProgress",
    "LightweightList",
    "LightweightTable",
]
