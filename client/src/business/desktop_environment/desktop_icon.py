# desktop_icon.py — 桌面图标组件
# ============================================================================
#
# 负责桌面图标的显示和交互
# 支持拖拽、编辑模式抖动、双击打开等功能
#
# ============================================================================

import json
import time
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum

# ============================================================================
# 配置与枚举
# ============================================================================

class IconSize(Enum):
    """图标尺寸"""
    SMALL = 48
    MEDIUM = 64
    LARGE = 84
    XLARGE = 128

class IconState(Enum):
    """图标状态"""
    NORMAL = "normal"
    SELECTED = "selected"
    DRAGGING = "dragging"
    WOBBLING = "wobbling"
    DISABLED = "disabled"

@dataclass
class IconAppearance:
    """图标外观配置"""
    size: int = 64
    border_radius: int = 12
    background_color: str = "transparent"
    selected_color: str = "#4A90D9"
    shadow: bool = True
    show_label: bool = True
    label_color: str = "#FFFFFF"
    label_shadow: bool = True

# ============================================================================
# 桌面图标
# ============================================================================

class DesktopIcon:
    """
    桌面应用图标

    功能:
    1. 显示应用图标和名称
    2. 处理单击、双击、长按事件
    3. 支持拖拽排序
    4. 编辑模式下抖动动画
    5. 选中状态高亮
    """

    def __init__(
        self,
        icon_id: str,
        name: str,
        icon_path: str = "",
        module: str = "",
        desktop_index: int = 0,
        appearance: IconAppearance = None
    ):
        # 基础信息
        self.icon_id = icon_id
        self.name = name
        self.icon_path = icon_path
        self.module = module
        self.desktop_index = desktop_index

        # 外观
        self.appearance = appearance or IconAppearance()

        # 状态
        self.state = IconState.NORMAL

        # 位置 (网格位置)
        self.row: int = 0
        self.col: int = 0

        # 像素位置 (用于拖拽)
        self.x: float = 0
        self.y: float = 0

        # 拖拽状态
        self._is_dragging: bool = False
        self._drag_offset_x: float = 0
        self._drag_offset_y: float = 0

        # 抖动动画
        self._wobble_angle: float = 0
        self._wobble_speed: float = 2.0

        # 事件回调
        self._on_click: Optional[Callable] = None
        self._on_double_click: Optional[Callable] = None
        self._on_long_press: Optional[Callable] = None
        self._on_drag_start: Optional[Callable] = None
        self._on_drag: Optional[Callable] = None
        self._on_drag_end: Optional[Callable] = None

    # --------------------------------------------------------------------------
    # 位置管理
    # --------------------------------------------------------------------------

    def set_position(self, row: int, col: int):
        """设置网格位置"""
        self.row = row
        self.col = col

    def set_pixel_position(self, x: float, y: float):
        """设置像素位置"""
        self.x = x
        self.y = y

    def get_pixel_position(self) -> tuple:
        """获取像素位置"""
        return (self.x, self.y)

    def get_grid_position(self) -> tuple:
        """获取网格位置"""
        return (self.row, self.col)

    # --------------------------------------------------------------------------
    # 拖拽操作
    # --------------------------------------------------------------------------

    def start_drag(self):
        """开始拖拽"""
        self._is_dragging = True
        self.state = IconState.DRAGGING
        if self._on_drag_start:
            self._on_drag_start(self)

    def drag_to(self, x: float, y: float):
        """拖拽到指定位置"""
        if self._is_dragging:
            self.x = x - self._drag_offset_x
            self.y = y - self._drag_offset_y
            if self._on_drag:
                self._on_drag(self, x, y)

    def end_drag(self):
        """结束拖拽"""
        self._is_dragging = False
        self.state = IconState.NORMAL
        if self._on_drag_end:
            self._on_drag_end(self)

    def set_drag_offset(self, offset_x: float, offset_y: float):
        """设置拖拽偏移量"""
        self._drag_offset_x = offset_x
        self._drag_offset_y = offset_y

    # --------------------------------------------------------------------------
    # 抖动动画 (编辑模式)
    # --------------------------------------------------------------------------

    def start_wobble(self):
        """开始抖动动画"""
        if self.state != IconState.WOBBLING:
            self.state = IconState.WOBBLING

    def stop_wobble(self):
        """停止抖动动画"""
        if self.state == IconState.WOBBLING:
            self.state = IconState.NORMAL
            self._wobble_angle = 0

    def update_wobble(self, delta_time: float):
        """更新抖动动画"""
        if self.state == IconState.WOBBLING:
            self._wobble_angle += self._wobble_speed * delta_time * 60
            if self._wobble_angle > 360:
                self._wobble_angle -= 360

    def get_wobble_rotation(self) -> float:
        """获取当前抖动旋转角度"""
        if self.state == IconState.WOBBLING:
            # 左右摇摆 5 度
            import math
            return math.sin(math.radians(self._wobble_angle * 10)) * 5
        return 0

    # --------------------------------------------------------------------------
    # 状态管理
    # --------------------------------------------------------------------------

    def select(self):
        """选中图标"""
        self.state = IconState.SELECTED

    def deselect(self):
        """取消选中"""
        if self.state == IconState.SELECTED:
            self.state = IconState.NORMAL

    def enable(self):
        """启用图标"""
        if self.state == IconState.DISABLED:
            self.state = IconState.NORMAL

    def disable(self):
        """禁用图标"""
        self.state = IconState.DISABLED

    def is_enabled(self) -> bool:
        """是否启用"""
        return self.state != IconState.DISABLED

    # --------------------------------------------------------------------------
    # 事件处理
    # --------------------------------------------------------------------------

    def handle_click(self) -> bool:
        """处理单击事件"""
        if self.state == IconState.DISABLED:
            return False
        if self._on_click:
            return self._on_click(self)
        return False

    def handle_double_click(self) -> bool:
        """处理双击事件"""
        if self.state == IconState.DISABLED:
            return False
        if self._on_double_click:
            return self._on_double_click(self)
        return False

    def handle_long_press(self, duration: float = 0.5) -> bool:
        """处理长按事件"""
        if self.state == IconState.DISABLED:
            return False
        if self._on_long_press:
            return self._on_long_press(self)
        return False

    def contains_point(self, x: float, y: float) -> bool:
        """检查点是否在图标范围内"""
        icon_x = self.x
        icon_y = self.y
        size = self.appearance.size

        return (
            icon_x <= x <= icon_x + size and
            icon_y <= y <= icon_y + size
        )

    # --------------------------------------------------------------------------
    # 事件绑定
    # --------------------------------------------------------------------------

    def set_on_click(self, callback: Callable[["DesktopIcon"], bool]):
        """设置单击回调"""
        self._on_click = callback

    def set_on_double_click(self, callback: Callable[["DesktopIcon"], bool]):
        """设置双击回调"""
        self._on_double_click = callback

    def set_on_long_press(self, callback: Callable[["DesktopIcon"], bool]):
        """设置长按回调"""
        self._on_long_press = callback

    def set_on_drag_start(self, callback: Callable[["DesktopIcon"], None]):
        """设置拖拽开始回调"""
        self._on_drag_start = callback

    def set_on_drag(self, callback: Callable[["DesktopIcon", float, float], None]):
        """设置拖拽回调"""
        self._on_drag = callback

    def set_on_drag_end(self, callback: Callable[["DesktopIcon"], None]):
        """设置拖拽结束回调"""
        self._on_drag_end = callback

    # --------------------------------------------------------------------------
    # 序列化
    # --------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "icon_id": self.icon_id,
            "name": self.name,
            "icon_path": self.icon_path,
            "module": self.module,
            "desktop_index": self.desktop_index,
            "row": self.row,
            "col": self.col,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DesktopIcon":
        """从字典创建"""
        return cls(
            icon_id=data["icon_id"],
            name=data["name"],
            icon_path=data.get("icon_path", ""),
            module=data.get("module", ""),
            desktop_index=data.get("desktop_index", 0),
        )

