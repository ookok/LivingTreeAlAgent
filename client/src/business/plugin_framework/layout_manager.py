"""
布局管理器 - Layout Manager

功能：
1. 管理插件视图的布局
2. 保存/加载布局模板
3. 支持布局场景切换（如编码模式、设计模式、聊天模式）
4. 记忆用户自定义布局

设计理念：
- 布局即代码
- 用户可以保存自己的布局配置
- 支持多场景预设
"""

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMainWindow, QDockWidget


class LayoutTemplate(Enum):
    """预置布局模板"""
    DEFAULT = "default"           # 默认布局
    CODING = "coding"            # 编码模式
    DESIGN = "design"            # 设计模式
    CHAT = "chat"                # 聊天模式
    MINIMAL = "minimal"          # 极简模式
    CUSTOM = "custom"            # 自定义


@dataclass
class DockState:
    """停靠区域状态"""
    area: str  # left, right, top, bottom
    visible: bool = True
    width: int = 0
    height: int = 0
    floating: bool = False
    pos_x: int = 0
    pos_y: int = 0


@dataclass
class ViewState:
    """视图状态"""
    view_id: str
    plugin_id: str
    visible: bool = True
    dock_state: Optional[DockState] = None
    tab_index: int = -1  # -1 表示不在标签页中


@dataclass
class LayoutConfig:
    """布局配置"""
    id: str
    name: str
    template: LayoutTemplate = LayoutTemplate.CUSTOM
    views: List[ViewState] = field(default_factory=list)
    splitter_sizes: Dict[str, List[int]] = field(default_factory=dict)  # splitter_id -> sizes
    window_state: Dict[str, Any] = field(default_factory=dict)  # 主窗口状态

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "template": self.template.value,
            "views": [
                {
                    "view_id": v.view_id,
                    "plugin_id": v.plugin_id,
                    "visible": v.visible,
                    "tab_index": v.tab_index,
                    "dock_state": {
                        "area": v.dock_state.area,
                        "visible": v.dock_state.visible,
                        "width": v.dock_state.width,
                        "height": v.dock_state.height,
                        "floating": v.dock_state.floating,
                        "pos_x": v.dock_state.pos_x,
                        "pos_y": v.dock_state.pos_y,
                    } if v.dock_state else None,
                }
                for v in self.views
            ],
            "splitter_sizes": self.splitter_sizes,
            "window_state": self.window_state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayoutConfig':
        views = []
        for v_data in data.get("views", []):
            dock_state = None
            if v_data.get("dock_state"):
                ds = v_data["dock_state"]
                dock_state = DockState(
                    area=ds["area"],
                    visible=ds.get("visible", True),
                    width=ds.get("width", 0),
                    height=ds.get("height", 0),
                    floating=ds.get("floating", False),
                    pos_x=ds.get("pos_x", 0),
                    pos_y=ds.get("pos_y", 0),
                )
            views.append(ViewState(
                view_id=v_data["view_id"],
                plugin_id=v_data["plugin_id"],
                visible=v_data.get("visible", True),
                tab_index=v_data.get("tab_index", -1),
                dock_state=dock_state,
            ))

        return cls(
            id=data["id"],
            name=data["name"],
            template=LayoutTemplate(data.get("template", "custom")),
            views=views,
            splitter_sizes=data.get("splitter_sizes", {}),
            window_state=data.get("window_state", {}),
        )


