"""
响应式布局系统

Flex布局、Grid布局、响应式断点
from __future__ import annotations
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

from .models import LayoutType, ResponsiveBreakpoint


@dataclass
class ResponsiveRule:
    """响应式规则"""
    breakpoint: ResponsiveBreakpoint
    min_width: int
    max_width: Optional[int] = None
    
    def matches(self, width: int) -> bool:
        if width < self.min_width:
            return False
        if self.max_width is not None and width > self.max_width:
            return False
        return True


class Layout:
    """基础布局类"""
    
    def __init__(self, direction: str = "row", gap: str = "0", **kwargs):
        self.direction = direction
        self.gap = gap
        self.children: List[Any] = []
    
    def add_child(self, child: Any):
        self.children.append(child)
    
    def remove_child(self, child: Any):
        if child in self.children:
            self.children.remove(child)
    
    def to_style(self) -> Dict[str, str]:
        return {
            "display": "flex",
            "flex-direction": self.direction,
            "gap": self.gap,
        }


class FlexLayout(Layout):
    """Flex布局"""
    
    def __init__(self, direction: str = "row", justify: str = "flex-start",
                 align: str = "stretch", wrap: bool = False, gap: str = "0", **kwargs):
        super().__init__(direction=direction, gap=gap, **kwargs)
        self.justify = justify
        self.align = align
        self.wrap = wrap
    
    def to_style(self) -> Dict[str, str]:
        style = super().to_style()
        style.update({"justify-content": self.justify, "align-items": self.align})
        if self.wrap:
            style["flex-wrap"] = "wrap"
        return style
    
    @classmethod
    def row(cls, justify: str = "flex-start", align: str = "center", gap: str = "8px"):
        return cls(direction="row", justify=justify, align=align, gap=gap)
    
    @classmethod
    def column(cls, justify: str = "flex-start", align: str = "stretch", gap: str = "8px"):
        return cls(direction="column", justify=justify, align=align, gap=gap)
    
    @classmethod
    def center(cls, gap: str = "0"):
        return cls(direction="row", justify="center", align="center", gap=gap)


class GridLayout(Layout):
    """Grid布局"""
    
    def __init__(self, columns: int = 12, rows: int = 0, column_gap: str = "0",
                 row_gap: str = "0", template: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.columns = columns
        self.rows = rows
        self.column_gap = column_gap
        self.row_gap = row_gap
        self.template = template
    
    def to_style(self) -> Dict[str, str]:
        style = {"display": "grid"}
        if self.template:
            style["grid-template"] = self.template
        else:
            style["grid-template-columns"] = f"repeat({self.columns}, 1fr)"
            if self.rows > 0:
                style["grid-template-rows"] = f"repeat({self.rows}, 1fr)"
        style["gap"] = self.column_gap
        return style
    
    @classmethod
    def auto_fit(cls, min_size: str = "200px", gap: str = "16px"):
        layout = cls()
        layout.template = f"repeat(auto-fit, minmax({min_size}, 1fr))"
        layout.column_gap = gap
        return layout


class ResponsiveLayout:
    """响应式布局"""
    
    def __init__(self):
        self.breakpoints: Dict[ResponsiveBreakpoint, Dict[str, Any]] = {
            ResponsiveBreakpoint.MOBILE: {},
            ResponsiveBreakpoint.TABLET: {},
            ResponsiveBreakpoint.DESKTOP: {},
            ResponsiveBreakpoint.LARGE: {},
            ResponsiveBreakpoint.EXTRA_LARGE: {},
        }
        self.current_breakpoint: ResponsiveBreakpoint = ResponsiveBreakpoint.DESKTOP
        self._listeners: List[Callable] = []
    
    def set_breakpoint_config(self, breakpoint: ResponsiveBreakpoint, config: Dict[str, Any]):
        self.breakpoints[breakpoint] = config
    
    def update_width(self, width: int):
        old = self.current_breakpoint
        if width < 576:
            self.current_breakpoint = ResponsiveBreakpoint.MOBILE
        elif width < 768:
            self.current_breakpoint = ResponsiveBreakpoint.TABLET
        elif width < 992:
            self.current_breakpoint = ResponsiveBreakpoint.DESKTOP
        elif width < 1200:
            self.current_breakpoint = ResponsiveBreakpoint.LARGE
        else:
            self.current_breakpoint = ResponsiveBreakpoint.EXTRA_LARGE
        
        if old != self.current_breakpoint:
            for listener in self._listeners:
                try:
                    listener(self.current_breakpoint, self.get_config())
                except Exception:
                    pass
    
    def get_config(self) -> Dict[str, Any]:
        return self.breakpoints.get(self.current_breakpoint, {})


__all__ = [
    "ResponsiveRule",
    "Layout",
    "FlexLayout",
    "GridLayout",
    "ResponsiveLayout",
]