# ============================================================================
# 桌面图标网格容器
# ============================================================================

class DesktopIconGrid:
    """
    桌面图标网格布局容器

    负责:
    1. 计算图标在网格中的位置
    2. 管理图标的增删改查
    3. 处理图标布局的重新计算
    """

    def __init__(
        self,
        columns: int = 6,
        rows: int = 4,
        icon_size: int = 64,
        spacing: int = 16,
        padding: int = 16
    ):
        self.columns = columns
        self.rows = rows
        self.icon_size = icon_size
        self.spacing = spacing
        self.padding = padding

        self._icons: dict[str, DesktopIcon] = {}

    def add_icon(self, icon: DesktopIcon) -> bool:
        """添加图标到网格"""
        if icon.icon_id in self._icons:
            return False

        # 分配位置
        position = self._allocate_position()
        if position is None:
            return False

        row, col = position
        icon.row = row
        icon.col = col
        icon.x = self._get_x_for_col(col)
        icon.y = self._get_y_for_row(row)

        self._icons[icon.icon_id] = icon
        return True

    def remove_icon(self, icon_id: str) -> bool:
        """从网格移除图标"""
        if icon_id not in self._icons:
            return False

        icon = self._icons.pop(icon_id)
        self._free_position(icon.row, icon.col)
        return True

    def get_icon(self, icon_id: str) -> Optional[DesktopIcon]:
        """获取图标"""
        return self._icons.get(icon_id)

    def get_all_icons(self) -> list[DesktopIcon]:
        """获取所有图标"""
        return list(self._icons.values())

    def get_icon_at(self, row: int, col: int) -> Optional[DesktopIcon]:
        """获取指定位置的图标"""
        for icon in self._icons.values():
            if icon.row == row and icon.col == col:
                return icon
        return None

    def move_icon(self, icon_id: str, new_row: int, new_col: int) -> bool:
        """移动图标到新位置"""
        if icon_id not in self._icons:
            return False

        icon = self._icons[icon_id]

        # 交换位置
        existing = self.get_icon_at(new_row, new_col)
        if existing and existing.icon_id != icon_id:
            # 交换位置
            existing.row, icon.row = icon.row, existing.row
            existing.col, icon.col = icon.col, existing.col
            existing.x = self._get_x_for_col(existing.col)
            existing.y = self._get_y_for_row(existing.row)

        icon.row = new_row
        icon.col = new_col
        icon.x = self._get_x_for_col(new_col)
        icon.y = self._get_y_for_row(new_row)

        return True

    def rearrange(self):
        """重新排列所有图标"""
        # 收集所有位置
        positions = []
        for icon in self._icons.values():
            positions.append((icon.row, icon.col, icon))

        # 按行列排序
        positions.sort(key=lambda p: (p[0], p[1]))

        # 重新分配位置
        for row in range(self.rows):
            for col in range(self.columns):
                idx = row * self.columns + col
                if idx < len(positions):
                    _, _, icon = positions[idx]
                    icon.row = row
                    icon.col = col
                    icon.x = self._get_x_for_col(col)
                    icon.y = self._get_y_for_row(row)

    def _allocate_position(self) -> Optional[tuple]:
        """分配一个空闲位置"""
        for row in range(self.rows):
            for col in range(self.columns):
                if self.get_icon_at(row, col) is None:
                    return (row, col)
        return None

    def _free_position(self, row: int, col: int):
        """释放一个位置"""
        # 位置总是空闲的，由 _allocate_position 管理
        pass

    def _get_x_for_col(self, col: int) -> float:
        """计算列的 X 坐标"""
        return self.padding + col * (self.icon_size + self.spacing)

    def _get_y_for_row(self, row: int) -> float:
        """计算行的 Y 坐标"""
        return self.padding + row * (self.icon_size + self.spacing)

    def get_grid_size(self) -> tuple:
        """获取网格总尺寸"""
        width = self.padding * 2 + self.columns * (self.icon_size + self.spacing) - self.spacing
        height = self.padding * 2 + self.rows * (self.icon_size + self.spacing) - self.spacing
        return (width, height)

    def rowcol_to_pixel(self, row: int, col: int) -> tuple:
        """网格坐标转像素坐标"""
        return (self._get_x_for_col(col), self._get_y_for_row(row))

    def pixel_to_rowcol(self, x: float, y: float) -> tuple:
        """像素坐标转网格坐标"""
        col = int((x - self.padding) / (self.icon_size + self.spacing))
        row = int((y - self.padding) / (self.icon_size + self.spacing))
        col = max(0, min(col, self.columns - 1))
        row = max(0, min(row, self.rows - 1))
        return (row, col)