class LayoutManager(QObject):
    """
    布局管理器

    管理主窗口布局、视图位置、模板切换

    使用示例：
        layout_manager = LayoutManager(main_window)

        # 保存当前布局
        layout_manager.save_layout("my_layout", "我的布局")

        # 切换布局
        layout_manager.apply_layout("coding_mode")

        # 获取当前布局
        current = layout_manager.get_current_layout()
    """

    # 信号定义
    layout_changed = pyqtSignal(str)  # layout_id
    view_visibility_changed = pyqtSignal(str, bool)  # view_id, visible

    def __init__(self, main_window: QMainWindow):
        super().__init__()
        self._main_window = main_window
        self._layouts: Dict[str, LayoutConfig] = {}
        self._current_layout_id: Optional[str] = None
        self._view_factory = None  # 视图工厂引用

        # 注册默认布局
        self._register_default_layouts()

    def set_view_factory(self, view_factory) -> None:
        """设置视图工厂"""
        self._view_factory = view_factory

    def _register_default_layouts(self) -> None:
        """注册默认布局模板"""

        # 默认布局
        default_layout = LayoutConfig(
            id="default",
            name="默认布局",
            template=LayoutTemplate.DEFAULT,
        )
        self._layouts["default"] = default_layout

        # 编码模式
        coding_layout = LayoutConfig(
            id="coding",
            name="编码模式",
            template=LayoutTemplate.CODING,
        )
        self._layouts["coding"] = coding_layout

        # 聊天模式
        chat_layout = LayoutConfig(
            id="chat",
            name="聊天模式",
            template=LayoutTemplate.CHAT,
        )
        self._layouts["chat"] = chat_layout

        self._current_layout_id = "default"

    def save_layout(self, layout_id: str, name: str, template: LayoutTemplate = LayoutTemplate.CUSTOM) -> LayoutConfig:
        """
        保存当前布局

        Args:
            layout_id: 布局ID
            name: 布局名称
            template: 布局模板类型

        Returns:
            保存的布局配置
        """
        config = self._capture_current_layout(layout_id, name, template)
        self._layouts[layout_id] = config
        return config

    def _capture_current_layout(self, layout_id: str, name: str, template: LayoutTemplate) -> LayoutConfig:
        """捕获当前布局状态"""
        views = []

        # 捕获所有dock widgets
        if self._main_window:
            for dock in self._main_window.findChildren(QDockWidget):
                dock_state = DockState(
                    area=self._get_dock_area_string(dock),
                    visible=dock.isVisible(),
                    width=dock.width(),
                    height=dock.height(),
                    floating=dock.isFloating(),
                )
                views.append(ViewState(
                    view_id=dock.objectName(),
                    plugin_id=dock.property("plugin_id") or "",
                    visible=dock.isVisible(),
                    dock_state=dock_state,
                ))

        # 捕获窗口状态
        window_state = {}
        if self._main_window:
            window_state = {
                "geometry": bytes(self._main_window.saveGeometry()).hex(),
                "state": bytes(self._main_window.saveState()).hex(),
            }

        return LayoutConfig(
            id=layout_id,
            name=name,
            template=template,
            views=views,
            window_state=window_state,
        )

    def _get_dock_area_string(self, dock: QDockWidget) -> str:
        """获取dock区域字符串"""
        area = self._main_window.dockWidgetArea(dock)
        area_map = {
            1: "left",   # LeftDockWidgetArea
            2: "right",  # RightDockWidgetArea
            4: "top",    # TopDockWidgetArea
            8: "bottom", # BottomDockWidgetArea
        }
        return area_map.get(int(area), "left")

    def apply_layout(self, layout_id: str) -> bool:
        """
        应用布局

        Args:
            layout_id: 布局ID

        Returns:
            是否成功
        """
        if layout_id not in self._layouts:
            return False

        config = self._layouts[layout_id]
        self._current_layout_id = layout_id

        # 应用窗口状态
        if config.window_state and self._main_window:
            if "geometry" in config.window_state:
                geometry_bytes = bytes.fromhex(config.window_state["geometry"])
                self._main_window.restoreGeometry(geometry_bytes)
            if "state" in config.window_state:
                state_bytes = bytes.fromhex(config.window_state["state"])
                self._main_window.restoreState(state_bytes)

        # 应用视图状态
        for view_state in config.views:
            self._apply_view_state(view_state)

        self.layout_changed.emit(layout_id)
        return True

    def _apply_view_state(self, view_state: ViewState) -> None:
        """应用单个视图状态"""
        # 查找对应的dock widget
        if not self._main_window:
            return

        dock = self._main_window.findChild(QDockWidget, view_state.view_id)
        if dock and view_state.dock_state:
            dock.setVisible(view_state.dock_state.visible)
            if view_state.dock_state.floating:
                dock.setFloating(True)

    def delete_layout(self, layout_id: str) -> bool:
        """
        删除布局

        Args:
            layout_id: 布局ID

        Returns:
            是否成功（默认布局不能删除）
        """
        if layout_id in ["default", "coding", "chat"]:
            return False
        if layout_id in self._layouts:
            del self._layouts[layout_id]
            return True
        return False

    def get_layout(self, layout_id: str) -> Optional[LayoutConfig]:
        """获取布局"""
        return self._layouts.get(layout_id)

    def get_current_layout(self) -> Optional[LayoutConfig]:
        """获取当前布局"""
        if self._current_layout_id:
            return self._layouts.get(self._current_layout_id)
        return None

    def get_all_layouts(self) -> Dict[str, LayoutConfig]:
        """获取所有布局"""
        return self._layouts.copy()

    def rename_layout(self, layout_id: str, new_name: str) -> bool:
        """
        重命名布局

        Args:
            layout_id: 布局ID
            new_name: 新名称

        Returns:
            是否成功
        """
        if layout_id in self._layouts:
            self._layouts[layout_id].name = new_name
            return True
        return False

    def duplicate_layout(self, source_id: str, target_id: str, new_name: str) -> Optional[LayoutConfig]:
        """
        复制布局

        Args:
            source_id: 源布局ID
            target_id: 目标布局ID
            new_name: 新名称

        Returns:
            新的布局配置
        """
        source = self._layouts.get(source_id)
        if not source:
            return None

        new_config = LayoutConfig(
            id=target_id,
            name=new_name,
            template=LayoutTemplate.CUSTOM,
            views=source.views.copy(),
            splitter_sizes=source.splitter_sizes.copy(),
            window_state=source.window_state.copy(),
        )
        self._layouts[target_id] = new_config
        return new_config

    def export_layout(self, layout_id: str) -> Optional[str]:
        """
        导出布局为JSON

        Args:
            layout_id: 布局ID

        Returns:
            JSON字符串
        """
        config = self._layouts.get(layout_id)
        if config:
            return json.dumps(config.to_dict(), ensure_ascii=False, indent=2)
        return None

    def import_layout(self, json_str: str) -> Optional[LayoutConfig]:
        """
        从JSON导入布局

        Args:
            json_str: JSON字符串

        Returns:
            布局配置
        """
        try:
            data = json.loads(json_str)
            config = LayoutConfig.from_dict(data)
            self._layouts[config.id] = config
            return config
        except Exception:
            return None

    def save_all_layouts(self) -> str:
        """
        保存所有布局到JSON

        Returns:
            JSON字符串
        """
        data = {
            "layouts": {k: v.to_dict() for k, v in self._layouts.items()},
            "current": self._current_layout_id,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def load_all_layouts(self, json_str: str) -> bool:
        """
        从JSON加载所有布局

        Args:
            json_str: JSON字符串

        Returns:
            是否成功
        """
        try:
            data = json.loads(json_str)
            self._layouts = {}
            for k, v in data.get("layouts", {}).items():
                self._layouts[k] = LayoutConfig.from_dict(v)
            self._current_layout_id = data.get("current", "default")
            return True
        except Exception:
            return False


# 全局单例
_layout_manager_instance: Optional[LayoutManager] = None


def get_layout_manager(main_window: Optional[QMainWindow] = None) -> LayoutManager:
    """获取布局管理器单例"""
    global _layout_manager_instance
    if _layout_manager_instance is None and main_window:
        _layout_manager_instance = LayoutManager(main_window)
    return _layout_manager_instance
